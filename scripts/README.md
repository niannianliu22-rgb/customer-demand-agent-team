# Scripts — 说明

本目录用于存放后续实现阶段的确定性数据处理脚本（如 Schema 探查、标准化、去重、日期转换、统计计算、预测计算等）。

当前已落地的确定性脚本仅限于已验证的 Intake / Schema Mapping 工具，以及发布机制的**非发布框架** `data/publish_dataset.py`。该框架只校验发布路由（stable / candidate / 禁止发布）并输出计划路径；在 Data Standardization、Data Quality、Data Gate 均未完成前，或未由后续实现显式启用时，它不得创建任何 processed 数据产品。
