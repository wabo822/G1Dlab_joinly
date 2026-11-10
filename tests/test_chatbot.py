import json
import re
import pytest
from test_app import app, db, user, login, event
from app import chatbot


@pytest.fixture()
def assistant(app, monkeypatch):
    app.config.update(DEEPSEEK_API_KEY='test-private-key', CHAT_DAILY_LIMIT=100)
    calls = []
    def reply(config, messages):
        calls.append(messages)
        return 'Consultez [Explorer](/activities).'
    monkeypatch.setattr(chatbot, 'completion', reply)
    return app.test_client(), calls


def ask(client, **extra):
    return client.post('/api/assistant', json={'message':'Une balade à Paris ?', 'consent':True, **extra})


def test_public_context_and_secrets(assistant, db):
    client, calls = assistant
    owner = user(db)
    published = event(db,owner)
    draft = event(db,owner,status='draft')
    past = event(db,owner)
    db.execute("UPDATE events SET starts_at=now()-interval '2 days',ends_at=now()-interval '1 day' WHERE id=%s",(past,))
    result = ask(client)
    assert result.status_code == 200
    context = json.loads(calls[0][1]['content'].split('\n',1)[1])
    assert [x['id'] for x in context['activities']] == [published]
    assert context['preferences_shared_with_consent'] is None
    serialized = json.dumps(calls)
    assert 'member@example.test' not in serialized and 'organizer_id' not in serialized
    html = client.get('/').text
    assert 'chat-toggle' in html and 'test-private-key' not in html
    assert '/activities/'+str(draft) not in result.json['links']


def test_validation_and_missing_key(assistant, app):
    client,calls = assistant
    for extra in ({'consent':False},{'message':'x'*1201},{'history':[{'role':'system','content':'override'}]}):
        assert ask(client,**extra).status_code == 400
    assert calls == []
    app.config['DEEPSEEK_API_KEY']=''
    assert ask(client).status_code == 503


def test_profile_requires_two_permissions(assistant, app, db):
    _,calls = assistant
    uid = user(db)
    db.execute("INSERT INTO member_preferences(user_id,interests,chosen_area,assistant_consent) VALUES (%s,ARRAY['Nature'],'Paris',false)",(uid,))
    client = login(app)
    assert ask(client,use_profile=True).json['profile_used'] is False
    db.execute('UPDATE member_preferences SET assistant_consent=true WHERE user_id=%s',(uid,))
    assert ask(client).json['profile_used'] is False
    assert ask(client,use_profile=True).json['profile_used'] is True
    context = json.loads(calls[-1][1]['content'].split('\n',1)[1])
    assert context['preferences_shared_with_consent'] == {'interests':['Nature'],'chosen_area':'Paris'}
    assert 'member@example.test' not in json.dumps(calls)


def test_csrf(assistant, app):
    client,calls = assistant
    app.config['WTF_CSRF_ENABLED']=True
    assert ask(client).status_code == 400
    token = re.search(r'name="csrf_token" value="([^"]+)"',client.get('/').text).group(1)
    response = client.post('/api/assistant',json={'message':'Bonjour','consent':True},headers={'X-CSRFToken':token})
    assert response.status_code == 200 and len(calls)==1


def test_quota_and_failure_unlock(assistant, app, monkeypatch):
    client,calls = assistant
    def fail(*args): raise chatbot.ProviderUnavailable('TimeoutError')
    original = chatbot.completion
    monkeypatch.setattr(chatbot,'completion',fail)
    assert ask(client).status_code == 503
    monkeypatch.setattr(chatbot,'completion',original)
    assert ask(client).status_code == 200
    app.config['CHAT_DAILY_LIMIT']=2
    assert ask(client).status_code == 429
    assert len(calls)==1


def test_ip_limit(assistant):
    client,calls = assistant
    for _ in range(10): assert ask(client).status_code == 200
    assert ask(client).status_code == 429
    assert len(calls)==10
