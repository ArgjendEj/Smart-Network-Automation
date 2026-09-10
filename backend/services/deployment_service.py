"""Push generated configuration to real devices over SSH (Netmiko).

Also writes an Ansible inventory + playbook for every deploy so the thesis can
demonstrate the Ansible workflow (`backend/automation/`).
"""
from __future__ import annotations

import socket
from datetime import datetime, timezone
from pathlib import Path

import yaml

from config import settings
from services.config_generator import config_to_commands

AUTOMATION_DIR = Path(__file__).resolve().parent.parent / "automation"
GENERATED_DIR = AUTOMATION_DIR / "generated"
GENERATED_DIR.mkdir(exist_ok=True)


class DeployError(RuntimeError):
    pass


# --------------------------------------------------------------------------- #
# Reachability
# --------------------------------------------------------------------------- #
def tcp_ping(host: str, port: int = 22, timeout: float = 2.0) -> bool:
    if not host:
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


# --------------------------------------------------------------------------- #
# Netmiko push
# --------------------------------------------------------------------------- #
def _connect(device):
    from netmiko import ConnectHandler  # imported lazily so tests don't need it

    if not device.mgmt_ip:
        raise DeployError(f"Device '{device.name}' has no management IP.")
    params = {
        "device_type": device.netmiko_driver or "cisco_ios",
        "host": device.mgmt_ip,
        "username": device.ssh_username or "",
        "password": device.ssh_password or "",
        "secret": device.ssh_secret or device.ssh_password or "",
        "timeout": settings.ssh_timeout,
        "fast_cli": False,
    }
    return ConnectHandler(**params)


def push_config(device, config: str) -> str:
    """Send config to the device, save it, return the session log."""
    if settings.deploy_dry_run:
        return "[dry-run] configuration NOT sent (DEPLOY_DRY_RUN=true)"

    commands = config_to_commands(config)
    if not commands:
        raise DeployError("Empty configuration.")

    conn = _connect(device)
    try:
        if device.ssh_secret:
            conn.enable()
        output = conn.send_config_set(commands, read_timeout=60)
        output += "\n" + conn.save_config()
    finally:
        conn.disconnect()
    return output


# --------------------------------------------------------------------------- #
# Ansible artifacts (generated, and runnable where ansible is installed)
# --------------------------------------------------------------------------- #
def write_ansible_artifacts(device, config: str, tag: str) -> dict[str, str]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    safe = f"{device.hostname}-{tag}-{stamp}"

    cfg_path = GENERATED_DIR / f"{safe}.cfg"
    cfg_path.write_text(config, encoding="utf-8")

    inv = {
        "all": {
            "hosts": {
                device.hostname: {
                    "ansible_host": device.mgmt_ip,
                    "ansible_user": device.ssh_username,
                    "ansible_password": device.ssh_password,
                    "ansible_connection": "network_cli",
                    "ansible_network_os": "ios",
                    "ansible_become": True,
                    "ansible_become_method": "enable",
                    "ansible_become_password": device.ssh_secret or device.ssh_password,
                }
            }
        }
    }
    inv_path = GENERATED_DIR / f"{safe}.inventory.yml"
    inv_path.write_text(yaml.safe_dump(inv, sort_keys=False), encoding="utf-8")

    playbook = [
        {
            "name": f"Apply {tag} configuration to {device.hostname}",
            "hosts": device.hostname,
            "gather_facts": False,
            "tasks": [
                {
                    "name": "Push configuration lines",
                    "cisco.ios.ios_config": {
                        "src": str(cfg_path.name),
                        "save_when": "modified",
                    },
                }
            ],
        }
    ]
    pb_path = GENERATED_DIR / f"{safe}.playbook.yml"
    pb_path.write_text(yaml.safe_dump(playbook, sort_keys=False), encoding="utf-8")

    return {
        "config": str(cfg_path),
        "inventory": str(inv_path),
        "playbook": str(pb_path),
    }
