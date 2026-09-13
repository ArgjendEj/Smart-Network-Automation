"""One-click Smart Auto Configuration driven purely by the topology.

The admin only places devices and connects them with cables. This then:
  * picks a LAN subnet for every router-to-LAN link (gateway = .1)
  * picks a /30 for every router-to-router link (.1 / .2) - reusing an address
    already set on one end if there is one
  * builds a DHCP pool per LAN and hands every connected PC an address (.2, .3, .4 ...)
  * enables OSPF so the whole topology is reachable
  * generates + stores the Cisco config for every device
"""
from __future__ import annotations

import ipaddress
import json

from sqlalchemy.orm import Session

from models import ENDPOINT_TYPES, Connection, Device, Interface, Routing, Vlan
from services.config_generator import generate_auto_router_config, generate_auto_switch_config
from services.logging_service import write_log
from services.smart_config_service import ROUTER_IFACE_POOL, _IfaceAllocator, _sync_connection


# local networks come out of 192.168.0.0/16 ; router-to-router links out of 10.0.0.0/8
def _lan_pools():
    base = int(ipaddress.ip_address("192.168.0.0"))
    for i in range(1, 256):
        yield ipaddress.ip_network((base + i * 256, 24))


def _wan_pools():
    for net in ipaddress.ip_network("10.0.0.0/8").subnets(new_prefix=30):
        yield net


def _sanitize(iface: str) -> str:
    return iface.replace("/", "_").replace(".", "_").replace(" ", "")


def _iface_for(conn: Connection, device_id: int) -> str | None:
    if conn.a_device_id == device_id:
        return conn.a_interface
    if conn.b_device_id == device_id:
        return conn.b_interface
    return None


def _set_conn_iface(conn: Connection, device_id: int, name: str) -> None:
    if conn.a_device_id == device_id:
        conn.a_interface = name
    else:
        conn.b_interface = name


def _lan_from_iface(i: Interface) -> dict:
    net = ipaddress.ip_network(f"{i.ip_address}/{i.subnet_mask}", strict=False)
    return {
        "iface": i.name, "network": str(net.network_address), "netmask": str(net.netmask),
        "prefix": net.prefixlen, "wildcard": str(net.hostmask), "gateway": i.ip_address,
        "pool_name": f"LAN_{_sanitize(i.name)}",
        "exclude_from": str(net.network_address + 1), "exclude_to": i.ip_address,
        "_net": net,
    }


def _wan_from_iface(db: Session, i: Interface) -> dict:
    net = ipaddress.ip_network(f"{i.ip_address}/{i.subnet_mask}", strict=False)
    peer = (i.description or "").replace("link to ", "").strip() or "peer"
    # find the peer router's address in this subnet (for BGP neighbor / info)
    peer_ip, peer_asn = None, 65000
    for pi in db.query(Interface).filter(
        Interface.device_id != i.device_id, Interface.ip_address.isnot(None)
    ).all():
        try:
            if ipaddress.ip_address(pi.ip_address) in net and pi.ip_address != i.ip_address:
                peer_ip, peer_asn = pi.ip_address, 65000 + min(pi.device_id, 500)
                break
        except ValueError:
            continue
    if peer_ip is None:
        for h in net.hosts():
            if str(h) != i.ip_address:
                peer_ip = str(h)
                break
    return {
        "iface": i.name, "ip": i.ip_address, "netmask": str(net.netmask),
        "network": str(net.network_address), "wildcard": str(net.hostmask),
        "peer_hostname": peer, "peer_ip": peer_ip or i.ip_address, "peer_asn": peer_asn,
    }


def _db_lans(db: Session, rid: int) -> list[dict]:
    out = []
    for i in db.query(Interface).filter(Interface.device_id == rid).all():
        if not (i.ip_address and i.subnet_mask):
            continue
        desc = (i.description or "")
        if desc.startswith("LAN ") or (
            desc.lower() == "manual" and not str(i.ip_address).startswith("10.")
        ):
            out.append(_lan_from_iface(i))
    return out


def _db_wans(db: Session, rid: int) -> list[dict]:
    out = []
    for i in db.query(Interface).filter(Interface.device_id == rid).all():
        if not (i.ip_address and i.subnet_mask):
            continue
        desc = (i.description or "")
        if desc.startswith("link to ") or (
            desc.lower() == "manual" and str(i.ip_address).startswith("10.")
        ):
            out.append(_wan_from_iface(db, i))
    return out


def _asn(device_id: int) -> int:
    return 65000 + min(device_id, 500)     # private ASN range 64512-65534


def run(db: Session, scope: str = "all", routing: str = "ospf", nat: bool = False) -> dict:
    if scope not in ("all", "lan", "wan"):
        raise ValueError("scope must be 'all', 'lan' or 'wan'.")
    if routing not in ("ospf", "bgp", "both"):
        raise ValueError("routing must be 'ospf', 'bgp' or 'both'.")
    do_lan = scope in ("all", "lan")
    do_wan = scope in ("all", "wan")

    devices = {d.id: d for d in db.query(Device).all()}
    conns = db.query(Connection).all()
    routers = [d for d in devices.values() if d.device_type == "router"]
    if not routers:
        raise ValueError("Add at least one router and connect it in the topology.")
    if not conns:
        raise ValueError("Connect the devices with cables in the Topology view first.")

    # collapse duplicate cables between the same two devices (they pile up from
    # re-cabling / re-runs). Keep the row that points at a hand-typed interface,
    # else the most recently drawn one. Two routers may legitimately have
    # SEVERAL links between them (redundant / load-sharing) - those are left
    # alone, except for an exact duplicate (both ends on the very same
    # interfaces already), which is always a stray leftover row.
    _hand_typed = {
        (i.device_id, i.name)
        for i in db.query(Interface).all()
        if (i.description or "").lower() == "manual"
    }

    def _conn_rank(c: Connection) -> tuple:
        typed = ((c.a_device_id, c.a_interface) in _hand_typed
                 or (c.b_device_id, c.b_interface) in _hand_typed)
        return (1 if typed else 0, c.id)

    def _is_router(dev_id: int) -> bool:
        d = devices.get(dev_id)
        return d is not None and d.device_type == "router"

    router_pair_conns = [c for c in conns if _is_router(c.a_device_id) and _is_router(c.b_device_id)]
    other_conns = [c for c in conns if c not in router_pair_conns]

    _exact_seen: set[frozenset] = set()
    kept_router_conns = []
    for c in router_pair_conns:
        if c.a_interface and c.b_interface:
            key = frozenset({(c.a_device_id, c.a_interface), (c.b_device_id, c.b_interface)})
            if key in _exact_seen:
                continue    # a stray exact copy of an existing link - drop it
            _exact_seen.add(key)
        kept_router_conns.append(c)

    _by_pair: dict[frozenset, Connection] = {}
    for c in other_conns:
        key = frozenset({c.a_device_id, c.b_device_id})
        best = _by_pair.get(key)
        if best is None or _conn_rank(c) > _conn_rank(best):
            _by_pair[key] = c

    keep_ids = {c.id for c in _by_pair.values()} | {c.id for c in kept_router_conns}
    if len(keep_ids) < len(conns):
        for c in conns:
            if c.id not in keep_ids:
                db.delete(c)
        db.flush()
    conns = list(_by_pair.values()) + kept_router_conns

    adj: dict[int, list[tuple[Connection, int]]] = {}
    for c in conns:
        adj.setdefault(c.a_device_id, []).append((c, c.b_device_id))
        adj.setdefault(c.b_device_id, []).append((c, c.a_device_id))
    # handle LAN links (to a switch/PC) before router-to-router links, so a
    # router's typed IP is claimed for its LAN first
    for lst in adj.values():
        lst.sort(key=lambda t: devices.get(t[1]) is not None
                 and devices[t[1]].device_type == "router")

    def l2_pcs(start: int) -> list[int]:
        seen, stack, found = {start}, [start], []
        while stack:
            x = stack.pop()
            d = devices.get(x)
            if d is None:
                continue
            if d.device_type in ENDPOINT_TYPES:
                found.append(x)
                if d.device_type != "ip_phone":
                    continue        # PC / printer are leaves; an IP phone passes through
            for c, peer in adj.get(x, []):
                if peer in seen or devices.get(peer) is None:
                    continue
                if devices[peer].device_type == "router":
                    continue
                seen.add(peer)
                stack.append(peer)
        return found

    alloc = _IfaceAllocator()
    for iface in db.query(Interface).all():  # respect interfaces already in use
        if devices.get(iface.device_id) and devices[iface.device_id].device_type == "router":
            alloc.reserve(iface.device_id, iface.name)

    existing_ip = {
        (i.device_id, i.name): i
        for i in db.query(Interface).all()
        if i.ip_address and i.subnet_mask
    }
    # interfaces the admin filled in by hand (Devices -> Edit -> Interface IPs).
    # 10.x manual IPs feed router-to-router links; everything else (192.168.x,
    # 172.16.x ...) is a hand-picked LAN gateway for a switch segment.
    manual_ifaces: dict[int, list[str]] = {}
    lan_manual_ifaces: dict[int, list[str]] = {}
    for (did, name), i in existing_ip.items():
        if (i.description or "").lower() != "manual":
            continue
        if str(i.ip_address).startswith("10."):
            manual_ifaces.setdefault(did, []).append(name)
        else:
            lan_manual_ifaces.setdefault(did, []).append(name)
    for names in lan_manual_ifaces.values():
        names.sort()
    # hand-typed interfaces keep their "manual" tag for good, so the admin's
    # choice survives every re-run (never silently turned into an auto LAN)
    manual_lan_names: set[tuple[int, str]] = {
        (did, n) for did, ns in lan_manual_ifaces.items() for n in ns
    }
    used_manual: set[tuple[int, str]] = set()
    used_manual_lan: set[tuple[int, str]] = set()

    # what each existing interface is currently used for, so a *stale* interface
    # name remembered on a connection (e.g. from before a LAN/WAN was split into
    # separate re-configure clicks) is never reused for a different purpose
    iface_purpose: dict[tuple[int, str], str] = {}
    for i in db.query(Interface).all():
        desc = (i.description or "").lower()
        purpose = "lan" if desc.startswith("lan") else "wan" if desc.startswith(("link to", "point-to-point")) else "manual" if desc == "manual" else "other"
        iface_purpose[(i.device_id, i.name)] = purpose

    def _pick_iface(conn, dev_id: int, want: str, prefer_manual: bool = False) -> str:
        named = _iface_for(conn, dev_id)

        if want == "lan":
            pool = [m for m in lan_manual_ifaces.get(dev_id, [])
                    if (dev_id, m) not in used_manual_lan]
            # 1. the cable is already bound to a hand-typed LAN gateway - keep it
            if named in pool:
                used_manual_lan.add((dev_id, named))
                return named
            # 2. an interface the admin explicitly pinned (the router's own
            #    management IP) stays where it is
            ni = existing_ip.get((dev_id, named)) if named else None
            dev = devices.get(dev_id)
            admin_pinned = ni is not None and dev is not None and ni.ip_address == dev.mgmt_ip
            # 3. otherwise a still-unused hand-typed gateway beats an
            #    auto-assigned (or stale) "LAN" interface remembered on the cable
            if not admin_pinned and pool:
                m = pool[0]
                used_manual_lan.add((dev_id, m))
                return m
            # 4. keep the remembered LAN interface, else take a fresh one
            if named and iface_purpose.get((dev_id, named), "lan") == "lan":
                return named
            return alloc.next_free(dev_id)

        if named and iface_purpose.get((dev_id, named), want) == want:
            return named
        if prefer_manual:
            for m in manual_ifaces.get(dev_id, []):
                if (dev_id, m) not in used_manual:
                    used_manual.add((dev_id, m))
                    return m
        return alloc.next_free(dev_id)

    lan_pool = _lan_pools()
    wan_pool = _wan_pools()

    router_lans: dict[int, list[dict]] = {r.id: [] for r in routers}
    router_wans: dict[int, list[dict]] = {r.id: [] for r in routers}
    pc_segment: dict[int, dict] = {}
    switch_lan: dict[int, dict] = {}   # switch device_id -> the LAN segment it carries
    lan_vlan_id: dict[str, int] = {}   # LAN network (str) -> VLAN id (deterministic)
    _next_vlan_id = [100]

    def _vlan_for(lan: dict) -> int:
        key = f"{lan['network']}/{lan['prefix']}"
        if key in lan_vlan_id:
            return lan_vlan_id[key]
        net = ipaddress.ip_network(key, strict=False)
        if str(net.network_address).startswith("192.168.") and net.prefixlen == 24:
            vid = net.network_address.packed[2] * 10 or 10   # 192.168.X.0/24 -> X*10
        else:
            vid = _next_vlan_id[0]
            _next_vlan_id[0] += 10
        while vid in lan_vlan_id.values() or vid > 4094:
            vid = (vid % 4090) + 1
        lan_vlan_id[key] = vid
        return vid
    used_lan_nets: set[str] = set()
    done_wan: set[int] = set()   # connection ids already turned into a WAN link
    done_lan: set[tuple[int, int]] = set()
    mgmt_used: set[int] = set()   # routers whose mgmt_ip is already placed on a LAN

    def _typed_ip(router: Device):
        if not router.mgmt_ip or router.id in mgmt_used:
            return None
        if any(i.ip_address == router.mgmt_ip
               for (did, _), i in existing_ip.items() if did == router.id):
            return None
        try:
            return ipaddress.ip_address(router.mgmt_ip)
        except ValueError:
            return None

    def _classA_link(router: Device):
        """Admin-typed Class-A address -> use it verbatim on a router-to-router
        link. Router-to-router links are always a /30 (255.255.255.252), so the
        peer takes the other address in that tiny subnet."""
        a = _typed_ip(router)
        if a is None or not str(a).startswith("10."):
            return None
        mgmt_used.add(router.id)
        return ipaddress.ip_network(f"{a}/30", strict=False), str(a)

    def _partner_host(net, anchor_ip):
        anchor = ipaddress.ip_address(anchor_ip)
        nxt = anchor + 1
        if nxt in net and nxt != net.broadcast_address:
            return str(nxt)
        for x in net.hosts():
            if str(x) != anchor_ip:
                return str(x)
        return anchor_ip

    def _mgmt_lan(router: Device):
        """If the admin typed an IP for the router, use it as the LAN gateway (/24)."""
        addr = _typed_ip(router)
        if addr is None:
            return None
        mgmt_used.add(router.id)
        return ipaddress.ip_network(f"{addr}/24", strict=False), str(addr)

    for r in routers:
        for c, peer_id in adj.get(r.id, []):
            peer = devices.get(peer_id)
            if peer is None:
                continue
            is_wan = peer.device_type == "router"
            if is_wan and not do_wan:
                continue
            if not is_wan and not do_lan:
                continue
            if not is_wan and (r.id, peer_id) in done_lan:
                continue  # already handled this router<->device pair (duplicate cable)
            if is_wan and c.id in done_wan:
                continue  # this exact cable was already turned into a WAN link
            done_lan.add((r.id, peer_id))
            r_iface = _pick_iface(c, r.id, "wan" if is_wan else "lan", prefer_manual=is_wan)
            _set_conn_iface(c, r.id, r_iface)

            if is_wan:
                done_wan.add(c.id)
                p_iface = _pick_iface(c, peer.id, "wan", prefer_manual=True)
                _set_conn_iface(c, peer.id, p_iface)

                # router-to-router links are Class A (10.x). Priority:
                #  1) a 10.x IP the admin put on one of the link interfaces
                #  2) a 10.x IP the admin typed as the router's management IP
                #  3) an auto /30 from 10.0.0.0/8
                r_have = existing_ip.get((r.id, r_iface))
                p_have = existing_ip.get((peer.id, p_iface))
                have = (r_have if r_have and str(r_have.ip_address).startswith("10.") else None) \
                    or (p_have if p_have and str(p_have.ip_address).startswith("10.") else None)
                r_typed, p_typed = _classA_link(r), _classA_link(peer)
                if have is not None:
                    # router-to-router links are always a /30 (255.255.255.252)
                    net = ipaddress.ip_network(f"{have.ip_address}/30", strict=False)
                    other = _partner_host(net, have.ip_address)
                    if have is r_have:
                        r_ip, p_ip = have.ip_address, other
                    else:
                        p_ip, r_ip = have.ip_address, other
                elif r_typed is not None:
                    net, r_ip = r_typed
                    p_ip = _partner_host(net, r_ip)
                elif p_typed is not None:
                    net, p_ip = p_typed
                    r_ip = _partner_host(net, p_ip)
                else:
                    net = next(wan_pool)
                    hosts = list(net.hosts())
                    r_ip, p_ip = str(hosts[0]), str(hosts[1])

                for rid, iface, ip, peer_h, peer_ip, peer_id in (
                    (r.id, r_iface, r_ip, peer.hostname, p_ip, peer.id),
                    (peer.id, p_iface, p_ip, r.hostname, r_ip, r.id),
                ):
                    router_wans[rid].append({
                        "iface": iface, "ip": ip, "netmask": str(net.netmask),
                        "network": str(net.network_address), "wildcard": str(net.hostmask),
                        "peer_hostname": peer_h, "peer_ip": peer_ip, "peer_asn": _asn(peer_id),
                    })
                _sync_connection(db, r, r_iface, peer, p_iface, link_type="p2p", conn_id=c.id)
            else:
                have = existing_ip.get((r.id, r_iface))
                if have:
                    # a hand-typed interface IP (or one from a previous run)
                    net = ipaddress.ip_network(f"{have.ip_address}/{have.subnet_mask}", strict=False)
                    gw = have.ip_address
                else:
                    mgmt = _mgmt_lan(r)
                    if mgmt is not None:
                        net, gw = mgmt      # admin-typed router mgmt IP -> LAN gateway
                    else:
                        net = next(lan_pool)
                        while str(net) in used_lan_nets:
                            net = next(lan_pool)
                        gw = str(list(net.hosts())[0])
                used_lan_nets.add(str(net))

                lan = {
                    "iface": r_iface,
                    "network": str(net.network_address),
                    "netmask": str(net.netmask),
                    "prefix": net.prefixlen,
                    "wildcard": str(net.hostmask),
                    "gateway": gw,
                    "pool_name": f"LAN_{_sanitize(r_iface)}",
                    "exclude_from": str(net.network_address + 1),
                    "exclude_to": gw,
                    "_net": net,
                }
                router_lans[r.id].append(lan)
                sw_iface = _iface_for(c, peer.id) or "GigabitEthernet0/1"
                _sync_connection(db, r, r_iface, peer, sw_iface, link_type="access", conn_id=c.id)
                if peer.device_type == "switch":
                    switch_lan.setdefault(
                        peer.id, {"lan": lan, "uplink": sw_iface, "router_hostname": r.hostname}
                    )
                else:
                    # an endpoint cabled straight to the router
                    for pc_id in l2_pcs(peer_id):
                        pc_segment.setdefault(pc_id, lan)

    # every endpoint behind a switch joins the segment of the NEAREST switch that
    # has a router uplink - so a PC on sw4 gets sw4's subnet even when sw4 is also
    # cabled to another uplinked switch (a Layer-2 loop between segments)
    if do_lan and switch_lan:
        for pc_id, dv in devices.items():
            if dv.device_type not in ENDPOINT_TYPES or pc_id in pc_segment:
                continue
            seen, frontier, best = {pc_id}, [pc_id], None
            while frontier and best is None:
                nxt: list[int] = []
                for x in frontier:
                    for _c, nb in adj.get(x, []):
                        nbd = devices.get(nb)
                        if nb in seen or nbd is None or nbd.device_type == "router":
                            continue
                        seen.add(nb)
                        if nb in switch_lan:
                            best = nb
                            break
                        nxt.append(nb)
                    if best is not None:
                        break
                frontier = nxt
            if best is not None:
                pc_segment[pc_id] = switch_lan[best]["lan"]

    # give every LAN network a globally-unique VLAN id (10, 20, 30 ...) in a
    # deterministic order, so it is consistent on the router, the switch and DHCP
    for lan in sorted(
        (l for lans in router_lans.values() for l in lans),
        key=lambda l: ipaddress.ip_address(l["network"]),
    ):
        _vlan_for(lan)

    # ---- addressing for every connected host --------------------------------
    #  servers first (they keep a low, static-looking address), then PCs / phones
    #  / printers via "DHCP" (.N ... in hostname order).
    pc_assignments = []
    if do_lan:
        for pc_id in pc_segment:
            d = devices[pc_id]
            # keep a server's admin-set IP if it already fits its own subnet
            if d.device_type == "server" and d.mgmt_ip:
                try:
                    if ipaddress.ip_address(d.mgmt_ip) in pc_segment[pc_id]["_net"]:
                        continue
                except ValueError:
                    pass
            d.mgmt_ip = None

        taken = {d.mgmt_ip for d in devices.values() if d.mgmt_ip}
        per_lan_next: dict[str, int] = {}

        def _order(kv):
            d = devices[kv[0]]
            return (0 if d.device_type == "server" else 1, d.hostname)

        for pc_id, lan in sorted(pc_segment.items(), key=_order):
            pc = devices[pc_id]
            if pc.mgmt_ip:                       # server kept its static address
                pc_assignments.append({
                    "pc": pc.hostname, "ip": pc.mgmt_ip, "gateway": lan["gateway"],
                    "network": f"{lan['network']}/{lan['prefix']}", "static": True,
                })
                continue
            gw = int(ipaddress.ip_address(lan["gateway"]))
            nxt = per_lan_next.get(lan["network"], gw + 1)
            ip = None
            for cand in range(nxt, int(lan["_net"].broadcast_address)):
                s = str(ipaddress.ip_address(cand))
                if s not in taken:
                    ip = s
                    per_lan_next[lan["network"]] = cand + 1
                    break
            if ip is None:
                continue
            pc.mgmt_ip = ip
            pc.status = "online"
            taken.add(ip)
            pc_assignments.append({
                "pc": pc.hostname, "ip": ip, "gateway": lan["gateway"],
                "network": f"{lan['network']}/{lan['prefix']}",
                "static": pc.device_type == "server",
            })

    # ---- server roles wired into the routers (DNS / Syslog / NTP / DHCP relay) --
    def _server_ip_for(role: str) -> str | None:
        for d in sorted(devices.values(), key=lambda x: x.hostname):
            if d.device_type == "server" and d.mgmt_ip and d.services:
                roles = {s.strip().lower() for s in d.services.split(",")}
                if role.lower() in roles:
                    return d.mgmt_ip
        return None

    dns_ip = _server_ip_for("DNS")
    syslog_ip = _server_ip_for("Syslog")
    ntp_ip = _server_ip_for("NTP")
    dhcp_relay_ip = _server_ip_for("DHCP")

    # ---- generate + persist (only the requested scope is rewritten) --------
    results = []
    for r in routers:
        lans = router_lans[r.id] if do_lan else _db_lans(db, r.id)
        wans = router_wans[r.id] if do_wan else _db_wans(db, r.id)
        if not lans and not wans:
            continue
        n = min(r.id, 255)
        # NAT overload: LANs are "inside", the first router-to-router link (the
        # closest thing to an uplink in this topology) is "outside"
        nat_outside_iface = wans[0]["iface"] if (nat and wans) else None
        cfg = generate_auto_router_config(
            hostname=r.hostname, lans=lans, wans=wans, router_id=f"{n}.{n}.{n}.{n}",
            routing=routing, asn=_asn(r.id), nat=nat, nat_outside_iface=nat_outside_iface,
            dns=dns_ip or "8.8.8.8", syslog_ip=syslog_ip, ntp_ip=ntp_ip,
            dhcp_relay_ip=dhcp_relay_ip,
        )

        keep_prefix = "link to " if do_lan and not do_wan else "LAN " if do_wan and not do_lan else None
        recreated_names = set()
        if do_lan:
            recreated_names |= {lan["iface"] for lan in lans}
        if do_wan:
            recreated_names |= {wan["iface"] for wan in wans}
        for i in db.query(Interface).filter(Interface.device_id == r.id).all():
            desc = (i.description or "")
            if desc.lower() == "manual" and i.name not in recreated_names:
                continue  # hand-typed interface IP not (yet) used by a link - keep it
            if keep_prefix and desc.startswith(keep_prefix):
                continue  # keep the other scope's interfaces untouched
            db.delete(i)
        db.query(Routing).filter(Routing.device_id == r.id).delete()
        db.query(Vlan).filter(Vlan.device_id == r.id).delete()
        db.flush()   # apply the deletes before re-inserting (unique names)

        nets = []
        for lan in lans:
            vid = _vlan_for(lan)
            if do_lan:
                is_manual = (r.id, lan["iface"]) in manual_lan_names
                db.add(Interface(
                    device_id=r.id, name=lan["iface"], ip_address=lan["gateway"],
                    subnet_mask=lan["netmask"], mode="routed",
                    description="manual" if is_manual
                    else f"LAN {lan['network']}/{lan['prefix']}", enabled=True,
                ))
            db.add(Vlan(device_id=r.id, vlan_id=vid, name=f"DATA_VLAN{vid}",
                        subnet=f"{lan['network']}/{lan['prefix']}", gateway=lan["gateway"],
                        department=None))
            nets.append(f"{lan['network']} {lan['wildcard']} area 0")
        for wan in wans:
            if do_wan:
                db.add(Interface(
                    device_id=r.id, name=wan["iface"], ip_address=wan["ip"],
                    subnet_mask=wan["netmask"], mode="routed",
                    description=f"link to {wan['peer_hostname']}", enabled=True,
                ))
            nets.append(f"{wan['network']} {wan['wildcard']} area 0")
        if routing in ("ospf", "both"):
            db.add(Routing(device_id=r.id, protocol="ospf", process_id=1, area="0",
                           networks=json.dumps(nets)))
        if routing in ("bgp", "both"):
            db.add(Routing(device_id=r.id, protocol="bgp", process_id=_asn(r.id), area="0",
                           networks=json.dumps(nets)))
        r.last_config = cfg
        r.status = "online"
        # never overwrite an admin-set management IP; only fill it when empty
        if not r.mgmt_ip:
            r.mgmt_ip = lans[0]["gateway"] if lans else wans[0]["ip"] if wans else None
        results.append({"device": r.hostname, "config": cfg})

    switch_targets = (
        [d for d in devices.values() if d.device_type == "switch" and adj.get(d.id)]
        if do_lan else []
    )
    for sw in switch_targets:
        info = switch_lan.get(sw.id)
        vlan_id = vlan_name = network = None
        uplink = "GigabitEthernet0/1"
        router_hostname = "R1"
        if info:
            lan = info["lan"]
            vlan_id = _vlan_for(lan)
            vlan_name = f"DATA_VLAN{vlan_id}"
            network = f"{lan['network']}/{lan['prefix']}"
            uplink = info["uplink"]
            router_hostname = info["router_hostname"]
            db.query(Vlan).filter(Vlan.device_id == sw.id).delete()
            db.add(Vlan(device_id=sw.id, vlan_id=vlan_id, name=vlan_name,
                        subnet=network, gateway=lan["gateway"]))
        cfg = generate_auto_switch_config(
            hostname=sw.hostname, uplink=uplink, router_hostname=router_hostname,
            vlan_id=vlan_id, vlan_name=vlan_name, network=network,
            ssh_username=sw.ssh_username, ssh_password=sw.ssh_password,
            ssh_secret=sw.ssh_secret,
        )
        sw.last_config = cfg
        sw.status = "online"
        results.append({"device": sw.hostname, "config": cfg, "vlan_id": vlan_id})

    db.commit()
    write_log(db, f"Auto configuration ({scope}, {routing}, nat={nat}) from topology: "
                  f"{len(results)} device(s), {len(pc_assignments)} PC(s) via DHCP",
              category="config")

    return {
        "routing": routing,
        "nat": nat,
        "services": {
            "dns": dns_ip, "syslog": syslog_ip, "ntp": ntp_ip, "dhcp_relay": dhcp_relay_ip,
        },
        "results": results,
        "segments": [
            {
                "router": r.hostname,
                "asn": _asn(r.id) if routing in ("bgp", "both") else None,
                "nat_outside": router_wans[r.id][0]["iface"] if (nat and router_wans[r.id]) else None,
                "lan": [{"iface": l["iface"], "network": f"{l['network']}/{l['prefix']}",
                         "gateway": l["gateway"], "vlan_id": lan_vlan_id.get(f"{l['network']}/{l['prefix']}")}
                        for l in router_lans[r.id]],
                "links": [
                    {"iface": w["iface"], "ip": w["ip"], "peer": w["peer_hostname"],
                     "peer_ip": w.get("peer_ip"),
                     "peer_asn": w.get("peer_asn") if routing in ("bgp", "both") else None}
                    for w in router_wans[r.id]
                ],
            }
            for r in routers if router_lans[r.id] or router_wans[r.id]
        ],
        "dhcp": pc_assignments,
    }
