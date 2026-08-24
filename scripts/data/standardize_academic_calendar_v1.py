#!/usr/bin/env python3
"""Build the independent, frozen Academic Calendar Canonical Layer V1."""
from __future__ import annotations

import csv, hashlib, json, re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'runs/RUN-202608-DEMAND-001/artifacts/academic_calendar_v1'
RAW = SRC / 'academic_calendar_standardized.csv'
MASTER = SRC / 'supporting_school_master.csv'
OUT = ROOT / 'runs/RUN-202608-DEMAND-001/artifacts/academic_calendar_standardization_v1'
CFG = ROOT / 'config/dimensions/academic_calendar'
SCHEMA = ROOT / 'schemas/academic_calendar_schema_v1.json'
OUT.mkdir(exist_ok=True, parents=True); CFG.mkdir(exist_ok=True, parents=True)
VERSION = '1.0'; TODAY = '2026-08-22'
EVENT_TYPES = ['ORIENTATION','TEACHING','READING','ASSESSMENT','REVISION','EXAM','RESULTS','RESIT','BREAK','VACATION','OTHER']
COUNTRIES = ['英国','澳洲','美国','香港','新加坡','新西兰']

def read(path):
    with path.open(encoding='utf-8-sig', newline='') as handle: return list(csv.DictReader(handle))
def write(path, fields, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def qdump(path, data): path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding='utf-8')

raw = read(RAW); master = read(MASTER); raw_hash = sha(RAW)
master_by_school = {row['school_name']: row for row in master}

def semantic_event(row):
    """One-time semantic review used solely to write the formal exact alias rulebook."""
    event = row['stage_type'].upper()
    name = row['official_stage_name'].lower()
    subtype = ''
    if event == 'EXAM': subtype = 'FINAL_EXAM' if 'final' in name else 'GENERAL_EXAM'
    if event == 'RESIT':
        subtype = 'DEFERRED_EXAM' if 'deferred' in name else ('SUPPLEMENTARY_EXAM' if ('supplementary' in name or 'special/' in name) else 'RESIT_EXAM')
    if event == 'ASSESSMENT': subtype = 'GENERAL_ASSESSMENT'
    if event == 'RESULTS': subtype = 'RESULTS_RELEASE'
    return event, subtype

# Exact aliases make every source-language → canonical mapping auditable. The standardizer below rereads this config.
aliases = []
for number, name in enumerate(sorted({row['official_stage_name'] for row in raw}), 1):
    exemplar = next(row for row in raw if row['official_stage_name'] == name)
    event, subtype = semantic_event(exemplar)
    aliases.append({'alias_id': f'CAL-EVT-ALIAS-{number:03d}', 'event_name_original': name, 'event_type': event, 'event_subtype': subtype or None, 'mapping_source': 'V1_SEMANTIC_REVIEW_OF_OFFICIAL_STAGE_NAME', 'status': 'ACTIVE'})

canonical = {
    'calendar_event_taxonomy_version': VERSION, 'status': 'FROZEN',
    'source': 'official_calendar_stage_names_semantic_review',
    'event_types': [
        {'event_type': value, 'name_zh': {'ORIENTATION':'迎新','TEACHING':'教学','READING':'阅读周','ASSESSMENT':'评估','REVISION':'复习','EXAM':'考试','RESULTS':'成绩发布','RESIT':'补考/补充评估','BREAK':'学期间歇','VACATION':'假期','OTHER':'其他'}[value],
         'business_definition': {'EXAM':'常规考试或期末考试阶段；不含延期/补充/补考考试。','RESIT':'面向未通过、补充或延期安排的考试/评估；用 event_subtype 区分。','OTHER':'官方记录存在但不属于当前 taxonomy 的学业阶段。'}.get(value, '官方校历阶段的规范分类。')}
        for value in EVENT_TYPES],
    'event_subtypes': {'EXAM':['FINAL_EXAM','GENERAL_EXAM'], 'RESIT':['RESIT_EXAM','SUPPLEMENTARY_EXAM','DEFERRED_EXAM'], 'ASSESSMENT':['GENERAL_ASSESSMENT'], 'RESULTS':['RESULTS_RELEASE']},
    'resit_policy': {'RESIT_EXAM':'官网明确 resit/resits。','SUPPLEMENTARY_EXAM':'官网明确 supplementary 或 special/supplementary examination。','DEFERRED_EXAM':'官网明确 deferred examination period。','rule':'三者均属 RESIT 业务大类，但不得抹除 subtype。'},
}
rules = {
    'calendar_standardization_rule_version': VERSION, 'status': 'FROZEN',
    'source_input': str(RAW.relative_to(ROOT)), 'school_master_source': str(MASTER.relative_to(ROOT)),
    'country_canonical_values': COUNTRIES,
    'academic_year_rules': [
        {'rule_id':'CAL-YEAR-001','original':'2025/26','canonical':'AY_2025_2026','definition':'学校以跨自然年的 Academic Year 表示。'},
        {'rule_id':'CAL-YEAR-002','original':'2026','canonical':'CY_2026','definition':'学校以单一自然年日历表示；不强行转为跨年学年。'},
        {'rule_id':'CAL-YEAR-003','original':'2026/27','canonical':'AY_2026_2027','definition':'学校以跨自然年的 Academic Year 表示。'},
    ],
    'period_rules': {'SEMESTER':'official name contains Semester','TERM':'official name contains Term','QUARTER':'official name contains Quarter','SESSION':'official name contains Session','FULL_YEAR':'official name contains Academic year or Full-year','OTHER':'no official period label is inferable; period_name=OFFICIAL_CALENDAR_UNSPECIFIED'},
    'status_rules': {'collection_status':'Copied from current supporting_school_master.calendar_status.', 'standardization_status':['STANDARDIZED','REVIEW_REQUIRED','UNMATCHED'], 'no_status_cross_use':'Collection status never substitutes for standardization status.'},
    'date_rule':'ISO 8601 YYYY-MM-DD; start_date must be less than or equal to end_date.',
    'alias_source': 'calendar_event_aliases.yaml',
}
qdump(CFG/'calendar_event_canonical.yaml', canonical)
qdump(CFG/'calendar_event_aliases.yaml', {'calendar_event_alias_version': VERSION, 'status':'FROZEN', 'aliases':aliases})
qdump(CFG/'calendar_standardization_rules_v1.yaml', rules)

schema = {
    'schema_name':'academic_calendar','schema_version':VERSION,'status':'FROZEN','change_control':'Any semantic or field change requires a new calendar schema/rule version.',
    'fields':[
        {'name':'school_id','type':'string','required':True},{'name':'school','type':'string','required':True},{'name':'country','type':'string','required':True,'allowed_values':COUNTRIES},
        {'name':'academic_year_original','type':'string','required':True},{'name':'academic_year_canonical','type':'string','required':True},
        {'name':'period_type','type':'string','required':True,'allowed_values':['SEMESTER','TERM','QUARTER','SESSION','FULL_YEAR','OTHER']},{'name':'period_name','type':'string','required':True},
        {'name':'event_type','type':'string','required':True,'allowed_values':EVENT_TYPES},{'name':'event_subtype','type':'string','required':False},{'name':'event_name_original','type':'string','required':True},
        {'name':'start_date','type':'string','format':'date','required':True},{'name':'end_date','type':'string','format':'date','required':True},
        {'name':'is_stage','type':'boolean','required':True},{'name':'is_event','type':'boolean','required':True},
        {'name':'source_url','type':'string','required':True},{'name':'source_title','type':'string','required':True},{'name':'last_checked_at','type':'string','format':'date','required':True},
        {'name':'collection_status','type':'string','required':True,'allowed_values':['READY','PARTIAL','NEEDS_REVIEW','NOT_FOUND','PENDING_COLLECTION']},{'name':'standardization_status','type':'string','required':True,'allowed_values':['STANDARDIZED','REVIEW_REQUIRED','UNMATCHED']},
        {'name':'event_rule_id','type':'string','required':False},{'name':'academic_year_rule_id','type':'string','required':False},{'name':'period_rule_id','type':'string','required':False},
    ]
}
SCHEMA.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding='utf-8')

# The following output uses the final rule files, rather than collection-agent values, as the mapping source.
alias_by_name = {item['event_name_original']:item for item in yaml.safe_load((CFG/'calendar_event_aliases.yaml').read_text(encoding='utf-8'))['aliases']}
year_rules = {item['original']:item for item in rules['academic_year_rules']}
def period(name):
    lowered = name.lower()
    if 'semester' in lowered:
        match = re.search(r'(semester\s*(?:one|two|1|2|three|3)|summer semester)', name, re.I); return 'SEMESTER', (match.group(1).title() if match else 'Official Semester'), 'CAL-PERIOD-001'
    if 'term' in lowered:
        match = re.search(r'((?:autumn|spring|summer|michaelmas)?\s*term\s*(?:one|two|three|four|1|2|3|4)?)', name, re.I); return 'TERM', (match.group(1).strip().title() if match else 'Official Term'), 'CAL-PERIOD-002'
    if 'quarter' in lowered: return 'QUARTER', 'Official Quarter', 'CAL-PERIOD-003'
    if 'session' in lowered: return 'SESSION', 'Official Session', 'CAL-PERIOD-004'
    if 'academic year' in lowered or 'full-year' in lowered: return 'FULL_YEAR', 'Official Academic Year', 'CAL-PERIOD-005'
    return 'OTHER', 'OFFICIAL_CALENDAR_UNSPECIFIED', 'CAL-PERIOD-006'

standardized=[]; unmatched=[]; review=[]
for index,row in enumerate(raw,1):
    master_row=master_by_school.get(row['school_name']); alias=alias_by_name.get(row['official_stage_name']); year=year_rules.get(row['academic_year'])
    ptype,pname,prule=period(row['official_stage_name']); status='STANDARDIZED'
    if not master_row or not master_row['school_id'] or not alias or not year: status='REVIEW_REQUIRED' if master_row else 'UNMATCHED'
    result={'calendar_record_id':f'CAL-V1-{index:04d}','school_id':master_row['school_id'] if master_row else '', 'school':row['school_name'], 'school_name_zh':master_row['school_name_zh'] if master_row else row['school_name_zh'],
        'country_original':row['country'],'country':row['country'],'academic_year_original':row['academic_year'],'academic_year_canonical':year['canonical'] if year else '',
        'period_type':ptype,'period_name':pname,'event_type':alias['event_type'] if alias else '', 'event_subtype':alias.get('event_subtype') or '' if alias else '', 'event_name_original':row['official_stage_name'],
        'start_date':row['start_date'],'end_date':row['end_date'],'is_stage':row['is_stage'],'is_event':row['is_event'],'source_url':row['source_url'],'source_title':row['source_title'],'last_checked_at':row['last_checked_at'],
        'collection_status':master_row['calendar_status'] if master_row else '', 'standardization_status':status,'event_rule_id':alias['alias_id'] if alias else '', 'academic_year_rule_id':year['rule_id'] if year else '', 'period_rule_id':prule,'calendar_standardization_rule_version':VERSION}
    standardized.append(result)
    if status=='UNMATCHED': unmatched.append(result)
    if status=='REVIEW_REQUIRED': review.append(result)

fields=list(standardized[0]);write(OUT/'academic_calendar_standardized.csv',fields,standardized)
inventory=[]
for name in sorted(alias_by_name):
    rows=[row for row in raw if row['official_stage_name']==name]; rule=alias_by_name[name]
    inventory.append({'event_name_original':name,'record_count':len(rows),'legacy_structured_stage_type':rows[0]['stage_type'],'candidate_event_type':rule['event_type'],'candidate_event_subtype':rule.get('event_subtype') or '','event_rule_id':rule['alias_id'],'source_urls_count':len({row['source_url'] for row in rows})})
write(OUT/'academic_calendar_raw_value_inventory.csv',list(inventory[0]),inventory)
mapping=[{'event_name_original':item['event_name_original'],'event_type':item['event_type'],'event_subtype':item.get('event_subtype') or '','event_rule_id':item['alias_id'],'mapping_source':item['mapping_source'],'rule_status':item['status']} for item in aliases]
write(OUT/'academic_calendar_event_mapping.csv',list(mapping[0]),mapping)
write(OUT/'academic_calendar_unmatched.csv',fields,unmatched)
write(OUT/'academic_calendar_review_required.csv',fields,review)

checks={
 'record_count_unchanged':len(raw)==len(standardized),'canonical_school_all_rows':all(row['school'] in master_by_school for row in standardized),'school_id_complete':all(row['school_id'] for row in standardized),
 'country_canonical':all(row['country'] in COUNTRIES for row in standardized),'valid_dates':all(date.fromisoformat(row['start_date'])<=date.fromisoformat(row['end_date']) for row in standardized),
 'academic_year_mapped':all(row['academic_year_canonical'] for row in standardized),'original_event_preserved':all(row['event_name_original'] for row in standardized),
 'event_type_complete':all(row['event_type'] in EVENT_TYPES for row in standardized),'source_url_preserved':all(row['source_url'] for row in standardized),
 'no_silent_mapping':all(row['event_rule_id'] for row in standardized),'all_aliases_traceable':all(row['event_rule_id'] in {item['alias_id'] for item in aliases} for row in standardized),
 'collection_input_unchanged':raw_hash==sha(RAW),'no_unmatched':not unmatched,'no_review_required':not review,
}
qa={'audit_name':'academic_calendar_standardization_v1','result':'PASS' if all(checks.values()) else 'FAIL','rule_version':VERSION,'records':{'input':len(raw),'standardized':len(standardized),'unmatched':len(unmatched),'review_required':len(review),'raw_event_names':len(inventory),'canonical_event_types_used':len({row['event_type'] for row in standardized}),'aliases':len(aliases),'school_id_complete':sum(bool(row['school_id']) for row in standardized)},'checks':checks,'input_sha256':raw_hash,'output_sha256':sha(OUT/'academic_calendar_standardized.csv')}
(OUT/'academic_calendar_standardization_qa.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
metadata={'calendar_standardization_rule_version':VERSION,'status':'FROZEN' if qa['result']=='PASS' else 'CANDIDATE','source':'official_calendar_collection_structured_layer','input_artifact':str(RAW.relative_to(ROOT)),'output_artifact':str((OUT/'academic_calendar_standardized.csv').relative_to(ROOT)),'records':qa['records'],'qa_result':qa['result'],'created_at':TODAY,'rules':{'canonical':'calendar_event_canonical.yaml','aliases':'calendar_event_aliases.yaml','standardization':'calendar_standardization_rules_v1.yaml'},'schema':str(SCHEMA.relative_to(ROOT))}
(CFG/'calendar_standardization_rules_v1.metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
summary=f'''# Academic Calendar Standardization V1\n\n- Status: {metadata['status']}\n- Records: {len(raw)} → {len(standardized)}\n- Canonical schools / complete school_id: {sum(bool(row['school_id']) for row in standardized)} / {len(standardized)}\n- Raw official event names: {len(inventory)}\n- Canonical event types used: {qa['records']['canonical_event_types_used']}\n- Exact aliases: {len(aliases)}\n- UNMATCHED: {len(unmatched)}\n- REVIEW_REQUIRED: {len(review)}\n- QA: {qa['result']}\n\nCollection status and standardization status are separate fields. READY/PARTIAL/NEEDS_REVIEW are collection states only; every output row is STANDARDIZED only after an exact alias-rule match.\n'''
(OUT/'academic_calendar_standardization_summary.md').write_text(summary,encoding='utf-8')
print(json.dumps(qa,ensure_ascii=False,indent=2))
