import json
import os

os.environ.setdefault('DATABASE_URL', 'sqlite+aiosqlite:///./calllens_auth_test.db')
os.environ.setdefault('APP_BASE_URL', 'http://localhost:8000')
os.environ.setdefault('EMAIL_MODE', 'log')
os.environ.setdefault('ALLOWED_ORIGINS', 'http://localhost:8000')

import pytest
from httpx import ASGITransport, AsyncClient

import backend
from backend import app, make_markdown, normalize


CHECKLIST = [{'name': 'Установил цель звонка', 'max_points': 10}, {'name': 'Выявил потребность', 'max_points': 20}]


def base_data(**extra):
    data = {
        'role_warning': False,
        'score': {'criteria': [
            {'name': 'Установил цель звонка', 'max_points': 10, 'earned_points': 10, 'verdict': 'выполнено', 'quote': 'Цель — демо', 'timestamp': '00:01', 'reason': 'ok'},
            {'name': 'Выявил потребность', 'max_points': 20, 'earned_points': 10, 'verdict': 'частично', 'quote': 'Частично', 'timestamp': '00:05', 'reason': 'ok'},
        ]},
        'client_communication_profile': {'primary_type': 'Доказательный эксперт', 'confidence': 0.7},
    }
    data.update(extra)
    return data


def test_personality_profile_defaults_added():
    """Старый ответ провайдера без personality_profile нормализуется обратно совместимо."""
    data = base_data()
    data['client_communication_profile'].pop('primary_type')
    result = normalize(data, 'transcript', CHECKLIST, {})
    pp = result['personality_profile']
    assert pp['disc_profile'] == {'d': 0, 'i': 0, 's': 0, 'c': 0, 'primary': 'NONE', 'confidence': 0.0}
    bf = pp['big_five_scores']
    assert [bf[k] for k in ('openness', 'conscientiousness', 'extraversion', 'agreeableness', 'neuroticism')] == [50] * 5
    assert bf['low_evidence'] is True
    assert pp['evidence'] == {'disc': [], 'big_five': []}
    assert pp['communication_style']['primary_type'] == 'Профиль не определён'
    # существующие поля не сломаны
    assert result['score']['criteria'][0]['verdict_key'] == 'pass'
    assert result['client_communication_profile']['confidence_percent'] == 70


def test_disc_primary_derived_from_communication_style():
    result = normalize(base_data(), 'transcript', CHECKLIST, {})
    pp = result['personality_profile']
    assert pp['disc_profile']['primary'] == 'C'
    assert pp['communication_style']['primary_type'] == 'Доказательный эксперт'
    assert pp['provisional'] is False


def test_personality_profile_values_clamped_and_preserved():
    data = base_data(personality_profile={
        'communication_style': {'primary_type': 'Результатный стратег', 'confidence': 0.9},
        'disc_profile': {'d': 140, 'i': -5, 's': 'не число', 'c': 30.6, 'primary': 'd', 'confidence': 2},
        'big_five_scores': {'openness': 80, 'extraversion': None},
        'evidence': {'disc': ['строка без словаря'], 'big_five': [{'timestamp': '01:00', 'quote': 'Давайте цифры', 'signal': 'C'}]},
    })
    pp = normalize(data, 'transcript', CHECKLIST, {})['personality_profile']
    assert pp['disc_profile']['d'] == 100 and pp['disc_profile']['i'] == 0
    assert pp['disc_profile']['s'] == 0 and pp['disc_profile']['c'] == 31
    assert pp['disc_profile']['primary'] == 'D' and pp['disc_profile']['confidence'] == 1.0
    bf = pp['big_five_scores']
    assert bf['openness'] == 80 and bf['extraversion'] == 50 and bf['low_evidence'] is True
    assert pp['evidence']['disc'] == [{'timestamp': '', 'quote': 'строка без словаря', 'signal': ''}]
    assert pp['evidence']['big_five'][0]['quote'] == 'Давайте цифры'


def test_role_warning_marks_profile_provisional():
    result = normalize(base_data(role_warning=True), 'transcript', CHECKLIST, {})
    assert result['personality_profile']['provisional'] is True


def test_markdown_contains_psychotype_section():
    result = normalize(base_data(), 'transcript', CHECKLIST, {})
    md = make_markdown(result)
    assert 'Психотип: DISC и Big Five' in md
    assert 'Big Five (0–100)' in md


@pytest.mark.asyncio
async def test_demo_endpoint_returns_personality_profile(monkeypatch):
    monkeypatch.setenv('CALLLENS_DEMO_MODE', '1')
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://localhost:8000') as client:
        r = await client.post('/api/analyze',
                              files={'audio': ('call.mp3', b'fake audio bytes', 'audio/mpeg')},
                              data={'checklist': json.dumps(CHECKLIST, ensure_ascii=False), 'manager_name': 'Менеджер', 'client_name': 'Клиент', 'call_goal': 'Демо'})
    assert r.status_code == 200
    body = r.json()
    pp = body['personality_profile']
    assert pp['disc_profile']['primary'] == 'C'
    assert 0 <= pp['disc_profile']['d'] <= 100
    assert set(pp['big_five_scores']) >= {'openness', 'conscientiousness', 'extraversion', 'agreeableness', 'neuroticism', 'low_evidence'}
    assert pp['evidence']['disc'] and pp['evidence']['disc'][0]['quote']
    assert pp['communication_style']['primary_type'] == 'Доказательный эксперт'
    # обратная совместимость: существующие поля ответа не изменились
    for field in ('score', 'client_communication_profile', 'objections', 'one_call_coaching', 'follow_up', 'team_insights', 'markdown', 'transcript'):
        assert field in body
    assert 'Психотип: DISC и Big Five' in body['markdown']


def test_demo_result_direct():
    result = backend.demo_result(CHECKLIST, {'manager_name': 'М', 'client_name': 'К', 'call_goal': ''})
    assert result['personality_profile']['disc_profile']['confidence'] == 0.5
