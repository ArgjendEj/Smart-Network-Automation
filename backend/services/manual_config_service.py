"""Manual Configuration: hostname, interfaces, IP/mask, VLAN, DHCP, OSPF, BGP."""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from models import Device, Interface, Routing, Vlan
from schemas import ConfigResult, ManualConfigIn
from services import deployment_service
from services.config_generator import generate_manual_config
from services.logging_service import write_log


def _persist(db: Session, device: Device, payload: ManualConfigIn, ifaces: list[dict]) -> None:
    if payload.hostname:
        device.hostname = payload.hostname

    for v in payload.vlans:
        row = (
            db.query(Vlan)
            .filter(Vlan.device_id == device.id, Vlan.vlan_id == v.vlan_id)
            .first()
        )
        if row is None:
            db.add(Vlan(device_id=device.id, vlan_id=v.vlan_id, name=v.name))
        else:
            row.name = v.name or row.name

    for i in ifaces:
        row = (
            db.query(Interface)
            .filter(Interface.device_id == device.id, Interface.name == i["name"])
            .first()
        )
        fields = dict(
            ip_address=i["ip_address"],
            subnet_mask=i["subnet_mask"],
            mode=i["mode"],
            vlan_id=i["vlan_id"],
            description=i["description"],
            enabled=i["enabled"],
        )
        if row is None:
            db.add(Interface(device_id=device.id, name=i["name"], **fields))
        else:
            for k, val in fields.items():
                if val is not None:
                    setattr(row, k, val)

    if payload.ospf and payload.ospf.networks:
        db.query(Routing).filter(
            Routing.device_id == device.id, Routing.protocol == "ospf"
        ).delete()
        db.add(Routing(
            device_id=device.id, protocol="ospf",
            process_id=payload.ospf.process_id, area="0",
            networks=json.dumps(
                [f"{n.network} {n.wildcard} {n.area}" for n in payload.ospf.networks]
            ),
        ))
    if payload.bgp and (payload.bgp.networks or payload.bgp.neighbors):
        db.query(Routing).filter(
            Routing.device_id == device.id, Routing.protocol == "bgp"
        ).delete()
        db.add(Routing(
            device_id=device.id, protocol="bgp",
            process_id=payload.bgp.asn, area="0",
            networks=json.dumps(
                [f"{n.network} {n.mask}" for n in payload.bgp.networks]
            ),
        ))
    db.commit()


def run(db: Session, payload: ManualConfigIn) -> ConfigResult:
    device = db.get(Device, payload.device_id)
    if device is None:
        raise ValueError("device_id does not exist.")

    ifaces = [i.model_dump() for i in payload.interfaces]
    if device.device_type == "switch":
        # a switch is pure Layer 2 here: never let the web server put an IP on it
        for i in ifaces:
            i["ip_address"] = None
            i["subnet_mask"] = None
            if i.get("mode") == "routed":
                i["mode"] = "access"
        # routing protocols only make sense on a router
        payload.ospf = None
        payload.bgp = None
    elif device.device_type == "router":
        # a router has no VLAN database and no switchport access-vlan commands
        payload.vlans = []
        for i in ifaces:
            i["vlan_id"] = None
            if i.get("mode") in ("access", "trunk"):
                i["mode"] = None

    config = generate_manual_config(
        hostname=payload.hostname or device.hostname,
        interfaces=ifaces,
        vlans=[v.model_dump() for v in payload.vlans],
        dhcp_pools=[] if device.device_type == "switch" else [d.model_dump() for d in payload.dhcp],
        ospf=payload.ospf.model_dump() if payload.ospf else None,
        bgp=payload.bgp.model_dump() if payload.bgp else None,
    )
    _persist(db, device, payload, ifaces)
    device.last_config = config
    db.commit()

    result = ConfigResult(
        device_id=device.id, device_name=device.name, config=config, deployed=False
    )

    if payload.deploy:
        artifacts = deployment_service.write_ansible_artifacts(device, config, "manual")
        try:
            result.deploy_output = deployment_service.push_config(device, config)
            result.deployed = True
            write_log(
                db,
                f"Manual config deployed to {device.hostname}",
                category="deploy",
                device_id=device.id,
                detail=f"ansible artifacts: {artifacts}",
            )
        except Exception as exc:  # noqa: BLE001
            result.error = str(exc)
            write_log(
                db,
                f"Manual config deploy FAILED for {device.hostname}",
                level="error",
                category="deploy",
                device_id=device.id,
                detail=str(exc),
            )
    else:
        write_log(
            db,
            f"Manual config generated for {device.hostname}",
            category="config",
            device_id=device.id,
        )
    db.commit()
    return result
