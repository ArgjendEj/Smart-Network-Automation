from services.config_generator import (
    config_to_commands,
    generate_manual_config,
    generate_router_config,
    generate_switch_config,
)
from services.subnet_calculator import plan_departments


def _plan():
    return plan_departments([("Sales", 100), ("IT", 20)], base_pool="10.10.0.0/16", vlan_start=10)


def test_router_config_has_subinterfaces_dhcp_ospf():
    cfg = generate_router_config("R1", _plan(), uplink="GigabitEthernet0/0")
    assert "hostname R1" in cfg
    assert "interface GigabitEthernet0/0.10" in cfg
    assert "encapsulation dot1Q 10" in cfg
    assert "ip dhcp pool SALES_POOL" in cfg
    assert "router ospf 1" in cfg
    assert "network 10.10.0.0 0.0.0.127 area 0" in cfg


def test_switch_config_vlans_and_trunk():
    cfg = generate_switch_config("SW1", _plan(), uplink="GigabitEthernet0/1")
    assert "vlan 10" in cfg
    assert "vlan 20" in cfg
    assert "switchport mode trunk" in cfg


def test_manual_config_interface_and_vlan():
    cfg = generate_manual_config(
        hostname="SW2",
        interfaces=[
            {"name": "GigabitEthernet0/1", "mode": "access", "vlan_id": 10,
             "description": "sales-pc", "enabled": True, "ip_address": None, "subnet_mask": None}
        ],
        vlans=[{"vlan_id": 10, "name": "SALES"}],
        dhcp_pools=[],
    )
    assert "hostname SW2" in cfg
    assert "switchport access vlan 10" in cfg
    assert config_to_commands(cfg)[0] == "hostname SW2"
