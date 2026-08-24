#!/usr/bin/env python3
"""CLI-login multi-provider runtime for provider-agnostic model aliases.

This module never reads API keys. It probes the actual CLI execution path and
passes the configured model and reasoning effort on every model invocation.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from model_output_envelope_adapter_v1 import normalize_provider_output, OutputNormalizationError

ROOT = Path(__file__).resolve().parents[2]
CFG = Path(os.environ.get('CDAT_RUNTIME_BINDING_CONFIG', ROOT / 'config/models/model_runtime_binding_v1.yaml'))
_PROBE_CACHE: dict[str, dict[str, Any]] = {}


class ModelInvocationError(RuntimeError):
    """Provider failure retaining prompt-free audit metadata for the caller."""
    def __init__(self, message: str, audit: dict[str, Any]):
        super().__init__(message)
        self.audit = audit


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_config() -> dict[str, Any]:
    return yaml.safe_load(CFG.read_text(encoding='utf-8'))


def _probe(provider_name: str, cfg: dict[str, Any], timeout: int = 30) -> dict[str, Any]:
    if provider_name in _PROBE_CACHE:
        return _PROBE_CACHE[provider_name]
    provider = cfg['providers'][provider_name]
    executable = provider['executable']
    path = shutil.which(executable)
    if not path:
        return {'available': False, 'reason': 'CLI_NOT_FOUND', 'missing_requirements': [executable]}
    if provider['availability_check'] == 'noninteractive_health_json':
        command = [path, '-p', provider['health_prompt'], '--output-format', 'json', '--no-session-persistence']
    else:
        command = [path, *provider['auth_status_command']]
    try:
        proc = subprocess.run(command, text=True, capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return {'available': False, 'reason': 'HEALTH_CHECK_TIMEOUT', 'missing_requirements': [f'{executable} login']}
    output = (proc.stdout or '').strip()
    text_output = '\n'.join(x for x in [proc.stdout, proc.stderr] if x).strip()
    if provider['availability_check'] == 'noninteractive_health_json':
        try:
            response = json.loads(output)
            authenticated = json.loads(response['result']) == provider['health_expected']
        except json.JSONDecodeError:
            authenticated = False
    else:
        # Codex may write this human-readable status to stderr when a shell
        # cannot create its PATH aliases, so inspect both streams here.
        authenticated = provider['authenticated_text'].lower() in text_output.lower()
    result = {
        'available': proc.returncode == 0 and authenticated,
        'reason': 'AVAILABLE' if proc.returncode == 0 and authenticated else 'CLI_HEALTH_CHECK_FAILED',
        'missing_requirements': [] if proc.returncode == 0 and authenticated else [f'{executable} login'],
        'executable_path': path,
    }
    _PROBE_CACHE[provider_name] = result
    return result


def resolve(alias: str, *, probe: bool = True) -> dict[str, Any]:
    """Resolve one logical alias; availability is based on binary + CLI login."""
    cfg = load_config()
    item = cfg['bindings'][alias]
    availability = _probe(item['provider'], cfg) if probe else {'available': None, 'reason': 'NOT_PROBED', 'missing_requirements': []}
    return {
        'model_alias': alias,
        'provider': item['provider'],
        'runtime_model_name': item['concrete_model'],
        'concrete_model': item['concrete_model'],
        'invocation_model': item['invocation_model'],
        'reasoning_effort': item['reasoning_effort'],
        'invocation_mode': item['invocation_mode'],
        'tier': item['required_tier'],
        'availability': 'AVAILABLE' if availability['available'] else ('NOT_PROBED' if availability['available'] is None else 'UNAVAILABLE'),
        'availability_reason': availability['reason'],
        'missing_requirements': availability['missing_requirements'],
        'fallback': None,
        'unavailable_status': 'AGENT_BLOCKED',
    }


def resolve_chain(alias: str) -> dict[str, Any]:
    """Select primary or its qualified fallback, never silently downgrading tiers."""
    primary = resolve(alias)
    candidates = [primary]
    if primary['fallback']:
        candidates.append(resolve(primary['fallback']))
    for candidate in candidates:
        if candidate['availability'] == 'AVAILABLE' and candidate['tier'] == primary['tier']:
            candidate['fallback_used'] = candidate['model_alias'] != alias
            return candidate
    return {**primary, 'fallback_used': False, 'availability': 'UNAVAILABLE',
            'availability_reason': 'NO_QUALIFIED_CLI_PROVIDER',
            'missing_requirements': sorted({x for c in candidates for x in c['missing_requirements']})}


def _command(runtime: dict[str, Any], prompt: str, output_schema: Path, output_file: Path) -> list[str]:
    provider = runtime['provider']
    if provider == 'claude_cli':
        claude_schema = json.loads(output_schema.read_text(encoding='utf-8'))
        claude_schema.pop('$schema', None)
        return ['claude', '--print', '--output-format', 'json', '--json-schema', json.dumps(claude_schema, separators=(',', ':')),
                '--model', runtime['invocation_model'], '--effort', runtime['reasoning_effort'], '--no-session-persistence', prompt]
    if provider == 'codex_cli':
        command = ['codex', 'exec', '--ephemeral', '--sandbox', 'read-only', '--cd', str(ROOT),
                   '--model', runtime['invocation_model'], '--config', f'model_reasoning_effort="{runtime["reasoning_effort"]}"']
        return [*command, '--output-schema', str(output_schema), '--output-last-message', str(output_file), prompt]
    raise ValueError(f"Unsupported CLI provider: {provider}")


def _persist_raw_response(raw_dir: Path, call_id: str, metadata: dict[str, Any], stdout: str, stderr: str, model_content: str) -> dict[str, Any]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    stdout_path=raw_dir/f'{call_id}_stdout.txt'; stderr_path=raw_dir/f'{call_id}_stderr.txt'; content_path=raw_dir/f'{call_id}_model_content.txt'; metadata_path=raw_dir/f'{call_id}_metadata.json'
    stdout_path.write_text(stdout,encoding='utf-8'); stderr_path.write_text(stderr,encoding='utf-8'); content_path.write_text(model_content,encoding='utf-8')
    metadata.update({'stdout_checksum':hashlib.sha256(stdout.encode()).hexdigest(),'stderr_checksum':hashlib.sha256(stderr.encode()).hexdigest(),'model_content_checksum':hashlib.sha256(model_content.encode()).hexdigest(),'raw_response_persisted':True,'stdout_ref':str(stdout_path),'stderr_ref':str(stderr_path),'model_content_ref':str(content_path)})
    metadata_path.write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return {**metadata,'metadata_ref':str(metadata_path)}


def invoke(alias: str, prompt: str, output_schema: str | Path, *, timeout: int = 600, raw_output_dir: Path | None = None, call_context: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run a structured, non-interactive CLI request and return response + safe audit metadata.

    Prompt text and raw response are intentionally excluded from audit metadata.
    """
    runtime = resolve_chain(alias)
    if runtime['availability'] != 'AVAILABLE':
        raise RuntimeError(f"No qualified CLI provider for {alias}: {runtime['missing_requirements']}")
    schema = Path(output_schema).resolve()
    if not schema.exists():
        raise FileNotFoundError(schema)
    started = now(); call_id=(call_context or {}).get('call_id',f'CALL-{uuid.uuid4().hex}')
    with tempfile.TemporaryDirectory(prefix='cdat-model-') as temp:
        output = Path(temp) / 'final.json'
        proc = subprocess.run(_command(runtime, prompt, schema, output), cwd=ROOT, text=True, capture_output=True, timeout=timeout, check=False)
        raw = output.read_text(encoding='utf-8') if output.exists() else proc.stdout
    completed = now()
    audit = {
        'model_name': f"{runtime['provider']}:{runtime['concrete_model']}",
        'configured_model': runtime['concrete_model'], 'actual_model': None,
        'configured_effort': runtime['reasoning_effort'], 'actual_effort': None,
        'invocation_mode': runtime['invocation_mode'],
        'explicit_model_argument': runtime['invocation_model'] in _command(runtime, '', schema, Path('/tmp/cdat-output.json')),
        'explicit_effort_argument': ('--effort' in _command(runtime, '', schema, Path('/tmp/cdat-output.json')) if runtime['provider'] == 'claude_cli' else any('model_reasoning_effort=' in x for x in _command(runtime, '', schema, Path('/tmp/cdat-output.json')))),
        'model_tier': runtime['tier'], 'fallback_used': runtime['fallback_used'],
        'started_at': started, 'completed_at': completed, 'exit_code':proc.returncode,
        'raw_output_checksum':hashlib.sha256(raw.encode('utf-8')).hexdigest(),
    }
    if raw_output_dir is not None:
        metadata={'run_id':(call_context or {}).get('run_id'),'call_id':call_id,'agent_id':(call_context or {}).get('agent_id'),'provider':runtime['provider'],'concrete_model':runtime['concrete_model'],'configured_effort':runtime['reasoning_effort'],'parallel_group_id':(call_context or {}).get('parallel_group_id'),'started_at':started,'completed_at':completed,'exit_code':proc.returncode}
        audit.update(_persist_raw_response(raw_output_dir,call_id,metadata,proc.stdout or '',proc.stderr or '',raw))
    if proc.returncode:
        audit['status']='FAILED'; audit['invocation_status']='CLI_FAILED'
        raise ModelInvocationError(f"{runtime['provider']} exited {proc.returncode}",audit)
    try:
        response = normalize_provider_output(runtime['provider'], raw, proc.stdout or '')
    except OutputNormalizationError as exc:
        audit['status']='FAILED'; audit['invocation_status']='OUTPUT_PARSE_FAILED'
        raise ModelInvocationError(str(exc),audit) from exc
    actual_model = runtime['concrete_model']
    if runtime['provider'] == 'claude_cli':
        provider_response = json.loads(raw)
        usage = provider_response.get('modelUsage', {})
        actual_model = next((x.get('canonicalModel') for x in usage.values() if x.get('canonicalModel') == runtime['concrete_model']), None)
        if actual_model != runtime['concrete_model']:
            audit['status']='FAILED'; audit['invocation_status']='MODEL_IDENTITY_FAILED'
            raise ModelInvocationError('CLAUDE_MODEL_IDENTITY_FAILED',audit)
    audit.update({'model_name':f"{runtime['provider']}:{actual_model}",'actual_model':actual_model,'actual_effort':runtime['reasoning_effort'],'status':'COMPLETED','invocation_status':'SUCCESS','response_checksum':hashlib.sha256(raw.encode('utf-8')).hexdigest()})
    return response, audit
