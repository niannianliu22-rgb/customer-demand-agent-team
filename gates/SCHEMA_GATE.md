# SCHEMA GATE

> 位置：Schema Mapping Agent 之后、Data Standardization Agent 之前。Gate 是独立、确定性、可审计的规则模块，不是 Agent；它直接读取真实 Artifact，绝不以 Agent 自述代替证据。唯一合法结果为 `PASS`、`CONDITIONAL`、`REJECT`、`HUMAN_REVIEW_REQUIRED`。Supervisor 只执行本文件规则，无权改判。

## 1. 直接读取的证据

每次正式运行必须至少读取同一 `run_id` 的：

- `runs/{run_id}/artifacts/schema_mapping.json`
- `runs/{run_id}/artifacts/source_manifest.json`
- `runs/{run_id}/artifacts/source_profiles/*.json`（确定性扫描的原始 Excel 字段证据）
- `policies/business_rules.md`（当前 ACTIVE 规则与 Business Rules Version）
- `config/data/standardization_rules.yaml`（机器可读版本，须与 Markdown 版本一致）

Gate 不修改这些文件、不重跑 Data Intake 或 Schema Mapping，也不运行 Data Standardization。原始 Excel 的字段仍存在这一事实，以 Data Intake 对该原始文件产生的 profile 字段及 manifest 中的 `file_path`/`source_id` 为可审计证据；标准化后是否确实未将排除字段写入 `unified_dataset` 由后续 Data Gate 再直接核验。

## 2. 四态 Mapping 协议

每个 `RECEIVED` source profile 中的原始字段必须在 `schema_mapping.json.items` 中恰好有一条、且仅有以下状态之一：

| Mapping 状态 | Gate 验收口径 |
|---|---|
| `CONFIRMED` | `canonical_field` 非空，并存在可验证映射依据。`manual_business_confirmation` 是有效的确认依据，与结构证据确认具有同等 `CONFIRMED` 效力。 |
| `REVIEW_REQUIRED` | 必须有具体原因与候选口径。核心字段出现该状态不得 `PASS`；现有 ACTIVE Business Rules 不能解决时命中 `HUMAN_REVIEW_REQUIRED`，Supervisor 不得自行放行。 |
| `UNMAPPED` | 必须有具体原因。核心分析字段出现时一律 `REJECT`；非核心字段只可按 SG-C1 或 SG-R6 预定义规则处理。 |
| `EXCLUDED_BY_BUSINESS_RULE` | 不是映射失败，也不计为核心字段缺失；仅在本文件第 4 节全部验收条件满足时合法。 |

### 映射依据（`mapping_basis`）

每个 item 必须有可核验的映射依据。新版本 Mapping Artifact 应直接写入 `mapping_basis`，取值为 `manual_business_confirmation` 或 `structural_evidence`，并保持 `evidence_refs`。为保持既有、不可改写的 Mapping v1 可审核，本 Gate 将包含有效 `evidence_refs.type = manual_business_confirmation` 的项归一为 `mapping_basis = manual_business_confirmation`，将包含 `source_profile_field` 的项归一为 `mapping_basis = structural_evidence`；两者均不存在即为 SG-R7。该兼容解释不改变任何既有业务映射。

## 3. 必检项目

1. `source_manifest.json` 的 `expected_source_count`、`received_source_count`、`sources` 长度和 source 状态完整一致；
2. 对每个 `RECEIVED` source，profile 原始字段与 Mapping item 一一对应，且当前 run 共 74 个原始字段均有状态；
3. `status_counts` 与从真实 `items` 重新统计的四态计数一致（四种状态均按 0 补齐后比较，避免“未出现的状态”因省略零值而产生伪差异）；
4. 分别列出 `REVIEW_REQUIRED`、`UNMAPPED` 的数量及条目；
5. 分别列出所有 `EXCLUDED_BY_BUSINESS_RULE` 条目并执行第 4 节检查；
6. 核心分析字段均为 `CONFIRMED`、无互相矛盾的 canonical 定义；
7. 每条 `CONFIRMED` 与合法 `EXCLUDED_BY_BUSINESS_RULE` 均有 `mapping_basis`；
8. 所有 `RECEIVED` 数据源覆盖完整，目标月份三年同期来源覆盖按 manifest 直接核验；
9. Mapping inputs 中引用的 Business Rules Version 与当前 `business_rules.md` / YAML 的版本一致；
10. Artifact 信封与 `run_id` 一致。

本 Gate 固定将 `consultation_date`、`task_type`、`channel`、`order_id`、`amount`、`order_status` 视为核心分析字段（在对应 source 有该字段时）；`department` 是每条记录必须从 manifest 继承的核心溯源维度。除非人工更新本文件，Gate 不得临时扩缩核心字段范围。

## 4. `EXCLUDED_BY_BUSINESS_RULE` 合法性

每个排除项必须同时满足以下条件，否则命中 SG-R5：

1. `status = EXCLUDED_BY_BUSINESS_RULE` 且 `canonical_field = null`；
2. item 带 `source_id`，该 source 在 manifest 中存在、为 `RECEIVED`，且可回指 profile；
3. `evidence_refs` 或 `mapping_basis` 中引用具体 `rule_id`；
4. 该 `rule_id` 在当前 `business_rules.md` 中为 `ACTIVE`，并明确规定该原始字段排除；
5. profile 仍含该原始字段，证明它仍存在于由原始 Excel 生成的结构证据中；
6. Mapping 仅将字段排除出未来 `unified_dataset`，不删除或修改原始 Excel。此阶段以 manifest/profile 与 Mapping 的排除声明核验；实际统一数据集的无残留检查属于 Data Gate。

当前 RULE-011 下的「跟进反馈」「客户备注」「未成交原因」在满足以上条件时均为合法排除。

## 5. Decision Rule Table

| Rule ID | 触发条件 | Gate 结果 | 下游权限 / 风险标记 |
|---|---|---|---|
| SG-P1 | 所有必检项目通过；全部字段为 `CONFIRMED` 或合法 `EXCLUDED_BY_BUSINESS_RULE`；`REVIEW_REQUIRED=0`、`UNMAPPED=0`；核心字段全部 `CONFIRMED`；所有来源完整 | `PASS` | Data Standardization Agent 可 `READY`；无风险标记 |
| SG-C1 | 核心字段均 `CONFIRMED`；仅非核心字段 `UNMAPPED`，每项有原因、source 影响范围明确，且不影响目标月份三年同期分析输入 | `CONDITIONAL` | 可 `READY`；`risk_flag: SCHEMA_NONCORE_UNMAPPED`，透传字段与 source 清单 |
| SG-C2 | 核心字段均 `CONFIRMED`；仅非核心字段 `REVIEW_REQUIRED`，每项有原因和人工待确认问题，且不影响目标月份三年同期分析输入 | `CONDITIONAL` | 可 `READY`；`risk_flag: SCHEMA_NONCORE_REVIEW_REQUIRED`，透传字段、source 与待确认问题 |
| SG-C3 | 存在命名变体但均已 `CONFIRMED`，并有结构证据或 ACTIVE Rule 支持同一 canonical 字段 | `CONDITIONAL` | 可 `READY`；`risk_flag: SCHEMA_NAMING_VARIANT_MERGED`，透传依据 |
| SG-C4 | 非目标月份范围外的数据源缺失/不可读，但所有已接收来源的核心字段 `CONFIRMED`，且不触及本次三年同期来源 | `CONDITIONAL` | 可 `READY`；`risk_flag: SCHEMA_SOURCE_MISSING_NONCRITICAL` |
| SG-R1 | manifest/source/profile 数量、run_id、信封或列一一覆盖不一致 | `REJECT` | 无；回退 Data Intake 或 Schema Mapping |
| SG-R2 | 核心字段为 `UNMAPPED`、`REVIEW_REQUIRED` 或存在矛盾 canonical 定义 | `REJECT`；若仅因 ACTIVE Rule 未覆盖而无法确定，则 SG-H1 优先 | 无；回退 Schema Mapping 或人工 |
| SG-R3 | 目标月份三年同期来源缺失、不可读或其核心字段不合格 | `REJECT` | 无；回退 Data Intake / Schema Mapping |
| SG-R4 | `status_counts` 与真实 items 不一致，存在无状态/未知状态 item，或 `REVIEW_REQUIRED`/`UNMAPPED` 未附原因 | `REJECT` | 无；回退 Schema Mapping |
| SG-R5 | 任一 `EXCLUDED_BY_BUSINESS_RULE` 未满足第 4 节全部条件 | `REJECT` | 无；回退 Schema Mapping |
| SG-R6 | 非核心 `UNMAPPED` 影响目标月份三年同期输入、无范围说明或不符合 SG-C1 | `REJECT` | 无；回退 Schema Mapping |
| SG-R7 | CONFIRMED/排除 item 缺少可验证 `mapping_basis` 或 Business Rules Version 与 Artifact inputs 不一致 | `REJECT` | 无；回退 Schema Mapping / 人工规则层核对 |
| SG-H1 | 核心字段为 `REVIEW_REQUIRED`，且现有 ACTIVE Business Rules 无法解决其业务口径 | `HUMAN_REVIEW_REQUIRED` | Data Standardization 保持 `BLOCKED`；等待人工规则或判断 |
| SG-H2 | 情形不被以上规则明确覆盖 | `HUMAN_REVIEW_REQUIRED` | Data Standardization 保持 `BLOCKED`；Supervisor 不得归类放行 |

## 6. Never-Conditional

- 核心字段 `UNMAPPED`、`REVIEW_REQUIRED` 或矛盾；
- 非法 `EXCLUDED_BY_BUSINESS_RULE`；
- 列覆盖、计数、run_id、映射依据或规则版本不一致；
- 目标月份三年同期来源缺失、不可读或其核心字段不合格。

## 7. 正式结果 Artifact

正式运行时只向 `runs/{run_id}/artifacts/schema_gate_result.json` 写入结果，至少为：

```json
{
  "run_id": "RUN-...",
  "gate_name": "SCHEMA_GATE",
  "gate_status": "PASS | CONDITIONAL | REJECT | HUMAN_REVIEW_REQUIRED",
  "checked_at": "ISO-8601 timestamp",
  "artifacts_checked": [],
  "business_rules_version": "2.0",
  "status_counts": {"CONFIRMED": 0, "REVIEW_REQUIRED": 0, "UNMAPPED": 0, "EXCLUDED_BY_BUSINESS_RULE": 0},
  "core_field_results": [],
  "excluded_field_results": [],
  "failed_rules": [],
  "conditional_rules": [],
  "blocking_issues": [],
  "downstream_permission": {"data_standardization": "READY | BLOCKED", "risk_flags": []},
  "evidence_refs": []
}
```

## 8. 下游影响

- `PASS`：Data Standardization Agent 可 `READY`。
- `CONDITIONAL`：仅命中 SG-C1～SG-C4 时可 `READY`，且必须携带风险标记；不等同于 `PASS`。
- `REJECT`：Data Standardization 保持 `BLOCKED`，按命中规则回退 Data Intake 或 Schema Mapping，并遵循返工上限。
- `HUMAN_REVIEW_REQUIRED`：Data Standardization 保持 `BLOCKED`，等待人工补充业务规则或 Gate 规则；Supervisor 不得自行放行。
