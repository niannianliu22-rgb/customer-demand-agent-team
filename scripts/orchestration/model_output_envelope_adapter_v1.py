#!/usr/bin/env python3
"""Provider-output normalization and runtime-owned Agent envelope building."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


class OutputNormalizationError(ValueError):
    pass


class EnvelopeValidationError(ValueError):
    pass


def _json_text(value: str) -> str:
    value = value.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", value, flags=re.S | re.I)
    return fenced.group(1).strip() if fenced else value


def _json_object(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(_json_text(value))
    except json.JSONDecodeError as exc:
        raise OutputNormalizationError('JSON_EXTRACTION_FAILED') from exc
    if not isinstance(parsed, dict):
        raise OutputNormalizationError('MODEL_PAYLOAD_NOT_OBJECT')
    return parsed


class CodexCLIOutputNormalizer:
    """Codex `--output-last-message` is the model content, not CLI stdout."""
    @staticmethod
    def normalize(model_content: str, _stdout: str) -> dict[str, Any]:
        return _json_object(model_content)


class ClaudeCLIOutputNormalizer:
    """Claude JSON output wraps the model content in the `result` field."""
    @staticmethod
    def normalize(model_content: str, _stdout: str) -> dict[str, Any]:
        outer = _json_object(model_content)
        result = outer.get('result')
        if not isinstance(result, str):
            raise OutputNormalizationError('CLAUDE_RESULT_FIELD_MISSING_OR_NOT_STRING')
        return _json_object(result)


def normalize_provider_output(provider: str, model_content: str, stdout: str) -> dict[str, Any]:
    if provider == 'codex_cli':
        return CodexCLIOutputNormalizer.normalize(model_content, stdout)
    if provider == 'claude_cli':
        return ClaudeCLIOutputNormalizer.normalize(model_content, stdout)
    raise OutputNormalizationError(f'UNSUPPORTED_PROVIDER:{provider}')


def build_agent_model_output_envelope(runtime: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Merge only business payload fields with runtime-owned identity fields."""
    contract = payload.get('contract_payload')
    if not isinstance(contract, dict):
        summary = payload.get('summary', payload.get('result'))
        contract = {
            'summary': str(summary) if summary is not None else '',
            'findings': payload.get('findings', []),
            'recommendations': payload.get('recommendations', []),
            'return_to_agent': payload.get('return_to_agent'),
        }
    envelope = {
        'agent_id': runtime['agent_id'],
        'model_tier': runtime['model_tier'],
        'status': str(payload.get('status', 'COMPLETED')).upper(),
        'confidence': payload.get('confidence'),
        'evidence_refs': payload.get('evidence_refs', []),
        'warnings': payload.get('warnings', []),
        'contract_payload': contract,
    }
    validate_agent_model_output_envelope(envelope)
    return envelope


def validate_agent_model_output_envelope(envelope: dict[str, Any]) -> None:
    expected = {'agent_id','model_tier','status','confidence','evidence_refs','warnings','contract_payload'}
    missing = sorted(expected - envelope.keys())
    extra = sorted(envelope.keys() - expected)
    issues: list[str] = []
    if missing: issues.append('missing=' + ','.join(missing))
    if extra: issues.append('additional=' + ','.join(extra))
    if not re.fullmatch(r'A(0[1-9]|1[0-3])', str(envelope.get('agent_id',''))): issues.append('agent_id')
    if envelope.get('model_tier') not in {'TIER_1_MEDIUM','TIER_2_STRONG_REASONING','TIER_3_CRITICAL_REASONING'}: issues.append('model_tier')
    if not isinstance(envelope.get('status'), str): issues.append('status')
    if envelope.get('confidence') is not None and not isinstance(envelope.get('confidence'), str): issues.append('confidence')
    if not isinstance(envelope.get('evidence_refs'), list): issues.append('evidence_refs')
    if not isinstance(envelope.get('warnings'), list): issues.append('warnings')
    contract=envelope.get('contract_payload')
    required_contract={'summary','findings','recommendations','return_to_agent'}
    if not isinstance(contract, dict): issues.append('contract_payload')
    else:
        if required_contract-contract.keys(): issues.append('contract_payload.missing')
        if contract.keys()-required_contract: issues.append('contract_payload.additional')
        if not isinstance(contract.get('summary'),str): issues.append('contract_payload.summary')
        if not isinstance(contract.get('findings'),list): issues.append('contract_payload.findings')
        if not isinstance(contract.get('recommendations'),list): issues.append('contract_payload.recommendations')
        if contract.get('return_to_agent') is not None and not isinstance(contract.get('return_to_agent'),str): issues.append('contract_payload.return_to_agent')
    if issues: raise EnvelopeValidationError(';'.join(issues))
