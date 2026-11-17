"""Exercise the real Streamable HTTP transport with the official SDK, test DB only."""
import asyncio
import hashlib
import json
import logging
import re
import secrets
import sys
from pathlib import Path
from threading import Thread
from uuid import uuid4

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import psycopg
import requests
from psycopg.rows import dict_row
from werkzeug.security import generate_password_hash
from werkzeug.serving import make_server, WSGIRequestHandler
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from app import create_app
from app.mcp_server import credential_hash


class QuietHandler(WSGIRequestHandler):
    def log(self,*args,**kwargs): pass


def main():
    application=create_app({'TESTING':True,'DATABASE':'joinly_test','SECRET_KEY':'sdk-test-only',
                            'SESSION_COOKIE_SECURE':False,'PUBLIC_BASE_URL':''})
    application.logger.setLevel(logging.CRITICAL)
    server=make_server('127.0.0.1',0,application,threaded=True,request_handler=QuietHandler)
    origin=f'http://127.0.0.1:{server.server_port}'
    password=secrets.token_urlsafe(24); secret='joinly_'+secrets.token_urlsafe(32)
    email=f'sdk-{uuid4()}@example.test'; uid=eid=None
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    with psycopg.connect(dbname='joinly_test',row_factory=dict_row,autocommit=True) as db:
        try:
            account=db.execute('''INSERT INTO users(email,display_name,password_hash,email_verified_at)
                VALUES (%s,'SDK verification',%s,now()) RETURNING id,email,password_hash''',(email,generate_password_hash(password))).fetchone()
            uid=account['id']
            db.execute("INSERT INTO user_roles SELECT %s,id FROM roles WHERE name='member'",(uid,))
            for name in ('SDK Nature','SDK Culture','SDK Sport'):
                category=db.execute('INSERT INTO categories(name) VALUES (%s) ON CONFLICT(name) DO UPDATE SET name=EXCLUDED.name RETURNING id',(name,)).fetchone()['id']
                db.execute('INSERT INTO user_interests(user_id,category_id) VALUES (%s,%s)',(uid,category))
            eid=db.execute('''INSERT INTO events(organizer_id,title,description,location,starts_at,ends_at,capacity,status)
                VALUES (%s,'SDK activity','Demo only','Paris',now()+interval '2 days',now()+interval '2 days 1 hour',1,'published') RETURNING id''',(uid,)).fetchone()['id']
            tid=db.execute('''INSERT INTO mcp_tokens(user_id,token_hash,label,scopes,credential_hash)
                VALUES (%s,%s,'SDK',ARRAY['public:read','bookings:read','bookings:write'],%s) RETURNING id''',
                (uid,hashlib.sha256(secret.encode()).hexdigest(),credential_hash(account))).fetchone()['id']

            async def exercise():
                async with streamablehttp_client(origin+'/mcp',headers={'Authorization':'Bearer '+secret}) as (reader,writer,_):
                    async with ClientSession(reader,writer) as session:
                        initialized=await session.initialize()
                        assert initialized.serverInfo.name=='joinly'
                        tools=await session.list_tools()
                        assert len(tools.tools)==6
                        found=await session.call_tool('search_activities',{'query':'SDK activity'})
                        assert not found.isError
                        result=await session.call_tool('book_activity',{'event_id':eid})
                        assert not result.isError
                        proposal=json.loads(result.content[0].text)
                        assert proposal['status']=='awaiting_confirmation'
                        assert db.execute('SELECT count(*) AS n FROM reservations WHERE event_id=%s',(eid,)).fetchone()['n']==0
                        # Browser confirmation is deliberately outside the MCP agent's capabilities.
                        browser=requests.Session()
                        page=browser.get(origin+'/login')
                        csrf=re.search(r'name="csrf_token" value="([^"]+)"',page.text).group(1)
                        response=browser.post(origin+'/login',data={'email':email,'password':password,'csrf_token':csrf})
                        assert response.status_code==200
                        page=browser.get(origin+proposal['confirmation_url'])
                        csrf=re.search(r'name="csrf_token" value="([^"]+)"',page.text).group(1)
                        response=browser.post(origin+proposal['confirmation_url'],data={'csrf_token':csrf,'confirm':'1','acknowledged':'1'})
                        assert response.status_code==200
                        mine=await session.call_tool('my_bookings',{})
                        assert json.loads(mine.content[0].text)['bookings'][0]['event_id']==eid
                        state=await session.call_tool('get_booking_request',{'request_id':proposal['request_id']})
                        assert json.loads(state.content[0].text)['status']=='confirmed'
                        print('Official MCP SDK: initialize, discovery, search, proposal, browser confirmation and status passed.')
            asyncio.run(exercise())
            db.execute('UPDATE mcp_tokens SET revoked_at=now() WHERE id=%s',(tid,))
            assert requests.post(origin+'/mcp',headers={'Authorization':'Bearer '+secret}).status_code==401
            print('Token revocation passed. All operations used joinly_test.')
        finally:
            if eid:
                db.execute('DELETE FROM reservations WHERE event_id=%s',(eid,))
                db.execute('DELETE FROM events WHERE id=%s',(eid,))
            if uid:
                db.execute('DELETE FROM dev_outbox WHERE recipient=%s',(email,))
                db.execute('DELETE FROM users WHERE id=%s',(uid,))
            server.shutdown();thread.join(timeout=5);server.server_close()


if __name__=='__main__': main()
