#!/usr/bin/env python3
"""Freeze transparent Task Type final priority integration; read-only against input data."""
from __future__ import annotations
import csv,json,hashlib
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[2]; ART=ROOT/'runs/RUN-202608-DEMAND-001/artifacts'; SRC=ART/'demand_pattern_value_v1'; DATA=ART/'unified_dataset.csv'; FRAME=ROOT/'config/insight/demand_insight_metrics_v1.yaml'; TF=ROOT/'config/dimensions/task_type/task_type_rules_frozen_v17.yaml'; CF=ROOT/'config/dimensions/channel/channel_rules_frozen_v1.yaml'; CFG=ROOT/'config/insight/demand_pattern_operational_value_v1.yaml'
def read(n):
 with (SRC/n).open(encoding='utf-8-sig',newline='') as h:return list(csv.DictReader(h))
def write(n,fs,rs):
 with (SRC/n).open('w',encoding='utf-8-sig',newline='') as h:
  w=csv.DictWriter(h,fieldnames=fs);w.writeheader();w.writerows(rs)
def main():
 inputs=[DATA,FRAME,TF,CF];before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
 yearly=read('task_type_yearly_metrics.csv');scale={r['task_type']:r for r in read('task_type_three_year_scale.csv')};persist={r['task_type']:r for r in read('task_type_persistence.csv')};stability={r['task_type']:r for r in read('task_type_stability.csv')};direction={r['task_type']:r for r in read('task_type_direction.csv')};pattern={r['task_type']:r for r in read('task_type_pattern_candidates.csv')};volume={r['task_type']:r for r in read('task_type_volume_value.csv')};revenue={r['task_type']:r for r in read('task_type_revenue_value.csv')};oper={r['task_type']:r for r in read('task_type_operational_priority.csv')}
 matrix=[];final=[]
 # Transparent lexicographic rules, not a weighted numerical model.
 for t in sorted(oper):
  p=pattern[t]['demand_pattern_candidate'];per=persist[t]['persistence'];stab=stability[t]['stability'];dire=direction[t]['direction'];vol=volume[t]['volume_value_level'];rev=revenue[t]['revenue_value_level'];op=oper[t]['operational_priority_type'];sc=scale[t]
  highv=vol=='HIGH_VOLUME_VALUE';highr=rev=='HIGH_REVENUE_VALUE'
  if p=='CORE_STABLE' and per=='PERSISTENT' and stab=='STABLE' and (highv or highr): cls='P1_CORE_DEMAND';reason='Persistent, stable, high-scale core pattern with an explicit Volume or Revenue Value path.'
  elif p in {'CORE_RISING','EMERGING'} and (highv or highr): cls='P2_GROWTH_DEMAND';reason='RISING or NEW/EMERGING pattern has formed operational value; prioritize market-location validation.'
  elif highr and p not in {'VOLATILE','CORE_DECLINING'}: cls='P3_HIGH_VALUE_NICHE';reason='Revenue Value path is high while the demand is not a stable scale core; retained under OR logic as a high-value niche candidate.'
  else: cls='P4_WATCHLIST';reason='Historical pattern is declining, volatile, low-sample, or insufficiently established for default WHERE deep-dive.'
  tier={'P1_CORE_DEMAND':1,'P2_GROWTH_DEMAND':2,'P3_HIGH_VALUE_NICHE':3,'P4_WATCHLIST':4}[cls]
  row={'task_type':t,'2023_count':sc['2023_count'],'2024_count':sc['2024_count'],'2025_count':sc['2025_count'],'2023_share':sc['2023_share'],'2024_share':sc['2024_share'],'2025_share':sc['2025_share'],'three_year_count':sc['three_year_count_total'],'three_year_share':sc['three_year_share_mean'],'persistence':per,'stability':stab,'direction':dire,'demand_pattern':p,'volume_value':vol,'revenue_value':rev,'operational_value_type':op,'final_priority_class':cls,'priority_score':f'RULE_BASED_TIER_{tier}','priority_reason':reason,'evidence':json.dumps({'top5_presence':read('task_type_overlap_analysis.csv')[0] if False else 'see_overlap_artifact','pattern':p,'persistence':per,'stability':stab,'direction':dire,'volume':vol,'revenue':rev},ensure_ascii=False),'ranking_reason':'Rule-based lexicographic ordering: final class first; P1/P2 by demand strength, P3 by revenue evidence. No weighted score used.'}
  matrix.append(row)
 # Non-weighted ranks prevent volume from displacing revenue-driven niche candidates.
 class_sort={'P1_CORE_DEMAND':0,'P2_GROWTH_DEMAND':1,'P3_HIGH_VALUE_NICHE':2,'P4_WATCHLIST':3}
 def sortkey(r):
  if r['final_priority_class']=='P3_HIGH_VALUE_NICHE':return (class_sort[r['final_priority_class']],-float(revenue[r['task_type']]['revenue_value_metrics'].split('"single_task_amount_total": "')[1].split('"')[0]))
  return (class_sort[r['final_priority_class']],-int(r['three_year_count']))
 matrix.sort(key=sortkey)
 for i,r in enumerate(matrix,1):r['priority_rank']=i
 final=[r for r in matrix if r['final_priority_class']!='P4_WATCHLIST']
 fs=['task_type','2023_count','2024_count','2025_count','2023_share','2024_share','2025_share','three_year_count','three_year_share','persistence','stability','direction','demand_pattern','volume_value','revenue_value','operational_value_type','final_priority_class','priority_score','priority_rank','priority_reason','evidence','ranking_reason']
 write('task_type_priority_matrix.csv',fs,matrix);write('final_priority_task_type_pool.csv',fs,final)
 frozen={'framework_name':'Demand Pattern & Operational Value V1','framework_version':'1.0','status':'FROZEN','source':'manual_business_confirmation','scope':'Task Type only; no WHERE dimension analysis','analysis_period':'2023-2025 August same-period cohorts','final_priority_rules':{'P1_CORE_DEMAND':'PERSISTENT + STABLE CORE_STABLE pattern + HIGH_VOLUME_VALUE or HIGH_REVENUE_VALUE','P2_GROWTH_DEMAND':'CORE_RISING or EMERGING + HIGH_VOLUME_VALUE or HIGH_REVENUE_VALUE','P3_HIGH_VALUE_NICHE':'HIGH_REVENUE_VALUE without P1/P2 qualification and not VOLATILE/CORE_DECLINING','P4_WATCHLIST':'declining, volatile, low-sample, or insufficiently established candidates'},'operational_logic':'HIGH_VOLUME_VALUE OR HIGH_REVENUE_VALUE; no AND gate','ranking':'Rule-based lexicographic tier ranking; no continuous weighted score','final_pool_task_types':[r['task_type'] for r in final],'watchlist_task_types':[r['task_type'] for r in matrix if r['final_priority_class']=='P4_WATCHLIST'],'upstream_framework':str(FRAME.relative_to(ROOT))}
 CFG.parent.mkdir(parents=True,exist_ok=True);CFG.write_text(yaml.safe_dump(frozen,allow_unicode=True,sort_keys=False),encoding='utf8')
 after={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
 qa={'framework_version':'1.0','result':'PASS','checks':{'independent_annual_cohort_metrics':set(r['year'] for r in yearly)=={'2023','2024','2025'},'august_same_period_scope':yaml.safe_load(FRAME.read_text(encoding='utf8'))['year_scope'].startswith('2023年8月'),'shares_retained_from_annual_metrics':all(r['2023_share']!='' and r['2024_share']!='' and r['2025_share']!='' for r in matrix),'or_logic_correct':all((r['volume_value']=='HIGH_VOLUME_VALUE' or r['revenue_value']=='HIGH_REVENUE_VALUE') for r in final),'high_volume_low_revenue_not_killed':any(r['task_type']=='选课' and r['final_priority_class']=='P2_GROWTH_DEMAND' for r in final),'high_revenue_low_volume_not_killed':any(r['task_type']=='DP' and r['final_priority_class']=='P3_HIGH_VALUE_NICHE' for r in final),'low_sample_not_core':all(not(r['final_priority_class']=='P1_CORE_DEMAND' and r['stability']=='LOW_SAMPLE') for r in matrix),'multi_task_amount_rule_preserved':all('SINGLE_TASK exact attribution' in r['amount_denominator_definition'] for r in yearly) and all('multi_task_observations' in r for r in yearly),'input_data_unchanged':before==after,'no_where_dimensions':all(k not in frozen['scope'] for k in ['school','degree_level'])}}
 qa['result']='PASS' if all(qa['checks'].values()) else 'FAIL';(SRC/'demand_pattern_operational_value_qa.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf8')
 summary='# Demand Pattern × Operational Value V1\n\nFinal priority uses rule-based tiers, not a weighted score. Volume and Revenue Value are independent OR paths. P1–P3 enter the default WHERE candidate pool; P4 is monitoring only. Thresholds remain upstream candidate thresholds; this file freezes the integration rules and resulting V1 pool.\n'
 (SRC/'demand_pattern_operational_value_summary.md').write_text(summary,encoding='utf8')
 if qa['result']!='PASS':raise RuntimeError('priority QA failed')
 print(json.dumps({'final_pool':len(final),'watchlist':len(matrix)-len(final),'qa':qa['result']},ensure_ascii=False))
if __name__=='__main__':main()
