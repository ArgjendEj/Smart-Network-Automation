"""Subnet calculator + VLIP planner for the Smart Auto Configuration module.

Given a list of departments with a user count, it:
  * picks the smallest prefix that fits (users + gateway + broadcast + margin),
  * carves consecutive subnets out of a configurable base pool,
  * assigns an incrementing VLAN id and a gateway (first usable host) to each.
"""
from __future__ import annotations

import ipaddress
import math
from dataclasses import dataclass, field

from config import settings


@dataclass
class DepartmentPlan:
    name: str
    users: int
    vlan_id: int
    network: ipaddress.IPv4Network
    gateway: ipaddress.IPv4Address
    dhcp_start: ipaddress.IPv4Address
    dhcp_end: ipaddress.IPv4Address

    @property
    def cidr(self) -> str:
        return str(self.network)

    @property
    def netmask(self) -> str:
        return str(self.network.netmask)

    @property
    def wildcard(self) -> str:
        return str(self.network.hostmask)

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "users": self.users,
            "vlan_id": self.vlan_id,
            "network": self.cidr,
            "netmask": self.netmask,
            "wildcard": self.wildcard,
            "gateway": str(self.gateway),
            "dhcp_start": str(self.dhcp_start),
            "dhcp_end": str(self.dhcp_end),
            "usable_hosts": self.network.num_addresses - 2,
        }


@dataclass
class NetworkPlan:
    base_pool: str
    departments: list[DepartmentPlan] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "base_pool": self.base_pool,
            "departments": [d.as_dict() for d in self.departments],
        }


def prefix_for_users(users: int) -> int:
    """Smallest IPv4 prefix length that fits `users` hosts + network + broadcast."""
    if users < 1:
        users = 1
    needed = users + 2  # network + broadcast
    host_bits = max(1, math.ceil(math.log2(needed)))
    prefix = 32 - host_bits
    return max(0, min(prefix, 30))  # /30 is the smallest we hand out


def plan_departments(
    departments: list[tuple[str, int]],
    base_pool: str | None = None,
    vlan_start: int | None = None,
) -> NetworkPlan:
    base_pool = base_pool or settings.ip_pool_base
    vlan_start = settings.vlan_id_start if vlan_start is None else vlan_start

    pool = ipaddress.ip_network(base_pool, strict=False)
    plan = NetworkPlan(base_pool=str(pool))

    # Largest departments first => tidier allocation, less fragmentation.
    ordered = sorted(enumerate(departments), key=lambda kv: kv[1][1], reverse=True)

    cursor = int(pool.network_address)
    pool_end = int(pool.broadcast_address)

    tmp: dict[int, DepartmentPlan] = {}
    for order_idx, (orig_idx, (name, users)) in enumerate(ordered):
        prefix = prefix_for_users(users)
        block_size = 2 ** (32 - prefix)

        # align cursor to the block boundary
        if cursor % block_size != 0:
            cursor += block_size - (cursor % block_size)
        if cursor + block_size - 1 > pool_end:
            raise ValueError(
                f"Base pool {base_pool} is too small for department '{name}' "
                f"({users} users -> /{prefix})."
            )

        net = ipaddress.ip_network((cursor, prefix))
        hosts = list(net.hosts())
        gateway = hosts[0]
        dhcp_start = hosts[1] if len(hosts) > 1 else hosts[0]
        dhcp_end = hosts[-1]

        tmp[orig_idx] = DepartmentPlan(
            name=name,
            users=users,
            vlan_id=vlan_start + orig_idx * 10,
            network=net,
            gateway=gateway,
            dhcp_start=dhcp_start,
            dhcp_end=dhcp_end,
        )
        cursor += block_size

    plan.departments = [tmp[i] for i in range(len(departments))]
    return plan
