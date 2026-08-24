#!/usr/bin/env python3
"""Read-only commercial modules for Demand Insight V1."""
from __future__ import annotations
import csv, json, hashlib
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import median

ROOT=Path(__file__).resolve().parents[2]; ART=ROOT/'runs/RUN-202608-DEMAND-001/artifacts'; DATA=ART/'unified_dataset.csv'; OUT=ART/'demand_insight_v1'; LOW=5; KEY={'学年包','毕业无忧','DP'}
def read(p):
 with p.open(encoding='utf-8-sig',newline='') as h:return list(csv.DictReader(h))
def write(p,fs,rs):
 with p.open('w',encoding='utf-8-sig',newline='') as h:
  w=csv.DictWriter(h,fieldnames=fs);w.writeheader();w.writerows(rs)
def a(v):
 try:return Decimal(v) if v.strip() else None
 except (InvalidOperation,AttributeError):return None
def f(v):return format(v.quantize(Decimal('0.01')),'f')
def pc(x,d):return format((Decimal(x)*100/Decimal(d)).quantize(Decimal('0.01')),'f') if d else ''
def fl(n):return 'LOW_SAMPLE' if n<LOW else ''
def keyid(r):return (r['source_id'],r['source_row_id'])
def parse(v):
 try:return datetime.fromisoformat(v)
 except (ValueError,TypeError):return None
def main():
 before=hashlib.sha256(DATA.read_bytes()).hexdigest(); rows=read(DATA); valid=[r for r in rows if a(r.get('amount_cny','')) is not None]; total=sum(a(r['amount_cny']) for r in valid); nvalid=len(valid)
 # channel group amount contribution
 cg=defaultdict(list)
 for r in rows:cg[r['channel_group']].append(r)
 cg_out=[]
 for g,b in sorted(cg.items()):
  vb=[r for r in b if a(r.get('amount_cny','')) is not None];m=sum(a(r['amount_cny']) for r in vb)
  cg_out.append({'channel_group':g,'record_count':len(b),'valid_amount_records':len(vb),'invalid_amount_records':len(b)-len(vb),'amount_cny_sum':f(m),'amount_share':pc(m,total),'average_order_value':f(m/len(vb)) if vb else '','amount_denominator':f(total),'denominator_definition':'sum of valid amount_cny across all records','sample_flag':fl(len(b))})
 write(OUT/'channel_group_amount_analysis.csv',['channel_group','record_count','valid_amount_records','invalid_amount_records','amount_cny_sum','amount_share','average_order_value','amount_denominator','denominator_definition','sample_flag'],cg_out)
 # Key account: exact single-task amounts only; multi-task coverage intentionally not attributed.
 single_key=[r for r in rows if r['task_type_mode']=='SINGLE_TASK' and r['task_type'] in KEY]; multi_key=[]
 for r in rows:
  if r['task_type_mode']=='MULTI_TASK' and any(t in KEY for t in json.loads(r['task_type_components'])):multi_key.append(r)
 sk_valid=[r for r in single_key if a(r.get('amount_cny','')) is not None];sk_amount=sum(a(r['amount_cny']) for r in sk_valid);non_key=[r for r in valid if keyid(r) not in {keyid(x) for x in single_key}];non_key_amount=sum(a(r['amount_cny']) for r in non_key)
 ka=[]
 for t in sorted(KEY):
  b=[r for r in single_key if r['task_type']==t];vb=[r for r in b if a(r.get('amount_cny','')) is not None];m=sum(a(r['amount_cny']) for r in vb)
  ka.append({'category':'KEY_ACCOUNT_SINGLE_TASK','task_type':t,'record_count':len(b),'valid_amount_records':len(vb),'amount_cny_sum':f(m),'amount_share':pc(m,total),'average_order_value':f(m/len(vb)) if vb else '','amount_attribution_status':'SINGLE_TASK_EXACT'})
 ka.append({'category':'MULTI_TASK_AMOUNT_AMBIGUOUS','task_type':'学年包|毕业无忧|DP components','record_count':len(multi_key),'valid_amount_records':sum(a(r.get('amount_cny','')) is not None for r in multi_key),'amount_cny_sum':'','amount_share':'','average_order_value':'','amount_attribution_status':'NOT_ATTRIBUTED_TO_AVOID_DUPLICATION'})
 write(OUT/'key_account_amount_analysis.csv',['category','task_type','record_count','valid_amount_records','amount_cny_sum','amount_share','average_order_value','amount_attribution_status'],ka)
 kas={'valid_total_amount_cny':f(total),'valid_total_amount_records':nvalid,'key_account_definition':'SINGLE_TASK task_type in 学年包, 毕业无忧, DP; MULTI_TASK is coverage-only and amount is not attributed','key_account_single_task_records':len(single_key),'key_account_multi_task_coverage_records':len(multi_key),'key_account_amount_cny':f(sk_amount),'key_account_amount_share':pc(sk_amount,total),'non_key_account_amount_cny':f(non_key_amount),'non_key_account_amount_share':pc(non_key_amount,total),'key_account_channel_group_coverage':dict(Counter(r['channel_group'] for r in single_key))}
 (OUT/'key_account_amount_summary.json').write_text(json.dumps(kas,ensure_ascii=False,indent=2),encoding='utf8')
 # High-value record profile: every record carries exactly one transaction amount.
 hv=[r for r in valid if a(r['amount_cny'])>Decimal('10000')];hvm=sum(a(r['amount_cny']) for r in hv);vals=sorted(a(r['amount_cny']) for r in hv)
 basic=[{'metric':'high_value_definition','value':'amount_cny > 10000','denominator_definition':'single business record; not customer LTV'},{'metric':'high_value_record_count','value':len(hv),'denominator':nvalid,'share':pc(len(hv),nvalid)},{'metric':'high_value_amount_cny','value':f(hvm),'denominator':f(total),'share':pc(hvm,total)},{'metric':'average_amount_cny','value':f(hvm/len(hv)) if hv else ''},{'metric':'median_amount_cny','value':f(median(vals)) if vals else ''},{'metric':'max_amount_cny','value':f(vals[-1]) if vals else ''}]
 write(OUT/'high_value_customer_profile.csv',['metric','value','denominator','share','denominator_definition'],basic)
 special={'','UNKNOWN','UNSTANDARDIZED','NON_SCHOOL','NON_UNIVERSITY_ENTITY','UNRESOLVED'}
 def profile(name,field,key=lambda r:None,filterfn=lambda r:True,channelnull=False):
  source=[r for r in hv if filterfn(r)];d=defaultdict(list)
  for r in source:d[key(r)].append(r)
  o=[]
  for v,b in sorted(d.items(),key=lambda x:(-len(x[1]),str(x[0]))):
   m=sum(a(r['amount_cny']) for r in b);o.append({field:v,'record_count':len(b),'record_share':pc(len(b),len(hv)),'amount_cny_sum':f(m),'amount_share':pc(m,hvm),'record_denominator':len(hv),'amount_denominator':f(hvm),'amount_attribution_status':'RECORD_EXACT','sample_flag':fl(len(b))})
  write(OUT/name,[field,'record_count','record_share','amount_cny_sum','amount_share','record_denominator','amount_denominator','amount_attribution_status','sample_flag'],o);return o
 hschool=profile('high_value_school_profile.csv','school',lambda r:r['school'],lambda r:r.get('school','') not in special)
 hcountry=profile('high_value_country_profile.csv','country',lambda r:r['country'] or '(空值)')
 hdegree=profile('high_value_degree_profile.csv','degree_level',lambda r:r['degree_level'] or '(空值)')
 hchannelgroup=profile('high_value_channel_group_profile.csv','channel_group',lambda r:r['channel_group'])
 hchannel=profile('high_value_channel_profile.csv','channel',lambda r:(r['channel'] if r['channel'] else '(legal null secondary channel)'))
 hdept=profile('high_value_department_profile.csv','department',lambda r:r['department'])
 htime=profile('high_value_time_profile.csv','year_month',lambda r:(str(r['year'])+'-'+(parse(r.get('consultation_date','')).strftime('%m') if parse(r.get('consultation_date','')) else 'UNPARSEABLE')))
 # Task profile uses all task observations, but attributes money only to exact SINGLE_TASK values.
 tp=defaultdict(lambda:{'obs':0,'single_rows':[],'multi_ambiguous':0})
 for r in hv:
  if r['task_type_mode']=='SINGLE_TASK' and r['task_type_standardization_status']=='STANDARDIZED':tp[r['task_type']]['obs']+=1;tp[r['task_type']]['single_rows'].append(r)
  elif r['task_type_mode']=='MULTI_TASK':
   for t in json.loads(r['task_type_components']):tp[t]['obs']+=1;tp[t]['multi_ambiguous']+=1
 tout=[];tobs=sum(x['obs'] for x in tp.values())
 for t,x in sorted(tp.items(),key=lambda i:(-i[1]['obs'],i[0])):
  m=sum(a(r['amount_cny']) for r in x['single_rows']);tout.append({'task_type':t,'observation_count':x['obs'],'record_share':pc(x['obs'],tobs),'single_task_amount_cny':f(m),'single_task_amount_share':pc(m,hvm),'multi_task_amount_ambiguous_observations':x['multi_ambiguous'],'amount_attribution_status':'SINGLE_TASK_EXACT; MULTI_TASK_NOT_ATTRIBUTED','observation_denominator':tobs,'amount_denominator':f(hvm),'sample_flag':fl(x['obs'])})
 write(OUT/'high_value_task_type_profile.csv',['task_type','observation_count','record_share','single_task_amount_cny','single_task_amount_share','multi_task_amount_ambiguous_observations','amount_attribution_status','observation_denominator','amount_denominator','sample_flag'],tout)
 # Combinations: exact money only for single task; multi is represented separately as coverage, never duplicated.
 combos=[]
 for dim,fn in [('school',lambda r:r['school'] if r.get('school','') not in special else None),('country',lambda r:r['country'] or '(空值)'),('channel_group',lambda r:r['channel_group']),('channel',lambda r:r['channel'] if r['channel'] else '(legal null secondary channel)')]:
  d=defaultdict(list)
  for r in hv:
   if r['task_type_mode']=='SINGLE_TASK' and r['task_type_standardization_status']=='STANDARDIZED' and fn(r) is not None:d[(fn(r),r['task_type'])].append(r)
  for (v,t),b in sorted(d.items(),key=lambda x:(-len(x[1]),x[0])):
   m=sum(a(r['amount_cny']) for r in b);combos.append({'combination_type':dim+' × task_type','dimension_value':v,'task_type':t,'record_count':len(b),'record_share':pc(len(b),len(hv)),'amount_cny_sum':f(m),'amount_share':pc(m,hvm),'amount_attribution_status':'SINGLE_TASK_EXACT','record_denominator':len(hv),'amount_denominator':f(hvm),'sample_flag':fl(len(b))})
 write(OUT/'high_value_combination_profile.csv',['combination_type','dimension_value','task_type','record_count','record_share','amount_cny_sum','amount_share','amount_attribution_status','record_denominator','amount_denominator','sample_flag'],combos)
 # Lead time uses only stable parseable dates; urgency is <=3 calendar days, explicitly stated.
 lead=[]
 for r in hv:
  c,d=parse(r.get('consultation_date','')),parse(r.get('ddl',''))
  if c and d and (d-c).days>=0:lead.append((d-c).days)
 leadbins=Counter('0-3_days' if x<=3 else '4-7_days' if x<=7 else '8-14_days' if x<=14 else '15+_days' for x in lead)
 leadinfo={'high_value_records':len(hv),'parseable_nonnegative_lead_time_records':len(lead),'ddl_valid_rate':pc(len(lead),len(hv)),'high_urgency_definition':'lead_time <= 3 days','high_urgency_records':sum(x<=3 for x in lead),'high_urgency_share_of_lead_time_records':pc(sum(x<=3 for x in lead),len(lead)),'lead_time_distribution':dict(leadbins)}
 # Update shared overview, denominator registry and summary without altering prior insight calculations.
 ov=json.loads((OUT/'demand_overview.json').read_text(encoding='utf8'));ov['commercial_modules']={'channel_group_amount_analysis':cg_out,'key_account_summary':kas,'high_value_profile':{'summary':basic,'lead_time':leadinfo,'top_school':hschool[:3],'top_task_type':tout[:3],'top_channel_group':hchannelgroup[:3],'top_channel':hchannel[:3],'top_department':hdept[:3],'top_combination':combos[:3]}}
 (OUT/'demand_overview.json').write_text(json.dumps(ov,ensure_ascii=False,indent=2),encoding='utf8')
 den=json.loads((OUT/'dimension_denominator_summary.json').read_text(encoding='utf8'));den['commercial_modules']={'amount':{'denominator':f(total),'denominator_definition':'sum of valid amount_cny; invalid/blank amount_cny excluded','valid_amount_records':nvalid,'invalid_amount_records':len(rows)-nvalid},'high_value':{'record_denominator':nvalid,'amount_denominator':f(total),'definition':'single record amount_cny > 10000; not customer LTV'}}
 (OUT/'dimension_denominator_summary.json').write_text(json.dumps(den,ensure_ascii=False,indent=2),encoding='utf8')
 sp=OUT/'demand_insight_summary.md';s=sp.read_text(encoding='utf8').split('\n\n## 客户结构金额贡献')[0];s+='\n\n## 客户结构金额贡献\n\n'+'; '.join(f"{x['channel_group']}：{x['record_count']}条，¥{x['amount_cny_sum']}（{x['amount_share']}%），客单价 ¥{x['average_order_value']}" for x in cg_out)+'.\n\n## 大客户贡献\n\n'+f"仅按 SINGLE_TASK 精确归因：学年包／毕业无忧／DP 合计 ¥{kas['key_account_amount_cny']}（{kas['key_account_amount_share']}%）；MULTI_TASK 覆盖 {kas['key_account_multi_task_coverage_records']} 条但金额未归因。\n\n## 高价值成交画像\n\n"+f">¥10,000 的单条成交记录 {len(hv)} 条（有效金额记录的 {pc(len(hv),nvalid)}%），金额 ¥{f(hvm)}（总金额的 {pc(hvm,total)}%）。这不是客户 LTV 画像。\n"
 sp.write_text(s,encoding='utf8')
 if hashlib.sha256(DATA.read_bytes()).hexdigest()!=before:raise RuntimeError('dataset modified')
 print(json.dumps({'valid_total_amount':f(total),'key_account_amount':f(sk_amount),'high_value_records':len(hv),'high_value_amount':f(hvm)},ensure_ascii=False))
if __name__=='__main__':main()
