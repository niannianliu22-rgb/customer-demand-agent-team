# Synthetic Demo Input

All six workbooks in this directory are synthetic, de-identified delivery fixtures. They do not contain real customer names, order identifiers, notes, follow-up feedback, revenue, schools, or courses.

Files mirror the six expected department/year inputs:

- `2023年8月学管部咨询数据.xlsx`
- `2023年8月顾问部咨询数据.xlsx`
- `2024年8月学管部咨询数据.xlsx`
- `2024年8月顾问部咨询数据.xlsx`
- `2025年8月学管部咨询数据.xlsx`
- `2025年8月顾问部咨询数据.xlsx`

Each has 12 synthetic rows and preserves the department-specific header schema used by the intake pipeline. Use it with:

```sh
python3 scripts/run_customer_demand_analysis.py --target-month 2026-09 --source-input-dir examples/input --initialize-only
```

The fixtures are intended for portability and initialization smoke tests. A full production analysis requires authorized, run-bound business input and authenticated provider CLIs.
