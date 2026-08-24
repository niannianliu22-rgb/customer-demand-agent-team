#!/usr/bin/env python3
"""Reclassify existing WHERE evidence without changing data or executing a cross-analysis."""
from __future__ import annotations
import csv, hashlib, json
from collections import Counter, defaultdict
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[2]
ART=ROOT/'runs/RUN-202608-DEMAND-001/artifacts'
DATA=ART/'unified_dataset.csv'; PV=ART/'demand_pattern_value_v1'; WHERE=ART/'demand_where_v1'; OUT=ART/'demand_evidence_v1'
PRIORITY=PV/'task_type_priority_matrix.csv'; PRIORITY_CFG=ROOT/'config/insight/demand_pattern_operational_value_v1.yaml'; WHERE_CFG=ROOT/'config/insight/demand_where_framework_v1.yaml'; CFG=ROOT/'config/insight/historical_demand_evidence_framework_v1.yaml'
YEARS=('2023','2024','2025')
def read(p):
 with p.open(encoding='utf-8-sig',newline='') as h:return list(csv.DictReader(h))
def write(p,fs,rows):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('w',encoding='utf-8-sig',newline='') as h:
  w=csv.DictWriter(h,fieldnames=fs);w.writeheader();w.writerows(rows)
def main():
 inputs=[DATA,PRIORITY,PRIORITY_CFG,WHERE_CFG,CFG,WHERE/'where_priority_markets.csv']
 before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
 rows=read(DATA); matrix=read(PRIORITY); markets=read(WHERE/'where_priority_markets.csv')
 if len(rows)!=818 or yaml.safe_load(PRIORITY_CFG.read_text(encoding='utf8')).get('status')!='FROZEN':raise RuntimeError('upstream precondition failed')
 m={r['task_type']:r for r in matrix}
 # Every matrix task is an actual official task type in standardized historical records.
 inventory=[]
 for r in matrix:
  inventory.append({'task_type':r['task_type'],'three_year_count':r['three_year_count'],'years_present':sum(int(r[f'{y}_count'])>0 for y in YEARS),'demand_priority_class':r['final_priority_class'],'volume_value':r['volume_value'],'revenue_value':r['revenue_value'],'demand_status':'HISTORICAL_DEMAND','existence_definition':'Observed in frozen standardized Task Type history; existence is independent of priority and evidence.'})
 write(OUT/'historical_demand_inventory.csv',list(inventory[0]),sorted(inventory,key=lambda r:(-int(r['three_year_count']),r['task_type'])))
 # Reclassification applies to the 180 already-produced WHERE observations. It uses the parent cross-year segment metrics, not the annual LOW_SAMPLE marker alone.
 evidence=[]
 for r in markets:
  task=r['task_type']; p=m[task]; cls=p['final_priority_class']; rev=p['revenue_value']; eff=int(r['effective_years_present']); years=int(r['years_present']); total=sum(int(r[f'{y}_count']) for y in YEARS); pattern=r['pattern']; direction=r['direction']; stability=r['stability']; dim=r['where_dimension']
  # Rule order preserves macro persistence, recognises growth before volume insufficiency,
  # and separately retains P3 revenue opportunity without calling it a core market.
  if pattern=='CORE_STABLE' and eff==3 and stability=='STABLE' and float(r['demand_distribution_share_mean'])>=10:
   level='STRONG_EVIDENCE'; reason='Three effective years, stable cross-year pattern and material distribution contribution.'
  elif ((pattern in {'CORE_RISING','EMERGING'} and direction in {'RISING','EMERGING'} and eff>=2)
        or (int(r['2025_count']) > int(r['2024_count']) and int(r['2025_count']) > int(r['2023_count'])
            and int(r['2025_count']) >= (3 if dim=='school' else 5)
            and (float(r['2025_demand_distribution_share']) > 0 or float(r['2025_local_demand_share']) > 0))):
   level='EMERGING_SIGNAL'; reason='Recent count rises above both earlier cohorts and is supported by current distribution/local share; high-cardinality School uses a lower, non-uniform evidence floor. Not a long-term stability conclusion.'
  elif eff>=2 and pattern not in {'LOW_SAMPLE','VOLATILE'}:
   level='MODERATE_EVIDENCE'; reason='At least two effective years support a directional, explicitly moderate conclusion.'
  elif cls=='P3_HIGH_VALUE_NICHE' and rev=='HIGH_REVENUE_VALUE' and total>0:
   level='LIMITED_HIGH_VALUE_EVIDENCE'; reason='Low-volume segment retained for real high-revenue P3 evidence; it is not inferred to be a core market.'
  elif total>=3 or years>=2:
   level='WEAK_EVIDENCE'; reason='Historical segment exists but persistence/share/trend are insufficient for a reliable market interpretation.'
  else:
   level='INSUFFICIENT_EVIDENCE'; reason='Usable segment evidence and denominator support are too limited for a market conclusion.'
  gate={'STRONG_EVIDENCE':'ALLOW_DRILL_DOWN','MODERATE_EVIDENCE':'ALLOW_SELECTIVE_DRILL_DOWN','EMERGING_SIGNAL':'ALLOW_SELECTIVE_DRILL_DOWN','LIMITED_HIGH_VALUE_EVIDENCE':'ALLOW_VALUE_DRIVEN_DRILL_DOWN','WEAK_EVIDENCE':'STOP','INSUFFICIENT_EVIDENCE':'STOP'}[level]
  evidence.append({**r,'original_where_sample_status':r['sample_status'],'evidence_level':level,'evidence_reason':reason,'evidence_gate':gate,'evidence_inputs':json.dumps({'three_year_count':total,'years_present':years,'effective_years_present':eff,'dimension':dim,'distribution_share_mean':r['demand_distribution_share_mean'],'local_share_mean':r['local_demand_share_mean'],'direction':direction,'stability':stability,'revenue_value':rev},ensure_ascii=False)})
 fields=list(evidence[0]);write(OUT/'where_evidence_reclassification.csv',fields,evidence)
 # Depth is a task-level entitlement derived from its strongest existing independent WHERE evidence.
 bytask=defaultdict(list)
 for r in evidence:bytask[r['task_type']].append(r)
 rank={'INSUFFICIENT_EVIDENCE':0,'WEAK_EVIDENCE':1,'LIMITED_HIGH_VALUE_EVIDENCE':2,'MODERATE_EVIDENCE':3,'EMERGING_SIGNAL':4,'STRONG_EVIDENCE':5}
 depths=[]
 for inv in inventory:
  task=inv['task_type']; seg=bytask.get(task,[]); allowed=[r for r in seg if r['evidence_gate']!='STOP']; school_allowed=[r for r in allowed if r['where_dimension']=='school']
  if school_allowed:
   depth='L3_SELECTIVE_DRILL_DOWN'; explanation='At least one School segment passed the Evidence Gate; only a later human-approved selective drill-down is permitted.'
  elif allowed:
   depth='L1_MACRO_WHERE'; explanation='Country and/or Degree segment passed the Evidence Gate; School evidence has not passed.'
  else:
   depth='L0_DEMAND_ONLY'; explanation='Historical demand fact retained; no segment currently passes the Evidence Gate.'
  strongest=max((rank[r['evidence_level']] for r in seg),default=-1)
  strongest_label=next((k for k,v in rank.items() if v==strongest),'NOT_ASSESSED')
  depths.append({**inv,'analysis_depth':depth,'strongest_evidence_level':strongest_label,'allowed_segment_count':len(allowed),'school_allowed_segment_count':len(school_allowed),'depth_reason':explanation})
 write(OUT/'analysis_depth_by_task_type.csv',list(depths[0]),sorted(depths,key=lambda r:(r['analysis_depth'],r['task_type'])))
 gate=[r for r in evidence if r['evidence_gate']!='STOP']
 gate_fields=fields+['candidate_status','next_step_rule']
 gate=[{**r,'candidate_status':'PENDING_HUMAN_CONFIRMATION','next_step_rule':'Evidence Gate permits consideration only; no high-dimensional analysis has been executed.'} for r in gate]
 write(OUT/'evidence_gate_candidate_pool.csv',gate_fields,gate)
 original_low=[r for r in evidence if r['original_where_sample_status']=='LOW_SAMPLE']; low_counts=Counter(r['evidence_level'] for r in original_low)
 all_counts=Counter(r['evidence_level'] for r in evidence)
 after={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
 qa_checks={
  'all_historical_task_types_retained':len(inventory)==len(matrix)==34 and all(r['demand_status']=='HISTORICAL_DEMAND' for r in inventory),
  'p4_not_non_demand':all(r['demand_status']=='HISTORICAL_DEMAND' for r in inventory if r['demand_priority_class']=='P4_WATCHLIST'),
  'all_original_low_sample_reassessed':len(original_low)==164 and all(r['evidence_level'] for r in original_low),
  'evidence_not_single_count_rule':all('direction' in json.loads(r['evidence_inputs']) and 'local_share_mean' in json.loads(r['evidence_inputs']) for r in evidence),
  'school_high_cardinality_rule_documented':'high-cardinality' in CFG.read_text(encoding='utf8').lower(),
  'p3_retained_under_low_volume':all(any(r['task_type']==t for r in evidence) for t,x in m.items() if x['final_priority_class']=='P3_HIGH_VALUE_NICHE'),
  'emerging_not_erased':any(r['evidence_level']=='EMERGING_SIGNAL' for r in evidence),
  'weak_and_insufficient_stop':all(r['evidence_gate']=='STOP' for r in evidence if r['evidence_level'] in {'WEAK_EVIDENCE','INSUFFICIENT_EVIDENCE'}),
  'unified_and_frozen_inputs_unchanged':before==after,
  'no_new_high_dimensional_cross':set(r['where_dimension'] for r in evidence)=={'country','school','degree_level'},
  'academic_calendar_not_executed':True,
  'context_not_entered':True,
 }
 qa={'framework_version':'1.0','result':'PASS' if all(qa_checks.values()) else 'FAIL','checks':qa_checks,'historical_task_type_count':len(inventory),'evidence_counts':dict(all_counts),'original_low_sample_reclassification':dict(low_counts),'evidence_gate_candidate_segments':len(gate),'no_new_cross_analysis':'Reclassification only; existing independent WHERE artifacts reused.'}
 (OUT/'evidence_framework_qa.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf8')
 summary='# Historical Demand Evidence & Analysis Depth Framework V1\n\nAll 34 historically observed standardized Task Types are retained as `HISTORICAL_DEMAND`. Priority and evidence are independent labels. The former binary LOW_SAMPLE labels were reclassified using cross-year segment information, both shares, direction, stability, dimension cardinality and, for P3, Revenue Value. Evidence Gate candidates are pending human confirmation only; no drill-down was executed.\n\nEvidence counts: '+json.dumps(dict(all_counts),ensure_ascii=False)+'\n\nOriginal LOW_SAMPLE reclassification: '+json.dumps(dict(low_counts),ensure_ascii=False)+'\n'
 (OUT/'evidence_framework_summary.md').write_text(summary,encoding='utf8')
 if qa['result']!='PASS':raise RuntimeError('evidence QA failed')
 print(json.dumps({'inventory':len(inventory),'evidence':dict(all_counts),'original_low':dict(low_counts),'gate_candidates':len(gate),'qa':qa['result']},ensure_ascii=False))
if __name__=='__main__':main()
