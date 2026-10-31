'use strict';
const $ = (id) => document.getElementById(id);
const storageKey = 'debt-case-guide:guided-defenses:2026-10-31:v1';
let history = [], cursor = 0, page = null, revision = null, editMode = false, busy = false, chatBusy = false, chatKey = '', chatController = null;
const drafts = new Map(), conversations = new Map();
let generation = 0;

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
function save() { try { sessionStorage.setItem(storageKey, JSON.stringify({history, cursor, revision, editMode})); } catch (_) {} }
function setError(message) { $('form-error').textContent = message; $('form-error').hidden = !message; }
function setBusy(value) {
  busy = value;
  $('main-content').setAttribute('aria-busy', String(value));
  $('next').disabled = value || !hasAnswer();
}
async function request(path, data, signal) {
  const response = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data), signal});
  const result = await response.json();
  if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Please check the answer and try again.');
  return result;
}
async function load(nextHistory = history, nextCursor = cursor, focus = true) {
  const currentGeneration = ++generation;
  setBusy(true); setError('');
  try {
    const result = await request('/api/state', {history:nextHistory.slice(0, nextCursor), revision});
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
  if (['text','currency'].includes(page.input_type)) return $('text-answer')?.value.trim() || '';
  const chosen = document.querySelector('input[name="answer"]:checked')?.value || '';
  return chosen === 'date' ? $('date-answer')?.value || '' : chosen;
}
function hasAnswer() {
  if (!page || page.input_type === 'complete') return false;
  return !!selectedValue() && ($('date-answer')?.disabled !== false || $('date-answer').validity.valid) && (!$('text-answer') || $('text-answer').validity.valid);
}
function rememberDraft() { if (page) drafts.set(page.node_id + prefixKey(), selectedValue()); }
function updateNext() { $('next').disabled = busy || !hasAnswer(); rememberDraft(); }
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
    const input=element('input','text-input'); input.id='text-answer'; input.type=page.input_type==='currency'?'number':'text'; input.maxLength=300; input.value=selected; input.autocomplete='off'; input.required=true;
    if (page.input_type==='currency') {input.min='0.01';input.step='0.01';input.inputMode='decimal';}
    input.addEventListener('input', updateNext); control.append(label,input,element('p','input-hint','Short answer · You can edit the prefilled example.'));
  } else if (page.input_type==='choice') {
    const fieldset=element('fieldset','choice-list'); fieldset.append(element('legend','',page.title));
    for(const item of page.options) fieldset.append(option(item,selected)); control.append(fieldset);
  } else if (page.input_type==='date') {
    const fieldset=element('fieldset','choice-list date-form'); fieldset.append(element('legend','',page.title));
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
      control.append(element('p','completion-note','You’ve finished the four defenses in this prototype. You can go back or use Change to review your selections.'));
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
    [['Verify case details','Review your complaint and account details once.'],['Review the defenses','This prototype covers SOL, Ambiguity, Identity Theft, and Laches.'],['Complete Attachment 4','Fill out the form using the choices recorded here.']].forEach(([title,body],i)=>{ const card=element('div','overview-step');card.append(element('span','',String(i+1)),element('strong','',title),element('p','',body));overview.append(card); });
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
  $('section-count').textContent=`0${page.section_number} / 0${page.section_count}`;
  $('body').replaceChildren(...page.body.filter(Boolean).map(text=>element('p','',friendly(text))));
  $('revision-notice').textContent=page.revision_notice||'';
  $('revision-notice').hidden=!page.revision_notice;
  $('why').textContent=page.why;$('aside-title').textContent=page.stage===2?'Your choices, in one place':'Why we ask';
  $('back').disabled=backIndex()<0;
  for(const li of document.querySelectorAll('[data-stage]')) { const stage=Number(li.dataset.stage);li.classList.toggle('active',stage===page.progress_stage);li.classList.toggle('done',stage<page.progress_stage);if(stage===page.progress_stage)li.setAttribute('aria-current','step');else li.removeAttribute('aria-current');li.querySelector('.step-number').textContent=stage<page.progress_stage?'✓':String(stage+1); }
  document.querySelector('.progress li.active')?.scrollIntoView({block:'nearest',inline:'center'});
  renderVisual();inputControls();$('case-fields').replaceChildren(detailsRows());
  $('next-label').textContent=page.next_label;$('next').hidden=page.input_type==='complete';
  $('step-note').textContent=['choice','date','text','currency'].includes(page.input_type)?'One question at a time':'';
  const nextKey=page.node_id+prefixKey();
  if(chatKey!==nextKey) {chatController?.abort();chatBusy=false;chatKey=nextKey;$('chat-send').disabled=false;$('chat-input').value='';renderChat();}
  $('chat-context').textContent=page.title;$('approved-text').textContent=page.help_text;
  setBusy(false);if(focus){$('question').focus({preventScroll:true});window.scrollTo({top:0,behavior:'instant'});}
}
function backIndex() {
  for(let index=cursor-1;index>=0;index--) if(!history[index].automatic) return index;
  return -1;
}
async function goto(index,asEdit=false) {
  if(busy || index<0 || index>history.length) return;
  rememberDraft();editMode=asEdit;$('case-dialog').close();closeChat(false);await load(history,index);
}
async function updateWorkflow(path,data) {
  const currentGeneration=++generation;
  setBusy(true);setError('');closeChat(false);
  try {
    const result=await request(path,data);
    if(currentGeneration!==generation)return;
    history=result.history;cursor=history.length;revision=result.revision;page=result.page;editMode=false;
    drafts.clear();conversations.clear();save();render();
  } catch(error) {
    if(currentGeneration!==generation)return;
    setBusy(false);setError(error.message||'The update could not be saved. Please try again.');
  }
}
$('back').addEventListener('click',()=>goto(backIndex()));
$('answer-form').addEventListener('submit',async event=>{
  event.preventDefault();if(busy || !hasAnswer()) return;
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
$('confirm-restart').onclick=()=>{ $('restart-dialog').close();$('case-dialog').close();closeChat(false);drafts.clear();conversations.clear();revision=null;editMode=false;try{sessionStorage.removeItem(storageKey);}catch(_){}load([],0); };
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
    const result=await request('/api/help',{history:history.slice(0,cursor),revision,question,conversation:previous},chatController.signal);
    if(chatKey!==key)return;pending.remove();chatMessage('assistant',result.assistant_reply);conversations.set(key,[...transcript,{role:'assistant',content:result.assistant_reply.slice(0,5000)}]);
  } catch(error) { if(error.name!=='AbortError'&&chatKey===key){pending.remove();chatMessage('assistant',error.message,'error-message');document.querySelector('.approved-help').open=true;} }
  finally {if(chatKey===key){chatBusy=false;$('chat-send').disabled=false;$('chat-input').focus();}}
});
try {const saved=JSON.parse(sessionStorage.getItem(storageKey));if(saved&&Array.isArray(saved.history)&&Number.isInteger(saved.cursor)&&saved.cursor>=0&&saved.cursor<=saved.history.length){history=saved.history;cursor=saved.cursor;revision=saved.revision||null;editMode=!!saved.editMode;}}catch(_){}
load(history,cursor,false);
