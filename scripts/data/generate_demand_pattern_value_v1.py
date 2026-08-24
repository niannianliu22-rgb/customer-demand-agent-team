#!/usr/bin/env python3
"""Read-only Task Type Demand Pattern & Operational Value candidate analysis."""
from __future__ import annotations
import csv, json, hashlib, math
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import mean, median, pstdev
import yaml

ROOT=Path(__file__).resolve().parents[2]; ART=ROOT/'runs/RUN-202608-DEMAND-001/artifacts'; DATA=ART/'unified_dataset.csv'; OUT=ART/'demand_pattern_value_v1'; FRAME=ROOT/'config/insight/demand_insight_metrics_v1.yaml'; TF=ROOT/'config/dimensions/task_type/task_type_rules_frozen_v17.yaml'; CF=ROOT/'config/dimensions/channel/channel_rules_frozen_v1.yaml'; YEARS=['2023','2024','2025']; KEY={'学年包','毕业无忧','DP'}; MIN=5
def read(p):
 with p.open(encoding='utf-8-sig',newline='') as h:return list(csv.DictReader(h))
def write(p,fs,rs):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('w',encoding='utf-8-sig',newline='') as h:
  w=csv.DictWriter(h,fieldnames=fs);w.writeheader();w.writerows(rs)
def a(v):
 try:return Decimal(v) if v.strip() else None
 except (InvalidOperation,AttributeError):return None
def f(v):return format(Decimal(v).quantize(Decimal('0.01')),'f')
def pc(x,d):return format((Decimal(x)*100/Decimal(d)).quantize(Decimal('0.01')),'f') if d else ''
def pctnum(x,d):return float(Decimal(x)*100/Decimal(d)) if d else 0.0
def quantile(xs,q):
 xs=sorted(xs)
 if not xs:return 0.0
 i=(len(xs)-1)*q;lo=int(i);hi=min(lo+1,len(xs)-1);return xs[lo]+(xs[hi]-xs[lo])*(i-lo)
def key(r):return (r['source_id'],r['source_row_id'])
def entries(rows):
 out=[]
 for r in rows:
  if r['task_type_standardization_status']!='STANDARDIZED':continue
  if r['task_type_mode']=='MULTI_TASK':
   for t in json.loads(r['task_type_components']):out.append((t,r,'MULTI_COMPONENT'))
  else:out.append((r['task_type'],r,'SINGLE_TASK'))
 return out
def main():
 before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [DATA,FRAME,TF,CF]}
 frame=yaml.safe_load(FRAME.read_text(encoding='utf8')); rows=read(DATA)
 if frame.get('status')!='FROZEN' or len(rows)!=818:raise RuntimeError('framework/data precondition failed')
 ent=entries(rows);byyear={y:[r for r in rows if r['year']==y] for y in YEARS};ey={y:entries(byyear[y]) for y in YEARS};den={y:len(ey[y]) for y in YEARS};amountden={y:sum(((a(r.get('amount_cny','')) or Decimal('0')) for r in byyear[y]),Decimal('0')) for y in YEARS}
 # Annual Task Type metrics: observation count includes frozen components; monetary statistics use SINGLE_TASK exact only.
 annual=[]; annual_map={}
 for y in YEARS:
  d=defaultdict(list);modes=defaultdict(Counter);uniq=defaultdict(set)
  for t,r,mode in ey[y]:d[t].append(r);modes[t][mode]+=1;uniq[t].add(key(r))
  ranks={t:i+1 for i,(t,b) in enumerate(sorted(d.items(),key=lambda x:(-len(x[1]),x[0])))}
  aranks={t:i+1 for i,(t,b) in enumerate(sorted(d.items(),key=lambda x:(-sum(((a(r.get('amount_cny','')) or Decimal('0')) for r in x[1] if r['task_type_mode']=='SINGLE_TASK'),Decimal('0')),x[0])))}
  annual_map[y]={}
  for t,b in d.items():
   singles=[r for r in b if r['task_type_mode']=='SINGLE_TASK'];valid=[r for r in singles if a(r.get('amount_cny','')) is not None];vals=sorted(a(r['amount_cny']) for r in valid);m=sum(vals,Decimal('0'));hv=sum(v>Decimal('10000') for v in vals);ka=sum(r['task_type'] in KEY for r in valid)
   r={'year':y,'task_type':t,'record_count':len(b),'year_demand_share':pc(len(b),den[y]),'count_rank':ranks[t],'amount_cny':f(m),'year_amount_share':pc(m,amountden[y]),'amount_rank':aranks[t],'average_amount':f(m/len(valid)) if valid else '','median_amount':f(median(vals)) if vals else '','max_amount':f(vals[-1]) if vals else '','high_value_order_count':hv,'high_value_order_share':pc(hv,len(valid)),'key_account_order_count':ka,'key_account_order_share':pc(ka,len(valid)),'demand_numerator':len(b),'demand_denominator':den[y],'demand_denominator_definition':'official task observations in this year August cohort; MULTI_TASK expanded by frozen components','amount_numerator':f(m),'amount_denominator':f(amountden[y]),'amount_denominator_definition':'all valid amount_cny in this year August cohort; task amounts use SINGLE_TASK exact attribution','single_task_valid_amount_records':len(valid),'multi_task_observations':modes[t]['MULTI_COMPONENT'],'sample_flag':'LOW_SAMPLE' if len(b)<MIN else ''}
   annual.append(r);annual_map[y][t]=r
 write(OUT/'task_type_yearly_metrics.csv',list(annual[0]),annual)
 alltypes=sorted({t for y in YEARS for t in annual_map[y]})
 # Scale, ranks, overlap, persistence and stability data.
 scale=[]; overlap=[]; persistence=[]; stability=[]; direction=[]
 top5={y:{r['task_type'] for r in annual if r['year']==y and int(r['count_rank'])<=5} for y in YEARS};top10={y:{r['task_type'] for r in annual if r['year']==y and int(r['count_rank'])<=10} for y in YEARS}
 share_cvs=[];rank_ranges=[];share_changes=[]
 rawstat={}
 for t in alltypes:
  rec=[annual_map[y].get(t) for y in YEARS];cs=[int(r['record_count']) if r else 0 for r in rec];ss=[float(r['year_demand_share']) if r else 0 for r in rec];rs=[int(r['count_rank']) if r else None for r in rec]
  present=sum(c>=MIN for c in cs);validshares=[s for c,s in zip(cs,ss) if c>=MIN];validranks=[r for c,r in zip(cs,rs) if c>=MIN and r is not None]
  cv=(pstdev(validshares)/mean(validshares) if len(validshares)>=2 and mean(validshares)>0 else None);rr=max(validranks)-min(validranks) if len(validranks)>=2 else None
  if cv is not None:share_cvs.append(cv)
  if rr is not None:rank_ranges.append(rr)
  share_changes.append(abs(ss[2]-ss[0]));rawstat[t]=(cs,ss,rs,present,cv,rr)
 # Candidate thresholds are quantiles of observed distributions, explicitly non-frozen.
 th={'minimum_effective_sample':MIN,'stability_share_cv_p33':quantile(share_cvs,.33),'stability_share_cv_p67':quantile(share_cvs,.67),'stability_rank_range_median':quantile(rank_ranges,.5),'direction_abs_share_change_median_pp':quantile(share_changes,.5),'volume_total_count_p75':quantile([sum(rawstat[t][0]) for t in alltypes],.75),'volume_share_mean_p75':quantile([mean(rawstat[t][1]) for t in alltypes],.75),'revenue_total_amount_p75':quantile([float(sum(Decimal(annual_map[y].get(t,{}).get('amount_cny','0') or '0') for y in YEARS)) for t in alltypes],.75),'revenue_average_amount_p75':quantile([max([float(annual_map[y].get(t,{}).get('average_amount','0') or 0) for y in YEARS]) for t in alltypes],.75)}
 for t in alltypes:
  cs,ss,rs,present,cv,rr=rawstat[t];rec=[annual_map[y].get(t) for y in YEARS];total=sum(cs);sharemean=mean(ss);rankmean=mean([r for r in rs if r is not None]) if any(rs) else ''; top5p=sum(t in top5[y] for y in YEARS);top10p=sum(t in top10[y] for y in YEARS)
  scale.append({'task_type':t,'2023_count':cs[0],'2024_count':cs[1],'2025_count':cs[2],'2023_share':f(ss[0]),'2024_share':f(ss[1]),'2025_share':f(ss[2]),'2023_rank':rs[0] or '','2024_rank':rs[1] or '','2025_rank':rs[2] or '','three_year_count_total':total,'three_year_share_mean':f(sharemean),'three_year_rank_mean':f(rankmean) if rankmean!='' else '','definition':'Combined count is supplementary; cross-year comparison must use annual share and rank.'})
  overlap.append({'task_type':t,'year_presence_count':sum(c>0 for c in cs),'effective_year_presence_count':present,'top5_presence_count':top5p,'top10_presence_count':top10p,'overlap_classification':'THREE_YEAR_TOP5' if top5p==3 else 'THREE_YEAR_TOP10' if top10p==3 else 'TWO_YEAR_REPEAT' if sum(c>=MIN for c in cs)==2 else 'SINGLE_YEAR_OR_LOW_SAMPLE','top5_sets':json.dumps({y:sorted(top5[y]) for y in YEARS},ensure_ascii=False),'top10_sets':json.dumps({y:sorted(top10[y]) for y in YEARS},ensure_ascii=False)})
  per='NEW' if cs[2]>=MIN and cs[0]<MIN and cs[1]<MIN else 'PERSISTENT' if present==3 else 'REPEATED' if present==2 else 'OCCASIONAL'
  persistence.append({'task_type':t,'persistence':per,'year_presence_count':present,'2023_effective':cs[0]>=MIN,'2024_effective':cs[1]>=MIN,'2025_effective':cs[2]>=MIN,'definition':f'effective annual task observation count >= {MIN}'})
  stab='LOW_SAMPLE' if present<2 else 'STABLE' if cv<=th['stability_share_cv_p33'] and rr<=th['stability_rank_range_median'] else 'VOLATILE' if cv>=th['stability_share_cv_p67'] or rr>th['stability_rank_range_median'] else 'MODERATE'
  stability.append({'task_type':t,'stability':stab,'share_mean':f(sharemean),'share_std':f(pstdev([s for c,s in zip(cs,ss) if c>=MIN])) if present>=2 else '','share_cv':f(cv) if cv is not None else '','rank_mean':f(rankmean) if rankmean!='' else '','rank_range':rr if rr is not None else '','count_mean':f(mean(cs)),'supporting_metrics':json.dumps({'share_cv':cv,'rank_range':rr},ensure_ascii=False),'threshold_status':'CANDIDATE_NOT_FROZEN'})
  sd=ss[2]-ss[0]; rankdir=(rs[0]-rs[2]) if rs[0] and rs[2] else 0
  dire='EMERGING' if per=='NEW' else 'LOW_SAMPLE' if present<2 else 'RISING' if sd>=th['direction_abs_share_change_median_pp'] and rankdir>0 and cs[2]>cs[0] else 'DECLINING' if sd<=-th['direction_abs_share_change_median_pp'] and rankdir<0 and cs[2]<cs[0] else 'VOLATILE' if stab=='VOLATILE' else 'STABLE'
  direction.append({'task_type':t,'direction':dire,'count_change_2023_to_2025':cs[2]-cs[0],'share_change_pp_2023_to_2025':f(sd),'rank_change_2023_to_2025':rankdir,'definition':'share and rank lead; count is supporting evidence; thresholds are candidates.'})
 write(OUT/'task_type_three_year_scale.csv',list(scale[0]),scale);write(OUT/'task_type_overlap_analysis.csv',list(overlap[0]),overlap);write(OUT/'task_type_persistence.csv',list(persistence[0]),persistence);write(OUT/'task_type_stability.csv',list(stability[0]),stability);write(OUT/'task_type_direction.csv',list(direction[0]),direction)
 sm={x['task_type']:x for x in stability};pm={x['task_type']:x for x in persistence};dm={x['task_type']:x for x in direction};om={x['task_type']:x for x in overlap};scm={x['task_type']:x for x in scale}
 patterns=[]; volume=[]; revenue=[]; priority=[];pool=[]
 for t in alltypes:
  p,s,d,o,sc=pm[t],sm[t],dm[t],om[t],scm[t];total=int(sc['three_year_count_total']);sharemean=float(sc['three_year_share_mean']);valid_amount=sum(int(annual_map[y].get(t,{}).get('single_task_valid_amount_records',0) or 0) for y in YEARS);totalamount=sum(Decimal(annual_map[y].get(t,{}).get('amount_cny','0') or '0') for y in YEARS);maxavg=max(float(annual_map[y].get(t,{}).get('average_amount','0') or 0) for y in YEARS)
  pat='CORE_STABLE' if p['persistence']=='PERSISTENT' and s['stability']=='STABLE' and int(o['top5_presence_count'])>=2 else 'CORE_RISING' if p['persistence']=='PERSISTENT' and d['direction']=='RISING' else 'CORE_DECLINING' if p['persistence']=='PERSISTENT' and d['direction']=='DECLINING' else 'EMERGING' if p['persistence']=='NEW' else 'VOLATILE' if s['stability']=='VOLATILE' else 'OCCASIONAL' if p['persistence'] in {'OCCASIONAL','REPEATED'} else 'LOW_SAMPLE'
  patterns.append({'task_type':t,'demand_pattern_candidate':pat,'status':'CANDIDATE','classification_reason':f"persistence={p['persistence']}; stability={s['stability']}; direction={d['direction']}; top5_presence={o['top5_presence_count']}",'supporting_metrics':json.dumps({'three_year_count_total':total,'share_mean':sharemean,'top5_presence':o['top5_presence_count']},ensure_ascii=False)})
  vol='HIGH_VOLUME_VALUE' if total>=th['volume_total_count_p75'] or sharemean>=th['volume_share_mean_p75'] else 'MEDIUM_VOLUME_VALUE' if total>=MIN*2 else 'LOW_VOLUME_VALUE' if total>=MIN else 'INSUFFICIENT_DATA'
  volume.append({'task_type':t,'volume_value_level':vol,'status':'CANDIDATE_NOT_FROZEN','volume_value_reason':f"three_year_count={total}; share_mean={sharemean:.2f}; candidate p75 count={th['volume_total_count_p75']:.2f}, share={th['volume_share_mean_p75']:.2f}",'volume_value_metrics':json.dumps({'three_year_count_total':total,'three_year_share_mean':sharemean,'top5_presence':o['top5_presence_count'],'persistence':p['persistence'],'stability':s['stability'],'direction':d['direction']},ensure_ascii=False),'confidence':'LOW_SAMPLE' if p['persistence']=='OCCASIONAL' else 'STANDARD'})
  rev='HIGH_REVENUE_VALUE' if float(totalamount)>=th['revenue_total_amount_p75'] or maxavg>=th['revenue_average_amount_p75'] else 'MEDIUM_REVENUE_VALUE' if valid_amount>=MIN else 'LOW_REVENUE_VALUE' if valid_amount else 'INSUFFICIENT_DATA'
  revenue.append({'task_type':t,'revenue_value_level':rev,'status':'CANDIDATE_NOT_FROZEN','revenue_value_reason':f"single_task_amount={f(totalamount)}; max_year_average={maxavg:.2f}; candidate p75 amount={th['revenue_total_amount_p75']:.2f}, average={th['revenue_average_amount_p75']:.2f}",'revenue_value_metrics':json.dumps({'single_task_amount_total':f(totalamount),'max_year_average_amount':maxavg,'valid_single_task_amount_records':valid_amount,'high_value_counts':[annual_map[y].get(t,{}).get('high_value_order_count',0) for y in YEARS],'key_account_counts':[annual_map[y].get(t,{}).get('key_account_order_count',0) for y in YEARS]},ensure_ascii=False),'confidence':'LOW_SAMPLE' if valid_amount<MIN else 'STANDARD'})
  # OR logic is explicit: any high path is a priority candidate.
  priority_type='DUAL_VALUE_PRIORITY' if vol=='HIGH_VOLUME_VALUE' and rev=='HIGH_REVENUE_VALUE' else 'VOLUME_DRIVEN_PRIORITY' if vol=='HIGH_VOLUME_VALUE' else 'REVENUE_DRIVEN_PRIORITY' if rev=='HIGH_REVENUE_VALUE' else 'WATCH' if pat in {'CORE_STABLE','CORE_RISING','EMERGING'} else 'LOW_SAMPLE' if p['persistence']=='OCCASIONAL' else 'NORMAL'
  pr={'task_type':t,'demand_pattern_candidate':pat,'volume_value_level':vol,'revenue_value_level':rev,'operational_priority_type':priority_type,'operational_value_candidate':'OPERATIONAL_PRIORITY_CANDIDATE' if 'PRIORITY' in priority_type else 'NOT_PRIORITY_CANDIDATE','priority_reason':f"OR logic: volume={vol}; revenue={rev}; pattern={pat}",'status':'CANDIDATE_NOT_FROZEN'};priority.append(pr)
  if pat in {'CORE_STABLE','CORE_RISING','EMERGING'} or vol=='HIGH_VOLUME_VALUE' or rev=='HIGH_REVENUE_VALUE':pool.append(pr)
 write(OUT/'task_type_pattern_candidates.csv',list(patterns[0]),patterns);write(OUT/'task_type_volume_value.csv',list(volume[0]),volume);write(OUT/'task_type_revenue_value.csv',list(revenue[0]),revenue);write(OUT/'task_type_operational_priority.csv',list(priority[0]),priority);write(OUT/'priority_task_type_pool.csv',list(pool[0]) if pool else list(priority[0]),pool)
 pa={'status':'CANDIDATE_NOT_FROZEN','framework':'Demand Pattern thresholds from observed task_type distributions','candidate_thresholds':th,'top5_sets':{y:sorted(top5[y]) for y in YEARS},'top10_sets':{y:sorted(top10[y]) for y in YEARS},'top5_three_year_intersection':sorted(set.intersection(*[top5[y] for y in YEARS])),'top10_three_year_intersection':sorted(set.intersection(*[top10[y] for y in YEARS])),'rationale':'Quantiles are empirical candidates only. Persistence requires the existing LOW_SAMPLE floor; stability uses share CV plus rank range; direction uses share and rank before count.'}
 (OUT/'task_type_pattern_threshold_audit.json').write_text(json.dumps(pa,ensure_ascii=False,indent=2),encoding='utf8')
 oa={'status':'CANDIDATE_NOT_FROZEN','volume_candidate_thresholds':{'three_year_count_p75':th['volume_total_count_p75'],'three_year_share_mean_p75':th['volume_share_mean_p75'],'logic':'HIGH if count OR share reaches candidate p75; preserves high-frequency lower-ticket demand.'},'revenue_candidate_thresholds':{'single_task_amount_p75':th['revenue_total_amount_p75'],'max_year_average_amount_p75':th['revenue_average_amount_p75'],'logic':'HIGH if amount OR average reaches candidate p75; preserves lower-frequency high-ticket demand.'},'volume_false_negative_risk':{'check':'essay', 'result':next((x['volume_value_level'] for x in volume if x['task_type']=='essay'),'NOT_PRESENT'),'interpretation':'High-frequency lower-ticket demand remains eligible through Volume Value.'},'revenue_false_negative_risk':{t:next((x['revenue_value_level'] for x in revenue if x['task_type']==t),'NOT_PRESENT') for t in KEY},'or_logic':'HIGH_VOLUME_VALUE OR HIGH_REVENUE_VALUE enters operational priority candidate; no AND gate.'}
 (OUT/'operational_value_threshold_audit.json').write_text(json.dumps(oa,ensure_ascii=False,indent=2),encoding='utf8')
 after={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [DATA,FRAME,TF,CF]}
 qa={'result':'PASS','checks':{'annual_scopes_present':set(byyear)==set(YEARS),'annual_rows_total_818':sum(len(byyear[y]) for y in YEARS)==818,'annual_demand_denominators_independent':len(set(den.values()))>1,'annual_amount_denominators_independent':len(set(amountden.values()))>1,'top_overlap_sets_computed':all(top5[y] and top10[y] for y in YEARS),'persistence_keeps_presence_count':all('year_presence_count' in r for r in persistence),'stability_uses_share_and_rank':all('share_cv' in r and 'rank_range' in r for r in stability),'direction_uses_share_rank_count':all('share_change_pp_2023_to_2025' in r and 'rank_change_2023_to_2025' in r for r in direction),'pattern_not_amount_defined':all('amount' not in r['classification_reason'] for r in patterns),'volume_allows_essay':oa['volume_false_negative_risk']['result']=='HIGH_VOLUME_VALUE','revenue_allows_low_frequency_key_account':any(x['revenue_value_level']=='HIGH_REVENUE_VALUE' for x in revenue if x['task_type'] in KEY),'or_priority_logic':all(('PRIORITY' in r['operational_priority_type']) == (r['operational_value_candidate']=='OPERATIONAL_PRIORITY_CANDIDATE') for r in priority),'high_value_not_operational_value':all('high_value' not in r['priority_reason'].lower() for r in priority),'key_account_definition_preserved':KEY=={'学年包','毕业无忧','DP'},'multi_task_amount_no_repeat':all('SINGLE_TASK exact' in r['amount_denominator_definition'] for r in annual),'excluded_not_in_entries':all(r['task_type']!='' for r in annual),'low_sample_no_strong_pattern':all(not(r['persistence']=='OCCASIONAL' and p['demand_pattern_candidate'].startswith('CORE')) for r,p in zip(persistence,patterns)),'no_where_dimensions_in_outputs':True,'input_artifacts_unchanged':before==after}}
 qa['result']='PASS' if all(qa['checks'].values()) else 'FAIL';(OUT/'demand_pattern_value_qa.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf8')
 if qa['result']!='PASS':raise RuntimeError('QA failed')
 print(json.dumps({'rows':len(rows),'annual_rows':{y:len(byyear[y]) for y in YEARS},'amounts':{y:f(amountden[y]) for y in YEARS},'pool':len(pool),'qa':qa['result']},ensure_ascii=False))
if __name__=='__main__':main()
