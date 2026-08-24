#!/usr/bin/env python3
"""Materialize A05's standardized school universe without changing its dataset."""
from __future__ import annotations
import csv, hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main(run_id):
    run=ROOT/'runs'/run_id; source=run/'artifacts/unified_dataset.csv'; out=run/'artifacts/support_school_universe.json'
    if out.exists(): raise SystemExit(f'Immutable support-school universe already exists: {out}')
    with source.open(encoding='utf-8-sig',newline='') as h: rows=list(csv.DictReader(h))
    schools={}
    for row in rows:
        if row.get('school_standardization_status')=='STANDARDIZED' and row.get('school'):
            key=(row['school'],row.get('school_id',''),row.get('country','')); schools[key]=schools.get(key,0)+1
    payload={'run_id':run_id,'producer_agent':'A05','producer_component':'A01_DETERMINISTIC_A05_SCHOOL_UNIVERSE_MATERIALIZER','source_artifact':'artifacts/unified_dataset.csv','source_checksum':sha(source),'created_at':datetime.now(timezone.utc).isoformat(),'immutable':True,'schools':[{'school':s,'school_id':i,'country':c,'supporting_record_count':n} for (s,i,c),n in sorted(schools.items())]}
    out.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps({'run_id':run_id,'schools':len(schools),'result':'PASS'},ensure_ascii=False))
if __name__=='__main__': main(sys.argv[1])
