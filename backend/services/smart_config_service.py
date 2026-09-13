"""Smart Auto Configuration orchestrator.

Input: a main router, optional switches, optional peer routers, and departments.
Pipeline:  subnet plan -> VLANs -> IP/gateways -> DHCP -> OSPF
           -> auto router<->router /30 links (interfaces auto-picked)
           -> Cisco config -> (optional) deploy -> persist to DB.
"""
from __future__ import annotations

import ipaddress
import json

from sqlalchemy.orm import Session

from models import Connection, Device, Interface, Routing, Vlan
from schemas import ConfigResult, SmartConfigIn, SmartConfigResult
from services import deployment_service
from services.config_generator import generate_router_config, generate_switch_config
from services.logging_service import write_log
from services.subnet_calculator import plan_departments

ROUTER_UPLINK = "GigabitEthernet0/0"
SWITCH_UPLINK = "GigabitEthernet0/1"
ACCESS_PORT_PREFIX = "FastEthernet0/"
ACCESS_PORT_FIRST = 1
ACCESS_PORT_LAST = 22  # leave Fa0/23-24 + Gi0/1-2 free for uplinks

# pool of router interfaces the auto-configurator is allowed to assign to links
ROUTER_IFACE_POOL = [
    "GigabitEthernet0/0", "GigabitEthernet0/1", "GigabitEthernet0/2",
    "GigabitEthernet0/3", "GigabitEthernet0/4", "GigabitEthernet0/5",
]
TRANSIT_POOL = "10.0.0.0/8"  # carved into /30s for router<->router links


class _IfaceAllocator:
    """Hands out the next unused interface for a device."""

    def __init__(self):
        self._used: dict[int, set[str]] = {}

    def reserve(self, device_id: int, name: str) -> None:
        self._used.setdefault(device_id, set()).add(name)

    def next_free(self, device_id: int) -> str:
        used = self._used.setdefault(device_id, set())
        for name in ROUTER_IFACE_POOL:
            if name not in used:
                used.add(name)
                return name
        raise ValueError("No free interface left on the router for another link.")


def build_p2p_links(
    main: Device, peers: list[Device], alloc: _IfaceAllocator, area: str = "0"
) -> list[dict]:
    """One /30 per (main <-> peer) link; interfaces auto-picked on both ends."""
    subnets = ipaddress.ip_network(TRANSIT_POOL).subnets(new_prefix=30)
    links: list[dict] = []
    for peer in peers:
        net = next(subnets)
        hosts = list(net.hosts())
        local_if = alloc.next_free(main.id)
        peer_if = alloc.next_free(peer.id)
        links.append(
            {
                "main_id": main.id,
                "peer_id": peer.id,
                "peer_hostname": peer.hostname,
                "main_hostname": main.hostname,
                "network": str(net.network_address),
                "mask": str(net.netmask),
                "wildcard": str(net.hostmask),
                "cidr": str(net),
                "area": area,
                "local_if": local_if,      # on main router
                "local_ip": str(hosts[0]),
                "peer_if": peer_if,        # on peer router
                "peer_ip": str(hosts[1]),
            }
        )
    return links


def allocate_access_ports(plan) -> list[dict]:
    """Spread the switch access ports across departments (min 1 each, then by size)
    so PCs plugged into a department's block land in the right VLAN."""
    depts = plan.departments
    if not depts:
        return []
    capacity = ACCESS_PORT_LAST - ACCESS_PORT_FIRST + 1
    total_users = sum(d.users for d in depts) or len(depts)

    counts = [max(1, round(capacity * d.users / total_users)) for d in depts]
    while sum(counts) > capacity:
        counts[counts.index(max(counts))] -= 1

    ports: list[dict] = []
    num = ACCESS_PORT_FIRST
    for d, c in zip(depts, counts):
        for _ in range(c):
            if num > ACCESS_PORT_LAST:
                break
            ports.append(
                {"port": f"{ACCESS_PORT_PREFIX}{num}", "department": d.name, "vlan_id": d.vlan_id}
            )
            num += 1
    return ports


def _persist_router(db: Session, router: Device, plan, ospf_process: int, ospf_area: str) -> None:
    db.query(Vlan).filter(Vlan.device_id == router.id).delete()
    db.query(Interface).filter(Interface.device_id == router.id).delete()
    db.query(Routing).filter(Routing.device_id == router.id).delete()

    networks = []
    for d in plan.departments:
        db.add(
            Vlan(
                device_id=router.id,
                vlan_id=d.vlan_id,
                name=d.name.replace(" ", "_"),
                department=d.name,
                subnet=d.cidr,
                gateway=str(d.gateway),
            )
        )
        db.add(
            Interface(
                device_id=router.id,
                name=f"{ROUTER_UPLINK}.{d.vlan_id}",
                ip_address=str(d.gateway),
                subnet_mask=d.netmask,
                mode="routed",
                vlan_id=d.vlan_id,
                description=d.name,
                enabled=True,
            )
        )
        networks.append(f"{d.network.network_address} {d.wildcard} area {ospf_area}")

    db.add(
        Routing(
            device_id=router.id,
            protocol="ospf",
            process_id=ospf_process,
            area=ospf_area,
            networks=json.dumps(networks),
        )
    )
    db.commit()


def _persist_switch(db: Session, switch: Device, plan, access_ports: list[dict]) -> None:
    db.query(Vlan).filter(Vlan.device_id == switch.id).delete()
    db.query(Interface).filter(Interface.device_id == switch.id).delete()
    for d in plan.departments:
        # a switch is pure Layer 2 - VLAN id + name only, never subnet/gateway (IP)
        db.add(
            Vlan(
                device_id=switch.id,
                vlan_id=d.vlan_id,
                name=d.name.replace(" ", "_"),
                department=d.name,
                subnet=None,
                gateway=None,
            )
        )
    db.add(
        Interface(
            device_id=switch.id, name=SWITCH_UPLINK, mode="trunk",
            description="trunk-to-router", enabled=True,
        )
    )
    for p in access_ports:
        db.add(
            Interface(
                device_id=switch.id, name=p["port"], mode="access", vlan_id=p["vlan_id"],
                description=f"{p['department']} access", enabled=True,
            )
        )
    db.commit()


def _deploy(db: Session, device: Device, config: str, tag: str) -> ConfigResult:
    device.last_config = config
    artifacts = deployment_service.write_ansible_artifacts(device, config, tag)
    res = ConfigResult(device_id=device.id, device_name=device.name, config=config, deployed=False)

    try:
        output = deployment_service.push_config(device, config)
        res.deployed = True
        res.deploy_output = output
        device.status = "online"
        write_log(
            db,
            f"Auto-config deployed to {device.hostname}",
            level="info",
            category="deploy",
            device_id=device.id,
            detail=f"ansible artifacts: {artifacts}",
        )
    except Exception as exc:  # noqa: BLE001 - surface any deploy failure to the UI
        res.error = str(exc)
        write_log(
            db,
            f"Auto-config deploy FAILED for {device.hostname}",
            level="error",
            category="deploy",
            device_id=device.id,
            detail=str(exc),
        )
    db.commit()
    return res


def _rid(device_id: int) -> str:
    n = min(device_id, 255)
    return f"{n}.{n}.{n}.{n}"


def _peer_view(link: dict) -> dict:
    """Same link seen from the peer router's side."""
    return {
        "local_if": link["peer_if"],
        "local_ip": link["peer_ip"],
        "mask": link["mask"],
        "network": link["network"],
        "wildcard": link["wildcard"],
        "peer_hostname": link["main_hostname"],
    }


def _free_interface(db: Session, device_id: int, iface: str, keep_conn_id: int | None = None) -> None:
    """Release `iface` from any other connection row on this device, so it can be
    reassigned without tripping the (device, interface) unique constraint."""
    for c in db.query(Connection).filter(
        (Connection.a_device_id == device_id) | (Connection.b_device_id == device_id)
    ):
        if keep_conn_id is not None and c.id == keep_conn_id:
            continue
        if c.a_device_id == device_id and c.a_interface == iface:
            c.a_interface = None
        if c.b_device_id == device_id and c.b_interface == iface:
            c.b_interface = None


def _sync_connection(
    db: Session, a: Device, a_if: str, b: Device, b_if: str, link_type: str = "p2p",
    conn_id: int | None = None,
) -> None:
    if conn_id is not None:
        # the caller already knows exactly which cable this is (it may be one
        # of SEVERAL links between the same two devices, e.g. two router-to-
        # router links) - update that row only, never collapse it with a sibling
        conn = db.get(Connection, conn_id)
    else:
        # dedupe: legacy/duplicate rows for the same device pair can accumulate
        # (re-running auto-config, manual re-cabling, etc.) - keep only the oldest
        dupes = (
            db.query(Connection)
            .filter(
                ((Connection.a_device_id == a.id) & (Connection.b_device_id == b.id))
                | ((Connection.a_device_id == b.id) & (Connection.b_device_id == a.id))
            )
            .order_by(Connection.id)
            .all()
        )
        conn = dupes[0] if dupes else None
        if len(dupes) > 1:
            for extra in dupes[1:]:
                db.delete(extra)
            db.flush()   # apply the deletes before anything else touches this pair

    keep_id = conn.id if conn else None
    _free_interface(db, a.id, a_if, keep_id)
    _free_interface(db, b.id, b_if, keep_id)
    db.flush()   # commit the "free" step on its own before reassigning below,

    if conn is None:
        conn = Connection(
            a_device_id=a.id, b_device_id=b.id,
            a_interface=a_if, b_interface=b_if, link_type=link_type, status="up",
        )
        db.add(conn)
    else:
        if conn.a_device_id == a.id:
            conn.a_interface, conn.b_interface = a_if, b_if
        else:
            conn.a_interface, conn.b_interface = b_if, a_if
        conn.link_type = link_type
    db.flush()   # ... and this step on its own, so no later call can batch the
                 # two UPDATEs together and hit a transient unique-constraint clash
    a.status = "online"
    b.status = "online"
    db.commit()


def _emit(db: Session, device: Device, cfg: str, deploy: bool, results: list, tag: str) -> None:
    device.last_config = cfg
    db.commit()
    if deploy:
        results.append(_deploy(db, device, cfg, tag=tag))
    else:
        results.append(
            ConfigResult(device_id=device.id, device_name=device.name, config=cfg, deployed=False)
        )


def run(db: Session, payload: SmartConfigIn) -> SmartConfigResult:
    router = db.get(Device, payload.router_id)
    if router is None or router.device_type != "router":
        raise ValueError("router_id must reference an existing device of type 'router'.")

    switches = []
    for sid in payload.switch_ids:
        sw = db.get(Device, sid)
        if sw is None or sw.device_type != "switch":
            raise ValueError(f"switch_ids: device {sid} is not a switch.")
        switches.append(sw)

    peers = []
    for pid in payload.peer_router_ids:
        pr = db.get(Device, pid)
        if pr is None or pr.device_type != "router":
            raise ValueError(f"peer_router_ids: device {pid} is not a router.")
        if pr.id == router.id:
            raise ValueError("peer_router_ids cannot include the main router.")
        peers.append(pr)

    plan = plan_departments([(d.name, d.users) for d in payload.departments])

    alloc = _IfaceAllocator()
    if plan.departments:
        alloc.reserve(router.id, ROUTER_UPLINK)   # kept for the switch trunk
    links = build_p2p_links(router, peers, alloc)

    results: list[ConfigResult] = []

    # --- main router ---
    router_cfg = generate_router_config(
        hostname=router.hostname,
        plan=plan,
        uplink=ROUTER_UPLINK,
        enable_dhcp=payload.enable_dhcp,
        switch_hostname=switches[0].hostname if switches else "SW1",
        router_id=_rid(router.id),
        p2p_links=links,
    )
    _persist_router(db, router, plan, ospf_process=1, ospf_area="0")
    for link in links:
        db.add(Interface(
            device_id=router.id, name=link["local_if"], ip_address=link["local_ip"],
            subnet_mask=link["mask"], mode="routed",
            description=f"P2P to {link['peer_hostname']}", enabled=True,
        ))
    db.commit()
    _emit(db, router, router_cfg, payload.deploy, results, "autoconfig")

    # --- peer routers ---
    empty_plan = plan_departments([])
    for peer, link in zip(peers, links):
        pv = _peer_view(link)
        peer_cfg = generate_router_config(
            hostname=peer.hostname,
            plan=empty_plan,
            enable_dhcp=False,
            router_id=_rid(peer.id),
            p2p_links=[pv],
        )
        db.query(Interface).filter(
            Interface.device_id == peer.id, Interface.name == pv["local_if"]
        ).delete()
        db.add(Interface(
            device_id=peer.id, name=pv["local_if"], ip_address=pv["local_ip"],
            subnet_mask=pv["mask"], mode="routed",
            description=f"P2P to {link['main_hostname']}", enabled=True,
        ))
        db.add(Routing(
            device_id=peer.id, protocol="ospf", process_id=1, area="0",
            networks=json.dumps([f"{link['network']} {link['wildcard']} area 0"]),
        ))
        db.commit()
        _sync_connection(db, router, link["local_if"], peer, link["peer_if"])
        _emit(db, peer, peer_cfg, payload.deploy, results, "autoconfig")

    # --- switches ---
    access_ports = allocate_access_ports(plan)
    for sw in switches:
        sw_cfg = generate_switch_config(
            hostname=sw.hostname, plan=plan, uplink=SWITCH_UPLINK,
            router_hostname=router.hostname, access_ports=access_ports,
        )
        _persist_switch(db, sw, plan, access_ports)
        _sync_connection(db, router, ROUTER_UPLINK, sw, SWITCH_UPLINK, link_type="trunk")
        _emit(db, sw, sw_cfg, payload.deploy, results, "autoconfig")

    plan_dict = plan.as_dict()
    plan_dict["access_ports"] = access_ports
    plan_dict["router_links"] = [
        {
            "a": router.hostname, "a_if": link["local_if"], "a_ip": link["local_ip"],
            "b": link["peer_hostname"], "b_if": link["peer_if"], "b_ip": link["peer_ip"],
            "subnet": link["cidr"],
        }
        for link in links
    ]

    write_log(
        db,
        f"Smart auto-configuration generated for "
        f"{1 + len(switches) + len(peers)} device(s)",
        level="info",
        category="config",
        device_id=router.id,
        detail=json.dumps(plan_dict),
    )
    return SmartConfigResult(plan=plan_dict, results=results)
