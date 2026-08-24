#!/usr/bin/env python3
"""Prepare a read-only, aggregated human-review package for Gate blockers."""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / 'runs/RUN-202608-DEMAND-001/artifacts'
DATA = ART / 'unified_dataset.csv'
MASTER = ART / 'academic_calendar_v1/supporting_school_master.csv'
OUT = ROOT / 'artifacts/standardization_human_review_round1'

# Candidates are explicitly non-binding review suggestions.  No candidate is
# applied to data or added to Frozen school rules by this package.
CANDIDATES = {
    '伯明翰': ('University of Birmingham', 'HIGH', 'MAP_TO_CANONICAL', 'UK country context plus an unambiguous city/university shorthand.'),
    '爱丁堡': ('University of Edinburgh', 'HIGH', 'MAP_TO_CANONICAL', 'UK country context plus an unambiguous city/university shorthand.'),
    '诺丁汉': ('University of Nottingham', 'HIGH', 'MAP_TO_CANONICAL', 'UK country context plus an unambiguous city/university shorthand.'),
    '卡迪夫': ('Cardiff University', 'HIGH', 'MAP_TO_CANONICAL', 'UK country context plus an unambiguous city/university shorthand.'),
    '多伦多': ('University of Toronto', 'HIGH', 'MAP_TO_CANONICAL', 'Canada country context plus an unambiguous city/university shorthand.'),
    '利物浦': ('University of Liverpool', 'HIGH', 'MAP_TO_CANONICAL', 'UK country context plus an unambiguous city/university shorthand.'),
    '考文垂': ('Coventry University', 'HIGH', 'MAP_TO_CANONICAL', 'UK country context plus an unambiguous city/university shorthand.'),
    '阿伯丁': ('University of Aberdeen', 'HIGH', 'MAP_TO_CANONICAL', 'UK country context plus an unambiguous city/university shorthand.'),
    '哥伦比亚': ('Columbia University', 'HIGH', 'MAP_TO_CANONICAL', 'US country context; candidate name is already represented by a related Frozen alias.'),
    '坎特伯雷': ('University of Canterbury', 'HIGH', 'MAP_TO_CANONICAL', 'New Zealand country context plus an unambiguous city/university shorthand.'),
    '纽卡斯尔': ('Newcastle University', 'HIGH', 'MAP_TO_CANONICAL', 'UK country context plus an unambiguous city/university shorthand.'),
    '莱斯': ('Rice University', 'HIGH', 'MAP_TO_CANONICAL', 'US country context plus a direct Chinese university shorthand.'),
    '东北大学': ('Northeastern University', 'MEDIUM', 'MAP_TO_CANONICAL', 'US country context supports this candidate, but the Chinese name can identify more than one institution.'),
    'csm': ('University of the Arts London', 'MEDIUM', 'REVIEW_REQUIRED', 'Likely a constituent/abbreviation rather than a direct canonical university name; confirm desired roll-up.'),
    '卡普兰': ('', 'MEDIUM', 'NON_CANONICAL', 'Singapore context conflicts with the existing Australian Kaplan Business School canonical entity; do not merge without confirmation.'),
    '约克大学': ('University of York', 'MEDIUM', 'MAP_TO_CANONICAL', 'UK context supports University of York, but the name can be institutionally ambiguous.'),
    '维多利亚大学': ('Victoria University', 'MEDIUM', 'MAP_TO_CANONICAL', 'Australia context supports this candidate; confirm canonical entity and master ID before mapping.'),
    '贝尔法斯特': ('Queen\'s University Belfast', 'MEDIUM', 'REVIEW_REQUIRED', 'City label may refer to more than one institution in Belfast.'),
    '贝法': ('Queen\'s University Belfast', 'MEDIUM', 'REVIEW_REQUIRED', 'Abbreviation needs confirmation before a canonical school mapping.'),
    '伦敦大学': ('', 'LOW', 'REVIEW_REQUIRED', 'Umbrella name; not a uniquely identifiable institution.'),
    '堪培拉': ('', 'LOW', 'REVIEW_REQUIRED', 'City label is not sufficient to choose among Canberra institutions.'),
    '悉尼': ('', 'LOW', 'REVIEW_REQUIRED', 'City label is not sufficient to choose University of Sydney versus other Sydney institutions.'),
    '疑似谢菲': ('', 'LOW', 'REVIEW_REQUIRED', 'The qualifier “suspected” prevents a reliable canonical mapping.')
}


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as h: return list(csv.DictReader(h))


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as h:
        w=csv.DictWriter(h, fieldnames=fields); w.writeheader(); w.writerows(rows)


def main():
    rows = read_csv(DATA)
    master_ids = {r['school_name']: r['school_id'] for r in read_csv(MASTER)}
    grouped = defaultdict(list)
    for r in rows:
        if r['school'] == 'UNSTANDARDIZED': grouped[r['school_original']].append(r)
    rank = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
    school_rows=[]
    for raw, items in grouped.items():
        candidate, confidence, decision, reason = CANDIDATES.get(raw, ('', 'LOW', 'REVIEW_REQUIRED', 'No evidence-backed candidate available in the review package.'))
        school_rows.append({'raw_school': raw, 'record_count': len(items), 'source_files': '; '.join(sorted({x['source_file'] for x in items})), 'country_if_available': '; '.join(sorted({x['country'] for x in items if x['country']})), 'current_school_value': 'UNSTANDARDIZED', 'candidate_canonical_school': candidate, 'candidate_school_id': master_ids.get(candidate, ''), 'candidate_reason': reason, 'confidence': confidence, 'recommended_decision': decision, 'manual_decision': '', 'manual_note': ''})
    school_rows.sort(key=lambda x: (-x['record_count'], rank[x['confidence']], x['raw_school']))
    fields=['raw_school','record_count','source_files','country_if_available','current_school_value','candidate_canonical_school','candidate_school_id','candidate_reason','confidence','recommended_decision','manual_decision','manual_note']
    write_csv(OUT/'school_manual_review.csv', fields, school_rows)
    write_csv(OUT/'top_school_review_priority.csv', fields, school_rows)

    date_rows=[]
    dates = [
        ('source_003:66','consultation_date','0.615384615384616','INVALID_DATE','Time-only numeric fraction; no calendar date can be determined.'),
        ('source_001:146','ddl','0.290322580645161','INVALID_DATE','Time-only numeric fraction; no calendar date can be determined.'),
        ('source_002:51','ddl','2024.2due','REVIEW_REQUIRED','Year/month text has no day and includes suffix contamination.'),
        ('source_002:122','ddl','2000','INVALID_DATE','Four-digit value has no supported date format or date context.'),
        ('source_003:11','ddl','8/7等','REVIEW_REQUIRED','Trailing “etc.” prevents a unique date interpretation.'),
        ('source_003:132','ddl','9/6，9/13','REVIEW_REQUIRED','Two dates are present; no rule permits choosing one.'),
        ('source_003:138','ddl','0.9','INVALID_DATE','Numeric fraction is not a complete date.')
    ]
    row_by_id={f"{r['source_id']}:{r['source_row_id']}":r for r in rows}
    for rid, field, raw, decision, reason in dates:
        r=row_by_id[rid]
        date_rows.append({'record_id':rid,'field_name':field,'raw_value':raw,'source':r['source_file'],'consultation_date_context':r['consultation_date'] or r['consultation_date_original'],'ddl_context':r['ddl'] or r['ddl_original'],'candidate_date':'','ambiguity_reason':reason,'recommended_decision':decision,'manual_decision':'','manual_note':''})
    date_fields=['record_id','field_name','raw_value','source','consultation_date_context','ddl_context','candidate_date','ambiguity_reason','recommended_decision','manual_decision','manual_note']
    write_csv(OUT/'date_manual_review.csv',date_fields,date_rows)

    school_md=['# School Human Review — Round 1','',f'74 records are aggregated into **{len(school_rows)}** unique raw school values. Candidates are suggestions only; no Frozen mapping is changed.','', '| Raw school | Records | Country | Candidate | Confidence | Recommended decision |','|---|---:|---|---|---|---|']
    school_md += [f"| {x['raw_school']} | {x['record_count']} | {x['country_if_available']} | {x['candidate_canonical_school'] or '—'} | {x['confidence']} | {x['recommended_decision']} |" for x in school_rows]
    (OUT/'school_manual_review.md').write_text('\n'.join(school_md),encoding='utf-8')
    date_md=['# Date Human Review — Round 1','', 'All seven remaining values lack a uniquely determinable date. `INVALID_DATE` is a suggested classification, not a data change.','', '| Record | Field | Raw value | Candidate | Recommended decision | Reason |','|---|---|---|---|---|---|']
    date_md += [f"| {x['record_id']} | {x['field_name']} | {x['raw_value']} | — | {x['recommended_decision']} | {x['ambiguity_reason']} |" for x in date_rows]
    (OUT/'date_manual_review.md').write_text('\n'.join(date_md),encoding='utf-8')
    print({'school_records':sum(x['record_count'] for x in school_rows),'unique_raw_school':len(school_rows),'confidence':{c:sum(x['confidence']==c for x in school_rows) for c in ['HIGH','MEDIUM','LOW']},'date_records':len(date_rows)})


if __name__=='__main__': main()
