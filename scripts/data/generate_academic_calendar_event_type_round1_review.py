#!/usr/bin/env python3
"""Read-only Round 1 manual recommendations for EXAM, ASSESSMENT and OTHER."""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SRC=ROOT/'runs/RUN-202608-DEMAND-001/artifacts/academic_calendar_standardization_v1/academic_calendar_standardized.csv'
OUT=ROOT/'runs/RUN-202608-DEMAND-001/artifacts/academic_calendar_event_type_review/round1_risk_types'
OUT.mkdir(parents=True,exist_ok=True)
def read(p):
 with p.open(encoding='utf-8-sig',newline='') as h:return list(csv.DictReader(h))
def write(p,fields,rows):
 with p.open('w',encoding='utf-8-sig',newline='') as h:
  w=csv.DictWriter(h,fieldnames=fields);w.writeheader();w.writerows(rows)

rows=[r for r in read(SRC) if r['event_type'] in {'EXAM','ASSESSMENT','OTHER'}]
def recommend(r):
 name=r['event_name_original'].lower(); typ=r['event_type']
 if typ=='EXAM':
  if 'revision and examination' in name: return 'REVIEW_REQUIRED','', '官网名称并列复习与考试，无法从现有区间判断是否应拆分为两个阶段。'
  if 'assessment and exams' in name or 'exam and assessment' in name or 'exam and assessment diet' in name: return 'REVIEW_REQUIRED','', '官网名称混合评估与考试，需人工确认主事件语义。'
  if 'final' in name: return 'KEEP_EXAM_WITH_SUBTYPE','FINAL_EXAM','明确期末考试语义；建议保留 EXAM，维持/确认 FINAL_EXAM subtype。'
  return 'KEEP_EXAM','GENERAL_EXAM','纯考试期或常规考试语义。'
 if typ=='ASSESSMENT':
  if 'teaching and assessment' in name: return 'KEEP_ASSESSMENT_WITH_SUBTYPE','TEACHING_AND_ASSESSMENT','教学与评估合并期间；建议不拆一级类型，后续以 subtype 表达。'
  return 'KEEP_ASSESSMENT','PURE_ASSESSMENT','纯评估期/评估周语义。'
 if name=='academic year closing interval': return 'MOVE_TO_PERIOD_METADATA','', '学年收尾区间是全学年边界信息，不是可直接映射的学业事件。'
 if name=='summer semester': return 'MOVE_TO_PERIOD_METADATA','', 'Summer Semester 已由 period_type/period_name 表达，更像期间元数据而非事件。'
 return 'REVIEW_REQUIRED','', '需要人工确认。'

detail=[]
for r in rows:
 action,subtype,reason=recommend(r)
 detail.append({'event_name_original':r['event_name_original'],'current_event_type':r['event_type'],'record_count':1,'school':r['school'],'country':r['country'],'current_event_subtype':r['event_subtype'],'start_date':r['start_date'],'end_date':r['end_date'],'period_type':r['period_type'],'period_name':r['period_name'],'semantic_issue':reason,'recommended_action':action,'recommended_event_type':({'KEEP_EXAM':'EXAM','KEEP_EXAM_WITH_SUBTYPE':'EXAM','MOVE_TO_REVISION':'REVISION','MOVE_TO_ASSESSMENT':'ASSESSMENT','KEEP_ASSESSMENT':'ASSESSMENT','MOVE_TO_TEACHING':'TEACHING','KEEP_ASSESSMENT_WITH_SUBTYPE':'ASSESSMENT','KEEP_OTHER':'OTHER','MOVE_TO_BREAK':'BREAK','MOVE_TO_PERIOD_METADATA':'PERIOD_METADATA','REVIEW_REQUIRED':r['event_type']}[action]),'recommended_subtype':subtype,'manual_decision':'REVIEW_REQUIRED','manual_note':''})
write(OUT/'event_type_round1_risk_detail.csv',list(detail[0]),detail)

groups=defaultdict(list)
for r in detail:groups[(r['event_name_original'],r['current_event_type'],r['recommended_event_type'],r['recommended_subtype'],r['semantic_issue'])].append(r)
simple=[]
for (name,current,recommended,subtype,reason),items in sorted(groups.items(),key=lambda x:(x[0][1],x[0][0])):
 simple.append({'event_name_original':name,'current_event_type':current,'recommended_event_type':recommended,'recommended_subtype':subtype,'reason':reason,'manual_decision':'REVIEW_REQUIRED','manual_note':''})
write(OUT/'event_type_manual_review_round1.csv',list(simple[0]),simple)

lines=['# Academic Calendar Event Type Manual Confirmation — Round 1','','本轮仅提出建议；未修改 event_type、event_subtype 或 Frozen Calendar。','']
for typ in ['EXAM','ASSESSMENT','OTHER']:
 lines.extend([f'# {typ}',''])
 for r in [x for x in detail if x['current_event_type']==typ]:
  lines.append(f"- {r['event_name_original']}｜{r['school']}｜{r['country']}｜{r['start_date']}–{r['end_date']}｜当前 subtype={r['current_event_subtype'] or '—'}｜建议={r['recommended_action']} {r['recommended_subtype']}｜{r['semantic_issue']}")
 lines.append('')
(OUT/'event_type_manual_review_round1.md').write_text('\n'.join(lines),encoding='utf-8')
print({'records':len(detail),'unique_events':len(simple),'output':str(OUT.relative_to(ROOT))})
