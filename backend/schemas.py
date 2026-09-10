"""Pydantic request/response schemas."""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

DeviceType = Literal["router", "switch", "pc", "ip_phone", "printer", "server"]


# ---------- Auth ----------
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    role: str


class LoginIn(BaseModel):
    username: str
    password: str


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)


# ---------- Device ----------
class ExtraIp(BaseModel):
    interface: str                       # e.g. GigabitEthernet0/1
    address: str                         # "10.0.5.1/24" or "10.0.5.1 255.255.255.0"


class DeviceBase(BaseModel):
    name: str
    hostname: str
    device_type: DeviceType
    services: Optional[str] = None            # server roles, e.g. "DHCP,DNS"
    mgmt_ip: Optional[str] = None
    ssh_username: Optional[str] = None
    ssh_password: Optional[str] = None
    ssh_secret: Optional[str] = None
    netmiko_driver: str = "cisco_ios"
    pos_x: float = 100.0
    pos_y: float = 100.0


class DeviceCreate(DeviceBase):
    extra_ips: Optional[list[ExtraIp]] = None


class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    hostname: Optional[str] = None
    device_type: Optional[DeviceType] = None
    services: Optional[str] = None
    mgmt_ip: Optional[str] = None
    ssh_username: Optional[str] = None
    ssh_password: Optional[str] = None
    ssh_secret: Optional[str] = None
    netmiko_driver: Optional[str] = None
    pos_x: Optional[float] = None
    pos_y: Optional[float] = None
    extra_ips: Optional[list[ExtraIp]] = None


class DeviceIp(BaseModel):
    interface: str
    ip: str            # e.g. 192.168.10.1/24
    role: str          # lan | link | mgmt


class DeviceOut(DeviceBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str
    last_checked: Optional[datetime] = None
    last_config: Optional[str] = None
    created_at: datetime
    ip_addresses: list[DeviceIp] = []


# ---------- Connection ----------
class ConnectionCreate(BaseModel):
    a_device_id: int
    b_device_id: int
    a_interface: Optional[str] = None
    b_interface: Optional[str] = None
    link_type: Literal["access", "trunk"] = "access"


class ConnectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    a_device_id: int
    b_device_id: int
    a_interface: Optional[str]
    b_interface: Optional[str]
    link_type: str
    status: str


# ---------- Interface / VLAN / Routing ----------
class InterfaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    device_id: int
    name: str
    ip_address: Optional[str]
    subnet_mask: Optional[str]
    mode: Optional[str]
    vlan_id: Optional[int]
    description: Optional[str]
    enabled: bool


class VlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    device_id: int
    vlan_id: int
    name: Optional[str]
    department: Optional[str]
    subnet: Optional[str]
    gateway: Optional[str]


class RoutingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    device_id: int
    protocol: str
    process_id: int
    area: str
    networks: Optional[str]
    dest_network: Optional[str]
    dest_mask: Optional[str]
    next_hop: Optional[str]


# ---------- Manual configuration ----------
class ManualIfaceConfig(BaseModel):
    name: str
    ip_address: Optional[str] = None
    subnet_mask: Optional[str] = None
    mode: Optional[Literal["access", "trunk", "routed"]] = None
    vlan_id: Optional[int] = None
    description: Optional[str] = None
    enabled: bool = True


class ManualVlanConfig(BaseModel):
    vlan_id: int
    name: Optional[str] = None


class ManualDhcpConfig(BaseModel):
    pool_name: str
    network: str          # 10.10.1.0
    netmask: str          # 255.255.255.0
    default_gateway: str
    dns: Optional[str] = "8.8.8.8"
    exclude_from: Optional[str] = None
    exclude_to: Optional[str] = None


class ManualOspfNetwork(BaseModel):
    network: str                  # 192.168.1.0
    wildcard: str = "0.0.0.255"
    area: str = "0"


class ManualOspfConfig(BaseModel):
    process_id: int = 1
    router_id: Optional[str] = None
    networks: list[ManualOspfNetwork] = Field(default_factory=list)
    passive_interfaces: list[str] = Field(default_factory=list)


class ManualBgpNetwork(BaseModel):
    network: str                  # 192.168.1.0
    mask: str = "255.255.255.0"


class ManualBgpNeighbor(BaseModel):
    ip: str
    remote_as: int


class ManualBgpConfig(BaseModel):
    asn: int
    router_id: Optional[str] = None
    networks: list[ManualBgpNetwork] = Field(default_factory=list)
    neighbors: list[ManualBgpNeighbor] = Field(default_factory=list)


class ManualConfigIn(BaseModel):
    device_id: int
    hostname: Optional[str] = None
    interfaces: list[ManualIfaceConfig] = Field(default_factory=list)
    vlans: list[ManualVlanConfig] = Field(default_factory=list)
    dhcp: list[ManualDhcpConfig] = Field(default_factory=list)
    ospf: Optional[ManualOspfConfig] = None
    bgp: Optional[ManualBgpConfig] = None
    deploy: bool = False   # if False -> only generate + save, don't push


# ---------- Smart auto configuration ----------
class DepartmentIn(BaseModel):
    name: str
    users: int = Field(gt=0, le=16000)


class SmartConfigIn(BaseModel):
    router_id: int
    switch_ids: list[int] = Field(default_factory=list)
    peer_router_ids: list[int] = Field(default_factory=list)  # routers to link R1<->Rx + OSPF
    departments: list[DepartmentIn] = Field(default_factory=list)
    routing_protocol: Literal["ospf"] = "ospf"
    enable_dhcp: bool = True
    deploy: bool = False


class ConfigResult(BaseModel):
    device_id: int
    device_name: str
    config: str
    deployed: bool
    deploy_output: Optional[str] = None
    error: Optional[str] = None


class SmartConfigResult(BaseModel):
    plan: dict
    results: list[ConfigResult]


# ---------- Logs / Dashboard ----------
class LogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    timestamp: datetime
    level: str
    category: str
    device_id: Optional[int]
    message: str
    detail: Optional[str]


class DashboardOut(BaseModel):
    total_devices: int
    online_devices: int
    offline_devices: int
    total_vlans: int
    routers: int
    switches: int
    pcs: int
    ip_phones: int = 0
    printers: int = 0
    servers: int = 0
    recent_deploys: list[LogOut]
