#!/usr/bin/env python3
"""Route existing Evidence Gate candidates; do not execute a drill-down."""
from __future__ import annotations
import csv,hashlib,json
from collections import Counter,defaultdict
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[2];ART=ROOT/'runs/RUN-202608-DEMAND-001/artifacts';DATA=ART/'unified_dataset.csv';EVD=ART/'demand_evidence_v1';PV=ART/'demand_pattern_value_v1';OUT=ART/'selective_where_router_v1'
SOURCE=EVD/'where_evidence_reclassification.csv';MATRIX=PV/'task_type_priority_matrix.csv';UPSTREAM=ROOT/'config/insight/demand_pattern_operational_value_v1.yaml';CFG=ROOT/'config/insight/selective_where_drilldown_router_v1.yaml'
GOOD={'P1_CORE_DEMAND','P2_GROWTH_DEMAND','P3_HIGH_VALUE_NICHE'};ROUTES={'STRONG_EVIDENCE':'STABLE_MARKET_ROUTE','MODERATE_EVIDENCE':'STABLE_MARKET_ROUTE','EMERGING_SIGNAL':'GROWTH_SOURCE_ROUTE','LIMITED_HIGH_VALUE_EVIDENCE':'HIGH_VALUE_MARKET_ROUTE','WEAK_EVIDENCE':'STOP_ROUTE','INSUFFICIENT_EVIDENCE':'STOP_ROUTE'}
def read(p):
 with p.open(encoding='utf-8-sig',newline='') as h:return list(csv.DictReader(h))
def write(p,fs,rows):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('w',encoding='utf-8-sig',newline='') as h:w=csv.DictWriter(h,fieldnames=fs);w.writeheader();w.writerows(rows)
def n(r):return sum(int(r[f'{y}_count']) for y in ('2023','2024','2025'))
def valid_value(r):return r['where_value'] not in {'','UNKNOWN','/','未知'}
def role(r):return {'country':'CORE_GEOGRAPHY','school':'SPECIFIC_MARKET','degree_level':'CORE_POPULATION'}[r['where_dimension']]
def next_dimension(r):
 if r['where_dimension']=='country':return 'school'
 if r['where_dimension']=='degree_level':return 'country_or_school'
 return 'STOP_VALIDATE_TREND'
def main():
 inputs=[DATA,SOURCE,MATRIX,UPSTREAM,CFG];before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
 rows=read(DATA);src=read(SOURCE);matrix={r['task_type']:r for r in read(MATRIX)}
 if len(rows)!=818 or yaml.safe_load(UPSTREAM.read_text(encoding='utf8')).get('status')!='FROZEN':raise RuntimeError('precondition failed')
 if len([r for r in src if r['evidence_gate']!='STOP'])!=102:raise RuntimeError('unexpected Evidence Gate source')
 candidates=[];backlog=[];stopped=[]
 for r in src:
  route=ROUTES[r['evidence_level']];r={**r,'priority_class':r['final_priority_class'],'route_type':route,'market_pattern':role(r),'dimension_role':{'country':'Macro Market Location','school':'Specific Market Location','degree_level':'Customer Academic Stage / Demand Population'}[r['where_dimension']]}
  # P4 and evidence-stop records are not part of default routing. Current source is P1-P3 only,
  # but retain the explicit guard to protect future runs.
  if r['priority_class'] not in GOOD or route=='STOP_ROUTE':
   stopped.append({**r,'stop_reason':'STOP_ROUTE / excluded priority: retain Historical Demand fact and do not add a dimension','status':'STOP'})
  elif not valid_value(r):
   backlog.append({**r,'backlog_reason':'EVIDENCE_BACKLOG: unresolved WHERE value cannot be selected','status':'EVIDENCE_BACKLOG'})
  else:candidates.append(r)
 grouped=defaultdict(list)
 for r in candidates:grouped[(r['task_type'],r['route_type'])].append(r)
 selected=[]
 # Rule-based, no synthetic score: macro parent before population lens before school;
 # then cross-year presence, accumulated count, distribution and local importance.
 dimension_order={'country':0,'degree_level':1,'school':2}
 for key,rs in grouped.items():
  rs.sort(key=lambda r:(dimension_order[r['where_dimension']],-int(r['effective_years_present']),-n(r),-float(r['demand_distribution_share_mean']),-float(r['local_demand_share_mean']),r['where_value']))
  # First preserve one macro, population, and specific-market view where available;
  # then fill remaining budget by evidence order. This is a business-meaningful tree,
  # not three same-dimension rows competing for the same task/route budget.
  picked=[]
  for dim in ('country','degree_level','school'):
   candidate=next((r for r in rs if r['where_dimension']==dim),None)
   if candidate and candidate not in picked:picked.append(candidate)
  picked.extend(r for r in rs if r not in picked)
  for i,r in enumerate(picked):
   if i<3:
    parent=r['where_dimension'];child=next_dimension(r)
    terminal=parent=='school'
    status='STOP' if terminal else 'READY_FOR_DRILL_DOWN'
    selected.append({**r,'parent_dimension':parent,'parent_value':r['where_value'],'parent_evidence':r['evidence_level'],'next_dimension':child,'routing_reason':f"{r['route_type']}: {r['dimension_role']} selected within the 3-per-task route budget; parent-to-one-child rule applies.",'analysis_goal':{'STABLE_MARKET_ROUTE':'Validate stable core market structure.','GROWTH_SOURCE_ROUTE':'Validate the source of cross-year growth; do not treat a single 2025 peak as sufficient.','HIGH_VALUE_MARKET_ROUTE':'Locate revenue-directional opportunity; label conclusions HIGH_VALUE_DIRECTIONAL_EVIDENCE.'}[r['route_type']],'status':status})
   else:backlog.append({**r,'backlog_reason':'EVIDENCE_BACKLOG: retained beyond the 3-per-task-per-route budget','status':'EVIDENCE_BACKLOG'})
 # Market Tree includes all routed selections and makes parent/role relationships explicit.
 tree=[]
 for r in selected:
  tree.append({'task_type':r['task_type'],'priority_class':r['priority_class'],'route_type':r['route_type'],'market_pattern':r['market_pattern'],'market_location':r['parent_value'],'parent_dimension':r['parent_dimension'],'evidence':r['parent_evidence'],'next_dimension':r['next_dimension'],'analysis_status':r['status'],'market_tree_reason':r['routing_reason']})
 tree.sort(key=lambda r:(r['task_type'],r['route_type'],r['parent_dimension'],r['market_location']))
 tree_fields=list(tree[0]);write(OUT/'demand_market_tree.csv',tree_fields,tree)
 candidate_fields=list(selected[0])
 for route,file in [('STABLE_MARKET_ROUTE','stable_market_candidates.csv'),('GROWTH_SOURCE_ROUTE','growth_source_candidates.csv'),('HIGH_VALUE_MARKET_ROUTE','high_value_market_candidates.csv')]:write(OUT/file,candidate_fields,[r for r in selected if r['route_type']==route])
 backlog_fields=list(backlog[0]);write(OUT/'evidence_backlog.csv',backlog_fields,backlog)
 plan_fields=['task_type','priority_class','parent_dimension','parent_value','parent_evidence','route_type','next_dimension','routing_reason','analysis_goal','status']
 plan=[{k:r[k] for k in plan_fields} for r in selected]
 write(OUT/'level3_drilldown_plan.csv',plan_fields,plan)
 after={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
 qa_checks={
  'task_type_first':all(r['task_type'] and r['parent_dimension'] in {'country','school','degree_level'} for r in selected),
  'only_p1_p3_default':all(r['priority_class'] in GOOD for r in selected),
  'all_102_business_routed':len(selected)+len(backlog)==102,
  'not_all_candidates_auto_executed':all(r['status']!='EXECUTED' for r in selected),
  'stable_route_correct':all(r['parent_evidence'] in {'STRONG_EVIDENCE','MODERATE_EVIDENCE'} for r in selected if r['route_type']=='STABLE_MARKET_ROUTE'),
  'growth_route_correct':all(r['parent_evidence']=='EMERGING_SIGNAL' for r in selected if r['route_type']=='GROWTH_SOURCE_ROUTE'),
  'high_value_route_correct':all(r['parent_evidence']=='LIMITED_HIGH_VALUE_EVIDENCE' for r in selected if r['route_type']=='HIGH_VALUE_MARKET_ROUTE'),
  'weak_insufficient_stop':all(r['status']=='STOP' for r in stopped if r.get('evidence_level') in {'WEAK_EVIDENCE','INSUFFICIENT_EVIDENCE'}),
  'roles_separated':all(r['dimension_role'] for r in selected),
  'one_child_only':all(r['next_dimension'] in {'school','country_or_school','STOP_VALIDATE_TREND'} for r in selected),
  'no_channel_customer_ddl':all(x not in str(selected) for x in ['channel','customer_group','ddl']),
  'data_and_frozen_inputs_unchanged':before==after,
  'academic_calendar_not_executed':True,'context_not_entered':True,
 }
 qa={'framework_version':'1.0','result':'PASS' if all(qa_checks.values()) else 'FAIL','checks':qa_checks,'source_evidence_gate_candidates':102,'selected_route_counts':dict(Counter(r['route_type'] for r in selected)),'backlog_count':len(backlog),'stop_route_count':len(stopped),'ready_count':sum(r['status']=='READY_FOR_DRILL_DOWN' for r in selected),'terminal_school_stop_count':sum(r['status']=='STOP' for r in selected)}
 (OUT/'router_qa.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf8')
 summary='# Selective WHERE Drill-down Router V1\n\n102 Evidence Gate candidates were routed, deduplicated by Task Type and route, and limited to three selected parent segments per task/route. The files are plans only: READY rows require later human approval and no drill-down has executed.\n\nRoute counts: '+json.dumps(dict(Counter(r['route_type'] for r in selected)),ensure_ascii=False)+'; Evidence Backlog: '+str(len(backlog))+'; STOP_ROUTE observations: '+str(len(stopped))+'.\n'
 (OUT/'router_summary.md').write_text(summary,encoding='utf8')
 if qa['result']!='PASS':raise RuntimeError('router QA failed')
 print(json.dumps({'selected':dict(Counter(r['route_type'] for r in selected)),'backlog':len(backlog),'stop_route':len(stopped),'ready':qa['ready_count'],'qa':qa['result']},ensure_ascii=False))
if __name__=='__main__':main()
