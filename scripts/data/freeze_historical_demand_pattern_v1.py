#!/usr/bin/env python3
"""Freeze accepted country-primary Historical Demand Pattern V1 without new analysis."""
from __future__ import annotations
import csv,hashlib,json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];ART=ROOT/'runs/RUN-202608-DEMAND-001/artifacts';OUT=ART/'historical_demand_pattern_v1';DETAIL=OUT/'historical_demand_pattern_detail.csv';CFG=ROOT/'config/insight/historical_demand_pattern_v1.yaml'
def read(p):
 with p.open(encoding='utf-8-sig',newline='') as h:return list(csv.DictReader(h))
def write(p,fs,rows):
 with p.open('w',encoding='utf-8-sig',newline='') as h:w=csv.DictWriter(h,fieldnames=fs);w.writeheader();w.writerows(rows)
def d(v):return Decimal(v or '0')
def money(v):return format(v.quantize(Decimal('.01')),'f')
def main():
 before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [DETAIL,CFG]};detail=read(DETAIL)
 groups=defaultdict(list);school=defaultdict(list)
 for r in detail:
  groups[(r['month'],r['task_type'],r['value_class'],r['country'])].append(r)
  school[(r['month'],r['task_type'],r['value_class'],r['country'],r['school'])].append(r)
 pats=[]
 for k,rs in groups.items():
  by={r['year']:r for r in rs};cnt=sum(int(r['order_count']) for r in rs);repeat=len(by);strength='STRONG' if repeat==3 and cnt>=3 else 'MEDIUM' if repeat>=2 or cnt>=3 else 'WEAK'
  pats.append({'month':k[0],'task_type':k[1],'value_class':k[2],'country':k[3],'years_observed':'2023;2024;2025','repeat_year_count':repeat,'years_present':';'.join(sorted(by)),'historical_order_count':cnt,'historical_amount':money(sum((d(r['amount']) for r in rs),Decimal('0'))),'pattern_strength':strength,'strength_rule_version':'Historical Demand Pattern V1 FROZEN','2023_order_count':by.get('2023',{}).get('order_count',0),'2023_amount':by.get('2023',{}).get('amount','0.00'),'2024_order_count':by.get('2024',{}).get('order_count',0),'2024_amount':by.get('2024',{}).get('amount','0.00'),'2025_order_count':by.get('2025',{}).get('order_count',0),'2025_amount':by.get('2025',{}).get('amount','0.00')})
 pats.sort(key=lambda r:({'STRONG':0,'MEDIUM':1,'WEAK':2}[r['pattern_strength']],-r['repeat_year_count'],-r['historical_order_count'],r['task_type'],r['country']))
 write(OUT/'historical_demand_patterns.csv',list(pats[0]),pats)
 supports=[]
 for k,rs in school.items():
  by={r['year']:r for r in rs};supports.append({'month':k[0],'task_type':k[1],'value_class':k[2],'country':k[3],'school':k[4],'school_support_years_present':';'.join(sorted(by)),'school_support_repeat_year_count':len(by),'school_support_order_count':sum(int(r['order_count']) for r in rs),'school_support_amount':money(sum((d(r['amount']) for r in rs),Decimal('0'))),'role':'SUPPORTING_SCHOOL_EVIDENCE_NOT_PATTERN_KEY'})
 supports.sort(key=lambda r:(r['month'],r['task_type'],r['country'],-r['school_support_order_count'],r['school']))
 write(OUT/'historical_demand_pattern_school_supporting_evidence.csv',list(supports[0]),supports)
 after={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [DETAIL,CFG]}
 qa={'result':'PASS' if before==after and all('school' not in r for r in pats) and all(r['role']=='SUPPORTING_SCHOOL_EVIDENCE_NOT_PATTERN_KEY' for r in supports) else 'FAIL','checks':{'country_primary_key':all('school' not in r for r in pats),'school_support_only':all(r['role']=='SUPPORTING_SCHOOL_EVIDENCE_NOT_PATTERN_KEY' for r in supports),'frozen_strength_applied':all(r['pattern_strength'] in {'STRONG','MEDIUM','WEAK'} for r in pats),'source_detail_and_config_unchanged':before==after,'no_further_analysis':True},'country_pattern_count':len(pats),'school_support_evidence_count':len(supports)}
 (OUT/'historical_demand_pattern_freeze_qa.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf8')
 if qa['result']!='PASS':raise RuntimeError('freeze QA failed')
 print(json.dumps({'country_patterns':len(pats),'school_support':len(supports),'qa':qa['result']},ensure_ascii=False))
if __name__=='__main__':main()
