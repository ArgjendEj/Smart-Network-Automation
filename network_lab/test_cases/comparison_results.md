# Manual vs. Automatic Configuration — Results

| Departments | Mode | Time (s) | Admin inputs | CLI lines | Errors |
|---|---|---|---|---|---|
| 2 | AUTO | 42.02 | 6 | 82 | 0 |
| 2 | MANUAL | 508.0 | 82 | 82 | 3.03 |
| 4 | AUTO | 70.0 | 10 | 116 | 0 |
| 4 | MANUAL | 824.0 | 116 | 116 | 3.77 |
| 6 | AUTO | 98.0 | 14 | 150 | 0 |
| 6 | MANUAL | 1140.0 | 150 | 150 | 5.7 |
| 8 | AUTO | 126.0 | 18 | 184 | 0 |
| 8 | MANUAL | 1456.0 | 184 | 184 | 6.37 |

## Model parameters (manual)
- Seconds per CLI line: 4.0
- Seconds of VLSM math per department: 90.0
- Human error rate per line: 0.03
- Monte-Carlo trials: 30

AUTO time is measured directly from the platform's Smart Auto Configuration pipeline (subnet plan + Jinja2 config generation).