"""Stateless MCP Streamable HTTP: JSON responses, no resident worker or SSE stream.

Supports the 2025-11-25 and 2025-06-18 protocol versions. Authentication uses
manually configured per-user bearer tokens; no OAuth discovery is advertised.
"""
import hashlib
import json
import secrets
from datetime import datetime, timezone
from urllib.parse import urlsplit
from flask import abort, g, jsonify, redirect, render_template, request, url_for, flash
from app.assistant_tools import ToolError, definitions
from app.bookings import create_booking, snapshot, BLOCK_MESSAGES

VERSIONS = ('2025-11-25', '2025-06-18')
ALL_SCOPES = {'public:read', 'bookings:read', 'bookings:write'}


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def credential_hash(user):
    return digest(user['password_hash'] + ':' + user['email'])


def register(app, query, db, service, send_notification):
    def browser_user():
        if not g.user: return redirect(url_for('login'))
        if g.impersonating or not g.user['email_verified_at']: abort(403)
        return None

    @app.route('/account/mcp', methods=['GET','POST'])
    def mcp_settings():
        denied = browser_user()
        if denied is not None: return denied
        secret = None
        if request.method == 'POST':
            if request.form.get('action') == 'revoke':
                try: token_id = int(request.form.get('token_id',''))
                except ValueError: abort(400)
                query('UPDATE mcp_tokens SET revoked_at=now() WHERE id=%s AND user_id=%s', (token_id,g.user['id']))
                flash('Accès MCP révoqué.', 'success')
                return redirect(url_for('mcp_settings'))
            label = request.form.get('label','').strip()
            scopes = set(request.form.getlist('scopes')) | {'public:read'}
            if not label or len(label)>80 or not scopes <= ALL_SCOPES: abort(400)
            with db().transaction():
                user = query('SELECT email,password_hash FROM users WHERE id=%s FOR UPDATE', (g.user['id'],),True)
                count = query('SELECT count(*) AS n FROM mcp_tokens WHERE user_id=%s AND revoked_at IS NULL AND expires_at>now()', (g.user['id'],), True)['n']
                if count >= 10: raise ValueError('Révoquez un accès avant d’en créer un autre (maximum 10).')
                secret = 'joinly_' + secrets.token_urlsafe(32)
                query('''INSERT INTO mcp_tokens(user_id,token_hash,label,scopes,credential_hash)
                         VALUES (%s,%s,%s,%s,%s)''',(g.user['id'],digest(secret),label,sorted(scopes),credential_hash(user)))
        tokens = query('''SELECT id,label,scopes,expires_at,revoked_at,last_used_at FROM mcp_tokens
            WHERE user_id=%s ORDER BY created_at DESC LIMIT 30''',(g.user['id'],))
        endpoint = app.config.get('PUBLIC_BASE_URL') or request.url_root.rstrip('/')
        return render_template('mcp_settings.html', tokens=tokens, secret=secret, endpoint=endpoint+'/mcp')

    @app.route('/assistant/bookings/<uuid:request_id>', methods=['GET','POST'])
    def assistant_booking(request_id):
        denied = browser_user()
        if denied is not None: return denied
        with db().transaction():
            proposal = query('''SELECT * FROM assistant_booking_requests WHERE id=%s AND user_id=%s FOR UPDATE''',
                             (request_id,g.user['id']),True)
            if not proposal: abort(404)
            if proposal['token_id']:
                token = query('''SELECT t.*,u.password_hash,u.email FROM mcp_tokens t JOIN users u ON u.id=t.user_id
                    WHERE t.id=%s AND t.revoked_at IS NULL AND t.expires_at>now()''',(proposal['token_id'],),True)
                if not token or 'bookings:write' not in token['scopes'] or token['credential_hash'] != credential_hash(token): abort(403)
            if proposal['reservation_id']:
                flash('Cette demande a déjà été traitée. Consultez votre inscription dans Mon espace.', 'info')
                return redirect(url_for('account'))
            if proposal['expires_at'] <= datetime.now(timezone.utc):
                raise ValueError('Cette proposition a expiré. Demandez-en une nouvelle à l’assistant.')
            event = service.activity(proposal['event_id'])
            if snapshot(event) != proposal['snapshot']:
                raise ValueError('Les informations ont changé. Demandez une nouvelle proposition à l’assistant.')
            if request.method == 'POST':
                if request.form.get('confirm') != '1' or request.form.get('acknowledged') != '1':
                    raise ValueError('Vérifiez les informations et cochez la confirmation.')
                event, ticket, created = create_booking(db(),g.user['id'],event['id'],service.cutoff(),
                    request.form.get('payment_simulated') == '1', expected=proposal['snapshot'], idempotent=True)
                query('UPDATE assistant_booking_requests SET reservation_id=%s WHERE id=%s',(ticket['reservation_id'],request_id))
            else:
                booking = query("SELECT id FROM reservations WHERE member_id=%s AND event_id=%s AND status='confirmed'",(g.user['id'],event['id']),True)
                return render_template('confirm.html',event=event,booking=booking,
                    reservable=not event['booking_block'],reason=BLOCK_MESSAGES.get(event['booking_block'],''),confirmation_action=request.path)
        if created: send_notification(event,ticket,g.user)
        flash('Votre place est réservée. Aucun paiement réel n’a été effectué.', 'success')
        return redirect(url_for('account'))

    def rpc_error(code, message, rid=None, status=200):
        return jsonify(jsonrpc='2.0',id=rid,error={'code':code,'message':message}),status

    @app.route('/mcp', methods=['POST','GET','DELETE'])
    @app.extensions['csrf'].exempt
    def mcp_endpoint():
        origin = request.headers.get('Origin')
        public = app.config.get('PUBLIC_BASE_URL') or request.url_root.rstrip('/')
        parsed = urlsplit(public)
        if origin and origin != parsed.scheme+'://'+parsed.netloc:
            return rpc_error(-32000,'Origin interdit.',status=403)
        auth = request.headers.get('Authorization','')
        if not auth.startswith('Bearer ') or len(auth)>200:
            response,status = rpc_error(-32001,'Jeton MCP requis.',status=401)
            response.headers['WWW-Authenticate'] = 'Bearer realm="joinly-mcp"'
            return response,status
        token = query('''SELECT t.id,t.user_id,t.scopes,t.credential_hash,u.password_hash,u.email FROM mcp_tokens t JOIN users u ON u.id=t.user_id
            WHERE t.token_hash=%s AND t.revoked_at IS NULL AND t.expires_at>now() AND u.status='active' AND u.email_verified_at IS NOT NULL''',
            (digest(auth[7:]),),True)
        if not token or token['credential_hash'] != credential_hash(token):
            return rpc_error(-32001,'Jeton invalide, expiré ou révoqué.',status=401)
        if request.method != 'POST': return '',405,{'Allow':'POST'}
        key = 'mcp:' + str(token['id'])
        count = query('''INSERT INTO rate_limits(key,attempts,expires_at) VALUES (%s,1,now()+interval '1 minute')
            ON CONFLICT(key) DO UPDATE SET attempts=CASE WHEN rate_limits.expires_at<now() THEN 1 ELSE rate_limits.attempts+1 END,
            expires_at=CASE WHEN rate_limits.expires_at<now() THEN EXCLUDED.expires_at ELSE rate_limits.expires_at END RETURNING attempts''',(key,),True)['attempts']
        if count>60: return rpc_error(-32000,'Limite de 60 requêtes par minute.',status=429)
        if request.content_length and request.content_length>16000: return rpc_error(-32600,'Requête trop volumineuse.',status=413)
        if not request.is_json: return rpc_error(-32600,'Content-Type application/json requis.',status=415)
        if not all(x in request.headers.get('Accept','') for x in ('application/json','text/event-stream')):
            return rpc_error(-32600,'Accept doit inclure application/json et text/event-stream.',status=406)
        if request.headers.get('MCP-Protocol-Version',VERSIONS[0]) not in VERSIONS:
            return rpc_error(-32600,'Version MCP non prise en charge.',status=400)
        # Bound the body even when sent without Content-Length.
        request.max_content_length = 16000
        data = request.get_json(silent=True)
        if data is None: return rpc_error(-32700,'JSON invalide.',status=400)
        if not isinstance(data,dict) or data.get('jsonrpc') != '2.0': return rpc_error(-32600,'Requête JSON-RPC invalide.',status=400)
        rid = data.get('id')
        if 'id' in data and (type(rid) not in (str,int) or isinstance(rid,str) and len(rid)>100):
            return rpc_error(-32600,'Identifiant invalide.',status=400)
        method,params = data.get('method'),data.get('params',{})
        if not isinstance(method,str) or not isinstance(params,dict): return rpc_error(-32600,'Requête invalide.',rid)
        if 'id' not in data:
            if method.startswith('notifications/'): return '',202
            return rpc_error(-32600,'Identifiant requis.',status=400)
        if method == 'initialize':
            if not isinstance(params.get('protocolVersion'),str) or not isinstance(params.get('capabilities'),dict) or not isinstance(params.get('clientInfo'),dict):
                return rpc_error(-32602,'Paramètres initialize invalides.',rid)
            result = {'protocolVersion':params['protocolVersion'] if params['protocolVersion'] in VERSIONS else VERSIONS[0],
                      'capabilities':{'tools':{}},'serverInfo':{'name':'joinly','version':'1.0.0'},
                      'instructions':'Access is scoped to the token owner. Booking tools prepare a request; the user MUST confirm on the Joinly website. Prices are simulated. Relative links resolve against '+public}
        elif method == 'ping': result = {}
        elif method == 'tools/list': result = {'tools':definitions(token['scopes'])}
        elif method == 'tools/call':
            if not isinstance(params.get('name'),str): return rpc_error(-32602,'Nom de l’outil requis.',rid)
            try:
                value = service.call(params['name'],params.get('arguments',{}),token['user_id'],token['scopes'],token['id'])
                result = {'content':[{'type':'text','text':json.dumps(value,ensure_ascii=False)}],'structuredContent':value,'isError':False}
            except ToolError as error:
                result = {'content':[{'type':'text','text':str(error)}],'isError':True}
        else: return rpc_error(-32601,'Méthode inconnue.',rid)
        query('UPDATE mcp_tokens SET last_used_at=now() WHERE id=%s',(token['id'],))
        return jsonify(jsonrpc='2.0',id=rid,result=result)
