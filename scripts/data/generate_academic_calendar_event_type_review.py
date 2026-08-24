#!/usr/bin/env python3
"""Create a read-only manual-review pack for frozen Calendar V1 event types."""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'runs/RUN-202608-DEMAND-001/artifacts/academic_calendar_standardization_v1/academic_calendar_standardized.csv'
OUT = ROOT / 'runs/RUN-202608-DEMAND-001/artifacts/academic_calendar_event_type_review'
OUT.mkdir(parents=True, exist_ok=True)

def read(path):
    with path.open(encoding='utf-8-sig', newline='') as handle: return list(csv.DictReader(handle))
def write(path, fields, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)

rows = read(SOURCE); total = len(rows)
risk = {
    'ASSESSMENT': 'HIGH: “Assessment Period/Weeks”与“Teaching and Assessment weeks”混合；需人工确认后者是否应维持 ASSESSMENT 或拆分。',
    'OTHER': 'HIGH: 包含 “Academic year closing interval” 与 “Summer Semester”；后者可能是 period 描述而非独立事件。',
    'TEACHING': 'MEDIUM: 包含 term/semester、classes、teaching resumes 等表述；一级教学语义一致，但需确认是否保留为一个事件类型。',
    'RESULTS': 'LOW: 当前均为成绩发布语义，需确认是否保留 RESULTS。',
    'RESIT': 'MEDIUM: resit、supplementary、deferred 已在 subtype 区分；本轮仅确认一级 RESIT 是否合理。',
    'EXAM': 'HIGH: 包含 final/general exam，以及 “Revision and examination period” 与 “assessment and exams”等混合表述。',
}
semantic = {
    'ORIENTATION':'Orientation / Welcome / Induction 等入学与迎新事件。','TEACHING':'正式教学、开课、教学恢复与学校命名的教学学期。','READING':'阅读周、阅读/田野周等非考试前学习阶段。','ASSESSMENT':'评估期或教学与评估合并安排。','REVISION':'复习、study days、SWOTVAC 或考前学习期。','EXAM':'常规或期末考试期。','RESULTS':'考试或学期成绩发布。','RESIT':'补考、补充考试或延期考试安排。','BREAK':'教学间歇、假日或学期中断。','VACATION':'寒暑假等较长假期。','OTHER':'当前 taxonomy 未明确归类的官方日历记录。',
}
by_type=defaultdict(list); by_mapping=defaultdict(list)
for row in rows:
    by_type[row['event_type']].append(row)
    by_mapping[(row['event_type'],row['event_name_original'],row['event_subtype'])].append(row)
summary=[]; mapping=[]
recommendation = {
    'ORIENTATION':'建议保留：Welcome / Induction / Arrivals 均服务于入学与开学准备，当前一级粒度足够。',
    'TEACHING':'建议保留：不同学校的 Term/Semester/classes/resumes 均是教学阶段；暂不建议拆分。',
    'READING':'建议保留：当前量小但语义清晰；不建议并入 REVISION，待后续样本增加再复核。',
    'ASSESSMENT':'建议人工确认后决定：Teaching and Assessment weeks 可能需要 subtype，而不是直接拆一级类型。',
    'REVISION':'建议保留：Revision、SWOTVAC、Study Days 均为考试前准备语义。',
    'EXAM':'建议保留一级 EXAM；以 subtype 区分 FINAL/GENERAL。含复习或评估字样的混合名称需人工确认。',
    'RESULTS':'建议保留：当前均为成绩发布；不建议与 ASSESSMENT 合并。',
    'RESIT':'建议保留：补考/补充/延期考试均属恢复性评估，现有 subtype 足以区分。',
    'BREAK':'建议保留：当前均为短期教学中断；不建议与 VACATION 合并。',
    'VACATION':'建议保留：较长假期与 BREAK 的运营时点含义不同。',
    'OTHER':'建议人工处理：Academic year closing interval 可能保留 OTHER；Summer Semester 更可能是 period 而非 event。',
}
for event_type in sorted(by_type):
    group=by_type[event_type]
    names={row['event_name_original'] for row in group}; schools={row['school'] for row in group}; countries={row['country'] for row in group}
    summary.append({'event_type':event_type,'record_count':len(group),'record_share':f'{len(group)/total*100:.2f}%','unique_event_name_count':len(names),'school_count':len(schools),'countries':'; '.join(sorted(countries)),'semantic_definition':semantic[event_type],'potential_conflict':risk.get(event_type,'NONE: 当前未识别出一级 event_type 内的明显语义混杂。'),'manual_decision':'REVIEW_REQUIRED','manual_note':''})
for (event_type,name,subtype),group in sorted(by_mapping.items()):
    schools=sorted({row['school'] for row in group}); countries=sorted({row['country'] for row in group})
    raw_conflict=''
    lower=name.lower()
    if event_type=='EXAM' and ('revision and examination' in lower or 'assessment and exams' in lower): raw_conflict='POTENTIAL_MIXED_SEMANTICS: 官网名称同时包含复习/评估与考试。'
    elif event_type=='OTHER': raw_conflict='POTENTIAL_RECLASSIFICATION: 请确认是否应进入已有正式一级类型。'
    elif event_type=='ASSESSMENT' and 'teaching and assessment' in lower: raw_conflict='POTENTIAL_COMBINED_PERIOD: 教学与评估合并表述。'
    mapping.append({'event_type':event_type,'event_name_original':name,'record_count':len(group),'school_count':len(schools),'schools':'; '.join(schools),'countries':'; '.join(countries),'current_event_subtype':subtype,'potential_semantic_issue':raw_conflict,'manual_decision':'REVIEW_REQUIRED','manual_note':''})
write(OUT/'event_type_manual_review.csv',list(summary[0]),summary)
write(OUT/'event_type_raw_event_detail.csv',list(mapping[0]),mapping)

lines=['# Academic Calendar Event Type Manual Review','','本文件只用于一级 `event_type` 人工确认；不修改 Frozen Calendar V1，也不修改 event_subtype。','']
for item in summary:
    group=[row for row in mapping if row['event_type']==item['event_type']]
    lines.extend([f"# {item['event_type']}",'',f"记录数：{item['record_count']}（{item['record_share']}）",f"unique 官网原始事件：{item['unique_event_name_count']}",f"涉及学校：{item['school_count']}",f"涉及国家：{item['countries']}",f"当前语义：{semantic[item['event_type']]}",f"潜在语义冲突：{item['potential_conflict']}",f"建议人工判断：{recommendation[item['event_type']]}",'','包含的官网原始事件：',''])
    for row in group:
        suffix=f"；{row['school_count']} 所学校；{row['countries']}"
        if row['current_event_subtype']: suffix+=f"；subtype={row['current_event_subtype']}"
        if row['potential_semantic_issue']: suffix+=f"；{row['potential_semantic_issue']}"
        lines.append(f"- {row['event_name_original']}：{row['record_count']} 条{suffix}")
    lines.extend(['','人工确认：','- [ ] 保留','- [ ] 改名','- [ ] 合并','- [ ] 拆分','- [ ] 部分事件映射错误','','---',''])
(OUT/'event_type_manual_review.md').write_text('\n'.join(lines),encoding='utf-8')
write(OUT/'event_type_summary.csv',['event_type','record_count','record_share','unique_event_name_count','school_count','countries','semantic_definition','potential_conflict','manual_decision','manual_note'],summary)
write(OUT/'event_type_raw_event_mapping.csv',list(mapping[0]),mapping)
print({'records':total,'event_types':len(summary),'raw_event_mappings':len(mapping),'output':str(OUT.relative_to(ROOT))})
