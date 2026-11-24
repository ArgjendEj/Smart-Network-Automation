"""A new installation: which network does it start with? Each case runs in its
own process and database, so the other tests keep their small demo network."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
SCRIPT = """
import json
from fastapi.testclient import TestClient
from main import app
def start():
    with TestClient(app) as c:
        r = c.post("/api/auth/login", data={"username": "admin", "password": "admin123"})
        h = {"Authorization": "Bearer " + r.json()["access_token"]}
        devices = c.get("/api/devices", headers=h).json()
        out = {"names": [d["name"] for d in devices], "cables": len(c.get("/api/topology", headers=h).json()["edges"]),
               "ssh": [d["name"] for d in devices if d.get("ssh_username") or d.get("ssh_password") or d.get("ssh_secret")]}
        ids = {d["name"]: d["id"] for d in devices}
        if "PC1.1" in ids:
            out["packet"] = c.post("/api/monitoring/packet", headers=h, json={
                "source_device_id": ids["PC3"], "target_device_id": ids["PC1.1"]}).json()["path"]
            out["auto"] = sorted(x["device"] for x in c.post(
                "/api/smart-config/auto", headers=h, json={"routing": "both", "nat": True}).json()["results"])
            if "PC4" in ids:
                c.delete(f"/api/devices/{ids['PC4']}", headers=h)
        return out
print("RESULT" + json.dumps([start(), start()]))
"""


@pytest.mark.parametrize("mode", ["example", "small", "none"])
def test_new_database(mode, tmp_path):
    env = {**os.environ, "DEMO_NETWORK": mode, "PYTHONIOENCODING": "utf-8",
           "DATABASE_URL": f"sqlite:///{(tmp_path / 'new folder' / 'n.db').as_posix()}"}
    run = subprocess.run([sys.executable, "-c", SCRIPT], cwd=BACKEND, env=env, capture_output=True, text=True,
                         encoding="utf-8", timeout=120)
    assert run.returncode == 0, run.stderr
    first, again = json.loads(run.stdout.split("RESULT")[1])
    if mode == "example":
        assert len(first["names"]) == 22 and first["cables"] == 22 and first["ssh"] == []
        assert first["packet"] == ["PC3", "Switch2", "Router1", "Router2", "Switch1.1", "PC1.1"]
        assert first["auto"] == ["R1", "R2", "SW1", "SW1.1", "SW2", "SW2.2"]
        # the second start must not bring a deleted device back
        assert len(again["names"]) == 21 and "PC4" not in again["names"]
    else:
        assert first["names"] == again["names"] == (["R1", "SW1", "PC1", "PC2"] if mode == "small" else [])
