# -*- coding: utf-8 -*-
"""Generates the figures that don't require a live screenshot of the running
app: the two results charts (measured data) and three architecture/flow
diagrams (drawn from the actual implementation described in the thesis)."""
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT = Path(__file__).resolve().parent
plt.rcParams["font.family"] = "DejaVu Sans"

# ---------------------------------------------------------------- Figura 7 --
rows = list(csv.DictReader(open(OUT / "comparison_results.csv", encoding="utf-8")))
sizes = sorted({int(r["departments"]) for r in rows})
manual_t = [float(next(r["time_s"] for r in rows if int(r["departments"]) == s and r["mode"] == "MANUAL")) / 60 for s in sizes]
auto_t = [float(next(r["time_s"] for r in rows if int(r["departments"]) == s and r["mode"] == "AUTO")) / 60 for s in sizes]

fig, ax = plt.subplots(figsize=(7, 4.2))
x = range(len(sizes))
w = 0.35
ax.bar([i - w/2 for i in x], manual_t, width=w, label="Manual", color="#c0392b")
ax.bar([i + w/2 for i in x], auto_t, width=w, label="Automatik", color="#2471a3")
ax.set_xticks(list(x))
ax.set_xticklabels([f"{s} departamente" for s in sizes])
ax.set_ylabel("Koha e konfigurimit (minuta)")
ax.set_title("Koha e konfigurimit sipas madhësisë së topologjisë")
for i, v in enumerate(manual_t):
    ax.text(i - w/2, v + 0.3, f"{v:.1f}", ha="center", fontsize=9)
for i, v in enumerate(auto_t):
    ax.text(i + w/2, v + 0.3, f"{v:.1f}", ha="center", fontsize=9)
ax.legend()
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(OUT / "figura7_koha_konfigurimit.png", dpi=200)
plt.close(fig)

# ---------------------------------------------------------------- Figura 8 --
err_rows = list(csv.DictReader(open(OUT / "error_breakdown.csv", encoding="utf-8")))
cats = [r["kategoria"] for r in err_rows if r["kategoria"] != "Gjithsej"]
manual_e = [float(r["manual"]) for r in err_rows if r["kategoria"] != "Gjithsej"]
auto_e = [float(r["automatik"]) for r in err_rows if r["kategoria"] != "Gjithsej"]

fig, ax = plt.subplots(figsize=(8, 4.6))
y = range(len(cats))
h = 0.35
ax.barh([i + h/2 for i in y], manual_e, height=h, label="Manual", color="#c0392b")
ax.barh([i - h/2 for i in y], auto_e, height=h, label="Automatik", color="#2471a3")
ax.set_yticks(list(y))
ax.set_yticklabels(cats)
ax.set_xlabel("Numri i gabimeve (mesatarja mbi 30 prova, 4 madhësi topologjie)")
ax.set_title("Numri i gabimeve: manual kundrejt automatik")
for i, v in enumerate(manual_e):
    ax.text(v + 0.15, i + h/2, f"{v:.1f}", va="center", fontsize=9)
for i, v in enumerate(auto_e):
    ax.text(v + 0.15, i - h/2, f"{v:.1f}" if v else "0", va="center", fontsize=9)
ax.legend()
ax.invert_yaxis()
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(OUT / "figura8_gabimet.png", dpi=200)
plt.close(fig)


def box(ax, xy, w, h, text, fc="#eaf2f8", ec="#2471a3", fontsize=9.5):
    b = FancyBboxPatch(xy, w, h, boxstyle="round,pad=0.02,rounding_size=0.06",
                        linewidth=1.4, edgecolor=ec, facecolor=fc)
    ax.add_patch(b)
    ax.text(xy[0] + w/2, xy[1] + h/2, text, ha="center", va="center",
            fontsize=fontsize, wrap=True)


def arrow(ax, p1, p2, text=None, style="-|>"):
    a = FancyArrowPatch(p1, p2, arrowstyle=style, mutation_scale=14,
                         linewidth=1.3, color="#333333")
    ax.add_patch(a)
    if text:
        mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
        ax.text(mx, my + 0.15, text, ha="center", fontsize=8, color="#333333")


# ---------------------------------------------------------------- Figura 1 --
fig, ax = plt.subplots(figsize=(8, 5))
ax.set_xlim(0, 10); ax.set_ylim(0, 8); ax.axis("off")
box(ax, (0.5, 6), 9, 1.4, "Ndërfaqja (React 18 + Vite + React Flow)\nkanavaca e topologjisë · formularët · dashboard-i", fc="#eafaf1", ec="#1e8449")
box(ax, (0.5, 3.4), 9, 1.4, "Serveri (Python 3.11 + FastAPI + Pydantic v2)\nroutera → shërbime → SQLAlchemy 2 → SQLite", fc="#eaf2f8", ec="#2471a3")
box(ax, (0.5, 0.4), 9, 1.4, "Automatizimi\nJinja2 → Cisco IOS  ·  Netmiko (SSH)  ·  Ansible (inventar + playbook)", fc="#fdedec", ec="#c0392b")
arrow(ax, (5, 6), (5, 4.8), "HTTP/REST + JWT")
arrow(ax, (5, 3.4), (5, 1.8), "gjenerim + dërgim")
fig.tight_layout()
fig.savefig(OUT / "figura1_arkitektura.png", dpi=200)
plt.close(fig)

# ---------------------------------------------------------------- Figura 2 --
fig, ax = plt.subplots(figsize=(9, 5.4))
ax.set_xlim(0, 12); ax.set_ylim(0, 8); ax.axis("off")
tables = [
    ("users", (0.3, 6.2)), ("devices", (4.5, 6.2)), ("connections", (8.7, 6.2)),
    ("vlans", (0.3, 3.4)), ("interfaces", (4.5, 3.4)), ("routing", (8.7, 3.4)),
    ("logs", (4.5, 0.6)),
]
for name, (x, y) in tables:
    box(ax, (x, y), 3, 1.2, name, fc="#eaf2f8", ec="#2471a3", fontsize=10)
arrow(ax, (6, 6.2), (6, 4.6))       # devices -> interfaces
arrow(ax, (5, 6.2), (2, 4.6))       # devices -> vlans
arrow(ax, (7.5, 6.2), (9.5, 4.6))   # devices -> routing
arrow(ax, (6, 3.4), (6, 1.8))       # interfaces -> logs
arrow(ax, (10, 6.2), (10.5, 6.2))
fig.tight_layout()
fig.savefig(OUT / "figura2_skema_db.png", dpi=200)
plt.close(fig)

# ---------------------------------------------------------------- Figura 4 --
fig, ax = plt.subplots(figsize=(9, 3.2))
ax.set_xlim(0, 12); ax.set_ylim(0, 2.4); ax.axis("off")
steps = [
    "1. Leximi i grafit\n(connections)",
    "2. Caktimi i adresimit\n(subnete, VLAN, DHCP)",
    "3. Gjenerimi\n(Jinja2 → Cisco IOS)",
    "4. Ruajtja & dërgimi\n(DB, Ansible, Netmiko)",
]
xs = [0.3, 3.3, 6.3, 9.3]
for x, s in zip(xs, steps):
    box(ax, (x, 0.6), 2.6, 1.2, s, fc="#eaf2f8", ec="#2471a3", fontsize=9)
for i in range(3):
    arrow(ax, (xs[i] + 2.6, 1.2), (xs[i+1], 1.2))
fig.tight_layout()
fig.savefig(OUT / "figura4_flow.png", dpi=200)
plt.close(fig)

print("Wrote figures in", OUT)
