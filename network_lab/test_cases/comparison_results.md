# Manual vs. Automatic Configuration — Results

| Departments | Mode | Time (s) | Admin inputs | CLI lines | Errors |
|---|---|---|---|---|---|
| 2 | AUTO | 42.01 | 6 | 49 | 0 |
| 2 | MANUAL | 376.0 | 49 | 49 | 1.97 |
| 4 | AUTO | 70.0 | 10 | 79 | 0 |
| 4 | MANUAL | 676.0 | 79 | 79 | 2.6 |
| 6 | AUTO | 98.0 | 14 | 109 | 0 |
| 6 | MANUAL | 976.0 | 109 | 109 | 4.3 |
| 8 | AUTO | 126.0 | 18 | 139 | 0 |
| 8 | MANUAL | 1276.0 | 139 | 139 | 5.23 |

## Model parameters (manual)
- Seconds per CLI line: 4.0
- Seconds of VLSM math per department: 90.0
- Human error rate per line: 0.03
- Monte-Carlo trials: 30

AUTO time is measured directly from the platform's Smart Auto Configuration pipeline (subnet plan + Jinja2 config generation).