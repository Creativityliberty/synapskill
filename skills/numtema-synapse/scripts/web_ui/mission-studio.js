/* Mission Studio v0.5 — anonymous client-side workflow builder.
   Calls ONLY the three public MCP planning/validation tools. No persistence, no LLM execution. */
(() => {
  'use strict';
  const el = id => document.getElementById(id);
  if (!el('studio-generate')) return;
  const meta = {
    'io.modelcontextprotocol/protocolVersion': '2026-07-28',
    'io.modelcontextprotocol/clientInfo': {name: 'numtema-mission-studio', version: '0.5.0'},
    'io.modelcontextprotocol/clientCapabilities': {}
  };
  const PRESETS = {
    landing: {
      name: 'Landing page & conversion', agent: 'Rhetorica',
      draft: 'Rédiger une proposition de structure de landing page (brouillon uniquement)',
      template: 'HERO : {{offer}}\nPUBLIC : {{audience}}\nBÉNÉFICE : {{benefit}}\nOBJECTIF : {{goal}}\nCTA : Demander une présentation',
      fragments: ['HERO', 'BÉNÉFICE', 'CTA']
    },
    strategy: {
      name: 'Cadrage stratégique', agent: 'Mapper',
      draft: 'Construire une trame de cadrage stratégique, sans prétendre effectuer une recherche',
      template: 'MISSION : {{goal}}\nSUJET : {{offer}}\nPUBLIC : {{audience}}\nRÉSULTAT : {{benefit}}\nLIVRABLE : Note de cadrage à vérifier',
      fragments: ['MISSION', 'RÉSULTAT', 'LIVRABLE']
    },
    content: {
      name: 'Plan éditorial', agent: 'Rhetorica',
      draft: 'Définir une trame éditoriale contrôlable, sans publication',
      template: 'ANGLE : {{offer}}\nCIBLE : {{audience}}\nPROMESSE : {{benefit}}\nOBJECTIF : {{goal}}\nLIVRABLE : Plan de contenu à compléter',
      fragments: ['ANGLE', 'PROMESSE', 'LIVRABLE']
    }
  };
  const names = {brief: 'Cadrage & contexte', draft: 'Livrable structuré', review: 'Contrôle qualité'};
  let lastBlueprint = null;
  let lastMission = null;
  let selectedTask = null;
  let rpcId = 50;
  let editRevision = 0;

  function status(message, kind) {
    const node = el('studio-message');
    node.textContent = message;
    node.className = 'studio-message' + (kind ? ' ' + kind : '');
  }
  function clean(id, limit) { return el(id).value.trim().slice(0, limit); }
  function collect() {
    const form = {
      mode: el('mission-preset').value,
      title: clean('mission-title', 100),
      goal: clean('mission-goal', 600),
      offer: clean('mission-offer', 140),
      audience: clean('mission-audience', 140),
      benefit: clean('mission-benefit', 200),
      constraints: clean('mission-constraints', 400)
    };
    if (!PRESETS[form.mode]) throw new Error('Type de mission non reconnu.');
    for (const key of ['title', 'goal', 'offer', 'audience', 'benefit']) {
      if (!form[key]) {
        const fields = {title:'mission-title',goal:'mission-goal',offer:'mission-offer',audience:'mission-audience',benefit:'mission-benefit'};
        el(fields[key]).focus();
        throw new Error('Complétez les champs obligatoires pour compiler le workflow.');
      }
    }
    return form;
  }
  function makeBlueprint(form) {
    const preset = PRESETS[form.mode];
    const unique = (globalThis.crypto && crypto.randomUUID) ? crypto.randomUUID().slice(0, 8) : String(Date.now());
    const missionId = 'STUDIO-' + unique.toUpperCase();
    const fields = ['offer', 'audience', 'benefit', 'goal'];
    return {
      mission_id: missionId,
      context: {
        origin: 'anonymous_mission_studio', mode: form.mode, title: form.title,
        goal: form.goal, constraints: form.constraints,
        environment: 'public_planning_only', execute: false
      },
      steps: [
        {
          id: 'brief', agent_id: 'FocusAgent',
          objective: 'Structurer le brief : ' + form.title,
          tool: 'local.extract_fields', capability: 'read',
          params: {data: {offer:form.offer,audience:form.audience,benefit:form.benefit,goal:form.goal},fields},
          expected_keys: fields, checks: {required_keys: fields}, max_revisions: 0
        },
        {
          id: 'draft', agent_id: preset.agent, depends_on: ['brief'],
          objective: preset.draft, tool: 'local.render_template', capability: 'draft',
          params: {values_from_task: 'brief', template: preset.template},
          expected_keys: ['text'],
          checks: {required_keys:['text'],required_text:preset.fragments}, max_revisions: 1,
          excluded_tasks: ['Publication externe', 'Exécution automatique']
        },
        {
          id: 'review', agent_id: 'VerifierAgent', depends_on: ['draft'],
          objective: 'Vérifier les sections obligatoires du livrable : ' + preset.name,
          tool: 'local.assert_contains', capability: 'read',
          params: {source_task:'draft',fragments:preset.fragments},
          expected_keys: ['passed','evidence'],
          checks: {required_keys:['passed','evidence'],require_passed:true},
          max_revisions: 0
        }
      ]
    };
  }
  async function call(name, args) {
    // Public endpoint. Never sends cookies, tokens or privileged claims.
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 12000);
    try {
      const response = await fetch('/mcp', {
        method: 'POST', credentials: 'omit', cache: 'no-store',
        headers: {'Content-Type':'application/json'}, signal: controller.signal,
        body: JSON.stringify({jsonrpc:'2.0',id:++rpcId,method:'tools/call',
                              params:{_meta:meta,name,arguments:args}})
      });
      if (!response.ok) throw new Error('Serveur indisponible (HTTP ' + response.status + ').');
      const packet = await response.json();
      if (packet.error) throw new Error(packet.error.message || 'Erreur JSON-RPC.');
      const result = packet.result;
      if (!result || result.isError || !result.structuredContent) {
        const detail = result && result.structuredContent && result.structuredContent.error;
        throw new Error(detail || 'Le serveur n\'a pas retourné de données exploitables.');
      }
      return result.structuredContent;
    } catch (error) {
      if (error.name === 'AbortError') throw new Error('Délai dépassé : le serveur ne répond pas.');
      throw error;
    } finally {
      clearTimeout(timeout);
    }
  }
  function span(text) { const node=document.createElement('span'); node.textContent=text; return node; }
  function renderTask(task) {
    selectedTask = task.id;
    const contract = task.contract;
    el('studio-contract-name').textContent = contract.identity.agent_id + ' / ' + names[task.id];
    el('studio-contract-objective').textContent = contract.mission.objective;
    el('studio-contract-meta').replaceChildren(
      span('OUTIL : ' + task.tool),
      span('CAPACITÉ : ' + (contract.permissions.draft ? 'READ / DRAFT' : 'READ')),
      span('RÉVISIONS : ' + contract.reflection.max_revisions)
    );
    el('studio-contract-json').textContent = JSON.stringify(contract,null,2);
    for (const button of el('studio-dag').querySelectorAll('.studio-node')) {
      const active = button.dataset.task === task.id;
      button.classList.toggle('selected',active);
      button.setAttribute('aria-pressed',String(active));
    }
  }
  function render(mission, plan, form) {
    el('studio-empty').hidden=true;
    el('studio-output').hidden=false;
    el('studio-mission-label').textContent=mission.mission_id + ' / ' + PRESETS[form.mode].name.toUpperCase();
    el('studio-mission-name').textContent=form.title;
    el('studio-order').textContent=plan.order.length+' contrats CoR validés · Ordre DAG contrôlé · 0 exécution';
    el('studio-validation').textContent='✓ VALIDÉ';
    el('studio-state').textContent='PLANNED';
    el('studio-state').classList.add('ready');
    const dag=el('studio-dag');
    dag.replaceChildren();
    plan.order.forEach((id,index) => {
      const task=mission.tasks.find(item=>item.id===id);
      const row=document.createElement('div'); row.className='studio-node-row';
      const track=document.createElement('div'); track.className='studio-node-track';
      const count=document.createElement('span'); count.className='studio-node-index';count.textContent=String(index+1).padStart(2,'0');
      const line=document.createElement('span');line.className='studio-node-line';track.append(count,line);
      const button=document.createElement('button');button.type='button';button.className='studio-node';button.dataset.task=id;
      const text=document.createElement('span');
      const title=document.createElement('strong');title.textContent=names[id]||id;
      const detail=document.createElement('small');detail.textContent=task.contract.identity.agent_id+' · '+task.tool;
      text.append(title,detail);
      const badge=document.createElement('em');badge.textContent='CoR ✓';
      button.append(text,badge);
      button.addEventListener('click',()=>renderTask(task));
      row.append(track,button);dag.append(row);
    });
    renderTask(mission.tasks.find(t=>t.id===plan.order[0]));
  }
  function download(data, filename) {
    const blob = new Blob([JSON.stringify(data,null,2)+'\n'],{type:'application/json'});
    const url=URL.createObjectURL(blob);
    const link=document.createElement('a');link.href=url;link.download=filename;
    document.body.append(link);link.click();link.remove();
    setTimeout(()=>URL.revokeObjectURL(url),2000);
  }
  function invalidate() {
    editRevision += 1;
    if (!lastMission) return;
    lastMission=null;lastBlueprint=null;selectedTask=null;
    el('studio-output').hidden=true;el('studio-empty').hidden=false;
    el('studio-state').textContent='MODIFIÉ';el('studio-state').classList.remove('ready');
    status('Le brief a changé. Recompilez pour obtenir un plan à jour.');
  }
  async function generate() {
    const button=el('studio-generate');
    if (button.disabled) return;
    let form;
    try {form=collect();} catch(e) {status(e.message,'error');return;}
    invalidate();
    const compiledRevision = editRevision;
    const assertFresh = () => {if(compiledRevision !== editRevision) throw new Error('Le brief a changé pendant la compilation. Relancez-la.');};
    button.disabled=true;button.textContent='Validation CoR en cours…';
    status('Compilation avec Agent Forge puis vérification des dépendances.');
    try {
      const blueprint=makeBlueprint(form);
      const mission=await call('numtema.compile_blueprint',{blueprint});
      assertFresh();
      if (!Array.isArray(mission.tasks) || mission.tasks.length!==3)
        throw new Error('Nombre de contrats inattendu.');
      const plan=await call('numtema.plan_workflow',{mission});
      assertFresh();
      if (plan.status!=='PLANNED' || !Array.isArray(plan.order) || plan.order.length!==3)
        throw new Error('DAG non validé : '+(plan.issues||[]).join(', '));
      for(const task of mission.tasks){
        const checked=await call('numtema.validate_cor',{contract:task.contract});
        assertFresh();
        if(!checked.valid) throw new Error('CoR '+task.id+' : '+(checked.issues||[]).join(', '));
      }
      lastBlueprint=blueprint;lastMission=mission;
      render(mission,plan,form);
      status('Mission structurée et validée. Aucun agent n’a été exécuté.','success');
    } catch(error) {
      status('Compilation impossible : '+error.message,'error');
    } finally {
      button.disabled=false;button.textContent='Compiler la mission ↗';
    }
  }
  el('studio-generate').addEventListener('click',generate);
  for(const id of ['mission-title','mission-offer','mission-audience','mission-benefit']){
    el(id).addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();generate();}});
  }
  el('studio-export').addEventListener('click',()=>{if(lastMission)download(lastMission,lastMission.mission_id.toLowerCase()+'-cor.json');});
  el('studio-export-blueprint').addEventListener('click',()=>{if(lastBlueprint)download(lastBlueprint,lastBlueprint.mission_id.toLowerCase()+'-blueprint.json');});
  el('studio-demo').addEventListener('click',()=>{
    el('mission-preset').value='landing';
    el('mission-title').value='Atelier conversion — exemple fictif';
    el('mission-goal').value='Structurer une page de présentation claire pour une offre fictive, sans publication.';
    el('mission-offer').value='Audit marketing découverte';
    el('mission-audience').value='Entrepreneurs et petites entreprises';
    el('mission-benefit').value='Identifier trois priorités concrètes';
    el('mission-constraints').value='Ne pas inventer de témoignages, de chiffres ou de résultats.';
    invalidate();
    status('Exemple fictif chargé. Vous pouvez modifier le brief ou le compiler.');
  });
  for(const id of ['mission-preset','mission-title','mission-goal','mission-offer','mission-audience','mission-benefit','mission-constraints']){
    el(id).addEventListener('input',invalidate);
    el(id).addEventListener('change',invalidate);
  }
})();
