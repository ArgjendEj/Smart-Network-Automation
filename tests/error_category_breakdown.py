"""Thesis experiment (section 6.4 / Tabela 10): categorized error breakdown,
manual vs. automatic, across the same four topology sizes used by
compare_manual_vs_auto.py.

This extends the base model (typing errors + VLSM slips) with two more
manual-only error categories that are procedurally identical in spirit:
independent per-block draws with a documented, fixed probability. AUTO is
always 0 in every category, because the configuration is produced by
validated Jinja2 templates (see backend/tests/, 32 automated tests) rather
than typed by hand.

Run:  python tests/error_category_breakdown.py
Output: console table + network_lab/test_cases/error_breakdown.csv
"""
from __future__ import annotations

import csv
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from services.config_generator import generate_router_config, generate_switch_config  # noqa: E402
from services.subnet_calculator import plan_departments  # noqa: E402

# same constants as compare_manual_vs_auto.py
HUMAN_ERROR_RATE_PER_LINE = 0.03   # typo / wrong keyword on a typed CLI line
SUBNET_SLIP_RATE = 0.15            # VLSM math mistake, per department
VLAN_MISMATCH_RATE = 0.08          # switch VLAN id typed differently than the router's, per department
FORGOTTEN_PARAM_RATE = 0.05        # a required line omitted (no shutdown / dns-server / description), per block
# Even in the automated path, the administrator MAY still hand-type one
# override value per department -- a pre-existing management IP that the
# algorithm is told to keep unchanged instead of generating (section 5.4).
# That single manual value is the one residual place a human can still make
# an addressing mistake (typing an address that collides with a segment the
# algorithm assumed was free); everything else in that department's config is
# template-generated. Modeled as a per-department Bernoulli draw at a rate
# far below the manual rate above, since it requires the override itself
# (rare) AND a collision with another segment (also rare).
AUTO_OVERRIDE_COLLISION_RATE = 0.004
TRIALS = 30

DEPT_NAMES = ["Sales", "IT", "HR", "Finance", "Support", "RnD", "Marketing", "Ops"]
USERS_CHOICES = [10, 20, 30, 50, 100, 200]
SCENARIOS = [2, 4, 6, 8]

CATEGORIES = [
    "Gabime sintaksore",
    "Gabime në llogaritjen e subnetit",
    "Mospërputhje e identifikuesit të VLAN-it",
    "Parametra të harruar",
]


def build_departments(n: int, seed: int = 42):
    rng = random.Random(seed)
    return [(DEPT_NAMES[i], rng.choice(USERS_CHOICES)) for i in range(n)]


def manual_categorized(departments):
    plan = plan_departments(departments)
    router_cfg = generate_router_config("R1", plan, uplink="GigabitEthernet0/0")
    switch_cfg = generate_switch_config("SW1", plan, uplink="GigabitEthernet0/1")
    cli_lines = len(router_cfg.splitlines()) + len(switch_cfg.splitlines())
    n_dept = len(departments)

    totals = {c: 0.0 for c in CATEGORIES}
    for _ in range(TRIALS):
        totals["Gabime sintaksore"] += sum(
            1 for _ in range(cli_lines) if random.random() < HUMAN_ERROR_RATE_PER_LINE
        )
        totals["Gabime në llogaritjen e subnetit"] += sum(
            1 for _ in range(n_dept) if random.random() < SUBNET_SLIP_RATE
        )
        totals["Mospërputhje e identifikuesit të VLAN-it"] += sum(
            1 for _ in range(n_dept) if random.random() < VLAN_MISMATCH_RATE
        )
        totals["Parametra të harruar"] += sum(
            1 for _ in range(n_dept) if random.random() < FORGOTTEN_PARAM_RATE
        )
    return {c: v / TRIALS for c, v in totals.items()}


_auto_rng = random.Random(2024)  # separate stream: doesn't perturb the manual draws above


def auto_categorized(departments):
    """The automated path is template-generated end to end, EXCEPT for the
    one optional hand-typed override IP per department (section 5.4). That
    single residual manual value can, rarely, collide with another segment
    -- the only way an "automated" run still carries a subnet-addressing
    error."""
    n_dept = len(departments)
    total = 0.0
    for _ in range(TRIALS):
        total += sum(1 for _ in range(n_dept) if _auto_rng.random() < AUTO_OVERRIDE_COLLISION_RATE)
    auto = {c: 0.0 for c in CATEGORIES}
    auto["Gabime në llogaritjen e subnetit"] = total / TRIALS
    return auto


def main():
    random.seed(11)
    grand_manual = {c: 0.0 for c in CATEGORIES}
    grand_auto = {c: 0.0 for c in CATEGORIES}

    print(f"\n{'Depts':>6} | " + " | ".join(f"{c[:18]:>18}" for c in CATEGORIES))
    print("-" * 100)
    for n in SCENARIOS:
        depts = build_departments(n)
        row = manual_categorized(depts)
        auto_row = auto_categorized(depts)
        for c in CATEGORIES:
            grand_manual[c] += row[c]
            grand_auto[c] += auto_row[c]
        print(f"{n:>6} | " + " | ".join(f"{row[c]:>18.2f}" for c in CATEGORIES))

    print("-" * 100)
    print("Gjithsej (4 skenarë, MANUAL): " +
          ", ".join(f"{c}={grand_manual[c]:.1f}" for c in CATEGORIES))
    print("Gjithsej (4 skenarë, AUTOMATIK): " +
          ", ".join(f"{c}={grand_auto[c]:.1f}" for c in CATEGORIES))

    out_dir = ROOT / "network_lab" / "test_cases"
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "error_breakdown.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["kategoria", "manual", "automatik"])
        for c in CATEGORIES:
            w.writerow([c, round(grand_manual[c], 1), round(grand_auto[c], 1)])
        w.writerow(["Gjithsej", round(sum(grand_manual.values()), 1), round(sum(grand_auto.values()), 1)])
    print(f"\nWrote {out_dir/'error_breakdown.csv'}")


if __name__ == "__main__":
    main()
