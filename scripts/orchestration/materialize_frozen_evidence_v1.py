#!/usr/bin/env python3
"""Bind registered frozen deterministic evidence into one immutable run snapshot."""
from __future__ import annotations
import hashlib, json, shutil, sys
from datetime import datetime, timezone
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[2]
REGISTRY=ROOT/'config/orchestration/frozen_evidence_registry_v1.yaml'
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def main(run_id):
    run=ROOT/'runs'/run_id
    # New runs bind this registry during initialization.  The fallback keeps
    # already-created recovery runs usable while recording the same frozen
    # source contract they were created under.
    registry_path=run/'snapshots/frozen_evidence_registry.yaml'
    registry_path=registry_path if registry_path.is_file() else REGISTRY
    registry=yaml.safe_load(registry_path.read_text(encoding='utf-8'))
    if not (run/'run_manifest.json').exists(): raise SystemExit(f'Run not found: {run_id}')
    entries=[]
    for name,spec in registry['sources'].items():
        source_root=ROOT/'runs'/spec['source_run']/'artifacts'; target_root=run/'snapshots'/'frozen_evidence'/name
        if target_root.exists(): raise SystemExit(f'Immutable evidence snapshot already exists: {target_root}')
        for rel in spec['artifacts']:
            source=source_root/rel; target=target_root/rel
            if not source.is_file(): raise SystemExit(f'Registered frozen evidence is missing: {source}')
            target.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(source,target)
            entries.append({'evidence_group':name,'path':str(target.relative_to(run)),'source_origin':str(source.relative_to(ROOT)),'source_checksum':sha(source),'snapshot_checksum':sha(target),'immutable':True,'producer_component':spec['producer_component'],'source_class':spec['source_class'],'consumer_agents':spec['consumer_agents']})
    manifest={'run_id':run_id,'materialized_at':datetime.now(timezone.utc).isoformat(),'registry_version':registry['version'],'registry_path':str(registry_path.relative_to(ROOT)),'entries':entries,'result':'PASS' if all(x['source_checksum']==x['snapshot_checksum'] for x in entries) else 'FAIL'}
    (run/'snapshots'/'frozen_evidence_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'run_id':run_id,'entries':len(entries),'result':manifest['result']},ensure_ascii=False))
if __name__=='__main__':
    if len(sys.argv)!=2: raise SystemExit('usage: materialize_frozen_evidence_v1.py <RUN_ID>')
    main(sys.argv[1])
