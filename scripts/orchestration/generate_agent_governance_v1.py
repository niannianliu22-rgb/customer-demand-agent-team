#!/usr/bin/env python3
"""Generate governance views and configuration QA; does not run business Agents."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
GOV = ROOT / 'config/agents/agent_governance_v1.yaml'
ROUTES = ROOT / 'config/models/model_routing_v1.yaml'
WORKFLOW = ROOT / 'config/orchestration/workflow_v2.yaml'
OUT = ROOT / 'artifacts/governance_v1/governance_qa.json'
DOCS = ROOT / 'docs'
IDS = [f'A{i:02d}' for i in range(1,14)]

def load(p): return yaml.safe_load(p.read_text(encoding='utf-8'))
def write(p, content):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content.rstrip()+'\n', encoding='utf-8')
def bullets(items): return '; '.join(str(x) for x in items) if items else 'None'

def governance_doc(g):
    lines=['# Agent Governance V1','', 'This frozen governance layer defines responsibility, authority, benefit and boundary. It does not alter business logic, Frozen Rules, Gate decisions or Runtime behavior.', '']
    for aid in IDS:
        a=g['agents'][aid]; au=a['authority']; b=a['boundary']
        lines += [f'## {aid} — {a["agent_name"]}','',f'**Mission:** {a["mission"]}','',f'**Responsibility:** {a["responsibility"]}','',f'**Benefit:** {a["benefit"]}','', '**Authority — CAN:**', '']
        lines += [f'- {x}' for x in au['can']]
        lines += ['', '**Authority — CANNOT:**', ''] + [f'- {x}' for x in au['cannot']]
        lines += ['', '**Boundary:**', '', f'- Data: {b["data_boundary"]}', f'- Decision: {b["decision_boundary"]}', f'- Model: {b["model_boundary"]}', f'- Artifact: {b["artifact_boundary"]}', f'- Business: {b["business_boundary"]}', '', f'**Accountability:** {a["accountability"]}', '', f'**Success criteria:** {bullets(a["success_criteria"])}', '', f'**Failure conditions:** {bullets(a["failure_conditions"])}', '']
    return '\n'.join(lines)

def matrix_doc(g):
    lines=['# Agent Accountability Matrix V1','', '| Agent | Mission | Responsibility | Authority | Benefit | Boundary | Input Owner | Output Owner | Can Block? | Can Return? | Accountable For | Not Accountable For |','|---|---|---|---|---|---|---|---|---|---|---|---|']
    for aid in IDS:
        a=g['agents'][aid]; b=a['boundary']; not_for=', '.join(a['authority']['cannot'])
        values=[aid,a['mission'],a['responsibility'],f"CAN: {bullets(a['authority']['can'])}",a['benefit'],f"Data: {b['data_boundary']}; Decision: {b['decision_boundary']}",bullets(a['owned_inputs']),bullets(a['owned_outputs']),bullets(a['blocking_rights']),bullets(a['return_rights']),a['accountability'],not_for]
        lines.append('| '+' | '.join(v.replace('|','/') for v in values)+' |')
    return '\n'.join(lines)

def interaction_doc(g, workflow):
    gate_after={
      'A03':'SOURCE_GATE','A04':'SCHEMA_GATE','A05':'STANDARDIZATION_GATE','A06':'DATA_QUALITY_GATE','A09':'CONTEXT_GATE','A10':'INSIGHT_GATE','A11':'CRITIC_GATE','A12':'FORECAST_GATE','A13':'ACTION_GATE'}
    lines=['# Agent Interaction Map V1','', '## Delivery and control flow','', '`A01` controls the flow; `A02` records every state, artifact and warning. Neither performs business analysis.', '', '```text','A03 → SOURCE_GATE → A04 → SCHEMA_GATE → A05 → STANDARDIZATION_GATE → A06 → DATA_QUALITY_GATE','                                                                          ├→ A07 Historical ─┐','                                                                          └→ A08 Academic ───┤','                                                                                              ↓','                                                                                            A09 → CONTEXT_GATE → A10 → INSIGHT_GATE → A11 → CRITIC_GATE → A12 → FORECAST_GATE → A13 → ACTION_GATE','```','', '## Handoffs, checks and returns','', '| From | Delivers | To | Gate / check | Return authority | Cannot bypass |','|---|---|---|---|---|---|']
    for aid in IDS:
        a=g['agents'][aid]
        if not a['downstream_agents']: continue
        gate=gate_after.get(aid,'Supervisor-controlled handoff')
        lines.append(f"| {aid} | {bullets(a['owned_outputs'])} | {bullets(a['downstream_agents'])} | {gate} | {bullets(a['return_rights'])} | A01 / applicable Gate |")
    lines += ['', '## Required checks and balances','', '- A01 Supervisor ≠ business decision maker; it only sequences registered decisions.', '- A02 Knowledge ≠ analysis Agent; it records evidence and state only.', '- A05 Standardization ≠ A06 Data Quality; A05 applies rules, while A06 independently judges fitness.', '- A07 Historical ≠ A12 Forecast; historical evidence cannot become a future forecast without A09–A11.', '- A08 Academic Context ≠ A10 Opportunity; Calendar signals remain potential context until synthesis.', '- A09 Validation ≠ opportunity creator; it classifies alignment only.', '- A10 Opportunity ≠ A12 Forecast; monthly synthesis precedes time-horizon forecasting.', '- A11 Critic ≠ opportunity editor; it returns a precise correction without changing A10.', '- A12 Forecast ≠ A13 Action; forecast confidence is immutable to A13.', '', '## Return and stale rule','', 'Only A01 calculates downstream invalidation from the dependency graph. An Agent may identify its registered return target, but cannot skip an upstream Gate or directly invoke another Agent.']
    return '\n'.join(lines)

def executive_doc(g):
    layers=g['organization_layers']
    lines=['# Customer Demand Agent Team — Executive View V1','', '## Why 13 Agents', '', 'This is not thirteen copies of one model. It is a controlled production line: source data is governed before it is interpreted; historical evidence and current academic context are kept independent; opportunity conclusions are challenged before they become forecasts; forecasts are then translated into actions without being rewritten.', '', 'One model doing all of this would be able to confuse a Calendar signal with an order, repair its own data-quality concern, or promote its own weak conclusion. The team separates these duties so evidence, judgment and execution can check one another.', '', '## Five operating layers','']
    names={aid:g['agents'][aid]['agent_name'] for aid in IDS}
    summaries={
      'CONTROL_LAYER':'Controls the run, records every version and prevents bypasses.',
      'DATA_GOVERNANCE_LAYER':'Turns received files into a standardized, quality-gated dataset.',
      'EVIDENCE_AND_CONTEXT_LAYER':'Answers what historically happened and what schools are officially doing now, then aligns the two without merging their facts.',
      'DECISION_AND_CONTROL_LAYER':'Builds the monthly demand opportunity view and independently challenges it.',
      'FORECAST_AND_EXECUTION_LAYER':'Turns Critic-approved opportunities into future windows and concrete sales/operations preparation.'}
    for layer, aids in layers.items():
        lines += [f'### {layer.replace("_"," ")}', '', summaries[layer], '', f'**Agents:** '+ ' → '.join(f'{aid} {names[aid]}' for aid in aids), '']
    lines += ['## How the checks work','', '- Data Standardization applies approved mappings; Data Quality independently decides whether analysis may proceed.', '- Historical Demand and Academic Context are separate evidence chains. Calendar silence never erases historical demand, and Calendar signals never become orders by themselves.', '- Demand Opportunity builds the business view. Critic is a separate checker that can return it for revision but cannot edit it.', '- Forecast can only use Critic-approved opportunities. Action can only turn forecasted opportunities into sales, content and preparation work; it cannot rewrite the forecast.', '', '## Business outcome','', 'The controlled chain turns governed source data into a practical answer: **when in the target month, in which country, at what academic stage, for which business direction, at which schools, and for what specific student demand should the team prepare or act?** Every answer remains traceable to data, Calendar context, validation and Critic review.']
    return '\n'.join(lines)

def main():
    g, routes, workflow = load(GOV), load(ROUTES), load(WORKFLOW)
    agents=g['agents']; issues=[]
    required=['mission','responsibility','authority','benefit','boundary','owned_inputs','owned_outputs','decision_rights','blocking_rights','return_rights','allowed_tools','allowed_models','upstream_agents','downstream_agents','success_criteria','failure_conditions','accountability']
    checks={}
    for label, field in [('responsibility','responsibility'),('authority','authority'),('benefit','benefit'),('boundary','boundary')]:
        checks[f'all_13_have_{label}']=set(agents)==set(IDS) and all(agents[a].get(field) for a in IDS)
    checks['all_required_governance_fields']=all(all(agents[a].get(x) is not None for x in required) for a in IDS)
    checks['unique_primary_accountability']=len([agents[a]['accountability'] for a in IDS])==len(set(agents[a]['accountability'] for a in IDS))
    checks['a01_not_business_analyst']='perform_business_analysis' in agents['A01']['authority']['cannot']
    checks['a02_not_decision_agent']='decide_business_or_gate_outcomes' in agents['A02']['authority']['cannot']
    checks['maker_checker_separation']=agents['A10']['owned_outputs'] != agents['A11']['owned_outputs'] and 'modify_A10_artifact' in agents['A11']['authority']['cannot']
    checks['a12_critic_constrained']='critic-approved' in agents['A12']['mission'].lower()
    checks['a13_no_forecast_mutation']='modify_forecast_or_confidence' in agents['A13']['authority']['cannot']
    checks['frozen_rules_protected']='no_agent_may_modify_frozen_rules' in g['global_constraints'] and all(not any('modify_frozen' in item for item in agents[a]['authority']['can']) for a in IDS)
    checks['gates_not_bypassable']='no_agent_may_bypass_gate_or_supervisor' in g['global_constraints']
    checks['model_routing_compatible']=all(agents[a]['allowed_models'] == ['NONE'] if routes['routes'][a]['primary_model']=='NONE' else len(agents[a]['allowed_models'])>0 for a in IDS)
    for name, ok in checks.items():
        if not ok: issues.append({'check':name,'detail':'Governance constraint not satisfied.'})
    result='PASS' if all(checks.values()) else 'FAIL'
    write(DOCS/'AGENT_GOVERNANCE_V1.md', governance_doc(g))
    write(DOCS/'AGENT_ACCOUNTABILITY_MATRIX_V1.md', matrix_doc(g))
    write(DOCS/'AGENT_INTERACTION_MAP_V1.md', interaction_doc(g,workflow))
    write(DOCS/'AGENT_TEAM_EXECUTIVE_VIEW_V1.md', executive_doc(g))
    report={'artifact':'governance_qa_v1','generated_at':datetime.now(timezone.utc).isoformat(),'result':result,'agent_count':len(agents),'checks':checks,'issues':issues,'governance_config':'config/agents/agent_governance_v1.yaml','generated_documents':['docs/AGENT_GOVERNANCE_V1.md','docs/AGENT_ACCOUNTABILITY_MATRIX_V1.md','docs/AGENT_INTERACTION_MAP_V1.md','docs/AGENT_TEAM_EXECUTIVE_VIEW_V1.md'],'runtime_behavior_changed':False,'business_agents_executed':False}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'result':result,'artifact':str(OUT.relative_to(ROOT))},ensure_ascii=False))
    if result!='PASS': raise SystemExit(1)
if __name__=='__main__': main()
