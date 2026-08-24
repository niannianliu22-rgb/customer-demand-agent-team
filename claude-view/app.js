const requestedRunId=new URLSearchParams(window.location.search).get('run_id');
const validRunId=requestedRunId&&/^RUN-[A-Za-z0-9-]+$/.test(requestedRunId);
const base=validRunId?`../runs/${encodeURIComponent(requestedRunId)}/view/`:'../examples/demo-view/';
const files=['01_run_overview','02_agent_graph','03_execution_timeline','04_gate_status','05_model_routing','06_artifact_lineage','07_warning_summary','08_forecast_summary','09_action_summary','10_e2e_evidence'];
const $=s=>document.querySelector(s), esc=x=>String(x??'—').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
async function get(n){let r=await fetch(base+n+'.json');if(!r.ok)throw Error(n);return r.json()}
function missing(err){document.querySelectorAll('section,#metrics').forEach(x=>x.innerHTML='<div class="warn">Data Missing / Artifact Missing: '+esc(err.message)+'</div>')}
(async()=>{try{let [o,g,t,gs,m,,w,f,a,e]=await Promise.all(files.map(get));$('#subtitle').textContent=`${o.run_id} · ${o.status} · Final E2E QA ${o.final_e2e_qa}`;let met=[['Run',o.run_id],['Agents',`${o.agent_completed}/${o.agent_total}`],['Gates',`${o.gate_passed}/${o.gate_total}`],['Forecast',o.forecast_count],['Action',o.action_count],['E2E QA',o.final_e2e_qa]];$('#metrics').innerHTML=met.map(x=>`<div class="metric"><span>${x[0]}</span><b>${esc(x[1])}</b></div>`).join('');
$('#flow').innerHTML=g.nodes.filter(x=>x.agent_id>='A03').map((x,i)=>`${i?'<span class="arrow">→</span>':''}<div class="node ${['A07','A08'].includes(x.agent_id)?'parallel':''}">${x.agent_id} ${esc(x.name)}<small class="muted"> · ${x.status}</small></div>`).join('');
let llm=m.agents.filter(x=>x.provider!=='NONE');$('#models').innerHTML='<table><tr><th>Agent</th><th>Provider</th><th>Model</th><th>Effort</th></tr>'+llm.map(x=>`<tr><td>${x.agent_id}</td><td>${x.provider}</td><td>${x.concrete_model}</td><td>${x.effort}</td></tr>`).join('')+'</table><p class="pass">Cross Provider = '+m.cross_provider_check+'</p>';
$('#gates').innerHTML=gs.gates.map(x=>`<div class="gate"><b>${esc(x.gate_name||x.name||x.decision)}</b><br><span class="${x.decision==='PASS'?'pass':'warn'}">${esc(x.decision)}</span></div>`).join('');
$('#timeline').innerHTML=t.events.slice(-70).reverse().map(x=>`<div class="event"><b>${esc(x.type)}</b> · ${esc(x.agent_id||x.event_type||'Run')} <span class="muted">${esc(x.timestamp||x.started_at||'')}</span></div>`).join('');
let bars=(obj)=>'<div class="bars">'+Object.entries(obj).map(([k,v])=>`<div class="bar"><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join('')+'</div>';
$('#forecast').innerHTML=`<p><b>${f.total_forecasts}</b> total forecasts</p>`+bars({...f.status_distribution,...f.horizon_distribution});$('#action').innerHTML=`<p><b>${a.total_actions}</b> total actions</p>`+bars({...a.horizon_distribution,...a.priority_distribution,...a.business_direction_distribution});
}catch(err){missing(err)}})();
