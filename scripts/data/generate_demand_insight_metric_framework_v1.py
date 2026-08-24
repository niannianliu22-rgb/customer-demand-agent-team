#!/usr/bin/env python3
"""Framework-driven, read-only Demand Insight V1 artifact generator."""
from __future__ import annotations
import csv, hashlib, json
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[2]; ART=ROOT/'runs/RUN-202608-DEMAND-001/artifacts'; DATA=ART/'unified_dataset.csv'; OUT=ART/'demand_insight_v1'; FRAME=ROOT/'config/insight/demand_insight_metrics_v1.yaml'; YEARS=['2023','2024','2025']; LOW=5
def read(p):
 with p.open(encoding='utf-8-sig',newline='') as h:return list(csv.DictReader(h))
def write(p,fs,rs):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('w',encoding='utf-8-sig',newline='') as h:
  w=csv.DictWriter(h,fieldnames=fs);w.writeheader();w.writerows(rs)
def a(v):
 try:return Decimal(v) if v.strip() else None
 except (InvalidOperation,AttributeError):return None
def f(v):return format(v.quantize(Decimal('0.01')),'f')
def pc(x,d):return format((Decimal(x)*100/Decimal(d)).quantize(Decimal('0.01')),'f') if d else ''
def flag(n):return 'LOW_SAMPLE' if n<LOW else ''
def dt(v):
 try:return datetime.fromisoformat(v)
 except (TypeError,ValueError):return None
def ddl_stage(r):
 x=dt(r.get('ddl',''));return x.strftime('%Y-%m') if x else None
def amt(rows):return sum((a(r.get('amount_cny','')) or Decimal('0') for r in rows),Decimal('0'))
def keys(r):return (r['source_id'],r['source_row_id'])
SPECIAL={'','UNKNOWN','UNSTANDARDIZED','NON_SCHOOL','NON_UNIVERSITY_ENTITY','UNRESOLVED'}; KEY={'学年包','毕业无忧','DP'}
def task_entries(rows):
 out=[]
 for r in rows:
  if r['task_type_standardization_status']!='STANDARDIZED':continue
  if r['task_type_mode']=='MULTI_TASK':
   for t in json.loads(r['task_type_components']):out.append((t,r,'MULTI_COMPONENT'))
  else:out.append((r['task_type'],r,'SINGLE_TASK'))
 return out
def profile(rows,name,fn,eligible=lambda r:True):
 source=[r for r in rows if eligible(r)];groups=defaultdict(list)
 for r in source:groups[fn(r)].append(r)
 total_amount=amt([r for r in source if a(r.get('amount_cny','')) is not None]);valid_amount=sum(a(r.get('amount_cny','')) is not None for r in source);out=[]
 for val,b in sorted(groups.items(),key=lambda x:(-len(x[1]),str(x[0]))):
  vb=[r for r in b if a(r.get('amount_cny','')) is not None];m=amt(vb);vals=sorted(a(r['amount_cny']) for r in vb)
  out.append({'dimension':name,'value':val,'record_count':len(b),'share':pc(len(b),len(source)),'amount_cny':f(m),'amount_share':pc(m,total_amount),'average_amount':f(m/len(vb)) if vb else '','median_amount':f(vals[len(vals)//2]) if vals else '','max_amount':f(vals[-1]) if vals else '','denominator':len(source),'denominator_definition':('eligible canonical-school records' if name=='school' else 'records in this analysis scope'),'amount_denominator':f(total_amount),'valid_amount_records':valid_amount,'sample_flag':flag(len(b))})
 return out,{'dimension':name,'denominator':len(source),'denominator_definition':('eligible canonical-school records' if name=='school' else 'records in this analysis scope'),'excluded_records':len(rows)-len(source),'valid_amount_records':valid_amount,'amount_denominator':f(total_amount)}
def task_profile(rows):
 ent=task_entries(rows);d=defaultdict(list);uniq=defaultdict(set);modes=defaultdict(Counter)
 for t,r,mode in ent:d[t].append(r);uniq[t].add(keys(r));modes[t][mode]+=1
 total_amount=amt([r for r in rows if a(r.get('amount_cny','')) is not None]);out=[]
 for t,b in sorted(d.items(),key=lambda x:(-len(x[1]),x[0])):
  singles=[r for r in b if r['task_type_mode']=='SINGLE_TASK' and a(r.get('amount_cny','')) is not None];m=amt(singles)
  out.append({'dimension':'task_type','value':t,'observation_count':len(b),'share':pc(len(b),len(ent)),'record_coverage_count':len(uniq[t]),'record_coverage_share':pc(len(uniq[t]),len(rows)),'single_task_amount_cny':f(m),'single_task_amount_share':pc(m,total_amount),'single_task_observations':modes[t]['SINGLE_TASK'],'multi_task_observations':modes[t]['MULTI_COMPONENT'],'denominator':len(ent),'denominator_definition':'official task observations; MULTI_TASK expanded by frozen components; excluded statuses omitted','amount_denominator':f(total_amount),'amount_rule':'SINGLE_TASK exact only; MULTI_TASK amount unallocated','sample_flag':flag(len(b))})
 return out,{'dimension':'task_type','denominator':len(ent),'denominator_definition':'official task observations; MULTI_TASK expanded by frozen components; excluded statuses omitted','excluded_records':len(rows)-len({keys(r) for _,r,_ in ent}),'amount_denominator':f(total_amount)}
def scope_outputs(rows,path,scope):
 path.mkdir(parents=True,exist_ok=True);meta={'scope':scope,'record_count':len(rows),'framework':str(FRAME.relative_to(ROOT)),'dimensions':[]}
 dimensions=[('country',lambda r:r['country'] or '(空值)',lambda r:True),('school',lambda r:r['school'],lambda r:r.get('school','') not in SPECIAL),('degree_level',lambda r:r['degree_level'] or '(空值)',lambda r:True),('channel_group',lambda r:r['channel_group'],lambda r:True),('channel',lambda r:r['channel'],lambda r:r['channel']!=''),('ddl',lambda r:ddl_stage(r),lambda r:ddl_stage(r) is not None)]
 for name,fn,ok in dimensions:
  o,m=profile(rows,name,fn,ok);write(path/f'{name}_profile.csv',list(o[0]) if o else ['dimension','value','record_count','share','amount_cny','amount_share','average_amount','median_amount','max_amount','denominator','denominator_definition','amount_denominator','valid_amount_records','sample_flag'],o);meta['dimensions'].append(m)
 t,tm=task_profile(rows);write(path/'task_type_profile.csv',list(t[0]) if t else ['dimension','value','observation_count','share','record_coverage_count','record_coverage_share','single_task_amount_cny','single_task_amount_share','single_task_observations','multi_task_observations','denominator','denominator_definition','amount_denominator','amount_rule','sample_flag'],t);meta['dimensions'].append(tm)
 (path/'metric_scope_metadata.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf8');return meta
def crosses(rows,path,scope):
 ent=task_entries(rows);out=[]
 defs=[('year_x_school_x_task_type',lambda r:r['school'] if r.get('school','') not in SPECIAL else None),('year_x_task_type_x_ddl',lambda r:ddl_stage(r)),('year_x_school_x_ddl',lambda r:r['school'] if r.get('school','') not in SPECIAL else None),('year_x_channel_x_task_type',lambda r:r['channel'] if r['channel'] else None),('year_x_customer_group_x_task_type',lambda r:r['channel_group'])]
 for name,fn in defs:
  d=Counter()
  if name=='year_x_school_x_ddl':
   for r in rows:
    if fn(r) and ddl_stage(r):d[(str(r['year']),fn(r),ddl_stage(r))]+=1
   for (y,x,z),n in d.items():out.append({'analysis':name,'year':y,'dimension_value':x,'task_type_or_ddl':z,'record_count':n,'share':pc(n,len(rows)),'amount_cny':f(Decimal('0')),'amount_rule':'count_only','sample_flag':flag(n)})
  else:
   for t,r,_ in ent:
    x=fn(r); z=ddl_stage(r) if name=='year_x_task_type_x_ddl' else t
    if x is not None and z is not None:d[(str(r['year']),x,z)]+=1
   for (y,x,z),n in d.items():out.append({'analysis':name,'year':y,'dimension_value':x,'task_type_or_ddl':z,'record_count':n,'share':'','amount_cny':'','amount_rule':'task_amount_not_allocated_for_cross','sample_flag':flag(n)})
 # value label crosses, exact amounts restricted to single records.
 for tag,pred in [('year_x_key_account_x_school',lambda r:r['task_type_mode']=='SINGLE_TASK' and r['task_type'] in KEY),('year_x_high_value_x_school',lambda r:a(r.get('amount_cny','')) is not None and a(r['amount_cny'])>10000),('year_x_high_value_x_task_type',lambda r:a(r.get('amount_cny','')) is not None and a(r['amount_cny'])>10000 and r['task_type_mode']=='SINGLE_TASK'),('year_x_high_value_x_channel',lambda r:a(r.get('amount_cny','')) is not None and a(r['amount_cny'])>10000)]:
  d=defaultdict(list)
  for r in rows:
   if pred(r):
    v=r['school'] if tag.endswith('_school') else r['task_type'] if tag.endswith('_task_type') else r['channel'] if r['channel'] else '(legal null)';d[(str(r['year']),v)].append(r)
  for (y,v),b in d.items():out.append({'analysis':tag,'year':y,'dimension_value':v,'task_type_or_ddl':'','record_count':len(b),'share':'','amount_cny':f(amt(b)),'amount_rule':'SINGLE_TASK_EXACT' if 'task_type' in tag or 'key_account' in tag else 'RECORD_EXACT','sample_flag':flag(len(b))})
 write(path/'fixed_cross_analyses.csv',['analysis','year','dimension_value','task_type_or_ddl','record_count','share','amount_cny','amount_rule','sample_flag'],out)
def key_output(rows,path,scope):
 multi=[];single=[]
 for r in rows:
  if r['task_type_mode']=='SINGLE_TASK' and r['task_type'] in KEY:single.append(r)
  elif r['task_type_mode']=='MULTI_TASK' and any(t in KEY for t in json.loads(r['task_type_components'])):multi.append(r)
 total=amt([r for r in rows if a(r.get('amount_cny','')) is not None]);out=[]
 for t in sorted(KEY):
  b=[r for r in single if r['task_type']==t];vb=[r for r in b if a(r.get('amount_cny','')) is not None];m=amt(vb);out.append({'scope':scope,'key_account':t,'record_count':len(b),'record_share':pc(len(b),len(rows)),'valid_amount_records':len(vb),'amount_cny':f(m),'amount_share':pc(m,total),'average_amount':f(m/len(vb)) if vb else '','amount_rule':'SINGLE_TASK_EXACT','denominator':len(rows),'amount_denominator':f(total),'multi_task_coverage_count':0,'sample_flag':flag(len(b))})
 m=amt([r for r in single if a(r.get('amount_cny','')) is not None]);out.append({'scope':scope,'key_account':'KEY_ACCOUNT_TOTAL_SINGLE_TASK','record_count':len(single),'record_share':pc(len(single),len(rows)),'valid_amount_records':sum(a(r.get('amount_cny','')) is not None for r in single),'amount_cny':f(m),'amount_share':pc(m,total),'average_amount':'','amount_rule':'SINGLE_TASK_EXACT','denominator':len(rows),'amount_denominator':f(total),'multi_task_coverage_count':len(multi),'sample_flag':''})
 write(path/'key_account_annual.csv',list(out[0]),out)
def high_output(rows,path,scope):
 valid=[r for r in rows if a(r.get('amount_cny','')) is not None];hv=[r for r in valid if a(r['amount_cny'])>10000];m=amt(hv);vals=sorted(a(r['amount_cny']) for r in hv)
 base=[{'scope':scope,'metric':'high_value_transaction','record_count':len(hv),'record_share':pc(len(hv),len(valid)),'amount_cny':f(m),'amount_share':pc(m,amt(valid)),'average_amount':f(m/len(hv)) if hv else '','median_amount':f(vals[len(vals)//2]) if vals else '','max_amount':f(vals[-1]) if vals else '','record_denominator':len(valid),'amount_denominator':f(amt(valid)),'definition':'amount_cny > 10000; transaction, not customer LTV'}]
 write(path/'high_value_annual.csv',list(base[0]),base)
 for name,fn,ok in [('country',lambda r:r['country'] or '(空值)',lambda r:True),('school',lambda r:r['school'],lambda r:r.get('school','') not in SPECIAL),('degree_level',lambda r:r['degree_level'] or '(空值)',lambda r:True),('customer_group',lambda r:r['channel_group'],lambda r:True),('channel',lambda r:r['channel'] if r['channel'] else '(legal null)',lambda r:True),('ddl',lambda r:ddl_stage(r) or 'UNPARSEABLE_OR_BLANK',lambda r:True)]:
  o,_=profile([r for r in hv if ok(r)],name,fn);write(path/f'high_value_{name}.csv',list(o[0]) if o else ['dimension','value','record_count','share','amount_cny','amount_share','average_amount','median_amount','max_amount','denominator','denominator_definition','amount_denominator','valid_amount_records','sample_flag'],o)
def main():
 before=hashlib.sha256(DATA.read_bytes()).hexdigest();frame=yaml.safe_load(FRAME.read_text(encoding='utf8'));rows=read(DATA)
 if frame['status']!='FROZEN' or len(rows)!=818:raise RuntimeError('framework/data precondition failed')
 overall=scope_outputs(rows,OUT/'overall','Combined 2023-2025 August cohorts');crosses(rows,OUT/'trend','Combined');key_output(rows,OUT/'key_account','Combined');high_output(rows,OUT/'high_value','Combined')
 annual={}
 for y in YEARS:
  b=[r for r in rows if r['year']==y];annual[y]=scope_outputs(b,OUT/y,f'{y}-08 cohort');key_output(b,OUT/'key_account'/y,f'{y}-08');high_output(b,OUT/'high_value'/y,f'{y}-08')
 # Same-period trend values; labels compare adjacent August cohorts on both count and share.
 trend=[]
 for dim,fn,ok in [('total',lambda r:'ALL',lambda r:True),('country',lambda r:r['country'] or '(空值)',lambda r:True),('school',lambda r:r['school'],lambda r:r.get('school','') not in SPECIAL),('degree_level',lambda r:r['degree_level'] or '(空值)',lambda r:True),('channel',lambda r:r['channel'] if r['channel'] else '(legal null)',lambda r:True)]:
  counts={y:Counter(fn(r) for r in rows if r['year']==y and ok(r)) for y in YEARS};den={y:sum(counts[y].values()) for y in YEARS}
  for value in set().union(*[set(c) for c in counts.values()]):
   for prev,curr in zip(YEARS,YEARS[1:]):
    a1,a2=counts[prev][value],counts[curr][value];s1=Decimal(a1)/den[prev] if den[prev] else 0;s2=Decimal(a2)/den[curr] if den[curr] else 0
    label='LOW_SAMPLE' if max(a1,a2)<LOW else 'NEW' if a1==0 and a2>=LOW else 'RISING' if a2>a1 and s2>s1 else 'DECLINING' if a2<a1 and s2<s1 else 'STABLE'
    trend.append({'dimension':dim,'value':value,'from_year':prev,'to_year':curr,'from_count':a1,'to_count':a2,'from_share':pc(a1,den[prev]),'to_share':pc(a2,den[curr]),'trend_label':label,'denominator_definition':'same-year August cohort within dimension'})
 write(OUT/'trend'/'same_period_trends.csv',['dimension','value','from_year','to_year','from_count','to_count','from_share','to_share','trend_label','denominator_definition'],trend)
 # QA explicitly validates core framework constraints.
 qa={'framework_version':frame['framework_version'],'result':'PASS','checks':{'combined_record_count_818':len(rows)==818,'annual_record_counts_match_combined':sum(m['record_count'] for m in annual.values())==len(rows),'metric_scope_metadata_present':all((OUT/x/'metric_scope_metadata.json').is_file() for x in ['overall',*YEARS]),'channel_group_counts_match':sum(int(r['record_count']) for r in read(OUT/'overall'/'channel_group_profile.csv'))==818,'legal_null_channel_not_named':all(r['value']!='未知来源' for r in read(OUT/'overall'/'channel_profile.csv')),'department_not_in_framework_dimensions':'department' not in frame['core_dimensions'],'course_not_in_framework_dimensions':not any(x in frame['core_dimensions'] for x in ['course_name','course_code']),'multi_task_amount_not_allocated':all(r['amount_rule']=='SINGLE_TASK_EXACT' or r['amount_rule']=='RECORD_EXACT' or r['amount_rule']=='count_only' or r['amount_rule']=='task_amount_not_allocated_for_cross' for r in read(OUT/'trend'/'fixed_cross_analyses.csv')),'dataset_unchanged':hashlib.sha256(DATA.read_bytes()).hexdigest()==before}}
 qa['result']='PASS' if all(qa['checks'].values()) else 'FAIL';(OUT/'demand_insight_metric_qa.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf8')
 overview_path=OUT/'demand_overview.json';ov=json.loads(overview_path.read_text(encoding='utf8'));ov['metric_framework']={'version':'1.0','status':'FROZEN','path':str(FRAME.relative_to(ROOT)),'official_artifact_structure':['overall','2023','2024','2025','trend','high_value','key_account'],'metric_qa':qa['result']};overview_path.write_text(json.dumps(ov,ensure_ascii=False,indent=2),encoding='utf8')
 summary=OUT/'demand_insight_summary.md';summary.write_text(summary.read_text(encoding='utf8')+'\n\n## Demand Insight Metric Framework V1.0\n\nOfficial analysis now follows the frozen Metric Framework V1.0. It uses only 2023–2025 August same-period cohorts; department and course dimensions are excluded from V1 customer-demand conclusions. Metric QA: '+qa['result']+'.\n',encoding='utf8')
 if qa['result']!='PASS':raise RuntimeError('metric QA failed')
 print(json.dumps({'framework':frame['framework_version'],'qa':qa['result'],'rows':len(rows)},ensure_ascii=False))
if __name__=='__main__':main()
