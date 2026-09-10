# Test cases

## Automated
- `backend/tests/` — pytest: subnet calculator, config generator, API (auth, devices,
  topology, smart-config, manual-config).
- `tests/compare_manual_vs_auto.py` — thesis experiment; writes `comparison_results.csv`
  and `comparison_results.md` into this folder.

## Manual lab checklist (GNS3 / Packet Tracer)

| # | Case | Expected |
|---|---|---|
| 1 | Add R1, SW1, PC1 in Devices; set R1/SW1 mgmt IP + SSH | devices listed, status = offline until reachable |
| 2 | Topology: link R1↔SW1 (trunk), SW1↔PC1 (access) | edges drawn, persisted after reload |
| 3 | Device → Ping | status flips to online when SSH:22 reachable |
| 4 | Manual Config: hostname + Gi0/1 access vlan 10 on SW1, deploy | config on SW1, `show run` matches |
| 5 | Smart Auto Config: R1 + SW1, depts Sales=100 / IT=20, deploy | sub-interfaces, DHCP pools, OSPF on R1; VLANs + trunk on SW1 |
| 6 | PC1 set to DHCP | receives address from the Sales pool, can ping gateway |
| 7 | Dashboard | device/VLAN counts + deploy history updated |
| 8 | Logs | config + deploy entries present; failed deploy → error entry |
| 9 | Run `compare_manual_vs_auto.py` | AUTO ~9x faster, ~0 errors vs manual |
