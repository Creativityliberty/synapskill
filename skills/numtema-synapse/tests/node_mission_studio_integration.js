/* Minimal DOM harness: executes the actual Mission Studio browser code against the local MCP HTTP API.
   Usage: SYNAPSE_TEST_URL=http://127.0.0.1:8019 node tests/node_mission_studio_integration.js */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const base=process.env.SYNAPSE_TEST_URL || 'http://127.0.0.1:8019';
class Element{
  constructor(tag='div',id=''){this.tagName=tag;this.id=id;this.children=[];this.listeners={};this.dataset={};this.hidden=false;this.value='';this.textContent='';this.className='';this.attributes={};this.focused=false;this.classList={add:x=>this.className+=' '+x,remove:x=>this.className=this.className.replace(x,''),toggle:(x,on)=>{this.className=this.className.replace(x,'')+(on?' '+x:'')}};}
  addEventListener(name,callback){this.listeners[name]=callback}
  async click(){if(this.listeners.click)return await this.listeners.click({preventDefault(){}})}
  setAttribute(name,value){this.attributes[name]=value}
  append(...nodes){this.children.push(...nodes)}
  replaceChildren(...nodes){this.children=nodes}
  remove(){}
  focus(){this.focused=true}
  querySelectorAll(selector){if(selector==='.studio-node')return this.children.flatMap(n=>n.children.filter(ch=>ch.className.includes('studio-node'))); return []}
}
const elements=new Map();
const el=id=>{if(!elements.has(id))elements.set(id,new Element('div',id));return elements.get(id)};
const document={getElementById:el,createElement:tag=>new Element(tag),body:new Element('body')};
const getOriginal=global.fetch;
const calls=[];
const fetch=async (url,options={})=>{
  calls.push(JSON.parse(options.body||'{}').params?.name||String(url));
  return getOriginal(base+url,options);
};
let lastDownloaded=null;
const URLshim={createObjectURL:blob=>{lastDownloaded=blob;return 'blob:local';},revokeObjectURL() {}};
const context={document,fetch,crypto:require('node:crypto').webcrypto,AbortController,Blob,URL:URLshim,setTimeout,clearTimeout,console};
const script=fs.readFileSync(path.resolve(__dirname,'../scripts/web_ui/mission-studio.js'),'utf8');
vm.runInNewContext(script,context,{filename:'mission-studio.js'});
async function run(){
  await el('studio-demo').click();
  assert.equal(el('mission-title').value,'Atelier conversion — exemple fictif');
  await el('studio-generate').click();
  assert.equal(el('studio-state').textContent,'PLANNED');
  assert.equal(el('studio-empty').hidden,true);
  assert.equal(el('studio-output').hidden,false);
  assert.equal(el('studio-dag').children.length,3);
  assert.match(el('studio-message').textContent,/validée/);
  assert.deepEqual(calls.filter(x=>x.startsWith('numtema.')),[
    'numtema.compile_blueprint','numtema.plan_workflow',
    'numtema.validate_cor','numtema.validate_cor','numtema.validate_cor'
  ]);
  await el('studio-export').click();
  assert(lastDownloaded);
  const compiled=JSON.parse(await lastDownloaded.text());
  assert.equal(compiled.tasks.length,3);
  assert(compiled.tasks.every(t=>t.contract.permissions.external_write===false));
  assert(compiled.tasks.every(t=>t.contract.permissions.financial_spend===false));
  el('mission-title').value='changé';
  el('mission-title').listeners.input();
  assert.equal(el('studio-output').hidden,true);
  assert.equal(el('studio-state').textContent,'MODIFIÉ');
  // v0.6: opt-in planning for a private LLM worker, not remote execution.
  el('mission-title').value='Atelier IA privé — fictif';
  el('mission-private-ai').checked=true;
  el('mission-private-ai').listeners.change();
  await el('studio-generate').click();
  assert.equal(el('studio-state').textContent,'PLANNED');
  assert.match(el('studio-message').textContent,/IA locale planifiée/);
  await el('studio-export-blueprint').click();
  const aiBlueprint=JSON.parse(await lastDownloaded.text());
  assert.equal(aiBlueprint.steps[1].tool,'llm.draft');
  await el('studio-export').click();
  const aiCompiled=JSON.parse(await lastDownloaded.text());
  assert.equal(aiCompiled.tasks[1].tool,'llm.draft');
  assert(aiCompiled.tasks.every(t=>t.contract.permissions.external_write===false));
  // Confirm no real model backend or remote execution was invoked by browser.
  assert.equal(calls.some(x=>/execute_workflow/.test(x)),false);
  console.log('PASS Mission Studio v0.6 DOM + JSON-RPC + private LLM blueprint export (no execution)');
}
run().catch(e=>{console.error(e);process.exitCode=1});
