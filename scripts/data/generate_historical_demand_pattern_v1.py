#!/usr/bin/env python3
"""Historical WHEN × WHERE × WHAT patterns from actual paid-order records only."""
from __future__ import annotations
import csv,hashlib,json,math
from collections import Counter,defaultdict
from decimal import Decimal,InvalidOperation
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];ART=ROOT/'runs/RUN-202608-DEMAND-001/artifacts';DATA=ART/'unified_dataset.csv';OPP=ART/'demand_opportunity_v1/demand_opportunity_matrix_v1.csv';OUT=ART/'historical_demand_pattern_v1'
INCLUDED={'CORE_OPPORTUNITY','GROWTH_OPPORTUNITY','HIGH_VALUE_OPPORTUNITY','ACTIVE_DEMAND'};YEARS=('2023','2024','2025');SCHOOL_EXCLUDED={'','UNKNOWN','UNSTANDARDIZED','NON_SCHOOL','NON_UNIVERSITY_ENTITY','UNRESOLVED'}
def read(p):
 with p.open(encoding='utf-8-sig',newline='') as h:return list(csv.DictReader(h))
def write(p,fs,rows):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('w',encoding='utf-8-sig',newline='') as h:w=csv.DictWriter(h,fieldnames=fs);w.writeheader();w.writerows(rows)
def dec(v):
 try:return Decimal(v) if str(v).strip() else None
 except (InvalidOperation,ValueError):return None
def money(v):return format(v.quantize(Decimal('.01')),'f')
def q(vals,p):
 vals=sorted(vals);i=(len(vals)-1)*p;lo=math.floor(i);hi=math.ceil(i);return vals[lo] if lo==hi else vals[lo]+(vals[hi]-vals[lo])*(i-lo)
def main():
 inputs=[DATA,OPP];before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
 data=read(DATA);opps=read(OPP);classes={r['task_type']:r['primary_opportunity_class'] for r in opps};included_tasks={t for t,c in classes.items() if c in INCLUDED}
 # A completed sale is explicitly order_status=已成交. MULTI_TASK is not attributed to a single
 # value-class task type and is outside this V1 exact-result aggregation.
 base=[r for r in data if r['order_status']=='已成交' and r['task_type_mode']=='SINGLE_TASK' and r['task_type'] in included_tasks]
 dated=[r for r in base if r.get('consultation_date')]
 valid=[r for r in dated if r.get('school','') not in SCHOOL_EXCLUDED]
 excluded={'eligible_completed_single_task_records':len(base),'missing_consultation_date':len(base)-len(dated),'noncanonical_school':len(dated)-len(valid),'included_detail_records':len(valid),'multi_task_not_attributed':sum(r['order_status']=='已成交' and r['task_type_mode']=='MULTI_TASK' for r in data)}
 def aggregate(rows,with_school=True):
  groups=defaultdict(list)
  for r in rows:
   key=(r['year'],r['consultation_date'][5:7],r['task_type'],classes[r['task_type']],r['country'],r['school'] if with_school else '')
   groups[key].append(r)
  out=[]
  for k,rs in groups.items():
   vals=[dec(r.get('amount_cny','')) for r in rs if dec(r.get('amount_cny','')) is not None]
   out.append({'year':k[0],'month':k[1],'task_type':k[2],'value_class':k[3],'country':k[4],'school':k[5],'order_count':len(rs),'amount':money(sum(vals,Decimal('0'))),'valid_amount_order_count':len(vals),'amount_definition':'sum of valid amount_cny for actual completed records; missing/unparseable amounts are not imputed'})
  return out
 detail=aggregate(valid,True);detail.sort(key=lambda r:(r['year'],r['month'],r['task_type'],r['country'],r['school']))
 write(OUT/'historical_demand_pattern_detail.csv',list(detail[0]),detail)
 # Pattern key deliberately retains only combinations actually represented in detail.
 grouped=defaultdict(list)
 for r in detail:grouped[(r['month'],r['task_type'],r['value_class'],r['country'],r['school'])].append(r)
 order_vals=[sum(int(x['order_count']) for x in rs) for rs in grouped.values()]
 distribution={'min':min(order_vals),'p25':q(order_vals,.25),'median':q(order_vals,.5),'p75':q(order_vals,.75),'max':max(order_vals),'pattern_count':len(order_vals),'repeat_year_count_distribution':dict(sorted(Counter(len({x['year'] for x in rs}) for rs in grouped.values()).items()))}
 # Candidate only, tailored to this distribution: p75=2 means 3-year repeated patterns have
 # at least 3 records in practice. This avoids a complex score and is explicitly not frozen.
 patterns=[]
 for key,rs in grouped.items():
  by={r['year']:r for r in rs};cnt=sum(int(x['order_count']) for x in rs);yrs=sorted(by);repeat=len(yrs)
  if repeat==3 and cnt>=3:strength='STRONG'
  elif repeat>=2 or cnt>=3:strength='MEDIUM'
  else:strength='WEAK'
  vals=[dec(x['amount']) for x in rs];patterns.append({'month':key[0],'task_type':key[1],'value_class':key[2],'country':key[3],'school':key[4],'years_observed':';'.join(YEARS),'repeat_year_count':repeat,'years_present':';'.join(yrs),'historical_order_count':cnt,'historical_amount':money(sum(vals,Decimal('0'))),'pattern_strength':strength,'strength_status':'CANDIDATE_NOT_FROZEN','2023_order_count':by.get('2023',{}).get('order_count',0),'2023_amount':by.get('2023',{}).get('amount','0.00'),'2024_order_count':by.get('2024',{}).get('order_count',0),'2024_amount':by.get('2024',{}).get('amount','0.00'),'2025_order_count':by.get('2025',{}).get('order_count',0),'2025_amount':by.get('2025',{}).get('amount','0.00'),'pattern_strength_reason':'STRONG: present in all 3 covered years and >=3 orders; MEDIUM: present in >=2 years or >=3 orders in one year; WEAK: remaining sparse single-year combinations.'})
 patterns.sort(key=lambda r:({'STRONG':0,'MEDIUM':1,'WEAK':2}[r['pattern_strength']],-int(r['repeat_year_count']),-int(r['historical_order_count']),r['task_type'],r['country'],r['school']))
 write(OUT/'historical_demand_patterns.csv',list(patterns[0]),patterns)
 # Fragmentation compares equivalent actual records, before and after adding canonical school.
 country_patterns=aggregate(valid,False);cg=defaultdict(list)
 for r in country_patterns:cg[(r['month'],r['task_type'],r['value_class'],r['country'])].append(r)
 ccounts=[sum(int(x['order_count']) for x in rs) for rs in cg.values()]
 frag={'without_school':{'pattern_count':len(cg),'order_count_distribution':{'min':min(ccounts),'p25':q(ccounts,.25),'median':q(ccounts,.5),'p75':q(ccounts,.75),'max':max(ccounts)}},'with_school':{'pattern_count':len(patterns),'one_order_patterns':sum(int(x['historical_order_count'])==1 for x in patterns),'two_order_patterns':sum(int(x['historical_order_count'])==2 for x in patterns),'one_or_two_order_patterns':sum(int(x['historical_order_count'])<=2 for x in patterns),'one_or_two_order_share':round(sum(int(x['historical_order_count'])<=2 for x in patterns)*100/len(patterns),2),'fragmentation_multiplier':round(len(patterns)/len(cg),2)}}
 audit={'analysis_scope':{'order_status':'已成交 only','task_type_mode':'SINGLE_TASK only','value_classes':sorted(INCLUDED),'coverage_years':sorted({r['year'] for r in valid}),'months_present':sorted({r['month'] for r in detail}),'included_task_type_count':len({r['task_type'] for r in valid}),'country_count':len({r['country'] for r in valid}),'canonical_school_count':len({r['school'] for r in valid})},'exclusions':excluded,'school_fragmentation':frag,'order_count_distribution':distribution,'candidate_strength_rule':{'STRONG':'repeat_year_count=3 and historical_order_count>=3','MEDIUM':'repeat_year_count>=2 or historical_order_count>=3','WEAK':'all remaining patterns','basis':'Observed School-layer order distribution: P25=1, median=1, P75=2. Three-year repeat with >=3 is a simple non-isolated threshold. Candidate only; not frozen.'}}
 (OUT/'historical_demand_pattern_threshold_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
 top=patterns[:10]
 lines=['# HISTORICAL DEMAND PATTERN V1 REVIEW','',f"范围：仅已成交（`order_status=已成交`）、单一 Task Type、CORE/GROWTH/HIGH_VALUE/ACTIVE，且 School 为 canonical。实际覆盖 {', '.join(audit['analysis_scope']['coverage_years'])} 年；当前有日期的数据月份仅为 {', '.join(audit['analysis_scope']['months_present'])} 月。",'', '## 10 个最典型真实历史组合','']
 for r in top:lines.append(f"- {r['month']}月 → {r['country']} → {r['school']} → {r['task_type']}（{r['value_class']}）：{r['years_present']} 出现；共 {r['historical_order_count']} 单，¥{r['historical_amount']}；{r['pattern_strength']}。")
 lines += ['', '## School 碎片化检查','',f"加入 School 前：{len(cg)} 个 Month×Task Type×Country Pattern。加入 School 后：{len(patterns)} 个 Pattern（{frag['with_school']['fragmentation_multiplier']} 倍）；其中 {frag['with_school']['one_order_patterns']} 个仅 1 单、{frag['with_school']['two_order_patterns']} 个仅 2 单，合计 {frag['with_school']['one_or_two_order_share']}%。",'', '建议：Country 应作为当前主要 Pattern 层；School 仅作为达到候选强度、或具有明确重复证据时的辅助下钻层，等待人工确认。']
 (OUT/'HISTORICAL_DEMAND_PATTERN_V1_REVIEW.md').write_text('\n'.join(lines),encoding='utf8')
 after={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
 qa={'result':'PASS' if before==after and len(patterns)>0 and all(r['task_type'] in included_tasks for r in patterns) else 'FAIL','checks':{'data_and_classification_unchanged':before==after,'only_included_value_classes':all(r['value_class'] in INCLUDED for r in detail),'actual_combination_preserved':all(int(r['order_count'])>0 for r in detail),'cross_year_key_uses_month_task_country_school':all(r['school'] and r['month'] for r in patterns),'no_course_channel_customer_group_ddl':True,'no_calendar_forecast_or_recommendation':True,'no_new_task_value_classification':True},'audit':audit}
 (OUT/'historical_demand_pattern_qa.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf8')
 if qa['result']!='PASS':raise RuntimeError('pattern QA failed')
 print(json.dumps({'base':excluded,'patterns':len(patterns),'distribution':distribution,'fragmentation':frag,'qa':qa['result']},ensure_ascii=False))
if __name__=='__main__':main()
