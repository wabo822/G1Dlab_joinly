import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
import pytest
from test_app import app, db, user, login, event, CONFIRM, CONFIRM_PAID
from app.mcp_server import credential_hash
from app import chatbot

ACCEPT = {'Accept':'application/json, text/event-stream'}


def token(db, uid, scopes=('public:read','bookings:read','bookings:write')):
    secret = 'joinly_test_' + str(uuid4())
    account = db.execute('SELECT email,password_hash FROM users WHERE id=%s',(uid,)).fetchone()
    row = db.execute('''INSERT INTO mcp_tokens(user_id,token_hash,label,scopes,credential_hash) VALUES (%s,%s,'test',%s,%s) RETURNING id''',
                     (uid,hashlib.sha256(secret.encode()).hexdigest(),list(scopes),credential_hash(account))).fetchone()
    return {**ACCEPT,'Authorization':'Bearer '+secret}, row['id']


def rpc(client, headers, method, params=None):
    return client.post('/mcp',headers=headers,json={'jsonrpc':'2.0','id':1,'method':method,'params':params or {}})


def call(client, headers, name, args=None):
    r = rpc(client,headers,'tools/call',{'name':name,'arguments':args or {}})
    assert r.status_code==200,r.text
    return r.json['result']


def proposal(client, headers, eid):
    r=call(client,headers,'book_activity',{'event_id':eid})
    assert r['isError'] is False,r
    return r['structuredContent']


def test_protocol_and_auth(app,db):
    uid=user(db); h,tid=token(db,uid); c=app.test_client()
    app.config['WTF_CSRF_ENABLED']=True
    assert rpc(c,ACCEPT,'tools/list').status_code==401
    assert rpc(c,{**h,'Origin':'https://evil.test'},'tools/list').status_code==403
    assert rpc(c,{**h,'Accept':'application/json'},'tools/list').status_code==406
    assert rpc(c,{**h,'MCP-Protocol-Version':'unknown'},'tools/list').status_code==400
    for version in ['2025-11-25','2025-06-18','2099-01-01']:
        response=rpc(c,h,'initialize',{'protocolVersion':version,'capabilities':{},'clientInfo':{'name':'test','version':'1'}})
        assert response.status_code==200
        assert response.json['result']['protocolVersion'] in ('2025-11-25','2025-06-18')
    tools=rpc(c,h,'tools/list').json['result']['tools']
    assert len(tools)==6 and all('_scope' not in t for t in tools)
    assert c.get('/mcp',headers=h).status_code==405
    assert c.post('/mcp',headers=h,json={'jsonrpc':'2.0','method':'notifications/initialized'}).status_code==202
    assert rpc(c,h,'missing').json['error']['code']==-32601
    assert c.post('/mcp',headers=h,json=[]).status_code==400
    assert c.post('/mcp',headers={**h,'Content-Type':'application/json'},data='{').json['error']['code']==-32700
    db.execute('UPDATE mcp_tokens SET revoked_at=now() WHERE id=%s',(tid,))
    assert rpc(c,h,'tools/list').status_code==401


def test_scope_identity_and_filters(app,db):
    one=user(db); two=user(db,'other@example.test'); h,_=token(db,one); limited,_=token(db,two,('public:read',)); c=app.test_client()
    eid=event(db,one,capacity=3); draft=event(db,one,status='draft')
    db.execute('INSERT INTO reservations(member_id,event_id) VALUES (%s,%s)',(one,eid))
    result=call(c,h,'my_bookings')['structuredContent']
    assert len(result['bookings'])==1 and 'member_id' not in json.dumps(result) and 'email' not in json.dumps(result)
    assert call(c,limited,'my_bookings')['isError']
    assert call(c,h,'my_bookings',{'user_id':two})['isError']
    h2,_=token(db,two)
    assert call(c,h2,'my_bookings')['structuredContent']['bookings']==[]
    assert call(c,h,'get_activity',{'event_id':draft})['isError']
    assert call(c,h,'get_activity',{'event_id':True})['isError']
    assert call(c,h,'search_activities',{'limit':200})['isError']
    assert call(c,h,'search_activities',{'date_from':'2026-99-99'})['isError']
    assert call(c,h,'search_activities',{'location':'Paris','max_price_cents':0})['structuredContent']['activities'][0]['id']==eid
    assert call(c,h,'search_activities',{'location':'Berlin'})['structuredContent']['activities']==[]
    db.execute('UPDATE events SET price_cents=2000 WHERE id=%s',(eid,))
    assert call(c,h,'search_activities',{'max_price_cents':1000})['structuredContent']['activities']==[]


def test_booking_confirmation_identity_paid_and_replay(app,db):
    uid=user(db); other=user(db,'other@example.test'); eid=event(db,uid,capacity=1)
    db.execute('UPDATE events SET price_cents=500 WHERE id=%s',(eid,))
    h,_=token(db,uid); c=app.test_client(); p=proposal(c,h,eid); url=p['confirmation_url']
    assert p['status']=='awaiting_confirmation'
    assert proposal(c,h,eid)['request_id']==p['request_id']
    assert db.execute('SELECT count(*) AS n FROM reservations').fetchone()['n']==0
    assert c.post(url,data=CONFIRM_PAID).status_code==302  # requires browser login, even with API token
    stranger=login(app,'other@example.test')
    assert stranger.get(url).status_code==404
    owner=login(app)
    assert owner.get(url).status_code==200
    assert owner.post(url,data=CONFIRM).status_code==400
    assert owner.post(url,data=CONFIRM_PAID).status_code==302
    assert owner.post(url,data=CONFIRM_PAID).status_code==302
    assert db.execute('SELECT count(*) AS n FROM reservations').fetchone()['n']==1
    assert db.execute('SELECT count(*) AS n FROM tickets').fetchone()['n']==1
    status=call(c,h,'get_booking_request',{'request_id':p['request_id']})['structuredContent']
    assert status['status']=='confirmed'
    assert proposal(c,h,eid)['status']=='already_booked'


@pytest.mark.parametrize('change',['price','date','expiry','full','cancel','revocation'])
def test_stale_or_unavailable_proposals(app,db,change):
    uid=user(db); other=user(db,'other@example.test'); eid=event(db,uid)
    h,tid=token(db,uid); p=proposal(app.test_client(),h,eid); browser=login(app)
    if change=='price': db.execute('UPDATE events SET price_cents=100 WHERE id=%s',(eid,))
    if change=='date': db.execute("UPDATE events SET starts_at=starts_at+interval '1 hour' WHERE id=%s",(eid,))
    if change=='expiry': db.execute("UPDATE assistant_booking_requests SET expires_at=now()-interval '1 second'")
    if change=='full': db.execute('INSERT INTO reservations(member_id,event_id) VALUES (%s,%s)',(other,eid))
    if change=='cancel': db.execute("UPDATE events SET status='cancelled' WHERE id=%s",(eid,))
    if change=='revocation': db.execute('UPDATE mcp_tokens SET revoked_at=now() WHERE id=%s',(tid,))
    assert browser.post(p['confirmation_url'],data=CONFIRM_PAID).status_code in (400,403)
    assert db.execute('SELECT count(*) AS n FROM reservations WHERE member_id=%s',(uid,)).fetchone()['n']==0


def test_token_ui_revocation_and_credential_change(app,db):
    uid=user(db); browser=login(app)
    result=browser.post('/account/mcp',data={'label':'My assistant','scopes':['bookings:read']})
    assert result.status_code==200
    secret=re.search(r'value="(joinly_[^"]+)"',result.text).group(1)
    assert secret not in browser.get('/account/mcp').text
    h={**ACCEPT,'Authorization':'Bearer '+secret}
    assert len(rpc(app.test_client(),h,'tools/list').json['result']['tools'])==4
    db.execute("UPDATE users SET password_hash=password_hash||'changed' WHERE id=%s",(uid,))
    assert rpc(app.test_client(),h,'tools/list').status_code==401


def test_csrf_on_booking_and_settings(app,db):
    uid=user(db); eid=event(db,uid); h,_=token(db,uid); p=proposal(app.test_client(),h,eid); browser=login(app)
    app.config['WTF_CSRF_ENABLED']=True
    assert browser.post('/account/mcp',data={'label':'bad'}).status_code==400
    assert browser.post(p['confirmation_url'],data=CONFIRM).status_code==400
    text=browser.get(p['confirmation_url']).text
    csrf=re.search(r'name="csrf_token" value="([^"]+)"',text).group(1)
    assert browser.post(p['confirmation_url'],data={**CONFIRM,'csrf_token':csrf}).status_code==302


def test_concurrent_confirmations_share_last_place(app,db):
    one=user(db); two=user(db,'other@example.test'); eid=event(db,one)
    h,_=token(db,one); h2,_=token(db,two)
    p=proposal(app.test_client(),h,eid); p2=proposal(app.test_client(),h2,eid)
    clients=[login(app),login(app,'other@example.test')]; barrier=Barrier(2)
    def confirm(pair):
        browser,proposal=pair; barrier.wait(timeout=5)
        return browser.post(proposal['confirmation_url'],data=CONFIRM).status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        result=list(executor.map(confirm,zip(clients,[p,p2])))
    assert sorted(result)==[302,400]
    assert db.execute('SELECT count(*) AS n FROM reservations').fetchone()['n']==1


def test_chat_tool_loop_and_private_consent(app,db,monkeypatch):
    uid=user(db); eid=event(db,uid); browser=login(app); app.config['DEEPSEEK_API_KEY']='test'
    captured=[]
    def reply(config,messages,**kwargs):
        captured.append(json.loads(json.dumps(messages)))
        if messages[-1]['role']=='tool': return {'content':'Ouvrez le lien pour confirmer.'}
        return {'tool_calls':[{'id':'call1','function':{'name':'book_activity','arguments':json.dumps({'event_id':eid})}}]}
    monkeypatch.setattr(chatbot,'completion',reply)
    data={'message':'Réserve cette activité','consent':True}
    denied=browser.post('/api/assistant',json=data).json
    assert denied['actions']==[]
    assert db.execute('SELECT count(*) AS n FROM assistant_booking_requests').fetchone()['n']==0
    response=browser.post('/api/assistant',json={**data,'use_bookings':True})
    assert response.status_code==200,response.text
    action=response.json['actions'][0]
    assert action['url'] in response.json['links']
    assert browser.get(action['url']).status_code==200
    assert db.execute('SELECT count(*) AS n FROM reservations').fetchone()['n']==0
    assert 'member@example.test' not in json.dumps(captured)


def test_mcp_suspended_user_and_impersonation(app,db):
    uid=user(db); h,_=token(db,uid)
    db.execute("UPDATE users SET status='suspended' WHERE id=%s",(uid,))
    assert rpc(app.test_client(),h,'tools/list').status_code==401


def test_impersonation_never_grants_private_tools(app,db,monkeypatch):
    target=user(db); admin=user(db,'admin@example.test',roles=('admin',))
    eid=event(db,target); h,_=token(db,target); p=proposal(app.test_client(),h,eid)
    client=login(app,'admin@example.test')
    with client.session_transaction() as session: session['view_as']=target
    assert client.get('/account/mcp').status_code==403
    assert client.get(p['confirmation_url']).status_code==403
    app.config['DEEPSEEK_API_KEY']='test'
    def reply(config,messages,**kwargs):
        assert all(t['name'] not in ('my_bookings','book_activity') for t in kwargs['tool_defs'])
        return {'content':'Accès public uniquement.'}
    monkeypatch.setattr(chatbot,'completion',reply)
    result=client.post('/api/assistant',json={'message':'mes inscriptions','consent':True,'use_bookings':True})
    assert result.status_code==200 and result.json['bookings_access'] is False


def test_expired_token_and_mcp_quota(app,db):
    uid=user(db); h,tid=token(db,uid); c=app.test_client()
    db.execute("INSERT INTO rate_limits(key,attempts,expires_at) VALUES (%s,60,now()+interval '1 minute')",('mcp:'+str(tid),))
    assert rpc(c,h,'tools/list').status_code==429
    db.execute("UPDATE mcp_tokens SET expires_at=now()-interval '1 second' WHERE id=%s",(tid,))
    assert rpc(c,h,'tools/list').status_code==401
