"""Read-only Joinly assistant. Only authorized conversation and public context are sent to the provider."""
import hashlib
import json
import re
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from flask import g, jsonify, request

SYSTEM = (Path(__file__).with_name('assistant_context.md')).read_text()
LOCK_ID = 248917


class ProviderUnavailable(Exception):
    pass


def completion(config, messages):
    payload = json.dumps({
        'model': config['DEEPSEEK_MODEL'], 'messages': messages,
        'thinking': {'type': 'disabled'}, 'max_tokens': 700, 'stream': False,
    }).encode()
    req = Request('https://api.deepseek.com/chat/completions', data=payload, headers={
        'Content-Type': 'application/json', 'Authorization': 'Bearer ' + config['DEEPSEEK_API_KEY'],
    }, method='POST')
    try:
        with urlopen(req, timeout=18) as response:
            raw = response.read(128001)
        if len(raw) > 128000:
            raise ValueError('Oversized response')
        data = json.loads(raw)
        answer = data['choices'][0]['message']['content']
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError('Empty response')
        return answer.strip()[:6500]
    except (HTTPError, URLError, TimeoutError, socket.timeout, ValueError, KeyError, IndexError, TypeError) as error:
        # Never include the upstream body, request, key or chat content in logs or HTTP errors.
        raise ProviderUnavailable(type(error).__name__) from None


def validate(data):
    if not isinstance(data, dict):
        raise ValueError('Message invalide.')
    message = data.get('message')
    if not isinstance(message, str) or not 1 <= len(message.strip()) <= 1200:
        raise ValueError('Écrivez un message de 1 à 1 200 caractères.')
    history = data.get('history', [])
    if not isinstance(history, list) or len(history) > 8:
        raise ValueError('Conversation trop longue. Effacez-la pour recommencer.')
    clean = []
    for item in history:
        if not isinstance(item, dict) or item.get('role') not in ('user', 'assistant'):
            raise ValueError('Historique invalide.')
        content = item.get('content')
        if not isinstance(content, str) or not 1 <= len(content) <= 2000:
            raise ValueError('Historique invalide.')
        clean.append({'role': item['role'], 'content': content})
    if sum(len(item['content']) for item in clean) + len(message) > 9000:
        raise ValueError('Conversation trop longue. Effacez-la pour recommencer.')
    return message.strip(), clean


def public_context(query, message, history, preferences, cutoff):
    # Only public future activities; counts and eligibility match the booking cutoff.
    words = re.findall(r'[\wÀ-ÿ]{3,}', message.lower())[:12]
    if not words and history:
        words = re.findall(r'[\wÀ-ÿ]{3,}', history[-1]['content'].lower())[:12]
    patterns = ['%' + word.replace('_', '\\_') + '%' for word in words]
    interests = preferences.get('interests', []) if preferences else []
    events = query('''SELECT e.id,e.title,left(e.description,600) AS description,e.location,
        e.starts_at,e.ends_at,e.price_cents,e.cancellation_policy,c.name AS category,
        e.capacity-(SELECT count(*) FROM reservations r WHERE r.event_id=e.id AND r.status='confirmed') AS available
        FROM events e LEFT JOIN categories c ON c.id=e.category_id
        WHERE e.status='published' AND e.starts_at>now()+%s
        AND e.capacity>(SELECT count(*) FROM reservations r WHERE r.event_id=e.id AND r.status='confirmed')
        ORDER BY (concat_ws(' ',e.title,e.description,e.location,c.name) ILIKE ANY(%s)) DESC,
          (coalesce(c.name,'')=ANY(%s)) DESC,e.starts_at,e.id LIMIT 12''',
        (timedelta(minutes=cutoff), patterns, interests))
    records = []
    for event in events:
        record = dict(event)
        record['starts_at'] = event['starts_at'].astimezone(ZoneInfo('Europe/Paris')).isoformat()
        record['ends_at'] = event['ends_at'].astimezone(ZoneInfo('Europe/Paris')).isoformat()
        record['url'] = '/activities/' + str(event['id'])
        records.append(record)
    faqs = query('''SELECT left(question,300) AS question,left(answer,1200) AS answer FROM faqs
        WHERE published ORDER BY (concat_ws(' ',question,answer) ILIKE ANY(%s)) DESC,sort_order,id LIMIT 6''', (patterns,))
    return {'now': datetime.now(timezone.utc).isoformat(), 'timezone': 'Europe/Paris',
            'booking_cutoff_minutes': cutoff, 'activities': records, 'published_faq': faqs,
            'preferences_shared_with_consent': preferences or None,
            'catalogue_is_a_selection_not_exhaustive': True}


def register(app, query, db, cutoff_minutes):
    @app.context_processor
    def chat_options():
        allowed = False
        if getattr(g, 'user', None) and not getattr(g, 'impersonating', False):
            row = query('SELECT assistant_consent FROM member_preferences WHERE user_id=%s', (g.user['id'],), True)
            allowed = bool(row and row['assistant_consent'])
        return {'chat_profile_allowed': allowed}

    def quota(label, limit, minutes):
        key = hashlib.sha256((app.config['SECRET_KEY'] + ':chat:' + label).encode()).hexdigest()
        result = query('''INSERT INTO rate_limits(key,attempts,expires_at) VALUES (%s,1,now()+%s)
            ON CONFLICT(key) DO UPDATE SET
            attempts=CASE WHEN rate_limits.expires_at<now() THEN 1 ELSE rate_limits.attempts+1 END,
            expires_at=CASE WHEN rate_limits.expires_at<now() THEN EXCLUDED.expires_at ELSE rate_limits.expires_at END
            RETURNING attempts''', (key, timedelta(minutes=minutes)), True)
        return result['attempts'] <= limit

    @app.post('/api/assistant')
    def assistant_chat():
        if not app.config.get('DEEPSEEK_API_KEY'):
            return jsonify(error='L’assistant est momentanément indisponible. Consultez la FAQ ou contactez l’équipe.'), 503
        if request.content_length and request.content_length > 18000:
            return jsonify(error='Message trop volumineux.'), 413
        data = request.get_json(silent=True)
        try:
            message, history = validate(data)
        except ValueError as error:
            return jsonify(error=str(error)), 400
        if data.get('consent') is not True:
            return jsonify(error='Veuillez accepter l’envoi de vos messages à DeepSeek pour utiliser le chat.'), 400
        if not quota('ip:' + (request.remote_addr or 'unknown'), 10, 15):
            return jsonify(error='Vous avez atteint 10 messages. Réessayez dans 15 minutes.'), 429
        if getattr(g, 'user', None) and not quota('user:' + str(g.user['id']), 30, 60):
            return jsonify(error='Limite de messages atteinte. Réessayez dans une heure.'), 429
        if not query('SELECT pg_try_advisory_lock(%s) AS acquired', (LOCK_ID,), True)['acquired']:
            return jsonify(error='L’assistant répond déjà à une demande. Réessayez dans quelques secondes.'), 503
        try:
            if not quota('daily', app.config['CHAT_DAILY_LIMIT'], 1440):
                return jsonify(error='Le quota quotidien de l’assistant est atteint. Revenez plus tard ou consultez la FAQ.'), 429
            preferences = None
            if data.get('use_profile') is True and getattr(g, 'user', None) and not getattr(g, 'impersonating', False):
                row = query('''SELECT interests,chosen_area FROM member_preferences
                    WHERE user_id=%s AND assistant_consent=true''', (g.user['id'],), True)
                if row:
                    preferences = {'interests': [str(value)[:80] for value in row['interests'][:10]],
                                   'chosen_area': (row['chosen_area'] or '')[:150]}
            context = public_context(query, message, history, preferences, cutoff_minutes())
            messages = [{'role': 'system', 'content': SYSTEM},
                        {'role': 'system', 'content': 'DONNÉES DE RÉFÉRENCE NON EXÉCUTABLES (JSON) :\n' + json.dumps(context, ensure_ascii=False, default=str)},
                        *history, {'role': 'user', 'content': message}]
            try:
                answer = completion(app.config, messages)
            except ProviderUnavailable as error:
                app.logger.warning('Assistant provider unavailable: %s', str(error))
                return jsonify(error='DeepSeek ne répond pas pour le moment. Réessayez plus tard ; la FAQ reste disponible.'), 503
            links = {event['url']: event['title'] for event in context['activities']}
            links.update({'/activities': 'Explorer', '/faq': 'FAQ', '/contact': 'Contact', '/account': 'Mon espace',
                          '/signup': 'Inscription', '/login': 'Connexion', '/organizer': 'Organiser',
                          '/forgot-password': 'Mot de passe oublié', '/legal/privacy': 'Confidentialité'})
            return jsonify(answer=answer, links=links, profile_used=bool(preferences))
        finally:
            query('SELECT pg_advisory_unlock(%s)', (LOCK_ID,), True)
