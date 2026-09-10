"""Database models — MVP: 7 tables (Users, Devices, Connections, VLANs,
Interfaces, Routing, Logs)."""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from database import Base

# device_type values that behave as plain Layer-2 hosts (no IOS config)
ENDPOINT_TYPES = ("pc", "ip_phone", "printer", "server")
# of those, the ones that pull an address from DHCP (servers use a static one)
DHCP_CLIENT_TYPES = ("pc", "ip_phone", "printer")
# services a server can run (free-form, comma-separated in Device.services)
SERVER_ROLES = ("DHCP", "DNS", "Web", "Syslog", "NTP", "Monitoring")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(16), default="admin", nullable=False)  # MVP: single role
    created_at = Column(DateTime, default=datetime.utcnow)


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(64), nullable=False)
    hostname = Column(String(64), nullable=False)
    device_type = Column(String(16), nullable=False)  # router|switch|pc|ip_phone|printer|server
    services = Column(String(128))                     # servers: "DHCP,DNS" etc.
    # management / SSH
    mgmt_ip = Column(String(45))
    ssh_username = Column(String(64))
    ssh_password = Column(String(128))
    ssh_secret = Column(String(128))  # enable secret
    netmiko_driver = Column(String(32), default="cisco_ios")
    # topology canvas position
    pos_x = Column(Float, default=100.0)
    pos_y = Column(Float, default=100.0)
    # runtime
    status = Column(String(16), default="unknown")  # online | offline | unknown
    last_checked = Column(DateTime)
    last_config = Column(Text)  # last generated/pushed config
    created_at = Column(DateTime, default=datetime.utcnow)

    interfaces = relationship("Interface", back_populates="device", cascade="all, delete-orphan")
    vlans = relationship("Vlan", back_populates="device", cascade="all, delete-orphan")
    routing = relationship("Routing", back_populates="device", cascade="all, delete-orphan")


class Connection(Base):
    __tablename__ = "connections"
    __table_args__ = (UniqueConstraint("a_device_id", "a_interface", name="uq_conn_endpoint_a"),)

    id = Column(Integer, primary_key=True, index=True)
    a_device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    b_device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    a_interface = Column(String(48))
    b_interface = Column(String(48))
    link_type = Column(String(16), default="access")  # access | trunk
    status = Column(String(16), default="up")
    created_at = Column(DateTime, default=datetime.utcnow)

    a_device = relationship("Device", foreign_keys=[a_device_id])
    b_device = relationship("Device", foreign_keys=[b_device_id])


class Vlan(Base):
    __tablename__ = "vlans"
    __table_args__ = (UniqueConstraint("device_id", "vlan_id", name="uq_vlan_per_device"),)

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    vlan_id = Column(Integer, nullable=False)
    name = Column(String(64))
    department = Column(String(64))
    subnet = Column(String(32))       # e.g. 10.10.1.0/24
    gateway = Column(String(45))      # SVI / router sub-interface address
    created_at = Column(DateTime, default=datetime.utcnow)

    device = relationship("Device", back_populates="vlans")


class Interface(Base):
    __tablename__ = "interfaces"
    __table_args__ = (UniqueConstraint("device_id", "name", name="uq_iface_per_device"),)

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(48), nullable=False)  # e.g. GigabitEthernet0/0
    ip_address = Column(String(45))
    subnet_mask = Column(String(45))
    mode = Column(String(16))          # access | trunk | routed
    vlan_id = Column(Integer)          # access vlan
    description = Column(String(128))
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    device = relationship("Device", back_populates="interfaces")


class Routing(Base):
    __tablename__ = "routing"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    protocol = Column(String(16), default="ospf")   # MVP: ospf (static allowed)
    process_id = Column(Integer, default=1)
    area = Column(String(16), default="0")
    networks = Column(Text)   # JSON list of "network wildcard area"
    # static route fields (optional)
    dest_network = Column(String(45))
    dest_mask = Column(String(45))
    next_hop = Column(String(45))
    created_at = Column(DateTime, default=datetime.utcnow)

    device = relationship("Device", back_populates="routing")


class Log(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    level = Column(String(16), default="info")        # info | warning | error
    category = Column(String(32), default="config")   # config | error | deploy | auth | system
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="SET NULL"))
    message = Column(Text, nullable=False)
    detail = Column(Text)
