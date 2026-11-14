"""Exercise the actual buildless browser script's collection timing hooks."""
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(shutil.which('node') is None, reason='Node is needed to run the browser script harness')
def test_answer_interactions_capture_check_time_separately_from_next():
    script = r'''
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
let clock = '2026-11-04T18:00:00.000Z';
let answer = 'yes';
const nodes = new Map(), requests = [];
function node(id) {
  if (!nodes.has(id)) nodes.set(id, {
    listeners: {}, validity: {valid:true},
    addEventListener(type, handler) { this.listeners[type] = handler; },
    setAttribute() {}, replaceChildren() {}, focus() {},
  });
  return nodes.get(id);
}
const context = vm.createContext({
  setTimeout, clearTimeout, AbortController,
  document: {
    getElementById(id) { return ['date-answer','text-answer'].includes(id) ? null : node(id); },
    querySelector(selector) { return selector.includes('input[name=') && answer ? {value:answer} : null; },
    querySelectorAll() { return []; }, addEventListener() {},
  },
  window: {addEventListener() {}, scrollTo() {}},
  sessionStorage: {getItem() { return null; }, setItem() {}},
  crypto: {randomUUID() { return 'test-uuid'; }},
  Date: class extends Date { constructor(...args) { super(...(args.length ? args : [clock])); } },
  fetch(path, options) { requests.push({path, data:JSON.parse(options.body)}); return new Promise(() => {}); },
});
vm.runInContext(fs.readFileSync('scripts/assets/clickthrough/app.js','utf8'), context);
vm.runInContext(`
  renderVisual = () => {}; inputControls = () => {}; detailsRows = () => {}; renderChat = () => {};
  page = {node_id:'test-question',section:'Test',section_number:1,section_count:5,
          body:[],title:'Test',input_type:'choice',progress_stage:0};
  render(false);
`, context);
function submit() {
  vm.runInContext("updateWorkflow('/api/advance',{history:[],value:selectedValue()})", context);
  return requests.at(-1).data.collection;
}
// Accepting a prefilled answer has no invented check timestamp.
clock = '2026-11-04T18:00:01.000Z';
assert.equal(submit().checked_at, null);
// A choice records selection time; waiting before Next preserves that time.
clock = '2026-11-04T18:00:02.000Z';
node('answer-control').listeners.change();
clock = '2026-11-04T18:00:05.000Z';
let timing = submit();
assert.equal(timing.displayed_at, '2026-11-04T18:00:00.000Z');
assert.equal(timing.checked_at, '2026-11-04T18:00:02.000Z');
assert.equal(timing.ended_at, '2026-11-04T18:00:05.000Z');
// Input edits update the most recent check, and clearing removes it.
clock = '2026-11-04T18:00:06.000Z';
node('answer-control').listeners.input();
assert.equal(submit().checked_at, '2026-11-04T18:00:06.000Z');
answer = '';
node('answer-control').listeners.input();
assert.equal(submit().checked_at, null);
// Displaying another page resets the check timestamp.
answer = 'yes';
clock = '2026-11-04T18:00:07.000Z';
vm.runInContext('render(false)', context);
assert.equal(submit().checked_at, null);
assert.equal(submit().displayed_at, '2026-11-04T18:00:07.000Z');
// Text clarification questions expose an explicit unknown without treating it as text.
vm.runInContext("page.input_type = 'text'", context);
node('text-unknown').checked = true;
assert.equal(vm.runInContext('selectedValue()', context), 'unknown');
node('text-unknown').checked = false;
// Back followed by Next must show a main SOL choice even if an earlier edit
// marked that saved choice automatic. Later automatic nested choices stay saved.
vm.runInContext(`
  page = {node_id:'sol_payment_age', input_type:'choice'};
  history = [{node_id:'sol_payment_age', value:'yes'},
             {node_id:'statute_of_limitations_decision', value:'no', automatic:true},
             {node_id:'sol_checkboxes_first_third', value:'yes', automatic:true}];
  cursor=0; busy=false; responsePending=false; responseFailed=false; editMode=false;
  goto=async index=>{globalThis.stoppedAt=index;};
`, context);
node('answer-form').listeners.submit({preventDefault() {}});
assert.equal(context.stoppedAt, 1);
vm.runInContext('cursor=2', context);
assert.equal(vm.runInContext('backIndex()', context), 1);
// Re-answering a saved disagreement must likewise visit personal timing.
answer='no';
vm.runInContext(`
  page={node_id:'sol_payment_estimate_agree',input_type:'choice'};
  history=[{node_id:'sol_payment_estimate_agree',value:'no'},
           {node_id:'sol_payment_age',value:'yes',automatic:true}];
  cursor=0; stoppedAt=null;
`, context);
node('answer-form').listeners.submit({preventDefault() {}});
assert.equal(context.stoppedAt, 1);
vm.runInContext('cursor=2', context);
assert.equal(vm.runInContext('backIndex()', context), 1);
'''
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(['node', '-e', script], cwd=root, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(shutil.which('node') is None, reason='Node is needed for the browser harness')
def test_inline_responses_replace_drafts_and_ignore_stale_dynamic_previews():
    script = r'''
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
let answer = 'yes', textInput = null, timerId = 0;
const nodes = new Map(), requests = [], timers = new Map();
function makeNode() { return {
  children:[], listeners:{}, validity:{valid:true},
  append(...children) {this.children.push(...children);},
  replaceChildren(...children) {this.children=children;},
  addEventListener(type, handler) {this.listeners[type]=handler;},
  setAttribute() {}, focus() {}, close() {},
}; }
function node(id) {if(!nodes.has(id)) nodes.set(id,makeNode());return nodes.get(id);}
const context = vm.createContext({
  setTimeout(callback) {const id=++timerId;timers.set(id,callback);return id;},
  clearTimeout(id) {timers.delete(id);}, AbortController,
  document: {
    getElementById(id) {if(id==='date-answer')return null;if(id==='text-answer')return textInput;return node(id);},
    createElement(tag) {const n=makeNode();n.tagName=tag;return n;},
    querySelector(selector) {return selector.includes('input[name=') && answer ? {value:answer}:null;},
    querySelectorAll() {return [];}, addEventListener() {},
  },
  window: {addEventListener() {},scrollTo() {}},
  sessionStorage:{getItem() {return null;},setItem() {}},
  crypto:{randomUUID() {return 'test-uuid';}},
  fetch(path, options) {return new Promise(resolve=>requests.push({path,data:JSON.parse(options.body),signal:options.signal,resolve}));},
});
vm.runInContext(fs.readFileSync('scripts/assets/clickthrough/app.js','utf8'),context);
function run(code) {return vm.runInContext(code,context);}
function responseText() {return node('answer-response').children.map(n=>n.textContent).filter(Boolean).join(' ');}
function fireTimer() {const [id,callback]=[...timers.entries()].at(-1);timers.delete(id);return callback();}
function resolveRequest(request, response, ok=true) {request.resolve({ok,json:async()=>response});}
(async()=>{
  requests.length=0;
  run(`busy=false;history=[];cursor=0;revision=null;
       page={node_id:'waiver_payment_without_penalty',input_type:'choice',answer_responses:{
         yes:['This defense may apply.'],no:['This defense does not apply.'],unknown:['Ask clinic staff.']}};
       displayedAt='2026-11-07T18:00:00.000Z';checkedAt=null;
       updateNext();`);
  assert.match(responseText(),/This defense may apply/);
  assert.equal(requests.length,0);
  assert.equal(run('history.length'),0);
  assert.equal(run('page.node_id'),'waiver_payment_without_penalty');
  assert.equal(run('checkedAt'),null);
  answer='no';run('updateNext()');
  assert.match(responseText(),/does not apply/);assert.doesNotMatch(responseText(),/may apply/);
  answer='unknown';run('updateNext()');assert.match(responseText(),/Ask clinic staff/);
  answer='';run('updateNext()');assert.equal(node('answer-response').hidden,true);assert.equal(node('next').disabled,true);
  // Restoring a saved answer renders its response without recording an interaction.
  answer='yes';run('updateNext()');assert.equal(node('next').disabled,false);assert.equal(run('checkedAt'),null);
  // Dynamic text previews stay separate from /advance and /edit.
  textInput={value:'Spanish',validity:{valid:true}};
  run("page={node_id:'language_primary',input_type:'text',dynamic_response:true};updateNext()");
  assert.equal(node('next').disabled,true);
  const first=fireTimer();const oldRequest=requests.at(-1);
  assert.equal(oldRequest.path,'/api/preview');assert.equal(oldRequest.data.value,'Spanish');
  assert.equal('collection' in oldRequest.data,false);
  textInput.value='French';run('updateNext()');assert.equal(oldRequest.signal.aborted,true);
  const second=fireTimer();const freshRequest=requests.at(-1);
  resolveRequest(freshRequest,{node_id:'language_primary',response:['Your primary language is French.']});await second;
  assert.match(responseText(),/French/);assert.equal(node('next').disabled,false);
  resolveRequest(oldRequest,{node_id:'language_primary',response:['Your primary language is Spanish.']});await first;
  assert.match(responseText(),/French/);assert.doesNotMatch(responseText(),/Spanish/);
  assert.equal(run('history.length'),0);
  assert.equal(run('displayedAt'),'2026-11-07T18:00:00.000Z');
  // Clearing a field cancels pending work and removes obsolete feedback.
  textInput.value='German';run('updateNext()');const third=fireTimer();const abandoned=requests.at(-1);
  textInput.value='';run('updateNext()');assert.equal(node('answer-response').hidden,true);
  resolveRequest(abandoned,{response:['German']});await third;assert.equal(node('answer-response').hidden,true);
  // A failed dynamic preview requires retry rather than advancing unseen.
  textInput.value='Spanish';run('updateNext()');const failed=fireTimer();
  resolveRequest(requests.at(-1),{detail:'Unavailable'},false);await failed;
  assert.match(responseText(),/could not load/);assert.equal(node('next').disabled,true);
  const retry=node('answer-response').children.at(-1);assert.equal(retry.textContent,'Try again');retry.onclick();
  const retried=fireTimer();resolveRequest(requests.at(-1),{response:['Spanish']});await retried;
  assert.match(responseText(),/Spanish/);assert.equal(node('next').disabled,false);
  assert.equal(requests.every(r=>r.path==='/api/preview'),true);
  // Source lists remain semantic lists; source/user text is inserted as text.
  const formatted=run(`scriptNodes([], [
    {type:'paragraph',text:'First paragraph.'},
    {type:'list',ordered:false,items:[{text:'One'},{text:'<b>Two</b>'}]},
    {type:'paragraph',text:'Last paragraph.'}
  ])`);
  assert.equal(formatted[0].tagName,'p');assert.equal(formatted[1].tagName,'ul');
  assert.equal(formatted[1].children.length,2);assert.equal(formatted[1].children[1].tagName,'li');
  assert.equal(formatted[1].children[1].textContent,'<b>Two</b>');
  assert.equal(formatted[2].textContent,'Last paragraph.');

  assert.equal(run("friendly('After 2025-09-20?')"),'After September 20, 2025?');
  // An edit may retain several answers, but the browser must show each screen.
  run('render=()=>setBusy(false)');
  const workflow=run("updateWorkflow('/api/edit',{history:[{node_id:'earlier',value:'yes'}],edit_index:0,value:'no'})");
  resolveRequest(requests.at(-1),{
    history:[{node_id:'earlier',value:'no'},
             {node_id:'laches',value:'yes',automatic:true},
             {node_id:'laches_statements',value:'yes',automatic:true}],
    revision:{saved_answers:[]},page:{node_id:'guided_laches_summary'}
  });
  for(let i=0;i<8;i++) await Promise.resolve();
  assert.equal(requests.at(-1).path,'/api/state');
  assert.equal(requests.at(-1).data.history.length,1);
  resolveRequest(requests.at(-1),{node_id:'laches',input_type:'choice'});
  await workflow;
  assert.equal(run('cursor'),1);assert.equal(run('page.node_id'),'laches');
  textInput=null;answer='yes';
  const next=node('answer-form').listeners.submit({preventDefault() {}});
  assert.equal(requests.at(-1).data.history.length,2);
  resolveRequest(requests.at(-1),{node_id:'laches_statements',input_type:'choice'});
  await next;
  assert.equal(run('cursor'),2);assert.equal(run('backIndex()'),1);

})().catch(error=>{console.error(error);process.exitCode=1;});
'''
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(['node', '-e', script], cwd=root, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
