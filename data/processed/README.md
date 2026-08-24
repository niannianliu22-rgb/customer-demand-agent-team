# Processed Data Products

本目录只存放经 Data Quality 与 Data Gate 验收后发布的可复用历史数据产品；它不是 run 临时 Artifact 的替代品。

- stable：仅 Data Gate `PASS`，文件直接位于本目录，metadata 的 `release_status` 必须为 `STABLE`。
- candidate：仅 Data Gate `CONDITIONAL`，文件只能位于 `candidate/`，metadata 的 `release_status` 必须为 `CONDITIONAL`。
- Data Gate `REJECT` 或 `HUMAN_REVIEW_REQUIRED`：禁止发布。

版本不可覆盖。消费者必须读取同版本的 `*.metadata.json` 和 `data_dictionary_v{N}.md`，并仅将 stable 产品用于正式跨项目、BI 或 Agent Team 输入。完整契约见 [`docs/DATA_PRODUCT_RELEASE.md`](../../docs/DATA_PRODUCT_RELEASE.md)。
