"""Bounded, identity-scoped tools shared by MCP and the website assistant."""
import json
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo
from psycopg.types.json import Jsonb
from app.bookings import BLOCK_MESSAGES, snapshot
from app.lifecycle import booking_block

PARIS = ZoneInfo('Europe/Paris')


def tool(name, description, properties=None, required=(), scope='public:read', readonly=True):
    return {'name': name, 'description': description,
            'inputSchema': {'type': 'object', 'properties': properties or {}, 'required': list(required), 'additionalProperties': False},
            'annotations': {'readOnlyHint': readonly, 'destructiveHint': False, 'idempotentHint': readonly, 'openWorldHint': False},
            '_scope': scope}


TEXT = {'type': 'string', 'maxLength': 100}
ID = {'type': 'integer', 'minimum': 1, 'maximum': 2147483647}
TOOLS = [
 tool('search_activities', 'Search published, upcoming activities with places. Dates are YYYY-MM-DD in Europe/Paris. Prices are simulated.', {
     'query': TEXT, 'location': TEXT, 'category': TEXT,
     'date_from': {'type': 'string', 'format': 'date'}, 'date_to': {'type': 'string', 'format': 'date'},
     'max_price_cents': {'type': 'integer', 'minimum': 0, 'maximum': 10000000},
     'limit': {'type': 'integer', 'minimum': 1, 'maximum': 20},
     'offset': {'type': 'integer', 'minimum': 0, 'maximum': 1000}}),
 tool('get_activity', 'Read public activity details, remaining places and cancellation policy.', {'event_id': ID}, ('event_id',)),
 tool('search_faq', 'Search published Joinly FAQ answers.', {'query': TEXT}),
 tool('my_bookings', 'Read only the authenticated user’s registrations, without email or ticket secrets.', {
     'period': {'type': 'string', 'enum': ['upcoming', 'history', 'all']},
     'limit': {'type': 'integer', 'minimum': 1, 'maximum': 20},
     'offset': {'type': 'integer', 'minimum': 0, 'maximum': 1000}}, scope='bookings:read'),
 tool('book_activity', 'Prepare a booking for the authenticated user. DOES NOT reserve a seat. The user must open confirmation_url, sign in as the same user, review details and click Confirm. Never claim a booking is confirmed from this result.',
      {'event_id': ID}, ('event_id',), scope='bookings:write', readonly=False),
 tool('get_booking_request', 'Check whether the user has confirmed a prepared booking in the website. No side effects.',
      {'request_id': {'type': 'string', 'format': 'uuid'}}, ('request_id',), scope='bookings:write'),
]


class ToolError(ValueError):
    pass


def definitions(scopes):
    return [{k: v for k, v in t.items() if not k.startswith('_')} for t in TOOLS if t['_scope'] in scopes]


def validate_arguments(definition, args):
    schema = definition['inputSchema']
    if not isinstance(args, dict) or set(args) - set(schema['properties']) or not set(schema['required']) <= set(args):
        raise ToolError('Paramètres invalides ou manquants.')
    for name, value in args.items():
        rule = schema['properties'][name]
        if rule['type'] == 'integer':
            if type(value) is not int or not rule.get('minimum', value) <= value <= rule.get('maximum', value):
                raise ToolError('Nombre hors limites : ' + name)
        elif not isinstance(value, str) or len(value) > rule.get('maxLength', 100):
            raise ToolError('Texte invalide : ' + name)
        if 'enum' in rule and value not in rule['enum']:
            raise ToolError('Choix invalide : ' + name)
        try:
            if rule.get('format') == 'date':
                if len(value) != 10: raise ValueError()
                date.fromisoformat(value)
            if rule.get('format') == 'uuid': UUID(value)
        except (ValueError, TypeError):
            raise ToolError('Format invalide : ' + name) from None


def wire(value):
    return json.loads(json.dumps(value, default=lambda x: x.astimezone(PARIS).isoformat() if isinstance(x, datetime) else str(x)))


EVENT_SQL = '''SELECT e.id,e.title,left(e.description,2000) AS description,e.location,e.starts_at,e.ends_at,
 e.price_cents,e.cancellation_policy,e.capacity,e.status,c.name AS category,u.display_name AS organizer,
 (u.email LIKE '%%@demo.joinly.fr' OR e.title ILIKE '%%[Démo]%%' OR e.description ILIKE '%%démonstration%%') AS demo,
 e.capacity-(SELECT count(*) FROM reservations r WHERE r.event_id=e.id AND r.status='confirmed') AS available
 FROM events e LEFT JOIN categories c ON c.id=e.category_id JOIN users u ON u.id=e.organizer_id'''


class ToolService:
    def __init__(self, query, db, cutoff):
        self.query, self.db, self.cutoff = query, db, cutoff

    def activity(self, event_id):
        row = self.query(EVENT_SQL + " WHERE e.id=%s AND e.status IN ('published','cancelled')", (event_id,), True)
        if not row: raise ToolError('Activité publique introuvable.')
        row['url'] = '/activities/' + str(row['id'])
        row['booking_block'] = booking_block(row, cutoff_minutes=self.cutoff(), available=row['available'])
        return row

    def call(self, name, args, user_id=None, scopes=('public:read',), token_id=None):
        definition = next((x for x in TOOLS if x['name'] == name), None)
        if not definition: raise ToolError('Outil inconnu.')
        if definition['_scope'] not in scopes or (definition['_scope'] != 'public:read' and not user_id):
            raise ToolError('Connectez-vous et autorisez cet accès dans le chat ou les réglages MCP.')
        validate_arguments(definition, args)
        return wire(getattr(self, name)(args, user_id, token_id))

    def search_activities(self, args, user_id, token_id):
        where = ["e.status='published'", 'e.starts_at>now()+%s',
                 "e.capacity>(SELECT count(*) FROM reservations r WHERE r.event_id=e.id AND r.status='confirmed')"]
        values = [timedelta(minutes=self.cutoff())]
        for key, column in [('query', "concat_ws(' ',e.title,e.description,e.location,c.name)"), ('location', 'e.location'), ('category', 'c.name')]:
            if args.get(key):
                where.append(column + ' ILIKE %s')
                values.append('%'+args[key].replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%')
        if args.get('date_from') and args.get('date_to') and args['date_from'] > args['date_to']:
            raise ToolError('La date de fin précède la date de début.')
        for key, op in [('date_from', '>='), ('date_to', '<')]:
            if args.get(key):
                dt = date.fromisoformat(args[key])
                try:
                    if key == 'date_to': dt += timedelta(days=1)
                except OverflowError: raise ToolError('Date hors limites.') from None
                where.append('e.starts_at'+op+'%s')
                values.append(datetime.combine(dt, time.min, PARIS))
        if 'max_price_cents' in args:
            where.append('e.price_cents<=%s'); values.append(args['max_price_cents'])
        limit, offset = args.get('limit', 10), args.get('offset', 0)
        rows = self.query(EVENT_SQL + ' WHERE ' + ' AND '.join(where) + ' ORDER BY e.starts_at,e.id LIMIT %s OFFSET %s', (*values, limit+1, offset))
        for row in rows: row['url'] = '/activities/' + str(row['id'])
        return {'activities': rows[:limit], 'has_more': len(rows)>limit, 'next_offset': offset+limit if len(rows)>limit else None,
                'timezone': 'Europe/Paris', 'payments': 'simulated'}

    def get_activity(self, args, user_id, token_id):
        return {'activity': self.activity(args['event_id'])}

    def search_faq(self, args, user_id, token_id):
        text = args.get('query', '').replace('%','\\%').replace('_','\\_')
        rows = self.query('''SELECT left(question,300) AS question,left(answer,2000) AS answer FROM faqs WHERE published
             ORDER BY (concat_ws(' ',question,answer) ILIKE %s) DESC,sort_order,id LIMIT 8''', ('%'+text+'%',))
        return {'faqs': rows, 'url': '/faq'}

    def my_bookings(self, args, user_id, token_id):
        period = args.get('period','upcoming')
        condition = {'upcoming': " AND r.status='confirmed' AND e.status='published' AND e.ends_at>now()",
                     'history': " AND (r.status='cancelled' OR e.status='cancelled' OR e.ends_at<=now())", 'all': ''}[period]
        limit, offset = args.get('limit',10), args.get('offset',0)
        rows = self.query('''SELECT r.id AS booking_id,r.status,r.reserved_at,e.id AS event_id,e.title,e.starts_at,e.ends_at,
             e.location,e.price_cents,e.status AS event_status,e.cancellation_policy
             FROM reservations r JOIN events e ON e.id=r.event_id WHERE r.member_id=%s''' + condition +
             ' ORDER BY e.starts_at,r.id LIMIT %s OFFSET %s', (user_id,limit+1,offset))
        for row in rows: row['url'] = '/activities/' + str(row['event_id'])
        return {'bookings': rows[:limit], 'has_more': len(rows)>limit,
                'next_offset': offset+limit if len(rows)>limit else None, 'account_url': '/account'}

    def book_activity(self, args, user_id, token_id):
        event = self.activity(args['event_id'])
        old = self.query("SELECT id FROM reservations WHERE member_id=%s AND event_id=%s AND status='confirmed'", (user_id,event['id']),True)
        if old: return {'status':'already_booked', 'booking_id':old['id'], 'url':'/account'}
        if event['booking_block']: raise ToolError(BLOCK_MESSAGES[event['booking_block']])
        # Reuse equivalent live proposals, so a retry does not create many confirmation links.
        with self.db().transaction():
            self.query('SELECT pg_advisory_xact_lock(249001,%s)',(user_id,),True)
            row = self.query('''SELECT id FROM assistant_booking_requests WHERE user_id=%s AND event_id=%s
                AND token_id IS NOT DISTINCT FROM %s AND snapshot=%s AND expires_at>now() AND reservation_id IS NULL
                ORDER BY created_at DESC LIMIT 1''',(user_id,event['id'],token_id,Jsonb(snapshot(event))),True)
            if not row:
                row = self.query('''INSERT INTO assistant_booking_requests(id,user_id,event_id,token_id,snapshot)
                    VALUES (%s,%s,%s,%s,%s) RETURNING id''',(uuid4(),user_id,event['id'],token_id,Jsonb(snapshot(event))),True)
        return {'status':'awaiting_confirmation', 'request_id':str(row['id']), 'activity':event,
                'confirmation_url':'/assistant/bookings/'+str(row['id']), 'expires_in_minutes':15,
                'message':'Aucune place réservée. Ouvrez le lien, vérifiez les informations et confirmez sur Joinly.'}

    def get_booking_request(self, args, user_id, token_id):
        row = self.query('''SELECT b.id,b.reservation_id,b.expires_at,r.status AS booking_status FROM assistant_booking_requests b
             LEFT JOIN reservations r ON r.id=b.reservation_id WHERE b.id=%s AND b.user_id=%s
             AND b.token_id IS NOT DISTINCT FROM %s''', (UUID(args['request_id']),user_id,token_id),True)
        if not row: raise ToolError('Demande introuvable.')
        status = row['booking_status'] if row['reservation_id'] else ('expired' if row['expires_at']<=datetime.now(timezone.utc) else 'awaiting_confirmation')
        return {'status':status,'request_id':str(row['id']),'booking_id':row['reservation_id'],'url':'/account'}
