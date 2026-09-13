"""Cisco IOS configuration generator (Jinja2 templates)."""
from __future__ import annotations

import ipaddress
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from services.subnet_calculator import NetworkPlan

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "automation" / "templates"
_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
)


def _render(name: str, **ctx) -> str:
    return _env.get_template(name).render(**ctx)


def _clean(text: str) -> str:
    lines = [ln.rstrip() for ln in text.splitlines()]
    out: list[str] = []
    for ln in lines:
        if ln == "" and (not out or out[-1] in ("", "!")):
            continue
        if ln == "!" and out and out[-1] == "!":
            continue
        out.append(ln)
    return "\n".join(out).strip() + "\n"


def _dept_context(plan: NetworkPlan, ospf_area: str, dhcp_reserve: int = 10) -> list[dict]:
    """Rich per-department context shared by router template."""
    ctx = []
    for d in plan.departments:
        net = d.network
        first = int(net.network_address) + 1
        last = int(net.broadcast_address) - 1
        reserve_to = min(int(d.gateway) + dhcp_reserve, last)
        ctx.append(
            {
                "name": d.name,
                "vlan_id": d.vlan_id,
                "network": str(net.network_address),
                "netmask": d.netmask,
                "wildcard": d.wildcard,
                "gateway": str(d.gateway),
                "pool_name": f"{d.name.upper().replace(' ', '_')}_POOL",
                "exclude_from": str(ipaddress.ip_address(first)),
                "exclude_to": str(ipaddress.ip_address(reserve_to)),
            }
        )
    return ctx


# --------------------------------------------------------------------------- #
# Smart Auto Configuration
# --------------------------------------------------------------------------- #
def generate_router_config(
    hostname: str,
    plan: NetworkPlan,
    uplink: str = "GigabitEthernet0/0",
    ospf_process: int = 1,
    ospf_area: str = "0",
    enable_dhcp: bool = True,
    switch_hostname: str = "SW1",
    domain: str = "lab.local",
    dns: str = "8.8.8.8",
    router_id: str | None = None,
    p2p_links: list[dict] | None = None,
) -> str:
    depts = _dept_context(plan, ospf_area)
    if router_id is None:
        router_id = f"{ospf_process}.{ospf_process}.{ospf_process}.{ospf_process}"

    cfg = _render(
        "router_stick.j2",
        hostname=hostname,
        uplink=uplink,
        departments=depts,
        p2p_links=p2p_links or [],
        enable_dhcp=enable_dhcp,
        ospf_process=ospf_process,
        ospf_area=ospf_area,
        router_id=router_id,
        switch_hostname=switch_hostname,
        domain=domain,
        dns=dns,
    )
    return _clean(cfg)


def _group_access_ports(ports: list[dict]) -> list[dict]:
    """Collapse consecutive same-VLAN ports into IOS `interface range` blocks.
    Input items: {port: 'FastEthernet0/3', department, vlan_id}."""
    import re

    parsed = []
    for p in ports:
        m = re.match(r"([A-Za-z]+)(\d+/)(\d+)$", p["port"])
        if not m:
            parsed.append({**p, "_key": None})
            continue
        parsed.append({**p, "_pfx": m.group(1) + m.group(2), "_n": int(m.group(3))})

    groups: list[dict] = []
    for p in parsed:
        if "_n" in p and groups:
            g = groups[-1]
            if (
                g.get("_pfx") == p["_pfx"]
                and g["vlan_id"] == p["vlan_id"]
                and p["_n"] == g["_end"] + 1
            ):
                g["_end"] = p["_n"]
                continue
        if "_n" in p:
            groups.append(
                {"_pfx": p["_pfx"], "_start": p["_n"], "_end": p["_n"],
                 "department": p["department"], "vlan_id": p["vlan_id"]}
            )
        else:
            groups.append({"range": p["port"], "department": p["department"], "vlan_id": p["vlan_id"]})

    out = []
    for g in groups:
        if "range" in g:
            out.append(g)
        elif g["_start"] == g["_end"]:
            out.append({"range": f"{g['_pfx']}{g['_start']}", "department": g["department"], "vlan_id": g["vlan_id"]})
        else:
            out.append({"range": f"{g['_pfx']}{g['_start']}-{g['_end']}",
                        "department": g["department"], "vlan_id": g["vlan_id"]})
    return out


def generate_auto_router_config(
    hostname: str,
    lans: list[dict],
    wans: list[dict],
    router_id: str,
    ospf_process: int = 1,
    dns: str = "8.8.8.8",
    routing: str = "ospf",
    asn: int | None = None,
    nat: bool = False,
    nat_outside_iface: str | None = None,
    syslog_ip: str | None = None,
    ntp_ip: str | None = None,
    dhcp_relay_ip: str | None = None,
) -> str:
    """Plain multi-interface router config produced by the topology auto-configurator."""
    cfg = _render(
        "router_auto.j2",
        hostname=hostname, lans=lans, wans=wans, router_id=router_id,
        ospf_process=ospf_process, dns=dns, routing=routing, asn=asn or 65000,
        nat=nat, nat_outside_iface=nat_outside_iface,
        syslog_ip=syslog_ip, ntp_ip=ntp_ip, dhcp_relay_ip=dhcp_relay_ip,
    )
    return _clean(cfg)


def generate_auto_switch_config(
    hostname: str,
    uplink: str,
    router_hostname: str = "R1",
    vlan_id: int | None = None,
    vlan_name: str | None = None,
    network: str | None = None,
    access_range: str = "FastEthernet0/1-24",
    ssh_username: str | None = None,
    ssh_password: str | None = None,
    ssh_secret: str | None = None,
) -> str:
    """Pure L2 switch config produced by the topology auto-configurator: one VLAN
    for the LAN segment it carries (access mode uplink - the router side is a
    plain routed interface, not a dot1Q trunk). SSH management block is emitted
    only when credentials are set - the switch still carries no IP."""
    cfg = _render(
        "switch_auto.j2",
        hostname=hostname, uplink=uplink, router_hostname=router_hostname,
        vlan_id=vlan_id, vlan_name=vlan_name, network=network, access_range=access_range,
        ssh_username=ssh_username, ssh_password=ssh_password, ssh_secret=ssh_secret,
    )
    return _clean(cfg)


def generate_switch_config(
    hostname: str,
    plan: NetworkPlan,
    uplink: str = "GigabitEthernet0/1",
    access_ports: list[dict] | None = None,
    trunk_encap_needed: bool = False,
    router_hostname: str = "R1",
    ssh_username: str | None = None,
    ssh_password: str | None = None,
    ssh_secret: str | None = None,
) -> str:
    """Pure Layer-2 switch config: hostname, STP, VLAN db, trunk uplink, access
    ports. The switch is never given an IP address by this platform; an SSH
    management block is emitted only when credentials are set."""
    vlans = [{"vlan_id": d.vlan_id, "name": d.name.replace(" ", "_")} for d in plan.departments]
    allowed = ",".join(str(d.vlan_id) for d in plan.departments) or "1"
    cfg = _render(
        "switch_access.j2",
        hostname=hostname,
        vlans=vlans,
        uplink=uplink,
        allowed_vlans=allowed,
        access_ports=_group_access_ports(access_ports or []),
        trunk_encap_needed=trunk_encap_needed,
        router_hostname=router_hostname,
        ssh_username=ssh_username, ssh_password=ssh_password, ssh_secret=ssh_secret,
    )
    return _clean(cfg)


# --------------------------------------------------------------------------- #
# Manual Configuration
# --------------------------------------------------------------------------- #
def generate_manual_config(
    hostname: str | None,
    interfaces: list[dict],
    vlans: list[dict],
    dhcp_pools: list[dict],
    ospf: dict | None = None,
    bgp: dict | None = None,
    ssh_username: str | None = None,
    ssh_password: str | None = None,
    ssh_secret: str | None = None,
) -> str:
    parts: list[str] = []
    if hostname:
        parts.append(f"hostname {hostname}\n!")
    if vlans:
        parts.append(_render("vlan.j2", vlans=vlans))
    if interfaces:
        parts.append(_render("interface.j2", interfaces=interfaces))
    if dhcp_pools:
        parts.append(_render("dhcp.j2", pools=dhcp_pools))
    if (ospf and ospf.get("networks")) or (bgp and (bgp.get("networks") or bgp.get("neighbors"))):
        parts.append(_render("routing_manual.j2", ospf=ospf, bgp=bgp))
    if ssh_username:
        parts.append(_render(
            "_ssh.j2",
            ssh_username=ssh_username, ssh_password=ssh_password, ssh_secret=ssh_secret,
        ))
    if not parts:
        return "! (nothing to configure)\n"
    return _clean("\n".join(parts))


def config_to_commands(config: str) -> list[str]:
    """Flatten a config blob into ordered CLI lines for netmiko send_config_set."""
    cmds: list[str] = []
    for raw in config.splitlines():
        line = raw.rstrip()
        if not line or line.startswith("!") or line.strip() == "end":
            continue
        cmds.append(line)
    return cmds


def netmask_to_wildcard(netmask: str) -> str:
    return str(ipaddress.ip_address(int(ipaddress.ip_address("255.255.255.255")) - int(ipaddress.ip_address(netmask))))
