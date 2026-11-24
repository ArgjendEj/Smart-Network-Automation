"""Seed the database with the default admin user (and optional demo devices)."""
from __future__ import annotations

import json
from pathlib import Path

from auth_utils import hash_password
from config import settings
from database import SessionLocal, init_db
from models import Connection, Device, Interface, Routing, User, Vlan

EXAMPLE_NETWORK = Path(__file__).resolve().parent / "demo_network.json"


def _load_example(db) -> int:
    """The finished 22-device network of the thesis (no SSH credentials)."""
    data = json.loads(EXAMPLE_NETWORK.read_text(encoding="utf-8"))
    for key, model in (("devices", Device), ("connections", Connection), ("interfaces", Interface),
                       ("vlans", Vlan), ("routing", Routing)):
        db.add_all([model(**row) for row in data[key]])
        db.flush()
    db.commit()
    return len(data["devices"])


def seed(with_demo: bool = True, example: bool = False) -> None:
    db = SessionLocal()
    try:
        if db.query(User).filter(User.username == settings.admin_username).first() is None:
            db.add(
                User(
                    username=settings.admin_username,
                    hashed_password=hash_password(settings.admin_password),
                    role="admin",
                )
            )
            db.commit()
            print(f"[seed] admin user created: {settings.admin_username} / {settings.admin_password}")

        # only ever into an empty database - an existing network is never touched
        if with_demo and example and db.query(Device).count() == 0 and EXAMPLE_NETWORK.exists():
            print(f"[seed] example network created ({_load_example(db)} devices)")

        if with_demo and db.query(Device).count() == 0:
            db.add_all(
                [
                    Device(
                        name="R1", hostname="R1", device_type="router",
                        mgmt_ip="192.168.10.2", ssh_username="admin",
                        ssh_password="cisco", ssh_secret="cisco",
                        pos_x=400, pos_y=120,
                    ),
                    Device(
                        name="SW1", hostname="SW1", device_type="switch",
                        pos_x=400, pos_y=320,
                    ),
                    Device(name="PC1", hostname="PC1", device_type="pc", pos_x=250, pos_y=480),
                    Device(name="PC2", hostname="PC2", device_type="pc", pos_x=550, pos_y=480),
                ]
            )
            db.commit()
            print("[seed] demo devices created (R1, SW1, PC1, PC2)")
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    seed()
