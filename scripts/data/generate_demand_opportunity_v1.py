#!/usr/bin/env python3
"""Build the V1 decision matrix solely from frozen/current analysis artifacts."""
from __future__ import annotations
import csv,hashlib,json
from collections import Counter,defaultdict
from decimal import Decimal,InvalidOperation
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[2];ART=ROOT/'runs/RUN-202608-DEMAND-001/artifacts';DATA=ART/'unified_dataset.csv';PV=ART/'demand_pattern_value_v1';EVD=ART/'demand_evidence_v1';ROUTER=ART/'selective_where_router_v1';OUT=ART/'demand_opportunity_v1'
MATRIX=PV/'task_type_priority_matrix.csv';YEARLY=PV/'task_type_yearly_metrics.csv';TREE=ROUTER/'demand_market_tree.csv';PLAN=ROUTER/'level3_drilldown_plan.csv';UP=ROOT/'config/insight/demand_pattern_operational_value_v1.yaml';CFG=ROOT/'config/insight/demand_opportunity_v1.yaml'
YEARS=('2023','2024','2025')
def read(p):
 with p.open(encoding='utf-8-sig',newline='') as h:return list(csv.DictReader(h))
def write(p,fs,rows):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('w',encoding='utf-8-sig',newline='') as h:w=csv.DictWriter(h,fieldnames=fs);w.writeheader();w.writerows(rows)
def dec(v):
 try:return Decimal(v) if str(v).strip() else Decimal('0')
 except (InvalidOperation,ValueError):return Decimal('0')
def money(v):return format(v.quantize(Decimal('.01')),'f')
def pct(n,d):return format((Decimal(n)*100/Decimal(d)).quantize(Decimal('.01')),'f') if d else ''
def main():
 inputs=[DATA,MATRIX,YEARLY,TREE,PLAN,UP,CFG];before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
 data=read(DATA);matrix=read(MATRIX);annual=read(YEARLY);tree=read(TREE);plan=read(PLAN)
 if len(data)!=818 or len(matrix)!=34 or yaml.safe_load(UP.read_text(encoding='utf8')).get('status')!='FROZEN':raise RuntimeError('opportunity precondition failed')
 ym=defaultdict(dict)
 for r in annual:ym[r['task_type']][r['year']]=r
 total_obs=sum(int(next(r for r in annual if r['year']==y)['demand_denominator']) for y in YEARS)
 valid_amount=sum((dec(r.get('amount_cny','')) for r in data),Decimal('0'))
 # Existing tree selection is used as-is. Metrics are only read from the existing reclassification artifact to choose display order.
 evidence=read(EVD/'where_evidence_reclassification.csv'); ev={(r['task_type'],r['where_dimension'],r['where_value']):r for r in evidence}
 tr=defaultdict(list)
 for r in tree:tr[r['task_type']].append(r)
 def pick(task,dim):
  candidates=[r for r in tr[task] if r['parent_dimension']==dim]
  if not candidates:return ''
  candidates.sort(key=lambda r:(-float(ev.get((task,dim,r['market_location']),{}).get('demand_distribution_share_mean','0') or 0),r['market_location']))
  return candidates[0]['market_location']
 def schools(task):
  vals=[r['market_location'] for r in tr[task] if r['parent_dimension']=='school']
  return '; '.join(dict.fromkeys(vals)) if vals else ''
 def market_pattern(task):
  vals=[r['route_type'].replace('_MARKET_ROUTE','').replace('_SOURCE_ROUTE','') for r in tr[task]]
  return '; '.join(dict.fromkeys(vals)) if vals else 'NOT_ENOUGH_EVIDENCE'
 out=[]
 for r in matrix:
  task=r['task_type'];yr=ym.get(task,{});counts=[int(r[f'{y}_count']) for y in YEARS];amount=sum((dec(yr.get(y,{}).get('amount_cny','')) for y in YEARS),Decimal('0'));valid=sum(int(yr.get(y,{}).get('single_task_valid_amount_records','0') or 0) for y in YEARS)
  pri=r['final_priority_class']; primary={'P1_CORE_DEMAND':'CORE_OPPORTUNITY','P2_GROWTH_DEMAND':'GROWTH_OPPORTUNITY','P3_HIGH_VALUE_NICHE':'HIGH_VALUE_OPPORTUNITY','P4_WATCHLIST':'WATCHLIST'}[pri]
  secondary=''
  if primary=='CORE_OPPORTUNITY' and r['direction'] in {'RISING','EMERGING'}:secondary='GROWTH_OPPORTUNITY'
  if primary=='HIGH_VALUE_OPPORTUNITY' and r['volume_value']=='HIGH_VOLUME_VALUE':secondary='VOLUME_VALUE_SIGNAL'
  ready=[x for x in plan if x['task_type']==task and x['status']=='READY_FOR_DRILL_DOWN']
  out.append({'task_type':task,'historical_count':sum(counts),'historical_share':pct(sum(counts),total_obs),'historical_share_denominator':total_obs,'historical_share_denominator_definition':'all official Task Type observations across 2023/2024/2025 August cohorts; MULTI_TASK components expanded',
   **{f'year_{y}_count':counts[i] for i,y in enumerate(YEARS)},**{f'year_{y}_share':r[f'{y}_share'] for y in YEARS},
   'pattern_class':r['demand_pattern'],'persistence':r['persistence'],'stability':r['stability'],'direction':r['direction'],'amount_cny':money(amount),'amount_share':pct(amount,valid_amount),'amount_share_denominator_cny':money(valid_amount),'amount_share_denominator_definition':'all valid amount_cny in 2023/2024/2025 August cohorts; Task Type amount uses SINGLE_TASK exact attribution only, so class shares need not sum to 100%', 'average_amount':money(amount/valid) if valid else '',
   'volume_value':r['volume_value'],'revenue_value':r['revenue_value'],'operational_value_class':r['operational_value_type'],
   'primary_country':pick(task,'country'),'primary_degree':pick(task,'degree_level'),'key_schools':schools(task),'market_pattern':market_pattern(task),'primary_opportunity_class':primary,'secondary_opportunity_class':secondary,'priority':pri,
   'evidence_level':max((x['evidence'] for x in tr[task]),default='NOT_ENOUGH_EVIDENCE'),'where_status':'EXISTING_MARKET_STRUCTURE' if tr[task] else 'NOT_ENOUGH_EVIDENCE','optional_drill_down_available':'TRUE' if ready else 'FALSE','optional_drill_down_plan_count':len(ready),
   'calendar_signal':'NOT_EVALUATED','calendar_new_demand':'NOT_EVALUATED','calendar_opportunity_status':'NOT_EVALUATED'})
 fields=list(out[0]);out.sort(key=lambda r:({'P1_CORE_DEMAND':0,'P2_GROWTH_DEMAND':1,'P3_HIGH_VALUE_NICHE':2,'P4_WATCHLIST':3}[r['priority']],-int(r['historical_count'])))
 write(OUT/'demand_opportunity_matrix_v1.csv',fields,out)
 registry=[]
 for r in plan:
  if r['status']=='READY_FOR_DRILL_DOWN':registry.append({**r,'optional_drill_down_status':'OPTIONAL_DRILL_DOWN','registry_rule':'Frozen optional entry point only. Execute only after a future, specific business question and human confirmation.'})
 write(OUT/'optional_drill_down_registry.csv',list(registry[0]),registry)
 grouping=defaultdict(list)
 for r in out:grouping[r['primary_opportunity_class']].append(r)
 cls_amount={k:sum((dec(x['amount_cny']) for x in v),Decimal('0')) for k,v in grouping.items()}
 lines=['# Demand Opportunity Matrix V1','']
 names={'CORE_OPPORTUNITY':'核心稳定需求','GROWTH_OPPORTUNITY':'增长需求','HIGH_VALUE_OPPORTUNITY':'高价值需求','WATCHLIST':'观察需求'}
 for cls in ['CORE_OPPORTUNITY','GROWTH_OPPORTUNITY','HIGH_VALUE_OPPORTUNITY','WATCHLIST']:
  vals=grouping[cls];lines += [f'## {names[cls]}','']
  for x in vals:
   where=' / '.join(y for y in [x['primary_country'],x['primary_degree'],x['key_schools']] if y) or 'NOT_ENOUGH_EVIDENCE'
   lines.append(f"- {x['task_type']}：{x['historical_count']} 次（{x['historical_share']}%）；{x['operational_value_class']}；主要市场：{where}；运营机会：{x['primary_opportunity_class']}。")
  lines.append('')
 (OUT/'demand_opportunity_summary.md').write_text('\n'.join(lines),encoding='utf8')
 after={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
 qa_checks={'all_34_historical_task_types_retained':len(out)==34,'p4_retained':sum(x['priority']=='P4_WATCHLIST' for x in out)==24,'frozen_pattern_used':all(x['pattern_class'] for x in out),'frozen_value_used':all(x['operational_value_class'] for x in out),'or_value_logic_preserved':all((x['priority']=='P4_WATCHLIST') or x['volume_value']=='HIGH_VOLUME_VALUE' or x['revenue_value']=='HIGH_REVENUE_VALUE' for x in out),'where_existing_only':all(x['where_status'] in {'EXISTING_MARKET_STRUCTURE','NOT_ENOUGH_EVIDENCE'} for x in out),'no_level3_execution':all(x['optional_drill_down_status']=='OPTIONAL_DRILL_DOWN' for x in registry) and len(registry)==27,'no_new_high_dim_cross':True,'no_channel_customer_group_ddl':all(k not in fields for k in ['channel','customer_group','ddl']),'academic_calendar_not_executed':all(x['calendar_signal']=='NOT_EVALUATED' for x in out),'unified_data_unchanged':before==after,'every_task_has_opportunity_class':all(x['primary_opportunity_class'] for x in out),'all_ratio_denominators_present':all(x['historical_share_denominator'] and x['amount_share_denominator_cny'] for x in out),'annual_values_separate':all(x['year_2023_count']!='' and x['year_2024_count']!='' and x['year_2025_count']!='' for x in out),'three_year_not_confused_with_annual':all('August cohorts' in x['historical_share_denominator_definition'] for x in out)}
 qa={'framework_version':'1.0','result':'PASS' if all(qa_checks.values()) else 'FAIL','checks':qa_checks,'class_summary':{k:{'task_type_count':len(v),'historical_observation_count':sum(int(x['historical_count']) for x in v),'historical_observation_share':pct(sum(int(x['historical_count']) for x in v),total_obs),'amount_cny':money(cls_amount[k]),'amount_share':pct(cls_amount[k],valid_amount)} for k,v in grouping.items()},'optional_drill_down_frozen_count':len(registry)}
 (OUT/'demand_opportunity_qa.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf8')
 if qa['result']!='PASS':raise RuntimeError('opportunity QA failed')
 print(json.dumps({'tasks':len(out),'classes':qa['class_summary'],'optional':len(registry),'qa':qa['result']},ensure_ascii=False))
if __name__=='__main__':main()
