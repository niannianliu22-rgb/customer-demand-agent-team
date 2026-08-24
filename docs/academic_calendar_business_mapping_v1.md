# Academic Calendar Business Mapping V1

Status: **FROZEN**. This document freezes interpretation rules only. It creates no Calendar → Demand records and no opportunities.

## Output separation

- `potential_task_type`: possible customer need.
- `potential_service_direction`: possible operating or promotion direction.
- `promotion_window`: when to begin preheat/outreach.
- `demand_window`: when demand may be more likely; it is not the same as `start_date`.

## Event rules

### ORIENTATION — CONTEXTUAL_OPPORTUNITY

- Business role: `SEMESTER_ONBOARDING_PREHEAT`
- Semantic: 开学、新生入学、新学期启动；长期服务的运营预热窗口，不证明客户已产生具体长期服务订单。
- Potential Task Type: None
- Potential service direction: 学年包, 包课, DP, 陪跑服务
- Promotion window: Orientation / Welcome 阶段
- Demand window: Semester Early Stage / Teaching Start 之后

### TEACHING — CONTEXTUAL_OPPORTUNITY

- Business role: `TEACHING_CYCLE_CONTEXT`
- Semantic: 正式开课及持续教学阶段；课程任务与作业需求的时间背景。TEACHING_START 提示作业需求周期即将开始，但不证明具体作业已产生。
- Potential Task Type: essay, assignment, 作业, 小组作业, project, Historical Demand Inventory 中其他合理的作业类 Task Type
- Potential service direction: 课程支持, 长期辅导, 包课, 陪跑服务
- Promotion window: TEACHING_START 及 Teaching Period 前段
- Demand window: Teaching Period

### READING — CONTEXTUAL_OPPORTUNITY

- Business role: `EXAM_PREPARATION_CONTEXT`
- Semantic: Reading Week、考前准备或集中学习阶段；不能单独证明具体考试订单。
- Potential Task Type: None
- Potential service direction: 考前辅导, 包过辅导, 押题
- Promotion window: Reading 阶段
- Demand window: Reading → Revision / Exam

### ASSESSMENT — CONTEXTUAL_OPPORTUNITY

- Business role: `ASSESSMENT_CONTEXT_WITH_KEY_SIGNAL`
- Semantic: Assessment Period / Week；默认仅为考核或 coursework 集中阶段背景，不自动推导 essay、report、project、presentation、作业或 tutoring。明确 key subtype 可提高时间信号强度，但本身不改变默认 Contextual 角色。复合 Assessment/Exam subtype 保持其已冻结的 EXAM 父类，并适用 EXAM 规则。
- Potential Task Type: None
- Potential service direction: assessment 支持, 课程辅导, tutoring
- Promotion window: Assessment 阶段
- Demand window: Assessment 阶段；复合 Assessment/Exam subtype 亦受 EXAM 规则约束

### REVISION — CONTEXTUAL_OPPORTUNITY

- Business role: `EXAM_PREHEAT_CONTEXT`
- Semantic: 考试前集中复习阶段；是考试服务的重要预热窗口，不是具体订单需求证明。
- Potential Task Type: None
- Potential service direction: 考前辅导, 包过辅导, 押题
- Promotion window: Revision 阶段
- Demand window: Revision → Exam

### EXAM — DIRECT_DEMAND_SIGNAL

- Business role: `EXAM_DEMAND_SIGNAL`
- Semantic: 正式考试阶段；明确支持考试类潜在需求/服务机会，但 Calendar Event 不得被计为真实成交需求。
- Potential Task Type: 考试
- Potential service direction: 考试, 考前辅导, 包过辅导, 押题
- Promotion window: Exam 前的 Revision / 考前阶段
- Demand window: Exam Period

### RESULTS — CONTEXTUAL_OPPORTUNITY

- Business role: `POST_RESULTS_FOLLOW_UP_CONTEXT`
- Semantic: 成绩发布或出分阶段；可能形成成绩风险与后续学习规划机会，但 Results 不等于挂科，不得自动生成真实补考需求。
- Potential Task Type: None
- Potential service direction: 补考, 考试辅导, 押题, 包过辅导
- Promotion window: Results Release
- Demand window: Results 后；补考须由 Resit Calendar Signal 或实际业务信号支持

### RESIT — DIRECT_DEMAND_SIGNAL

- Business role: `RESIT_DEMAND_SIGNAL`
- Semantic: 补考、Supplementary 或 Deferred Exam 阶段；为补考/考试类潜在需求提供强信号，不能直接计为真实成交。
- Potential Task Type: 补考, 考试
- Potential service direction: 补考, 考试辅导, 押题, 包过辅导
- Promotion window: Resit 前的 Results 后 / 考前阶段
- Demand window: Resit / Supplementary / Deferred Exam Period

### BREAK — CONTEXTUAL_OPPORTUNITY

- Business role: `NEXT_TERM_PREHEAT_CONTEXT`
- Semantic: 学期间隔或 Term Break；用于下一学习阶段长期服务预热。
- Potential Task Type: None
- Potential service direction: 学年包, 包课, DP, 陪跑服务
- Promotion window: Break 中后段
- Demand window: 下一 Teaching Period / Semester Start

### VACATION — CONTEXTUAL_OPPORTUNITY

- Business role: `NEXT_SEMESTER_PREHEAT_CONTEXT`
- Semantic: 较长假期；用于下一学期或下一学年的长期服务预热。
- Potential Task Type: None
- Potential service direction: 学年包, 包课, DP, 陪跑服务
- Promotion window: Vacation 中后段
- Demand window: 下一 Teaching Period / Semester Start

### OTHER — NO_MAPPING

- Business role: `NO_MAPPING_METADATA_OR_REVIEW`
- Semantic: 当前 OTHER 是 PERIOD_METADATA；保留原始证据但不参与 Calendar → Demand 或 Opportunity Mapping。未来真正 Academic Event 的 OTHER 必须单独 Review。
- Potential Task Type: None
- Potential service direction: None
- Promotion window: 不适用
- Demand window: 不适用

## Evidence boundary

Historical Demand and Academic Calendar are independent evidence sources. Historical Demand remains intact; Calendar can add future opportunities. Final Operational Demand Pool uses Historical Demand + Academic Calendar Opportunity, never an intersection gate.

`Academic year closing interval` and `Summer Semester` are `PERIOD_METADATA` and mapping-ineligible.
