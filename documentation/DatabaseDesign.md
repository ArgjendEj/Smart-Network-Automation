# Database Design — MVP (7 tables)

SQLite + SQLAlchemy. Full schema in [`backend/models.py`](../backend/models.py).

| Table | Purpose |
|---|---|
| `users` | Admin accounts (single role in MVP). Password stored as PBKDF2-SHA256 hash. |
| `devices` | Router / Switch / PC. Management IP + SSH credentials + canvas position + runtime status + last generated config. |
| `connections` | Physical links between two devices (endpoint interfaces, access/trunk). |
| `vlans` | VLAN per device: id, name, department, subnet (CIDR), gateway. |
| `interfaces` | Interface per device: IP/mask, mode (access/trunk/routed), access VLAN, description, admin state. |
| `routing` | Routing config per device — MVP: OSPF (process id, area, network statements as JSON). Static-route columns available. |
| `logs` | Configuration / error / deploy / auth / system events; optional `device_id`. |

## Relationships

```
users            (standalone)

devices 1───* interfaces
devices 1───* vlans
devices 1───* routing
devices 1───* connections   (as endpoint A or B)
devices 1───* logs          (nullable, ON DELETE SET NULL)
```

- `interfaces`, `vlans`, `routing`, `connections` → `devices.id` **ON DELETE CASCADE**
- `logs.device_id` → `devices.id` **ON DELETE SET NULL**
- Unique constraints: `users.username`, `(vlans.device_id, vlan_id)`, `(interfaces.device_id, name)`, `(connections.a_device_id, a_interface)`

## Out of MVP (section 21.3)

`DHCP`, `ACL`, `NAT`, `Deployments`, `Backups` tables — future work. DHCP in the MVP
is generated into the device config and reflected by VLAN gateway data, but not
stored in a dedicated table.
