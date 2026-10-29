import json, os, re, shutil, subprocess, tempfile
from pathlib import Path
from typing import Annotated
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from openai import OpenAI
from auth_routes import router as auth_router
from auth_settings import get_settings

ROOT = Path(__file__).parent
PROMPT = (ROOT / 'prompt.md').read_text(encoding='utf-8')
app = FastAPI(title='CallLens API')
app.add_middleware(CORSMiddleware, allow_origins=get_settings().allowed_origin_list, allow_methods=['GET', 'POST', 'PATCH', 'OPTIONS'], allow_headers=['Content-Type', 'Origin'], allow_credentials=True)
app.include_router(auth_router)
SUPPORTED_AUDIO_SUFFIXES = {'.mp3', '.wav', '.m4a', '.ogg', '.mp4', '.webm', '.mpeg', '.mpga'}

STYLE_LABELS = {
 'Result-Oriented Strategist':'Результатный стратег',
 'Evidence-Driven Expert':'Доказательный эксперт',
 'Visionary Catalyst':'Визионер-вдохновитель',
 'Trust-Oriented Partner':'Надёжный партнёр',
 'result_oriented_strategist':'Результатный стратег',
 'evidence_driven_expert':'Доказательный эксперт',
 'visionary_catalyst':'Визионер-вдохновитель',
 'trust_oriented_partner':'Надёжный партнёр'
}

def client():
    key = os.getenv('OPENAI_API_KEY')
    if not key: raise HTTPException(500, 'Не найден OPENAI_API_KEY. Создайте .env или экспортируйте переменную окружения.')
    return OpenAI(api_key=key)

def ffprobe_duration(path):
    try:
        out=subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(path)], text=True)
        return round(float(out.strip()), 1)
    except Exception: return None

def chunks(path, work):
    if path.stat().st_size <= 25*1024*1024: return [path]
    out=work/'chunk_%03d.mp3'
    subprocess.run(['ffmpeg','-y','-i',str(path),'-f','segment','-segment_time','900','-c:a','libmp3lame','-b:a','96k',str(out)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return sorted(work.glob('chunk_*.mp3'))

def transcribe(path, work):
    api=client(); parts=[]
    for chunk in chunks(path, work):
        with chunk.open('rb') as f:
            result=api.audio.transcriptions.create(model=os.getenv('OPENAI_TRANSCRIBE_MODEL','whisper-1'), file=f, response_format='verbose_json', timestamp_granularities=['segment'])
        text=getattr(result,'text','') or ''
        segments=getattr(result,'segments',None) or []
        if segments:
            for s in segments:
                start=float(getattr(s,'start',0)); end=float(getattr(s,'end',start)); seg=getattr(s,'text','')
                parts.append(f'[{int(start//60):02d}:{int(start%60):02d}–{int(end//60):02d}:{int(end%60):02d}] Speaker 1: {seg.strip()}')
        else: parts.append(text)
    return '\n'.join(parts)

def call_json(api, system, user, max_tokens):
    response=api.chat.completions.create(model=os.getenv('OPENAI_ANALYSIS_MODEL','gpt-5-nano'), temperature=0, max_tokens=max_tokens, reasoning_effort='low', response_format={'type':'json_object'}, messages=[{'role':'system','content':system},{'role':'user','content':user}])
    if not getattr(response, 'choices', None) or not response.choices[0].message or not response.choices[0].message.content:
        provider_error=getattr(response, 'error', None) or 'Провайдер не вернул JSON-ответ.'
        raise HTTPException(502, f'Ошибка AI-провайдера: {provider_error}')
    try:
        return json.loads(response.choices[0].message.content)
    except (TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(502, f'AI-провайдер вернул некорректный JSON: {exc}')

def ask_llm(transcript, checklist, meta):
    api=client()
    score_system='''Ты — строгий аудитор sales-звонков. Верни только JSON. Оцени каждый критерий ровно один раз по фактическому транскрипту. Не используй placeholders. Для каждого критерия верни name, max_points, earned_points, verdict (выполнено/частично/провал/не наблюдалось), quote, timestamp и reason. Если голос нельзя надежно атрибутировать, сохраняй role_warning и не выдумывай роль. Цитаты должны быть точными и взяты из транскрипта.'''
    score_user=f"""Чек-лист JSON:\n{json.dumps(checklist,ensure_ascii=False)}\n\nТранскрипт с тайм-кодами:\n{transcript}"""
    score_data=call_json(api,score_system,score_user,10000)
    rows=score_data.get('criteria',[])
    if len(rows)!=len(checklist):
        raise HTTPException(502,f'AI вернул {len(rows)} критериев вместо {len(checklist)}; отчёт не собран.')
    insight_system='''Ты — coach отдела продаж. Верни только JSON без placeholders. Определи наблюдаемый стиль клиента только по его репликам, дай confidence, минимум реальные цитаты-доказательства при наличии, возражения с LAER и максимум три конкретных coaching-приоритета. Не делай клинических выводов и не выдумывай цитаты.'''
    insight_user=f"""Метаданные: {json.dumps(meta,ensure_ascii=False)}\n\nТранскрипт с тайм-кодами:\n{transcript}\n\nВерни JSON с полями client_communication_profile, objections, one_call_coaching, follow_up, team_insights, role_warning."""
    insight_data=call_json(api,insight_system,insight_user,7000)
    data=insight_data
    data['score']={'criteria':rows}
    earned=0; maximum=0; observable=0; observable_earned=0
    for i,row in enumerate(rows):
        row['name']=row.get('name') or checklist[i].get('name','Критерий')
        row['max_points']=float(row.get('max_points',checklist[i].get('max_points',1)))
        row['earned_points']=float(row.get('earned_points',0) or 0)
        maximum+=row['max_points']; earned+=row['earned_points']
        if row.get('verdict')!='не наблюдалось': observable+=row['max_points']; observable_earned+=row['earned_points']
    data['score'].update({'earned_points':earned,'max_points':maximum,'observable_max_points':observable,'evidence_percent':round(observable_earned/observable*100,1) if observable else 0,'strict_percent':round(earned/maximum*100,1) if maximum else 0})
    return normalize(data, transcript, checklist, meta)
    return normalize(data, transcript, checklist, meta)

def normalize(data, transcript, checklist, meta):
    data['transcript']=transcript; data.setdefault('meta',meta)
    if not isinstance(data.get('role_warning'),bool):
        data['role_warning_detail']=data.get('role_warning'); data['role_warning']=True
    else: data.setdefault('role_warning',True)
    p=data.setdefault('client_communication_profile',{}); p.setdefault('confidence_percent',round(float(p.get('confidence',0))*100)); p.setdefault('confidence_label','low' if p['confidence_percent']<55 else 'medium' if p['confidence_percent']<80 else 'high')
    p['primary_type'] = STYLE_LABELS.get(p.get('primary_type',''), p.get('primary_type','Профиль не определён'))
    p['secondary_type'] = STYLE_LABELS.get(p.get('secondary_type',''), p.get('secondary_type','')) if p.get('secondary_type') else ''
    p['primary_type_label'] = STYLE_LABELS.get(p.get('primary_type_label',''), p.get('primary_type_label', p['primary_type']))
    p['secondary_type_label'] = STYLE_LABELS.get(p.get('secondary_type_label',''), p.get('secondary_type_label', p['secondary_type'])) if p.get('secondary_type') else ''
    for key in ('evidence','counter_evidence'):
        p[key]=[item if isinstance(item,dict) else {'timestamp':'','quote':str(item),'signal':''} for item in (p.get(key) or [])]
    score=data.setdefault('score',{}); rows=score.setdefault('criteria',[])
    for row in rows:
        row.setdefault('verdict_key', {'выполнено':'pass','частично':'partial','провал':'fail','не наблюдалось':'na'}.get(row.get('verdict'),'na'))
    data.setdefault('omissions',{'not_observed':[],'partial':[]})
    data.setdefault('objections',[])
    for objection in data['objections']:
        if not isinstance(objection,dict):
            objection={'category':str(objection)}
        objection.setdefault('handling_status','not_observable')
        objection.setdefault('confidence',0)
        if not isinstance(objection.get('laer'),dict): objection['laer']={}
        objection.setdefault('laer',{})
        for key in ('listen','acknowledge','explore','respond','confirm'):
            objection['laer'].setdefault(key,False)
    data.setdefault('one_call_coaching',[])
    data['one_call_coaching'] = [item if isinstance(item,dict) else {'priority':i+1,'behavior':str(item)} for i,item in enumerate(data['one_call_coaching'][:3])]
    data.setdefault('follow_up',{'next_comparable_call':'','review_behavior':'','evidence_to_collect':'','recheck_when':''})
    data.setdefault('team_insights',{'sample_size':1,'repeated_objections':[],'win_loss_reason':'unknown'})
    if not data.get('markdown') or 'Полный markdown-отчёт' in str(data.get('markdown')) or 'normalized transcript' in str(data.get('markdown')):
        data['markdown']=make_markdown(data)
    return data

def make_markdown(d):
    s=d.get('score',{}); p=d.get('client_communication_profile',{}); lines=[f"# Разбор sales-звонка",'',f"Менеджер: {d.get('meta',{}).get('manager_name') or '—'}  ",f"Клиент: {d.get('meta',{}).get('client_name') or '—'}",'', '## 1. Оценка по чек-листу', f"- Evidence-based: **{s.get('evidence_percent',0)}%** ({s.get('earned_points',0)} / {s.get('observable_max_points',s.get('max_points',0))})", f"- Strict: **{s.get('strict_percent',0)}%** ({s.get('earned_points',0)} / {s.get('max_points',0)})",'', '| Критерий | Статус | Баллы | Доказательство |', '|---|---|---:|---|']
    for x in s.get('criteria',[]): lines.append(f"| {x.get('name','')} | {x.get('verdict','')} | {x.get('earned_points',0)} / {x.get('max_points',0)} | {x.get('quote','')} ({x.get('timestamp','')}) — {x.get('reason','')} |")
    lines += ['', '## 2. Что не было сказано', '### Не наблюдалось']
    for x in d.get('omissions',{}).get('not_observed',[]): lines.append(f"- **{x.get('name','')}** — {x.get('stage','')}. Влияние: {x.get('impact','')}. Фраза: “{x.get('example_phrase','')}”")
    lines += ['', '### Частично выполнено']
    for x in d.get('omissions',{}).get('partial',[]): lines.append(f"- **{x.get('name','')}** — {x.get('reason','')}. Следующий раз: “{x.get('example_phrase','')}”")
    lines += ['', '## 3. Психотип клиента и рекомендации', f"**{p.get('primary_type_label',p.get('primary_type',''))}** · уверенность {p.get('confidence_percent',0)}%",'', '### Цитаты-доказательства']
    for x in p.get('evidence',[]): lines.append(f"- [{x.get('timestamp','')}] “{x.get('quote','')}” — {x.get('signal','')}")
    lines += ['', '### Контрдоводы']
    for x in p.get('counter_evidence',[]): lines.append(f"- [{x.get('timestamp','')}] “{x.get('quote','')}” — {x.get('signal','')}")
    pb=p.get('manager_playbook',{}); lines += ['', '### Playbook', f"- Начать: {pb.get('opening','')}", f"- Аргументы: {'; '.join(pb.get('arguments',[]))}", f"- Возражения: {pb.get('objection_handling','')}", f"- Избегать: {'; '.join(pb.get('avoid',[]))}", '', '### Адаптация менеджера', p.get('manager_adaptation',{}).get('summary','')]
    lines += ['', '## 4. Возражения и качество обработки']
    for o in d.get('objections',[]):
        laer=o.get('laer',{}); done=', '.join(k for k,v in laer.items() if v) or 'нет подтверждённых шагов LAER'
        lines.append(f"- **{o.get('category','')}** [{o.get('timestamp','')}] — {o.get('handling_status','not_observable')}; “{o.get('quote','')}”; LAER: {done}. {o.get('reason','')}")
    lines += ['', '## 5. Коучинг на следующий звонок']
    for item in d.get('one_call_coaching',[])[:3]:
        lines.append(f"### Приоритет {item.get('priority','—')}: {item.get('behavior','')}")
        lines.append(f"- Наблюдение: {item.get('observed_moment','')}")
        lines.append(f"- Влияние: {item.get('impact','')}")
        lines.append(f"- Фраза для тренировки: “{item.get('replacement_phrase','')}”")
        lines.append(f"- Триггер: {item.get('cue','')}; сигнал успеха: {item.get('success_signal','')}")
    fu=d.get('follow_up',{}); fu=fu if isinstance(fu,dict) else {'next_comparable_call':str(fu)}; lines += ['', '### Follow-up', f"- Следующий сопоставимый звонок: {fu.get('next_comparable_call','')}", f"- Что проверить: {fu.get('review_behavior','')}", f"- Какие доказательства собрать: {fu.get('evidence_to_collect','')}", f"- Когда пересмотреть: {fu.get('recheck_when','')}"]
    ti=d.get('team_insights',{}); ti=ti if isinstance(ti,dict) else {'repeated_objections':ti}; lines += ['', '## 6. Командные инсайты', f"- Размер выборки: {ti.get('sample_size',1)}", f"- Причина win/loss: {ti.get('win_loss_reason','unknown')}"]
    for item in ti.get('repeated_objections',[]): lines.append(f"- Повторяющееся возражение: {item}")
    return '\n'.join(lines)

def demo_result(checklist, meta):
    """Deterministic local fixture for validating the upload-to-report flow."""
    criteria=[]
    verdicts=['выполнено','частично','выполнено','не наблюдалось']
    for i, item in enumerate(checklist):
        verdict=verdicts[i % len(verdicts)]
        max_points=float(item.get('max_points', 10))
        earned=max_points if verdict=='выполнено' else max_points/2 if verdict=='частично' else 0
        criteria.append({'name': item.get('name','Критерий'), 'max_points': max_points, 'verdict': verdict,
                         'earned_points': earned, 'timestamp': f'00:{10+i:02d}–00:{11+i:02d}',
                         'quote': 'Демонстрационная цитата для проверки интерфейса.',
                         'reason': 'Локальный demo-режим: результат не является оценкой реального звонка.'})
    maximum=sum(float(x.get('max_points',10)) for x in checklist)
    earned=sum(float(x['earned_points']) for x in criteria)
    observable=sum(x['max_points'] for x in criteria if x['verdict']!='не наблюдалось')
    observable_earned=sum(x['earned_points'] for x in criteria if x['verdict']!='не наблюдалось')
    data={'meta':meta,'role_warning':False,'transcript':'[00:00–00:08] Speaker 1: Демонстрационная реплика для проверки полного пути MVP.\n[00:09–00:16] Speaker 2: Это тестовый результат, а не транскрибация реального звонка.',
          'score':{'criteria':criteria,'earned_points':earned,'max_points':maximum,
                   'observable_max_points':observable,'observable_earned_points':observable_earned,
                   'evidence_percent':round(observable_earned/observable*100,1) if observable else 0,
                   'strict_percent':round(earned/maximum*100,1) if maximum else 0},
          'client_communication_profile':{'primary_type':'Доказательный эксперт','secondary_type':'Надёжный партнёр',
                   'confidence':0.5,'evidence':[{'timestamp':'00:00–00:08','quote':'Демонстрационная реплика','signal':'fixture'}],
                   'counter_evidence':[],'manager_playbook':{'opening':'Уточнить цель и критерии успеха.','arguments':['Показать доказательство.'],
                   'objection_handling':'Признать вопрос и проверить следующий шаг.','avoid':['Не делать выводов без цитаты.']},
                   'manager_adaptation':{'summary':'Demo-режим: адаптация не оценивается.'}},
          'omissions':{'not_observed':[{'name':'Демо-проверка','stage':'MVP','impact':'Не влияет на реальный звонок.','example_phrase':'Замените demo-режим реальным анализом.'}],'partial':[]},
          'objections':[{'category':'demo','handling_status':'not_observable','confidence':0,'timestamp':'00:00–00:08','quote':'','reason':'Demo-режим не оценивает реальные возражения.','laer':{}}],
          'one_call_coaching':[{'priority':1,'behavior':'Проверить полный путь загрузки и отображения отчёта','observed_moment':'Demo fixture','impact':'Подтверждает связность MVP.','replacement_phrase':'Перейти к реальному звонку после настройки API ключа.','cue':'После smoke-теста','success_signal':'Отчёт отображается без ошибок.'}],
          'follow_up':{'next_comparable_call':'Загрузить реальную запись','review_behavior':'Проверить транскрипт и чек-лист','evidence_to_collect':'Тайм-коды и цитаты','recheck_when':'После первого реального анализа'},
          'team_insights':{'sample_size':1,'repeated_objections':[],'win_loss_reason':'demo_fixture'}}
    return normalize(data, data['transcript'], checklist, meta)

@app.get('/')
def index(): return FileResponse(ROOT/'index.html')
@app.get('/api/health')
def health():
    demo = os.getenv('CALLLENS_DEMO_MODE','0') == '1'
    return {'status': 'ok', 'service': 'calllens-mvp', 'crm': False,
            'mode': 'demo' if demo else 'ai', 'provider': 'openai',
            'ai_configured': bool(os.getenv('OPENAI_API_KEY')) or demo}
@app.get('/{asset}')
def asset(asset:str):
    if asset in {'app.js','styles.css','prompt.md','dashboard.html','dashboard.js','dashboard.css','login.html','app-home.html'}: return FileResponse(ROOT/asset)
    raise HTTPException(404)

@app.post('/api/analyze')
async def analyze(audio: Annotated[UploadFile, File()], checklist: Annotated[str, Form()], manager_name: Annotated[str, Form()]='', client_name: Annotated[str, Form()]='', call_goal: Annotated[str, Form()]=''):
    try: criteria=json.loads(checklist)
    except Exception: raise HTTPException(400,'Некорректный JSON чек-листа')
    suffix=Path(audio.filename or 'call.mp3').suffix.lower() or '.mp3'
    if suffix not in SUPPORTED_AUDIO_SUFFIXES:
        raise HTTPException(415, 'Формат записи не поддерживается. Используйте MP3, WAV, M4A, OGG, MP4 или WEBM.')
    if os.getenv('CALLLENS_DEMO_MODE','0') == '1':
        return demo_result(criteria, {'manager_name':manager_name,'client_name':client_name,'call_goal':call_goal,
                                      'duration':None,'filename':audio.filename,'mode':'demo'})
    with tempfile.TemporaryDirectory(prefix='call_lens_') as td:
        work=Path(td); source=work/f'input{suffix}'
        with source.open('wb') as f: shutil.copyfileobj(audio.file,f)
        if source.stat().st_size > 250*1024*1024: raise HTTPException(413,'Файл больше 250 МБ. Сначала сожмите запись.')
        transcript=transcribe(source,work)
        meta={'manager_name':manager_name,'client_name':client_name,'call_goal':call_goal,'duration':ffprobe_duration(source),'filename':audio.filename}
        return ask_llm(transcript,criteria,meta)
