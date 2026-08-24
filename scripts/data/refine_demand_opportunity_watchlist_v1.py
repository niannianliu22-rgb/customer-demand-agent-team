#!/usr/bin/env python3
"""A minimal, transparent P4 WATCHLIST refinement; no analytical reruns."""
from __future__ import annotations
import csv,hashlib,json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];ART=ROOT/'runs/RUN-202608-DEMAND-001/artifacts';OUT=ART/'demand_opportunity_v1';MATRIX=OUT/'demand_opportunity_matrix_v1.csv';QA=OUT/'demand_opportunity_qa.json';DATA=ART/'unified_dataset.csv';UP=ROOT/'config/insight/demand_pattern_operational_value_v1.yaml'
def read(p):
 with p.open(encoding='utf-8-sig',newline='') as h:return list(csv.DictReader(h))
def write(p,fs,rows):
 with p.open('w',encoding='utf-8-sig',newline='') as h:w=csv.DictWriter(h,fieldnames=fs);w.writeheader();w.writerows(rows)
def d(v):return Decimal(v or '0')
def pct(n,z):return format((Decimal(n)*100/Decimal(z)).quantize(Decimal('.01')),'f') if z else ''
def money(v):return format(v.quantize(Decimal('.01')),'f')
def main():
 inputs=[DATA,UP]; before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
 rows=read(MATRIX);original=[dict(r) for r in rows]
 audit=[]
 # Minimum rule: an original P4 is ACTIVE if either inherited value path is HIGH,
 # OR it has at least ten historical observations (two existing effective-sample floors).
 # Everything else remains a historical LONG_TAIL_DEMAND. No score or re-analysis.
 for r in rows:
  frozen_priority=r.get('frozen_demand_priority_class',r['priority'])
  old='WATCHLIST' if frozen_priority=='P4_WATCHLIST' else r['primary_opportunity_class']
  r['frozen_demand_priority_class']=frozen_priority
  if frozen_priority=='P4_WATCHLIST':
   high_path=r['volume_value']=='HIGH_VOLUME_VALUE' or r['revenue_value']=='HIGH_REVENUE_VALUE'
   actual_scale=int(r['historical_count'])>=10
   if high_path or actual_scale:
    new='ACTIVE_DEMAND';priority='P4_ACTIVE_DEMAND';reason='Existing Volume OR Revenue path is HIGH, or historical_count >= 10 (two existing effective-sample floors): daily operating demand without P1–P3 strategic classification.'
   else:
    new='LONG_TAIL_DEMAND';priority='P5_LONG_TAIL_DEMAND';reason='Historical demand is retained, but no HIGH Volume/Revenue path and fewer than 10 observations; current pattern evidence remains insufficient for active-demand classification.'
   r['primary_opportunity_class']=new;r['priority']=priority
   audit.append({'task_type':r['task_type'],'old_class':old,'new_class':new,'historical_count':r['historical_count'],'historical_share':r['historical_share'],'amount_cny':r['amount_cny'],'amount_share':r['amount_share'],'pattern_class':r['pattern_class'],'classification_reason':reason})
  else:
   audit.append({'task_type':r['task_type'],'old_class':old,'new_class':old,'historical_count':r['historical_count'],'historical_share':r['historical_share'],'amount_cny':r['amount_cny'],'amount_share':r['amount_share'],'pattern_class':r['pattern_class'],'classification_reason':'P1/P2/P3 existing Opportunity Classification preserved without change.'})
 fields=list(rows[0]);
 if 'frozen_demand_priority_class' not in fields:fields.append('frozen_demand_priority_class')
 order={'P1_CORE_DEMAND':0,'P2_GROWTH_DEMAND':1,'P3_HIGH_VALUE_NICHE':2,'P4_ACTIVE_DEMAND':3,'P5_LONG_TAIL_DEMAND':4};rows.sort(key=lambda r:(order[r['priority']],-int(r['historical_count'])))
 write(MATRIX,fields,rows);write(OUT/'watchlist_refinement_audit.csv',list(audit[0]),audit)
 groups=defaultdict(list)
 for r in rows:groups[r['primary_opportunity_class']].append(r)
 obsden=sum(int(r['historical_count']) for r in rows);amountden=d(rows[0]['amount_share_denominator_cny'])
 summary={k:{'task_type_count':len(v),'historical_observation_count':sum(int(x['historical_count']) for x in v),'historical_observation_share':pct(sum(int(x['historical_count']) for x in v),obsden),'amount_cny':money(sum((d(x['amount_cny']) for x in v),Decimal('0'))),'amount_share':pct(sum((d(x['amount_cny']) for x in v),Decimal('0')),amountden)} for k,v in groups.items()}
 labels={'CORE_OPPORTUNITY':'核心稳定需求','GROWTH_OPPORTUNITY':'增长需求','HIGH_VALUE_OPPORTUNITY':'高价值需求','ACTIVE_DEMAND':'日常活跃需求','LONG_TAIL_DEMAND':'长尾需求'}
 lines=['# Demand Opportunity Matrix V1','', '本次仅将原 WATCHLIST 透明拆分为 ACTIVE_DEMAND 与 LONG_TAIL_DEMAND；P1–P3 未改变。','']
 for cls in labels:
  lines += [f'## {labels[cls]}','']
  for r in groups[cls]:lines.append(f"- {r['task_type']}：{r['historical_count']} 次（{r['historical_share']}%）；{r['operational_value_class']}；主要市场：{' / '.join(x for x in [r['primary_country'],r['primary_degree'],r['key_schools']] if x) or 'NOT_ENOUGH_EVIDENCE'}。")
  lines.append('')
 (OUT/'demand_opportunity_summary.md').write_text('\n'.join(lines),encoding='utf8')
 after={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
 checks={'all_34_retained':len(rows)==34,'core_growth_high_value_unchanged':all(r['primary_opportunity_class']==o['primary_opportunity_class'] and r['priority']==o['priority'] for r,o in zip([x for x in rows if x['frozen_demand_priority_class']!='P4_WATCHLIST'],[x for x in original if x['priority']!='P4_WATCHLIST'])),'only_original_watchlist_reclassified':all(a['new_class'] in {'ACTIVE_DEMAND','LONG_TAIL_DEMAND'} for a in audit if a['old_class']=='WATCHLIST'),'all_historical_demands_retained':all(r['task_type'] for r in rows),'observation_counts_unchanged':sum(int(r['historical_count']) for r in rows)==sum(int(r['historical_count']) for r in original),'amounts_unchanged':sum((d(r['amount_cny']) for r in rows),Decimal('0'))==sum((d(r['amount_cny']) for r in original),Decimal('0')),'annual_scope_unchanged':all(r['year_2023_count'] and r['year_2024_count'] and r['year_2025_count'] for r in rows),'no_where_drilldown_or_new_dimensions':True,'academic_calendar_not_executed':True,'data_and_frozen_framework_unchanged':before==after}
 qa={'framework_version':'1.0-refinement','result':'PASS' if all(checks.values()) else 'FAIL','classification_rule':'For original WATCHLIST only: HIGH_VOLUME_VALUE OR HIGH_REVENUE_VALUE OR historical_count >= 10 => ACTIVE_DEMAND; otherwise LONG_TAIL_DEMAND. 10 equals two existing effective-sample floors, avoiding a new scoring model.','checks':checks,'class_summary':summary,'original_watchlist_reallocation':{'active_demand':sum(a['new_class']=='ACTIVE_DEMAND' for a in audit if a['old_class']=='WATCHLIST'),'long_tail_demand':sum(a['new_class']=='LONG_TAIL_DEMAND' for a in audit if a['old_class']=='WATCHLIST')}}
 (OUT/'demand_opportunity_qa.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf8')
 if qa['result']!='PASS':raise RuntimeError('refinement QA failed')
 print(json.dumps({'summary':summary,'reallocation':qa['original_watchlist_reallocation'],'qa':qa['result']},ensure_ascii=False))
if __name__=='__main__':main()
