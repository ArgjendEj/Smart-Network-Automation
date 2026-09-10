"""Thin wrapper that runs `ansible-playbook` when it is available on the host.

On Windows Ansible is not supported natively; in that case the platform relies on
the Netmiko deployment path (services/deployment_service.py) and this module only
reports that ansible is unavailable. The generated playbooks/inventories remain
valid and can be run from Linux/WSL.
"""
from __future__ import annotations

import shutil
import subprocess


def ansible_available() -> bool:
    return shutil.which("ansible-playbook") is not None


def run_playbook(playbook_path: str, inventory_path: str) -> tuple[bool, str]:
    if not ansible_available():
        return False, "ansible-playbook not found on host (use the Netmiko deploy path)."
    try:
        proc = subprocess.run(
            ["ansible-playbook", "-i", inventory_path, playbook_path],
            capture_output=True,
            text=True,
            timeout=300,
        )
        return proc.returncode == 0, proc.stdout + proc.stderr
    except subprocess.TimeoutExpired:
        return False, "ansible-playbook timed out after 300s."
