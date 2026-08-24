#!/usr/bin/env python3
"""Refresh Demand Insight V1 with denominator-specific shares; reads data only."""
from __future__ import annotations
import csv, hashlib, json
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]; RUN=ROOT/'runs/RUN-202608-DEMAND-001'; ART=RUN/'artifacts'; DATA=ART/'unified_dataset.csv'; OUT=ART/'demand_insight_v1'; LOW=5
def read(p):
    with p.open(encoding='utf-8-sig',newline='') as h:return list(csv.DictReader(h))
def write(p,fs,rs):
    with p.open('w',encoding='utf-8-sig',newline='') as h:
        w=csv.DictWriter(h,fieldnames=fs);w.writeheader();w.writerows(rs)
def amt(v):
    try:return Decimal(v) if v.strip() else None
    except (InvalidOperation,AttributeError):return None
def money(rows):return sum((amt(r.get('amount_cny','')) or Decimal('0') for r in rows),Decimal('0'))
def fmt(v):return format(v.quantize(Decimal('0.01')),'f')
def pct(a,b):return format((Decimal(a)*100/Decimal(b)).quantize(Decimal('0.01')),'f') if b else ''
def flag(n):return 'LOW_SAMPLE' if n<LOW else ''
def month(v):
    try:return datetime.fromisoformat(v).strftime('%Y-%m')
    except (ValueError,TypeError):return 'UNPARSEABLE_OR_BLANK'
def grouped(rows,key):
    d=defaultdict(list)
    for r in rows:d[key(r)].append(r)
    return d
def main():
    before=hashlib.sha256(DATA.read_bytes()).hexdigest(); rows=read(DATA); total=len(rows)
    if total!=818:raise RuntimeError('expected 818')
    total_money=money(rows); amount_valid=sum(amt(r.get('amount_cny','')) is not None for r in rows)
    special={'','UNKNOWN','UNSTANDARDIZED','NON_SCHOOL','NON_UNIVERSITY_ENTITY','UNRESOLVED'}
    school=[r for r in rows if r.get('school','') not in special]; school_d=grouped(school,lambda r:r['school']); school_den=len(school)
    school_out=[]
    for k,b in sorted(school_d.items(),key=lambda x:(-len(x[1]),x[0])):
        m=money(b);school_out.append({'school':k,'record_count':len(b),'record_share':pct(len(b),school_den),'amount_cny':fmt(m),'amount_share':pct(m,total_money),'denominator':school_den,'denominator_definition':'canonical-school records eligible for school-demand ranking','amount_denominator':fmt(total_money),'amount_denominator_definition':'sum of all valid amount_cny across 818 records','sample_flag':flag(len(b))})
    write(OUT/'school_demand.csv',['school','record_count','record_share','amount_cny','amount_share','denominator','denominator_definition','amount_denominator','amount_denominator_definition','sample_flag'],school_out)
    # Frozen MULTI_TASK components are expanded into separate task observations.
    task=[]
    for r in rows:
        st=r['task_type_standardization_status']
        if st=='EXCLUDED_BY_BUSINESS_RULE' or st in {'UNKNOWN','UNMATCHED','REVIEW_REQUIRED'}:continue
        if r['task_type_mode']=='MULTI_TASK':
            for t in json.loads(r['task_type_components']):task.append((t,r,'MULTI_COMPONENT'))
        elif st=='STANDARDIZED':task.append((r['task_type'],r,'SINGLE_TASK'))
    task_d=defaultdict(list);task_records=defaultdict(set);task_modes=defaultdict(Counter)
    for t,r,m in task:task_d[t].append(r);task_records[t].add((r['source_id'],r['source_row_id']));task_modes[t][m]+=1
    task_den=len(task);task_out=[]
    for t,b in sorted(task_d.items(),key=lambda x:(-len(x[1]),x[0])):
        m=money(b);task_out.append({'task_type':t,'task_type_count':len(b),'task_type_share':pct(len(b),task_den),'record_coverage_count':len(task_records[t]),'record_coverage_rate':pct(len(task_records[t]),total),'single_task_observations':task_modes[t]['SINGLE_TASK'],'multi_component_observations':task_modes[t]['MULTI_COMPONENT'],'amount_cny':fmt(m),'amount_share':pct(m,total_money),'denominator':task_den,'denominator_definition':'expanded official task_type observations; MULTI_TASK contributes one observation per frozen component; EXCLUDED omitted','record_coverage_denominator':total,'record_coverage_definition':'all business records','amount_denominator':fmt(total_money),'amount_denominator_definition':'sum of all valid amount_cny across 818 records; MULTI_TASK component amount shares can overlap','sample_flag':flag(len(b))})
    write(OUT/'task_type_demand.csv',['task_type','task_type_count','task_type_share','record_coverage_count','record_coverage_rate','single_task_observations','multi_component_observations','amount_cny','amount_share','denominator','denominator_definition','record_coverage_denominator','record_coverage_definition','amount_denominator','amount_denominator_definition','sample_flag'],task_out)
    group_d=grouped(rows,lambda r:r['channel_group']);group_out=[]
    for k,b in sorted(group_d.items(),key=lambda x:(-len(x[1]),x[0])):
        m=money(b);group_out.append({'channel_group':k,'record_count':len(b),'record_share':pct(len(b),total),'amount_cny':fmt(m),'amount_share':pct(m,total_money),'denominator':total,'denominator_definition':'all business records','amount_denominator':fmt(total_money),'amount_denominator_definition':'sum of all valid amount_cny across 818 records','sample_flag':flag(len(b))})
    write(OUT/'channel_group_demand.csv',['channel_group','record_count','record_share','amount_cny','amount_share','denominator','denominator_definition','amount_denominator','amount_denominator_definition','sample_flag'],group_out)
    known=[r for r in rows if r['channel']!=''];channel_d=grouped(known,lambda r:r['channel']);channel_out=[]
    for k,b in sorted(channel_d.items(),key=lambda x:(-len(x[1]),x[0])):
        m=money(b);channel_out.append({'channel_group':b[0]['channel_group'],'channel':k,'record_count':len(b),'share_of_all_records':pct(len(b),total),'share_of_known_channel_records':pct(len(b),len(known)),'amount_cny':fmt(m),'amount_share':pct(m,total_money),'all_records_denominator':total,'known_channel_records_denominator':len(known),'null_channel_records':total-len(known),'amount_denominator':fmt(total_money),'amount_denominator_definition':'sum of all valid amount_cny across 818 records','sample_flag':flag(len(b))})
    write(OUT/'channel_demand.csv',['channel_group','channel','record_count','share_of_all_records','share_of_known_channel_records','amount_cny','amount_share','all_records_denominator','known_channel_records_denominator','null_channel_records','amount_denominator','amount_denominator_definition','sample_flag'],channel_out)
    # Year-month shares use all records in that source year, not overall records.
    yd=grouped(rows,lambda r:(r['year'],month(r.get('consultation_date',''))));year_totals=Counter(r['year'] for r in rows);monthly=[]
    for (y,mo),b in sorted(yd.items(),key=lambda x:(x[0][0],x[0][1])):
        m=money(b);monthly.append({'year':y,'month':mo,'record_count':len(b),'record_share':pct(len(b),year_totals[y]),'share_within_year':pct(len(b),year_totals[y]),'year_record_denominator':year_totals[y],'denominator_definition':'all business records in the same source year','amount_cny':fmt(m),'amount_share':pct(m,total_money),'amount_denominator':fmt(total_money),'sample_flag':flag(len(b))})
    write(OUT/'monthly_demand_trend.csv',['year','month','record_count','record_share','share_within_year','year_record_denominator','denominator_definition','amount_cny','amount_share','amount_denominator','sample_flag'],monthly)
    valid_ddl=[r for r in rows if month(r.get('ddl',''))!='UNPARSEABLE_OR_BLANK'];invalid_ddl=[r for r in rows if month(r.get('ddl',''))=='UNPARSEABLE_OR_BLANK'];ddl_d=grouped(valid_ddl,lambda r:month(r['ddl']));ddl=[]
    for mo,b in sorted(ddl_d.items(),key=lambda x:(-len(x[1]),x[0])):
        m=money(b);ddl.append({'ddl_month':mo,'ddl_count':len(b),'ddl_share':pct(len(b),len(valid_ddl)),'valid_ddl_records':len(valid_ddl),'invalid_or_null_ddl_records':len(invalid_ddl),'denominator_definition':'records whose standardized ddl parses to a date','amount_cny':fmt(m),'amount_share':pct(m,total_money),'amount_denominator':fmt(total_money),'sample_flag':flag(len(b))})
    write(OUT/'ddl_demand_distribution.csv',['ddl_month','ddl_count','ddl_share','valid_ddl_records','invalid_or_null_ddl_records','denominator_definition','amount_cny','amount_share','amount_denominator','sample_flag'],ddl)
    school_month_cells=Counter((r['school'],r['year'],month(r.get('consultation_date',''))) for r in school); school_month=[]
    for (s,y,mo),n in sorted(school_month_cells.items(),key=lambda x:(-x[1],x[0])):
        school_month.append({'school':s,'year':y,'month':mo,'record_count':n,'share_within_school':pct(n,len(school_d[s])),'share_of_all_valid_school_records':pct(n,school_den),'school_denominator':len(school_d[s]),'all_valid_school_records_denominator':school_den,'sample_flag':flag(n)})
    write(OUT/'school_month_trend.csv',['school','year','month','record_count','share_within_school','share_of_all_valid_school_records','school_denominator','all_valid_school_records_denominator','sample_flag'],school_month)
    task_month_cells=Counter((t,r['year'],month(r.get('consultation_date',''))) for t,r,_ in task); task_month=[]
    for (t,y,mo),n in sorted(task_month_cells.items(),key=lambda x:(-x[1],x[0])):
        task_month.append({'task_type':t,'year':y,'month':mo,'task_type_observation_count':n,'share_within_task_type':pct(n,len(task_d[t])),'share_of_all_task_type_observations':pct(n,task_den),'task_type_denominator':len(task_d[t]),'all_task_type_observations_denominator':task_den,'sample_flag':flag(n)})
    write(OUT/'task_type_month_trend.csv',['task_type','year','month','task_type_observation_count','share_within_task_type','share_of_all_task_type_observations','task_type_denominator','all_task_type_observations_denominator','sample_flag'],task_month)
    def cross(name,left,left_name,entries):
        cells=Counter((left(r),t) for t,r,_ in entries); left_den=Counter(left(r) for t,r,_ in entries); all_den=sum(cells.values());out=[]
        for (a,t),n in sorted(cells.items(),key=lambda x:(-x[1],x[0])):out.append({left_name:a,'task_type':t,'combination_count':n,'share_of_'+left_name:pct(n,left_den[a]),'share_of_all_'+left_name+'_task_observations':pct(n,all_den),'left_denominator':left_den[a],'all_observations_denominator':all_den,'sample_flag':flag(n)})
        write(OUT/name,[left_name,'task_type','combination_count','share_of_'+left_name,'share_of_all_'+left_name+'_task_observations','left_denominator','all_observations_denominator','sample_flag'],out);return out,all_den
    school_task,school_task_den=cross('school_task_type_matrix.csv',lambda r:r['school'],'school',[(t,r,m) for t,r,m in task if r.get('school','') not in special])
    degree_task,degree_task_den=cross('degree_task_type_matrix.csv',lambda r:r['degree_level'] or '(空值)','degree_level',task)
    channel_task,channel_task_den=cross('channel_task_type_matrix.csv',lambda r:r['channel'] if r['channel'] else '(legal null)','channel',task)
    # Amount contribution distributions for other principal dimensions.
    for name,field,key in [('country_demand.csv','country',lambda r:r['country'] or '(空值)'),('degree_demand.csv','degree_level',lambda r:r['degree_level'] or '(空值)'),('department_demand.csv','department',lambda r:r['department'])]:
        d=grouped(rows,key);o=[]
        for v,b in sorted(d.items(),key=lambda x:(-len(x[1]),x[0])):
            m=money(b);o.append({field:v,'record_count':len(b),'record_share':pct(len(b),total),'amount_cny':fmt(m),'amount_share':pct(m,total_money),'denominator':total,'denominator_definition':'all business records','amount_denominator':fmt(total_money),'amount_denominator_definition':'sum of all valid amount_cny across 818 records','sample_flag':flag(len(b))})
        write(OUT/name,[field,'record_count','record_share','amount_cny','amount_share','denominator','denominator_definition','amount_denominator','amount_denominator_definition','sample_flag'],o)
    denominators={'total_records':total,'valid_amount_records':amount_valid,'valid_amount_cny_total':fmt(total_money),'dimensions':[{'dimension':'school','numerator_definition':'records by eligible canonical school','denominator':school_den,'denominator_definition':'canonical-school records eligible for ranking','excluded_records':total-school_den},{'dimension':'task_type','numerator_definition':'expanded official task_type observations','denominator':task_den,'denominator_definition':'SINGLE_TASK once; MULTI_TASK once per frozen component; EXCLUDED/unknown omitted','excluded_records':task_den-len(task)},{'dimension':'channel_group','numerator_definition':'records by channel_group','denominator':total,'denominator_definition':'all business records','excluded_records':0},{'dimension':'known_secondary_channel','numerator_definition':'records by explicit secondary channel','denominator':len(known),'denominator_definition':'records with non-null channel; legal new-customer null secondary omitted','excluded_records':total-len(known)},{'dimension':'ddl','numerator_definition':'records by parseable standardized DDL month','denominator':len(valid_ddl),'denominator_definition':'records whose ddl parses to a date','excluded_records':len(invalid_ddl)},{'dimension':'school_task_type','numerator_definition':'expanded task observations with eligible school','denominator':school_task_den,'denominator_definition':'same expanded task logic, restricted to eligible-school records','excluded_records':0}]}
    (OUT/'dimension_denominator_summary.json').write_text(json.dumps(denominators,ensure_ascii=False,indent=2),encoding='utf8')
    overview=json.loads((OUT/'demand_overview.json').read_text(encoding='utf8'));overview.update({'denominators':denominators,'top_10_schools':school_out[:10],'top_10_task_types':task_out[:10],'top_channels':channel_out,'top_school_task_type_combination':school_task[0] if school_task else {},'monthly_trend':monthly,'ddl_distribution':ddl,'amount_distribution':{'valid_amount_records':amount_valid,'valid_amount_cny_total':fmt(total_money)}})
    (OUT/'demand_overview.json').write_text(json.dumps(overview,ensure_ascii=False,indent=2),encoding='utf8')
    summary=f'''# Demand Insight V1 Summary — Counts and Shares

## Denominators

- Valid school records: {school_den}; excluded school records: {total-school_den}.
- Task type observations: {task_den}; MULTI_TASK is component-expanded and EXCLUDED values are omitted.
- Known secondary-channel records: {len(known)}; legal null secondary-channel records: {total-len(known)}.
- Valid DDL records: {len(valid_ddl)}; invalid or null DDL records: {len(invalid_ddl)}.
- Valid amount records: {amount_valid}; total valid amount: ¥{fmt(total_money)}.

## Main signals

- {school_out[0]['school']}: {school_out[0]['record_count']} records ({school_out[0]['record_share']}% of valid-school records).
- {task_out[0]['task_type']}: {task_out[0]['task_type_count']} observations ({task_out[0]['task_type_share']}% of task-type observations); record coverage {task_out[0]['record_coverage_rate']}%.
- 老客户: {group_out[0]['record_count'] if group_out[0]['channel_group']=='老客户' else group_out[1]['record_count']} records ({next(x['record_share'] for x in group_out if x['channel_group']=='老客户')}%); 新客户: {next(x['record_count'] for x in group_out if x['channel_group']=='新客户')} records ({next(x['record_share'] for x in group_out if x['channel_group']=='新客户')}%).
- Top school × task_type: {school_task[0]['school']} × {school_task[0]['task_type']} = {school_task[0]['combination_count']} ({school_task[0]['share_of_school']}% of that school's task observations; {school_task[0]['share_of_all_school_task_observations']}% overall).

All percentages are rounded to two decimals. Cross-year data are August extracts and are not a full-year seasonality series. `LOW_SAMPLE` marks groups with fewer than {LOW} observations.
'''
    (OUT/'demand_insight_summary.md').write_text(summary,encoding='utf8')
    if hashlib.sha256(DATA.read_bytes()).hexdigest()!=before:raise RuntimeError('dataset modified')
    print(json.dumps({'school_denominator':school_den,'task_observation_total':task_den,'known_channel_records':len(known),'valid_ddl_records':len(valid_ddl),'amount_total':fmt(total_money)},ensure_ascii=False))
if __name__=='__main__':main()
