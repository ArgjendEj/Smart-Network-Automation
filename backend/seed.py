"""Seed the database with the default admin user (and optional demo devices)."""
from __future__ import annotations

from auth_utils import hash_password
from config import settings
from database import SessionLocal, init_db
from models import Device, User


def seed(with_demo: bool = True) -> None:
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
