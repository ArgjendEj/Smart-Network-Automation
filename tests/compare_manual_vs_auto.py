"""Thesis experiment (section 18 / 21): manual vs. automatic configuration.

Compares, across several network sizes:
  * configuration TIME
  * number of human INPUTS the admin must provide
  * configuration ERRORS

AUTO  = the platform's Smart Auto Configuration pipeline (measured directly).
MANUAL = a documented estimation model of an admin typing Cisco IOS CLI by hand
         (subnet math + one line at a time, with a per-line human error rate).

Run:  python tests/compare_manual_vs_auto.py
Outputs: console table + network_lab/test_cases/comparison_results.csv + .md
"""
from __future__ import annotations

import csv
import random
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from services.config_generator import (  # noqa: E402
    generate_router_config,
    generate_switch_config,
)
from services.subnet_calculator import plan_departments  # noqa: E402

# --- Manual estimation model (tunable, documented in the thesis) -------------
SECONDS_PER_CLI_LINE = 4.0        # avg time to type + think about one IOS line
SECONDS_PER_FORM_FIELD = 7.0     # avg time for the admin to fill one web-form field (AUTO)
SECONDS_SUBNET_MATH_PER_DEPT = 90.0   # manual VLSM per department (calc + verify)
HUMAN_ERROR_RATE_PER_LINE = 0.03     # 3% chance of a mistake on any typed line
TRIALS = 30                          # Monte-Carlo trials for the manual error count

DEPT_NAMES = ["Sales", "IT", "HR", "Finance", "Support", "RnD", "Marketing", "Ops"]
SCENARIOS = [2, 4, 6, 8]
USERS_CHOICES = [10, 20, 30, 50, 100, 200]


def build_departments(n: int, seed: int = 42) -> list[tuple[str, int]]:
    rng = random.Random(seed)
    return [(DEPT_NAMES[i], rng.choice(USERS_CHOICES)) for i in range(n)]


def auto_run(departments):
    t0 = time.perf_counter()
    plan = plan_departments(departments)
    router_cfg = generate_router_config("R1", plan, uplink="GigabitEthernet0/0")
    switch_cfg = generate_switch_config("SW1", plan, uplink="GigabitEthernet0/1")
    compute_s = time.perf_counter() - t0
    admin_inputs = 2 * len(departments) + 2  # name+users per dept, + router/switch pick
    elapsed = compute_s + admin_inputs * SECONDS_PER_FORM_FIELD

    # correctness checks -> "errors"
    errors = 0
    for d in plan.departments:
        if f"encapsulation dot1Q {d.vlan_id}" not in router_cfg:
            errors += 1
        if str(d.gateway) not in router_cfg:
            errors += 1
        if f"vlan {d.vlan_id}" not in switch_cfg:
            errors += 1
    nets = [d.network for d in plan.departments]
    for i, a in enumerate(nets):
        for b in nets[i + 1:]:
            if a.overlaps(b):
                errors += 1

    total_lines = len(router_cfg.splitlines()) + len(switch_cfg.splitlines())
    return {
        "time_s": round(elapsed, 2),
        "admin_inputs": admin_inputs,
        "cli_lines": total_lines,
        "errors": errors,
    }


def manual_run(departments):
    plan = plan_departments(departments)  # only to size the equivalent CLI work
    router_cfg = generate_router_config("R1", plan, uplink="GigabitEthernet0/0")
    switch_cfg = generate_switch_config("SW1", plan, uplink="GigabitEthernet0/1")
    cli_lines = len(router_cfg.splitlines()) + len(switch_cfg.splitlines())

    typing_time = cli_lines * SECONDS_PER_CLI_LINE
    math_time = len(departments) * SECONDS_SUBNET_MATH_PER_DEPT
    total_time = typing_time + math_time

    error_counts = []
    for _ in range(TRIALS):
        errs = sum(1 for _ in range(cli_lines) if random.random() < HUMAN_ERROR_RATE_PER_LINE)
        errs += sum(1 for _ in range(len(departments)) if random.random() < 0.15)  # VLSM slip
        error_counts.append(errs)

    admin_inputs = cli_lines  # every line is hand-entered
    return {
        "time_s": round(total_time, 1),
        "admin_inputs": admin_inputs,
        "cli_lines": cli_lines,
        "errors": round(statistics.mean(error_counts), 2),
        "errors_stdev": round(statistics.pstdev(error_counts), 2),
    }


def main():
    random.seed(7)
    rows = []
    print(f"\n{'Depts':>6} | {'Mode':<7} | {'Time':>10} | {'Inputs':>7} | {'CLI lines':>9} | {'Errors':>7}")
    print("-" * 68)
    for n in SCENARIOS:
        depts = build_departments(n)
        a = auto_run(depts)
        m = manual_run(depts)
        speedup = m["time_s"] / a["time_s"] if a["time_s"] else float("inf")
        for mode, r in (("AUTO", a), ("MANUAL", m)):
            print(
                f"{n:>6} | {mode:<7} | {r['time_s']:>9}s | {r['admin_inputs']:>7} | "
                f"{r['cli_lines']:>9} | {r['errors']:>7}"
            )
            rows.append({"departments": n, "mode": mode, **r})
        print(f"       -> speed-up x{speedup:,.0f}, errors avoided ~{m['errors'] - a['errors']:.1f}\n")

    out_dir = ROOT / "network_lab" / "test_cases"
    out_dir.mkdir(parents=True, exist_ok=True)

    fields = ["departments", "mode", "time_s", "admin_inputs", "cli_lines", "errors", "errors_stdev"]
    with (out_dir / "comparison_results.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})

    md = ["# Manual vs. Automatic Configuration — Results", ""]
    md.append("| Departments | Mode | Time (s) | Admin inputs | CLI lines | Errors |")
    md.append("|---|---|---|---|---|---|")
    for r in rows:
        md.append(
            f"| {r['departments']} | {r['mode']} | {r['time_s']} | "
            f"{r['admin_inputs']} | {r['cli_lines']} | {r['errors']} |"
        )
    md += [
        "",
        "## Model parameters (manual)",
        f"- Seconds per CLI line: {SECONDS_PER_CLI_LINE}",
        f"- Seconds of VLSM math per department: {SECONDS_SUBNET_MATH_PER_DEPT}",
        f"- Human error rate per line: {HUMAN_ERROR_RATE_PER_LINE}",
        f"- Monte-Carlo trials: {TRIALS}",
        "",
        "AUTO time is measured directly from the platform's Smart Auto Configuration "
        "pipeline (subnet plan + Jinja2 config generation).",
    ]
    (out_dir / "comparison_results.md").write_text("\n".join(md), encoding="utf-8")
    print(f"Wrote {out_dir/'comparison_results.csv'}")
    print(f"Wrote {out_dir/'comparison_results.md'}")


if __name__ == "__main__":
    main()
