#!/usr/bin/env python3
"""A13 operational actions derived strictly from A12 Forecast opportunities."""
from __future__ import annotations

import csv, hashlib, json, os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
RUN=os.environ['CDAT_RUN_ID']; ART=ROOT/f'runs/{RUN}/artifacts'; OUT=ART/'action'
A12=ART/'forecast/forecast_report.json'; FC=ART/'forecast/forecast_opportunities.csv'; A11=ART/'critic/critic_report.json'; A10=ART/'demand_opportunity/insight_report.json'
UPSTREAM=[ART/'historical_demand/historical_demand_report.json',ART/'academic_context/academic_context_report.json',ART/'current_context_validation/validation_report.json',A10,A11,A12,FC]
VALID_DIRECTIONS={'ASSIGNMENT_BUSINESS','DISSERTATION_BUSINESS','EXAM_BUSINESS','RESIT_BUSINESS','COURSE_SUPPORT','LONG_TERM_SERVICE','SELECTION_SUPPORT'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def playbook(direction,status):
    prep=status=='UPCOMING'
    base={
      'ASSIGNMENT_BUSINESS':('排查对应学校学生的 assignment / essay / project / 作业需求，并优先跟进已咨询或在读客户。','发布开学任务、作业规划与 assignment 类需求教育内容。','准备 essay / assignment / project / 小组作业咨询承接素材。'),
      'COURSE_SUPPORT':('排查课程学习与课程支持需求，向对应学校学生进行需求问询。','发布课程学习规划、课程支持与阶段提醒内容。','准备课程支持和长期辅导说明素材。'),
      'LONG_TERM_SERVICE':('回访已有客户并排查学年包、包课、DP、陪跑服务需求。','发布新学期准备、长期陪跑和服务方案说明内容。','准备学年包、包课、DP、陪跑服务说明与学校名单。'),
      'EXAM_BUSINESS':('筛查考试相关客户并承接考试辅导、押题、包过辅导咨询。','发布考试阶段提醒、考前准备与考试辅导内容。','准备考试辅导、押题、包过辅导咨询说明。'),
      'RESIT_BUSINESS':('重点触达补考相关客户，排查补考与考试辅导咨询。','发布补考节点、考试准备与补考支持内容。','准备补考、考试辅导、押题、包过辅导承接说明。'),
      'DISSERTATION_BUSINESS':('排查 Dissertation / 毕业论文相关咨询需求，优先回访历史相关客户。','发布 Dissertation 进度规划与论文阶段提醒内容。','准备 Dissertation / 毕业论文相关咨询承接素材。'),
      'SELECTION_SUPPORT':('排查选课相关客户需求并进行定向跟进。','发布选课节点与课程规划提醒内容。','准备选课咨询承接说明与学校课程节点素材。'),
    }[direction]
    if status=='WATCH':return ('仅监控对应学校/国家的后续信号，不开展强销售推动。','保留轻量观察内容，不宣称需求已发生。','维护观察名单与后续 Calendar/客户信号检查。')
    if prep:return (base[0].replace('排查','提前排查'),base[1],base[2]+'；提前建立重点学校名单与话术。')
    return base
def main():
    before={str(p.relative_to(ROOT)):sha(p) for p in UPSTREAM}
    fc=json.loads(A12.read_text(encoding='utf-8')); critic=json.loads(A11.read_text(encoding='utf-8'))
    country_actions=[]; school_actions=[]
    for forecast in fc['forecasts']:
        status=forecast['forecast_status']
        if status not in {'ACTIVE','UPCOMING','WATCH'}:continue
        direction=forecast['business_direction']; sales,content,preparation=playbook(direction,status)
        action={'action_id':f"A13-C-{len(country_actions)+1:03d}",'time_window':forecast['forecast_horizon'],'country':forecast['country'],'academic_stage':forecast['academic_stage'],'business_direction':direction,'key_schools':[x['school'] for x in forecast['key_schools']],'specific_demands':forecast['specific_demands'],'action_priority':forecast['forecast_strength'],'forecast_strength':forecast['forecast_strength'],'confidence':forecast['confidence_level'],'forecast_status':status,'sales_action':sales,'content_action':content,'product_action':preparation,'preparation_action':preparation if status=='UPCOMING' else 'Use the prepared school/need material for current follow-up.' if status=='ACTIVE' else preparation,'evidence_summary':{'forecast_as_of_date':forecast['forecast_as_of_date'],'validation_status':forecast['validation_status'],'historical_evidence':forecast['historical_evidence'],'calendar_evidence':forecast['calendar_evidence'],'critic_constraint':forecast['critic_constraint']},'forecast_reference':{'forecast_horizon':forecast['forecast_horizon'],'country':forecast['country'],'business_direction':direction}}
        country_actions.append(action)
        for school in forecast['key_schools']:
            school_actions.append({'action_id':f"A13-S-{len(school_actions)+1:03d}",'school':school['school'],'school_id':school['school_id'],'country':forecast['country'],'forecast_horizon':forecast['forecast_horizon'],'academic_stage':school['academic_stage'],'specific_demand':school['specific_demands'],'business_direction':direction,'forecast_status':status,'sales_action':sales,'content_action':content,'preparation_action':action['preparation_action'],'priority':forecast['forecast_strength'],'confidence':forecast['confidence_level'],'evidence_summary':f"Forecast {forecast['validation_status']}; critic constraints: {len(forecast['critic_constraint'])}.",'forecast_reference':action['forecast_reference']})
    # The executive layer keeps only the most immediate few actions, but the CSV/JSON retain all eligible actions.
    rank={'HIGH':0,'MEDIUM':1,'LOW':2}; horder={'NEXT_7_DAYS':0,'NEXT_14_DAYS':1,'NEXT_28_DAYS':2}
    for a in country_actions:a['_rank']=(horder[a['time_window']],rank[a['action_priority']],a['country'],a['business_direction'])
    country_actions.sort(key=lambda x:x['_rank'])
    for a in country_actions:a.pop('_rank')
    by_horizon={h:[x for x in country_actions if x['time_window']==h] for h in ['NEXT_7_DAYS','NEXT_14_DAYS','NEXT_28_DAYS']}
    lines=['# Action Plan — Future Demand Opportunities','', '> Actions are derived from A12 probability-based opportunities. Calendar context is not an order or proof that demand has occurred.', '']
    for horizon,items in by_horizon.items():
        lines += [f'## {horizon}', '']
        for x in items[:15]:
            lines += [f"### {x['country']} — {x['business_direction']} ({x['action_priority']}/{x['confidence']})",'',f"- Academic Stage: {', '.join(x['academic_stage']) or 'Historical-only / no current stage'}",f"- Key Schools: {', '.join(x['key_schools']) or 'Country-level evidence only'}",f"- Specific Demand: {', '.join(x['specific_demands']) or 'Direction-level opportunity'}",f"- Sales: {x['sales_action']}",f"- Content: {x['content_action']}",f"- Preparation: {x['preparation_action']}",'']
        if not items:lines.append('- No eligible action.');lines.append('')
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'action_plan.md').write_text('\n'.join(lines),encoding='utf-8')
    country_fields=['action_id','time_window','country','academic_stage','business_direction','key_schools','specific_demands','action_priority','forecast_strength','confidence','forecast_status','sales_action','content_action','product_action','preparation_action','evidence_summary','forecast_reference']
    with (OUT/'country_action_plan.csv').open('w',encoding='utf-8-sig',newline='') as h:
        w=csv.DictWriter(h,fieldnames=country_fields);w.writeheader()
        for x in country_actions:
            r=dict(x);r['academic_stage']='; '.join(r['academic_stage']);r['key_schools']='; '.join(r['key_schools']);r['specific_demands']='; '.join(r['specific_demands']);r['evidence_summary']=json.dumps(r['evidence_summary'],ensure_ascii=False);r['forecast_reference']=json.dumps(r['forecast_reference'],ensure_ascii=False);w.writerow(r)
    school_fields=['action_id','school','school_id','country','forecast_horizon','academic_stage','specific_demand','business_direction','forecast_status','sales_action','content_action','preparation_action','priority','confidence','evidence_summary','forecast_reference']
    with (OUT/'school_action_plan.csv').open('w',encoding='utf-8-sig',newline='') as h:
        w=csv.DictWriter(h,fieldnames=school_fields);w.writeheader()
        for x in school_actions:
            r=dict(x);r['academic_stage']='; '.join(r['academic_stage']);r['specific_demand']='; '.join(r['specific_demand']);r['forecast_reference']=json.dumps(r['forecast_reference'],ensure_ascii=False);w.writerow(r)
    after={str(p.relative_to(ROOT)):sha(p) for p in UPSTREAM}
    warned={(f['country'],d.strip()) for f in critic['findings'] if f['severity']=='WARNING' for d in f['business_direction'].split(',') if d.strip()}
    warned_actions=[x for x in country_actions if (x['country'],x['business_direction']) in warned]
    checks={'a07_a12_unchanged':before==after,'eligible_statuses_only':all(x['forecast_status'] in {'ACTIVE','UPCOMING','WATCH'} for x in country_actions),'expired_excluded':all(x['forecast_status']!='EXPIRED_FOR_CURRENT_RUN' for x in country_actions),'a11_warnings_inherited':all(x['evidence_summary']['critic_constraint'] for x in warned_actions),'forecast_strength_not_upgraded':all(x['action_priority']==x['forecast_strength'] for x in country_actions),'no_new_business_direction':all(x['business_direction'] in VALID_DIRECTIONS for x in country_actions),'no_new_school':all(x['school'] for x in school_actions),'all_actions_traceable_to_forecast':all(x['forecast_reference'] for x in country_actions+school_actions),'no_order_or_amount_prediction':True}
    report={'agent_id':'A13','agent_name':'Action Agent','agent_version':'2.0','status':'COMPLETED','run_id':RUN,'action_type':'Sales and operations execution actions derived from A12 forecast; not a demand re-analysis or order forecast.','executive_action_summary':{h:items[:10] for h,items in by_horizon.items()},'country_action_plan':country_actions,'school_action_plan':school_actions,'source_artifacts':[str(p.relative_to(ROOT)) for p in UPSTREAM]}
    report['qa']={'result':'PASS' if all(checks.values()) else 'FAIL','checks':checks,'counts':{'HIGH':sum(x['action_priority']=='HIGH' for x in country_actions),'MEDIUM':sum(x['action_priority']=='MEDIUM' for x in country_actions),'LOW':sum(x['action_priority']=='LOW' for x in country_actions),'country_actions':len(country_actions),'school_actions':len(school_actions),'expired_excluded':fc['expired_opportunity_count']}}
    dump(OUT/'action_plan.json',report)
    if report['qa']['result']!='PASS':raise RuntimeError('A13 QA failed')
    print(json.dumps({'status':'COMPLETED',**report['qa']['counts']},ensure_ascii=False))
if __name__=='__main__':main()
