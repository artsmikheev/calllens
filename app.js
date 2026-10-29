const $ = (s) => document.querySelector(s);
const state = { audio: null, checklist: [], result: null };
const STYLE_LABELS_RU = {
  'Result-Oriented Strategist': 'Результатный стратег',
  'Evidence-Driven Expert': 'Доказательный эксперт',
  'Visionary Catalyst': 'Визионер-вдохновитель',
  'Trust-Oriented Partner': 'Надёжный партнёр',
  'result_oriented_strategist': 'Результатный стратег',
  'evidence_driven_expert': 'Доказательный эксперт',
  'visionary_catalyst': 'Визионер-вдохновитель',
  'trust_oriented_partner': 'Надёжный партнёр'
};
function styleLabel(value = '') {
  const raw = String(value).trim();
  return STYLE_LABELS_RU[raw] || raw.replace(/\s*[—-]\s*[^—-]+$/, '').trim() || 'Профиль не определён';
}
const DEMO = [
  { name: 'Установил цель и повестку звонка', max_points: 10 },
  { name: 'Выявил текущую ситуацию и потребность', max_points: 20 },
  { name: 'Задал уточняющие вопросы', max_points: 15 },
  { name: 'Связал решение с бизнес-эффектом', max_points: 20 },
  { name: 'Отработал возражения', max_points: 20 },
  { name: 'Зафиксировал конкретный следующий шаг', max_points: 15 }
];

function escapeHtml(value = '') { return String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c])); }
function formatBytes(bytes) { if (!bytes) return '0 Б'; const units = ['Б','КБ','МБ','ГБ']; const i = Math.floor(Math.log(bytes)/Math.log(1024)); return `${(bytes/1024**i).toFixed(i ? 1 : 0)} ${units[i]}`; }
function formatSeconds(s) { if (!Number.isFinite(s)) return 'длительность будет определена при обработке'; const m=Math.floor(s/60), sec=Math.floor(s%60); return `${m}:${String(sec).padStart(2,'0')}`; }
const MAX_UPLOAD_BYTES = 250 * 1024 * 1024;
const SUPPORTED_AUDIO_EXTENSIONS = new Set(['.mp3','.wav','.m4a','.ogg','.mp4','.webm','.mpeg','.mpga']);
function formStatus(message='', kind='info') { const el=$('#formStatus'); if(!el) return; el.textContent=message; el.className=`form-status ${kind}`; }
function validateAudio(file) {
  if(!file) return 'Выберите запись звонка.';
  const ext = `.${String(file.name).split('.').pop().toLowerCase()}`;
  if(!SUPPORTED_AUDIO_EXTENSIONS.has(ext)) return 'Формат не поддерживается. Используйте MP3, WAV, M4A, OGG, MP4 или WEBM.';
  if(file.size > MAX_UPLOAD_BYTES) return 'Файл больше 250 МБ. Сначала сожмите запись или выберите более короткий файл.';
  return '';
}
function validateChecklist() {
  if(!state.checklist.length) return 'Добавьте хотя бы один пункт чек-листа.';
  const bad = state.checklist.find(x=>!String(x.name||'').trim() || !Number.isFinite(Number(x.max_points)) || Number(x.max_points)<=0);
  return bad ? 'В каждом пункте чек-листа укажите название и положительный максимальный балл.' : '';
}
async function loadHealth() {
  const el=$('#aiStatus');
  if(!el) return;
  try {
    const res=await fetch('/api/health');
    if(!res.ok) throw new Error('health unavailable');
    const data=await res.json();
    el.textContent=data.mode==='demo' ? 'Demo-режим' : data.ai_configured ? 'AI готов' : 'Нужен API-ключ';
    el.title=data.mode==='demo' ? 'Локальный тестовый режим' : data.ai_configured ? 'OpenAI API настроен' : 'Задайте OPENAI_API_KEY на backend';
  } catch (_) {
    el.textContent='Локальный просмотр';
    el.title='Backend health endpoint недоступен';
  }
}
function renderChecklist() {
  const list = $('#manualList'); list.innerHTML = '';
  state.checklist.forEach((item, i) => {
    const row = document.createElement('div'); row.className='criterion-row';
    row.innerHTML = `<input aria-label="Название критерия ${i+1}" value="${escapeHtml(item.name)}" data-field="name" data-index="${i}"><input aria-label="Максимальный балл ${i+1}" type="number" min="1" step="1" value="${item.max_points}" data-field="max_points" data-index="${i}"><button type="button" aria-label="Удалить критерий" data-remove="${i}">×</button>`;
    list.appendChild(row);
  });
  localStorage.setItem('callLensChecklist', JSON.stringify(state.checklist));
}
function addCriterion(item={name:'Новый критерий', max_points:10}) { state.checklist.push(item); renderChecklist(); }
function parseChecklistText(text, filename='') {
  const items=[]; text.split(/\r?\n/).forEach(line => {
    const clean=line.trim(); if(!clean || clean.startsWith('#')) return;
    const parts=clean.split(/[;,\t]/).map(x=>x.trim()).filter(Boolean);
    let points = Number((parts[parts.length-1]||'').replace(',', '.'));
    if(!Number.isFinite(points)) { const match=clean.match(/(?:\(|\[)?\s*(\d+(?:\.\d+)?)\s*(?:балл|points?)?\s*(?:\)|\])?$/i); points=match?Number(match[1]):10; }
    const name=parts.length>1 && Number.isFinite(Number(parts[parts.length-1])) ? parts.slice(0,-1).join(' — ') : clean.replace(/\s*[-–—:]\s*\d+\s*$/,'');
    if(name) items.push({name, max_points:points});
  });
  if(items.length) { state.checklist=items; renderChecklist(); }
}
function setupAudio() {
  const input=$('#audioFile'), zone=$('#dropzone');
  const setFile=(file)=>{ const error=validateAudio(file); if(error){state.audio=null;zone.classList.add('invalid');$('#audioMeta').textContent=error;formStatus(error,'error');return} zone.classList.remove('invalid');state.audio=file;formStatus(`Запись готова к анализу: ${file.name}`,'success'); const url=URL.createObjectURL(file); const audio=new Audio(url); audio.addEventListener('loadedmetadata',()=>{$('#audioMeta').textContent=`${file.name} · ${formatBytes(file.size)} · ${formatSeconds(audio.duration)}`; URL.revokeObjectURL(url);},{once:true}); $('#audioMeta').textContent=`${file.name} · ${formatBytes(file.size)} · определяем длительность…`; };
  input.addEventListener('change',e=>setFile(e.target.files[0]));
  ['dragenter','dragover'].forEach(type=>zone.addEventListener(type,e=>{e.preventDefault();zone.classList.add('dragging')}));
  ['dragleave','drop'].forEach(type=>zone.addEventListener(type,e=>{e.preventDefault();zone.classList.remove('dragging')}));
  zone.addEventListener('drop',e=>setFile(e.dataTransfer.files[0]));
  zone.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' ') input.click()});
}
function setProgress(step, hint='') { const labels=['Загрузка','Транскрибация','Чек-лист','Психотип','Готово']; const pct=[10,38,60,82,100][step]; $('#progressSection').classList.remove('hidden'); $('#progressBar').style.width=pct+'%'; $('#progressPercent').textContent=pct+'%'; $('#progressHint').textContent=hint; $('#progressSteps').querySelectorAll('span').forEach((el,i)=>{el.classList.toggle('active',i<=step)}); }
async function apiAnalyze() {
  const form=new FormData(); form.append('audio',state.audio); form.append('checklist',JSON.stringify(state.checklist)); form.append('manager_name',$('#managerName').value); form.append('client_name',$('#clientName').value); form.append('call_goal',$('#callGoal').value);
  setProgress(0,'Файл загружен. Проверяем формат и размер…'); await new Promise(r=>setTimeout(r,350)); setProgress(1,'Транскрибируем и сохраняем тайм-коды…');
  const res=await fetch('/api/analyze',{method:'POST',body:form}); if(!res.ok) throw new Error((await res.json().catch(()=>({detail:'Ошибка сервера'}))).detail||'Не удалось выполнить анализ'); setProgress(3,'Формируем профиль коммуникации и рекомендации…'); const data=await res.json(); setProgress(4,'Отчёт готов.'); return data;
}
function renderScore(result) {
  const score=result.score||{}; const rows=(score.criteria||[]).map(x=>`<tr><td>${escapeHtml(x.name)}</td><td><span class="status-pill status-${x.verdict_key||'na'}">${escapeHtml(x.verdict||'не наблюдалось')}</span></td><td><strong>${x.earned_points ?? 0}</strong> / ${x.max_points ?? 0}<div class="scorebar"><span style="width:${Math.min(100,(x.earned_points/(x.max_points||1))*100)}%"></span></div></td><td><div class="quote">${escapeHtml(x.quote||'Доказательство не найдено')}<small>${escapeHtml(x.timestamp||'')}</small></div><div>${escapeHtml(x.reason||'')}</div></td></tr>`).join('');
  $('#scoreCard').innerHTML=`<p class="result-kicker">01 / CHECKLIST SCORE</p><h3>Оценка по чек-листу</h3><p class="muted">Баллы рассчитаны по вашим критериям с разделением evidence-based и strict.</p><div class="score-summary"><div class="score-tile highlight"><span class="label">Evidence-based</span><strong>${score.evidence_percent ?? 0}%</strong><span class="label">${score.earned_points ?? 0} из ${score.observable_max_points ?? score.max_points ?? 0}</span></div><div class="score-tile"><span class="label">Strict</span><strong>${score.strict_percent ?? 0}%</strong><span class="label">${score.earned_points ?? 0} из ${score.max_points ?? 0}</span></div></div><table class="criteria-table"><thead><tr><th>Критерий</th><th>Статус</th><th>Баллы</th><th>Доказательство</th></tr></thead><tbody>${rows}</tbody></table>`;
}
function renderProfile(result) {
  const p=result.client_communication_profile||{}; const ev=(p.evidence||[]).map(x=>`<li><strong>${escapeHtml(x.signal||'Сигнал')} · ${escapeHtml(x.timestamp||'')}</strong>“${escapeHtml(x.quote||'')}”</li>`).join('')||'<li>Доказательства не найдены</li>'; const counters=(p.counter_evidence||[]).map(x=>`<li><strong>${escapeHtml(x.signal||'Контрдовод')} · ${escapeHtml(x.timestamp||'')}</strong>“${escapeHtml(x.quote||'')}”</li>`).join('')||'<li>Контрдоводы не выявлены</li>'; const play=p.manager_playbook||{};
  const primaryRu = styleLabel(p.primary_type_label || p.primary_type);
  const secondaryRu = p.secondary_type ? styleLabel(p.secondary_type_label || p.secondary_type) : '';
  $('#profileCard').innerHTML=`<p class="result-kicker">03 / CLIENT PROFILE</p><h3>Стиль клиента и рекомендации</h3><div class="profile-badge">${escapeHtml(primaryRu)} ${secondaryRu ? ' + '+escapeHtml(secondaryRu):''}</div><p class="confidence">Уверенность: <strong>${p.confidence_percent ?? Math.round((p.confidence||0)*100)}%</strong> · ${escapeHtml(p.confidence_label||'доказательность зависит от качества транскрипта')}</p><h4>Цитаты-доказательства</h4><ul class="evidence-list">${ev}</ul><div class="counter-note"><strong>Контрдоводы:</strong><ul class="evidence-list">${counters}</ul></div><div class="playbook"><h4>Playbook менеджера</h4><div class="playbook-row"><strong>Начать</strong><span>${escapeHtml(play.opening||'Сформулировать цель и уточнить приоритет клиента.')}</span></div><div class="playbook-row"><strong>Аргументы</strong><span>${escapeHtml((play.arguments||[]).join('; ')||'Связать решение с подтверждённым бизнес-эффектом.')}</span></div><div class="playbook-row"><strong>Возражения</strong><span>${escapeHtml(play.objection_handling||'Признать вопрос, дать доказательство и согласовать следующий шаг.')}</span></div><div class="playbook-row"><strong>Избегать</strong><span>${escapeHtml((play.avoid||[]).join('; ')||'Не делать выводов без цитат.')}</span></div></div><div class="playbook"><h4>Адаптация менеджера</h4><p class="muted">${escapeHtml(p.manager_adaptation?.summary||'Нет отдельной оценки адаптации.')}</p><div class="scorebar"><span style="width:${p.manager_adaptation?.score_percent||0}%"></span></div></div>`;
}
function renderOmissions(result) { const o=result.omissions||{}; const missing=(o.not_observed||[]).map(x=>`<li><strong>${escapeHtml(x.name)}</strong>${escapeHtml(x.stage||'')}<br>${escapeHtml(x.impact||'Влияние не указано')}<br><em>Можно было сказать: “${escapeHtml(x.example_phrase||'') }”</em></li>`).join('')||'<li>Все критерии получили наблюдаемое состояние.</li>'; const partial=(o.partial||[]).map(x=>`<li><strong>${escapeHtml(x.name)}</strong>${escapeHtml(x.reason||'')}<br><em>Следующий раз: “${escapeHtml(x.example_phrase||'') }”</em></li>`).join('')||'<li>Частично выполненных пунктов нет.</li>'; $('#omissionsCard').innerHTML=`<p class="result-kicker">02 / MISSED SIGNALS</p><h3>Что не было сказано</h3><div class="omissions-columns"><div><h4>Не наблюдалось</h4><ul class="omission-list">${missing}</ul></div><div><h4>Начал, но не довёл</h4><ul class="omission-list">${partial}</ul></div></div>`; }
function renderCoaching(result) {
  const objections=(result.objections||[]).map(o=>{
    const laer=o.laer||{}; const steps=['listen','acknowledge','explore','respond','confirm'].filter(k=>laer[k]).map(k=>({listen:'выслушал',acknowledge:'признал',explore:'исследовал',respond:'ответил',confirm:'проверил'}[k])).join(' · ')||'шаги не подтверждены';
    return `<li><strong>${escapeHtml(o.category||'Возражение')}</strong> · ${escapeHtml(o.handling_status||'не наблюдалось')} · ${escapeHtml(o.timestamp||'')}<br><span class="quote">“${escapeHtml(o.quote||'Цитата не найдена')}”</span><br><small>LAER: ${escapeHtml(steps)}${o.reason?' · '+escapeHtml(o.reason):''}</small></li>`;
  }).join('')||'<li>Возражения не выделены или не наблюдались.</li>';
  const coaching=(result.one_call_coaching||[]).slice(0,3).map(x=>`<li><strong>${escapeHtml(x.behavior||'Поведение для практики')}</strong><br><span>${escapeHtml(x.observed_moment||'Наблюдение не указано')}</span><br><em>Фраза: “${escapeHtml(x.replacement_phrase||'')}”</em><br><small>Триггер: ${escapeHtml(x.cue||'')} · Успех: ${escapeHtml(x.success_signal||'')}</small></li>`).join('')||'<li>Coaching-приоритеты не сформированы.</li>';
  const f=result.follow_up||{};
  $('#coachingCard').innerHTML=`<p class="result-kicker">04 / OBJECTIONS + COACHING</p><h3>Возражения и следующий звонок</h3><div class="omissions-columns"><div><h4>Карта возражений</h4><ul class="omission-list">${objections}</ul></div><div><h4>1–3 поведения для практики</h4><ul class="omission-list">${coaching}</ul></div></div><div class="method-note"><span class="mini-label">FOLLOW-UP</span><p>${escapeHtml(f.next_comparable_call||'Следующий сопоставимый звонок не указан.')}${f.review_behavior?' · Проверить: '+escapeHtml(f.review_behavior):''}${f.recheck_when?' · Пересмотреть: '+escapeHtml(f.recheck_when):''}</p></div>`;
}
function renderTranscript(result){ const t=result.transcript||''; $('#transcriptCard').innerHTML=`<p class="result-kicker">SOURCE / TRANSCRIPT</p><h3>Транскрипт <span class="transcript-toggle" id="toggleTranscript">показать</span></h3><div class="transcript-body hidden" id="transcriptBody">${escapeHtml(t)}</div>`; $('#toggleTranscript').addEventListener('click',()=>{$('#transcriptBody').classList.toggle('hidden');$('#toggleTranscript').textContent=$('#transcriptBody').classList.contains('hidden')?'показать':'скрыть'}); }
function renderResults(result){ state.result=result; $('#resultsSection').classList.remove('hidden'); $('#reportMeta').textContent=[result.meta?.client_name,result.meta?.manager_name,result.meta?.duration].filter(Boolean).join(' · '); if(result.role_warning)$('#roleWarning').classList.remove('hidden'); renderScore(result);renderProfile(result);renderOmissions(result);renderCoaching(result);renderTranscript(result); window.scrollTo({top:$('#resultsSection').offsetTop-20,behavior:'smooth'}); }
function reportMarkdown(){ const r=state.result; return r?.markdown || '# Отчёт\n\nРезультат ещё не сформирован.'; }
$('#analysisForm').addEventListener('submit',async e=>{e.preventDefault(); const audioError=validateAudio(state.audio); const checklistError=validateChecklist(); if(audioError||checklistError){formStatus(audioError||checklistError,'error');return} $('#analyzeButton').disabled=true; formStatus('Запрос принят. Анализ выполняется, не закрывайте вкладку.','info'); try{renderResults(await apiAnalyze());formStatus('Анализ завершён. Отчёт доступен ниже.','success')}catch(err){setProgress(0,'Ошибка: '+err.message);formStatus(err.message,'error')}finally{$('#analyzeButton').disabled=false}});
$('#addCriterion').addEventListener('click',()=>addCriterion()); $('#manualList').addEventListener('input',e=>{const i=Number(e.target.dataset.index), field=e.target.dataset.field;if(field){state.checklist[i][field]=field==='max_points'?Number(e.target.value):e.target.value;localStorage.setItem('callLensChecklist',JSON.stringify(state.checklist))}}); $('#manualList').addEventListener('click',e=>{if(e.target.dataset.remove!==undefined){state.checklist.splice(Number(e.target.dataset.remove),1);renderChecklist()}}); $('#loadDemoChecklist').addEventListener('click',()=>{state.checklist=DEMO.map(x=>({...x}));renderChecklist()}); $('#checklistFile').addEventListener('change',async e=>{const f=e.target.files[0];if(f)parseChecklistText(await f.text(),f.name)}); $('#copyReport').addEventListener('click',async()=>{await navigator.clipboard.writeText(reportMarkdown());$('#copyReport').textContent='Скопировано';setTimeout(()=>$('#copyReport').textContent='Скопировать',1600)}); $('#downloadReport').addEventListener('click',()=>{const blob=new Blob([reportMarkdown()],{type:'text/markdown;charset=utf-8'}),a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='call-analysis-report.md';a.click();URL.revokeObjectURL(a.href)}); $('#printReport').addEventListener('click',()=>window.print());
const saved=JSON.parse(localStorage.getItem('callLensChecklist')||'null'); state.checklist=saved?.length?saved:DEMO.map(x=>({...x})); renderChecklist(); setupAudio(); loadHealth();
