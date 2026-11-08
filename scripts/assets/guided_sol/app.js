'use strict';
const $ = (id) => document.getElementById(id);
const debugMode = document.body?.dataset?.debugMode === 'true';
const storageKey = 'debt-case-guide:guided-defenses:2026-11-07:collection-v4' + (debugMode ? ':debug' : '');
let debugSection = null;
let history = [], cursor = 0, page = null, revision = null, editMode = false, busy = false, chatBusy = false, chatKey = '', chatController = null;
const drafts = new Map(), conversations = new Map();
let generation = 0;
let responseGeneration = 0, responseController = null, responseTimer = null, responsePending = false, responseFailed = false;
let sessionId = crypto.randomUUID(), displayedAt = new Date().toISOString(), checkedAt = null;

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function dateLabel(value) {
  const [year, month, day] = value.split('-').map(Number);
  return new Intl.DateTimeFormat('en-US', {month:'short', day:'numeric', year:'numeric', timeZone:'UTC'}).format(new Date(Date.UTC(year, month-1, day)));
}
function friendly(text) { return text.replace(/\b\d{4}-\d{2}-\d{2}\b/g, (value) => dateLabel(value)); }
function prefixKey() { return JSON.stringify(history.slice(0, cursor)); }
function save() { try { sessionStorage.setItem(storageKey, JSON.stringify({history, cursor, revision, editMode, sessionId, debugSection})); } catch (_) {} }
function setError(message) { $('form-error').textContent = message; $('form-error').hidden = !message; }
function setBusy(value) {
  busy = value;
  $('main-content').setAttribute('aria-busy', String(value));
  $('next').disabled = value || responsePending || responseFailed || !hasAnswer();
  $('restart').disabled = value;
  for(const button of document.querySelectorAll('.debug-section-button')) button.disabled=value;
}
async function request(path, data, signal) {
  if(debugMode && path!=='/api/collection/end') data={...data,debug_section:debugSection};
  const response = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data), signal});
  const result = await response.json();
  if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Please check the answer and try again.');
  return result;
}
async function load(nextHistory = history, nextCursor = cursor, focus = true) {
  const currentGeneration = ++generation;
  setBusy(true); setError('');
  try {
    const result = await request('/api/state', {history:nextHistory.slice(0, nextCursor), revision, session_id:debugMode?null:sessionId});
    if (currentGeneration !== generation) return;
    history = nextHistory; cursor = nextCursor; page = result; save(); render(focus);
  } catch (error) {
    if (currentGeneration !== generation) return;
    setBusy(false); setError(error.message || 'The review could not connect. Please try again.');
    if (!page) {
      $('question').textContent = 'We couldn’t load your review';
      const retry = element('button', 'outline-button', 'Try again');
      retry.type = 'button'; retry.onclick = () => load(); $('answer-control').replaceChildren(retry);
    }
  }
}
function selectedValue() {
  if (!page) return '';
  if (['continue','summary','preliminary_summary'].includes(page.input_type)) return 'continue';
  if (['text','currency'].includes(page.input_type)) return $('text-unknown')?.checked ? 'unknown' : $('text-answer')?.value.trim() || '';
  const chosen = document.querySelector('input[name="answer"]:checked')?.value || '';
  return chosen === 'date' ? $('date-answer')?.value || '' : chosen;
}
function hasAnswer() {
  if (!page || page.input_type === 'complete') return false;
  return !!selectedValue() && ($('date-answer')?.disabled !== false || $('date-answer').validity.valid) && (!$('text-answer') || $('text-answer').validity.valid);
}
function rememberDraft() { if (page) drafts.set(page.node_id + prefixKey(), selectedValue()); }
function updateNext() { rememberDraft(); updateAnswerResponse(); }
function clearAnswerResponse() {
  responseGeneration++;
  responseController?.abort(); responseController=null;
  clearTimeout(responseTimer); responseTimer=null;
  responsePending=false;responseFailed=false;
  $('answer-response').replaceChildren();$('answer-response').hidden=true;
}
function scriptNodes(texts, blocks) {
  if(!blocks) return texts.filter(Boolean).map(text=>element('p','script-paragraph',friendly(text)));
  return blocks.map(block=>{
    if(block.type==='paragraph') return element('p','script-paragraph',friendly(block.text));
    const list=element(block.ordered?'ol':'ul','script-list');
    for(const item of block.items) {
      const row=element('li','',friendly(item.text));
      if(item.children) row.append(...scriptNodes([],item.children));
      list.append(row);
    }
    return list;
  });
}
function showAnswerResponse(paragraphs,blocks) {
  const panel=$('answer-response');
  panel.replaceChildren();panel.hidden=!paragraphs.length;
  if(paragraphs.length) panel.append(element('h2','','Based on this answer'),...scriptNodes(paragraphs,blocks));
}
function updateAnswerResponse() {
  clearAnswerResponse();
  if(!page || !hasAnswer()) {setBusy(busy);return;}
  const value=selectedValue();
  if(page.answer_responses) {
    showAnswerResponse(page.answer_responses[value] || [],page.answer_response_blocks?.[value]);setBusy(busy);return;
  }
  if(!page.dynamic_response) {setBusy(busy);return;}
  const previewGeneration=responseGeneration;
  const previewHistory=history.slice(0,cursor), previewRevision=revision;
  responsePending=true;setBusy(busy);
  responseTimer=setTimeout(async()=>{
    responseController=new AbortController();
    try {
      const result=await request('/api/preview',{history:previewHistory,revision:previewRevision,value},responseController.signal);
      if(previewGeneration!==responseGeneration)return;
      showAnswerResponse(result.response,result.response_blocks);
    } catch(error) {
      if(previewGeneration!==responseGeneration || error.name==='AbortError')return;
      responseFailed=true;
      showAnswerResponse(['The response could not load. Try again before continuing.']);
      const retry=element('button','text-button','Try again');retry.type='button';retry.onclick=updateAnswerResponse;$('answer-response').append(retry);
    } finally {
      if(previewGeneration===responseGeneration){responsePending=false;setBusy(busy);}
    }
  },150);
}
function option(option, selected) {
  const label = element('label','choice');
  const radio = element('input'); radio.type='radio'; radio.name='answer'; radio.value=option.value; radio.checked=selected===option.value;
  const copy=element('span'); copy.append(element('span','choice-title',option.label));
  if(option.description) copy.append(element('span','choice-description',option.description));
  label.append(radio,copy); radio.addEventListener('change', updateNext); return label;
}
function inputControls() {
  const control=$('answer-control'); control.replaceChildren();
  const saved=history[cursor]?.node_id===page.node_id ? history[cursor].value : null;
  const draft=drafts.get(page.node_id + prefixKey());
  const selected=draft ?? saved ?? page.default_value ?? '';
  if (['text','currency'].includes(page.input_type)) {
    const label=element('label','field-label',page.field_label || 'Short answer'); label.htmlFor='text-answer';
    const input=element('input','text-input'); input.id='text-answer'; input.type=page.input_type==='currency'?'number':'text'; input.maxLength=300; input.value=page.allow_unknown && selected==='unknown' ? '' : selected; input.autocomplete='off'; input.required=true;
    if (page.input_type==='currency') {input.min='0.01';input.step='0.01';input.inputMode='decimal';}
    input.addEventListener('input', updateNext); control.append(label,input,element('p','input-hint',page.allow_unknown ? 'Short answer' : 'Short answer · You can edit the prefilled example.'));
    if (page.allow_unknown) {
      const unknownLabel=element('label','choice');
      const unknown=element('input'); unknown.type='checkbox'; unknown.id='text-unknown'; unknown.checked=selected==='unknown';
      input.disabled=unknown.checked;
      unknown.addEventListener('change',()=>{ input.disabled=unknown.checked; updateNext(); });
      unknownLabel.append(unknown,element('span','choice-title','I’m not sure')); control.append(unknownLabel);
    }
  } else if (page.input_type==='choice') {
    const fieldset=element('fieldset','choice-list'); fieldset.append(element('legend','',page.question_text || page.title));
    for(const item of page.options) fieldset.append(option(item,selected)); control.append(fieldset);
  } else if (page.input_type==='date') {
    const fieldset=element('fieldset','choice-list date-form'); fieldset.append(element('legend','',page.question_text || page.title));
    const special=page.date_alternatives.some(o=>o.value===selected);
    const dateSelected=!!selected && !special;
    const dateBox=element('div','date-field'), label=element('label');
    const radio=element('input'); radio.type='radio'; radio.name='answer'; radio.value='date'; radio.checked=dateSelected;
    label.append(radio,element('span','','Enter the date'));
    const input=element('input'); input.id='date-answer'; input.type='date'; input.setAttribute('aria-label','Date listed in the complaint'); input.value=dateSelected?selected:''; input.disabled=!dateSelected; input.required=true;
    dateBox.append(label,input); fieldset.append(dateBox);
    for(const item of page.date_alternatives) fieldset.append(option(item,selected));
    fieldset.addEventListener('change',()=>{ input.disabled = !radio.checked; updateNext(); });
    input.addEventListener('input',updateNext); control.append(fieldset,element('p','input-hint','Enter the date as shown in the complaint.'));
  } else if (page.input_type==='preliminary_summary') {
    control.append(detailsRows());
  } else if (page.input_type==='summary' || page.input_type==='complete') {
    if(page.input_type==='complete') {
      $('visual').append(element('div','complete-icon','✓'));
      control.append(element('p','completion-note','You’ve finished the 17 defenses in this prototype. You can go back or use Change to review your selections.'));
    }
    for (const group of page.groups || [{section:page.section,rows:page.rows}]) control.append(summaryTable(group));
    control.append(answerReview());
  }
}
function renderVisual() {
  const container=$('visual'); container.replaceChildren(); const visual=page.visual;
  if(!visual) return;
  if(visual.type==='timeline') {
    const timeline=element('div','timeline'); timeline.setAttribute('role','img');
    timeline.setAttribute('aria-label',`Last payment ${dateLabel(visual.payment)}; complaint filed ${dateLabel(visual.filing)}. About ${visual.months} months apart.`);
    const labels=element('div','timeline-labels');
    for(const [label,date] of [['Last payment',visual.payment],['Complaint filed',visual.filing]]) { const end=element('div','',label);end.append(element('strong','',dateLabel(date)));labels.append(end); }
    const track=element('div','timeline-track'); track.append(element('span','timeline-line'),element('span','timeline-chip',`About ${visual.months} months apart`),element('span','timeline-line'));
    timeline.append(labels,track); container.append(timeline);
  } else if(visual.type==='overview') {
    const overview=element('div','overview-visual');
    [['Verify case details','Review your complaint and account details once.'],['Review the defenses','Review 17 defenses in Attachment 4 order.'],['Complete Attachment 4','Fill out the form using the choices recorded here.']].forEach(([title,body],i)=>{ const card=element('div','overview-step');card.append(element('span','',String(i+1)),element('strong','',title),element('p','',body));overview.append(card); });
    container.append(overview);
  }
}
function editButton(index, label) {
  const button=element('button','text-button','Change');button.type='button';button.setAttribute('aria-label',`Change ${label}`);button.onclick=()=>goto(index,true);return button;
}
function summaryTable(group) {
  const table=element('section','selection-table'); table.setAttribute('aria-label',`${group.section} checkbox selections`);table.append(element('h2','',`Attachment 4 · ${group.section}`));
  for(const item of group.rows) {
    const row=element('div','selection-row'); const mark=element('span',`selection-mark${item.checked?' checked':''}`,item.checked?'✓':'');mark.setAttribute('aria-hidden','true');
    const content=element('div','selection-main');content.append(element('strong','',item.label),element('small','',item.detail),element('span',`selection-status${item.checked?' selected':''}`,item.status));row.append(mark,content);
    if(item.previous_status) content.append(element('small','selection-change',`Previously: ${item.previous_status}`));
    if(item.edit_index!==null) row.append(editButton(item.edit_index,item.label)); table.append(row);
  }
  return table;
}
function detailsRows(items = page.case_details) {
  const details=element('div');
  for(const item of items) { const row=element('div','review-detail'), text=element('div');text.append(element('strong','',item.label),element('span','',item.value));if(item.derived)text.append(element('small','','Same as plaintiff'));row.append(text);if(item.edit_index!==null) row.append(editButton(item.edit_index,item.label));details.append(row); }
  return details;
}
function answerReview() {
  const details=element('details','answer-review');
  details.append(element('summary','',page.input_type==='complete'?'Review the answers used for these defenses':'Review the answers used in this section'));
  const answers=page.review_answers || [];
  if(answers.length) details.append(detailsRows(answers));
  else { const empty=element('div');empty.append(element('p','quiet','No preliminary fields determine whether this checkbox is offered. Your choice is shown above.'));details.append(empty); }
  return details;
}
function render(focus=true) {
  $('question').textContent=page.title;
  $('eyebrow').textContent=page.section.toUpperCase();
  $('section-name').textContent=page.section;
  $('section-count').textContent=`${String(page.section_number).padStart(2,'0')} / ${String(page.section_count).padStart(2,'0')}`;
  $('body').replaceChildren(...scriptNodes(page.body,page.body_blocks));
  $('revision-notice').textContent=page.revision_notice||'';
  $('revision-notice').hidden=!page.revision_notice;
  $('why').textContent=page.why;$('aside-title').textContent=page.stage===2?'Your choices, in one place':'Why we ask';
  $('back').disabled=backIndex()<0;
  for(const li of document.querySelectorAll('[data-stage]')) { const stage=Number(li.dataset.stage);li.classList.toggle('active',stage===page.progress_stage);li.classList.toggle('done',!debugMode&&stage<page.progress_stage);if(stage===page.progress_stage)li.setAttribute('aria-current','step');else li.removeAttribute('aria-current');li.querySelector('.step-number').textContent=!debugMode&&stage<page.progress_stage?'✓':String(stage+1); }
  document.querySelector('.progress li.active')?.scrollIntoView({block:'nearest',inline:'center'});
  renderVisual();inputControls();updateAnswerResponse();$('case-fields').replaceChildren(detailsRows());
  $('next-label').textContent=page.next_label;$('next').hidden=page.input_type==='complete';
  $('step-note').textContent=['choice','date','text','currency'].includes(page.input_type)?'One question at a time':'';
  const nextKey=page.node_id+prefixKey();
  if(chatKey!==nextKey) {chatController?.abort();chatBusy=false;chatKey=nextKey;$('chat-send').disabled=false;$('chat-input').value='';renderChat();}
  $('chat-context').textContent=page.title;$('approved-text').replaceChildren(...scriptNodes([page.help_text],page.help_blocks));
  setBusy(false);if(focus){$('question').focus({preventScroll:true});window.scrollTo({top:0,behavior:'instant'});}
  displayedAt = new Date().toISOString();
  checkedAt = null;
}
function backIndex() {
  for(let index=cursor-1;index>=0;index--) if(!history[index].automatic && !['guided_mistake_intro','guided_unconscionable_contract_intro'].includes(history[index].node_id)) return index;
  return -1;
}
async function goto(index,asEdit=false) {
  if(busy || index<0 || index>history.length) return;
  rememberDraft();clearAnswerResponse();editMode=asEdit;$('case-dialog').close();closeChat(false);await load(history,index);
}
async function updateWorkflow(path,data) {
  const currentGeneration=++generation;
  clearAnswerResponse();setBusy(true);setError('');closeChat(false);
  try {
    const collection=debugMode?{}:{collection:{session_id:sessionId,event_id:crypto.randomUUID(),displayed_at:displayedAt,checked_at:checkedAt,ended_at:new Date().toISOString()}};
    const result=await request(path,{...data,...collection});
    if(currentGeneration!==generation)return;
    history=result.history;cursor=history.length;revision=result.revision;debugSection=result.debug_section||null;page=result.page;editMode=false;
    drafts.clear();conversations.clear();save();render();
  } catch(error) {
    if(currentGeneration!==generation)return;
    setBusy(false);setError(error.message||'The update could not be saved. Please try again.');
  }
}
$('back').addEventListener('click',()=>goto(backIndex()));
function markAnswerChecked() { checkedAt = hasAnswer() ? new Date().toISOString() : null; }
$('answer-control').addEventListener('input',markAnswerChecked);
$('answer-control').addEventListener('change',markAnswerChecked);
$('answer-form').addEventListener('submit',async event=>{
  event.preventDefault();if(busy || responsePending || responseFailed || !hasAnswer()) return;
  const value=selectedValue(), old=history[cursor];
  if(old && old.node_id===page.node_id) {
    if(editMode || old.value!==value || old.timing_basis) {
      await updateWorkflow('/api/edit',{history,revision,edit_index:cursor,value});
    } else {
      let nextCursor=cursor+1;
      while(nextCursor<history.length && history[nextCursor].automatic) nextCursor++;
      await goto(nextCursor);
    }
  } else {
    await updateWorkflow('/api/advance',{history:history.slice(0,cursor),revision,value});
  }
});
$('view-details').onclick=()=>{if(page)$('case-dialog').showModal();};
$('close-details').onclick=()=>$('case-dialog').close();
$('restart').onclick=()=>$('restart-dialog').showModal();
$('cancel-restart').onclick=()=>$('restart-dialog').close();
$('confirm-restart').onclick=async()=>{
  if(busy)return;
  setBusy(true);
  try { if(!debugMode) await request('/api/collection/end',{session_id:sessionId}); }
  catch(error) { $('restart-dialog').close();setBusy(false);setError(error.message);return; }
  $('restart-dialog').close();$('case-dialog').close();closeChat(false);drafts.clear();conversations.clear();revision=null;editMode=false;
  sessionId=crypto.randomUUID();history=[];cursor=0;debugSection=null;save();load([],0);
};
function chatMessage(role,text,kind='') { const bubble=element('div',`message ${role}${kind?' '+kind:''}`,text);$('chat-messages').append(bubble);$('chat-messages').scrollTop=$('chat-messages').scrollHeight;return bubble; }
function renderChat() { $('chat-messages').replaceChildren();chatMessage('assistant','What would you like to clarify about this page?');for(const msg of conversations.get(chatKey)||[])chatMessage(msg.role,msg.content); }
function closeChat(returnFocus=true) { $('chat-panel').hidden=true;if(returnFocus)$('ask').focus(); }
$('ask').onclick=()=>{if(!page)return;$('chat-panel').hidden=false;$('chat-input').focus();};
$('close-chat').onclick=()=>closeChat();
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!$('chat-panel').hidden)closeChat();});
$('chat-input').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();$('chat-form').requestSubmit();}});
$('chat-form').addEventListener('submit',async event=>{
  event.preventDefault();const question=$('chat-input').value.trim();if(chatBusy||!question||!page)return;
  const key=chatKey, previous=(conversations.get(key)||[]).slice(-12), transcript=[...previous,{role:'user',content:question}];
  conversations.set(key,transcript);chatMessage('user',question);$('chat-input').value='';chatBusy=true;$('chat-send').disabled=true;
  const pending=chatMessage('assistant','Thinking…','pending');chatController=new AbortController();
  try {
    const result=await request('/api/help',{history:history.slice(0,cursor),revision,question,conversation:previous,draft_value:['choice','date','text','currency'].includes(page.input_type)&&hasAnswer()?selectedValue():null},chatController.signal);
    if(chatKey!==key)return;pending.remove();chatMessage('assistant',result.assistant_reply);conversations.set(key,[...transcript,{role:'assistant',content:result.assistant_reply.slice(0,5000)}]);
  } catch(error) { if(error.name!=='AbortError'&&chatKey===key){pending.remove();chatMessage('assistant',error.message,'error-message');document.querySelector('.approved-help').open=true;} }
  finally {if(chatKey===key){chatBusy=false;$('chat-send').disabled=false;$('chat-input').focus();}}
});
window.addEventListener('pagehide',()=>{
  if(!debugMode) navigator.sendBeacon('/api/collection/end',new Blob([JSON.stringify({session_id:sessionId})],{type:'application/json'}));
});
window.addEventListener('pageshow',event=>{if(event.persisted)load(history,cursor,false);});
try {
  const saved=JSON.parse(sessionStorage.getItem(storageKey));
  if(saved&&Array.isArray(saved.history)&&Number.isInteger(saved.cursor)&&saved.cursor>=0&&saved.cursor<=saved.history.length) {
    history=saved.history;cursor=saved.cursor;revision=saved.revision||null;editMode=!!saved.editMode;
    if(debugMode)debugSection=saved.debugSection||null;
    if(typeof saved.sessionId==='string')sessionId=saved.sessionId;
  } else if(debugMode) {
    const normal=JSON.parse(sessionStorage.getItem(storageKey.replace(/:debug$/,'')));
    if(normal&&Array.isArray(normal.history)) {
      const end=normal.history.findIndex(a=>a.node_id==='guided_preliminary_summary');
      history=normal.history.slice(0,end<0?normal.history.length:end);cursor=history.length;
    }
  }
} catch(_) {}
function jumpDebugSection(section) {
  if(!debugMode || busy)return;
  const intro=section==='preliminary'?'guided_preliminary_summary':section==='statute_of_limitations'?'guided_sol_intro':section==='ambiguity'?'ambiguity_decision':section==='mistake'?'mistake_decision':section==='unconscionable_contract'?'unconscionable_contract_decision':`guided_${section}_intro`;
  const existing=history.findIndex(a=>a.node_id===intro);
  if(existing>=0) {goto(existing);return;}
  const draft=page?.section==='Preliminary fields' && ['choice','date','text','currency'].includes(page.input_type) && hasAnswer()?selectedValue():null;
  $('case-dialog').close();
  updateWorkflow('/api/debug/jump',{history,cursor,revision,section,draft_value:draft});
}
if(debugMode) {
  $('debug-banner').hidden=false;
  $('case-default-note').textContent='Debug jumps fill unanswered intake with example defaults. Use Change to adjust any case detail.';
  for(const item of document.querySelectorAll('[data-section]')) {
    const label=item.querySelector('span:last-child');
    const button=element('button','debug-section-button');button.type='button';
    button.setAttribute('aria-label',`Go to ${label.textContent}`);
    button.append(...item.children);item.replaceChildren(button);
    button.onclick=()=>jumpDebugSection(item.dataset.section);
  }
}
load(history,cursor,false);
