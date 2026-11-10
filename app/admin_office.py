"""Extra administration screens. Existing /admin posts stay in the application factory."""
import csv
import io

from flask import abort, flash, g, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash

PAGE = 20


def register_office(app, query, db, text, email_value, money_cents):
    def audit(action, entity_type, entity_id, detail=''):
        actor = g.impersonator['id'] if getattr(g, 'impersonator', None) else (g.user['id'] if g.user else None)
        query(
            'INSERT INTO audit_log(actor_id, action, entity_type, entity_id, detail) VALUES (%s,%s,%s,%s,%s)',
            (actor, action, entity_type, None if entity_id is None else str(entity_id), detail[:2000]),
        )

    def guard():
        if not g.user:
            return redirect(url_for('login'))
        if 'admin' not in g.roles or getattr(g, 'impersonating', False):
            abort(403)
        return None

    def page_no():
        raw = request.args.get('page', '1')
        if not str(raw).isdigit() or not 1 <= int(raw) <= 10000:
            raise ValueError('Page invalide.')
        return int(raw)

    def like(value):
        cleaned = (value or '').strip()[:120].replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        return f'%{cleaned}%'

    def csv_response(filename, header, rows):
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(header)
        writer.writerows(rows)
        return app.response_class('\ufeff' + buffer.getvalue(), mimetype='text/csv; charset=utf-8', headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
        })

    @app.get('/admin/utilisateurs')
    def admin_users():
        blocked = guard()
        if blocked:
            return blocked
        current = page_no()
        term = request.args.get('q', '').strip()
        status = request.args.get('status', '')
        filters, args = ['true'], []
        if term:
            filters.append('(email ILIKE %s ESCAPE %s OR display_name ILIKE %s ESCAPE %s)')
            needle = like(term)
            args.extend([needle, '\\', needle, '\\'])
        if status in ('active', 'suspended', 'banned'):
            filters.append('status=%s')
            args.append(status)
        where = ' AND '.join(filters)
        total = query(f'SELECT count(*) AS n FROM users WHERE {where}', args, True)['n']
        rows = query(
            f'''SELECT id, email, display_name, status, created_at, avatar_path FROM users WHERE {where}
                ORDER BY id DESC LIMIT %s OFFSET %s''',
            (*args, PAGE, (current - 1) * PAGE),
        )
        return render_template('admin_users.html', rows=rows, total=total, page=current, pages=max(1, (total + PAGE - 1) // PAGE))

    @app.get('/admin/utilisateurs.csv')
    def admin_users_csv():
        blocked = guard()
        if blocked:
            return blocked
        rows = query('SELECT id, email, display_name, status FROM users ORDER BY id')
        return csv_response('utilisateurs.csv', ['id', 'email', 'nom', 'statut'], [(r['id'], r['email'], r['display_name'], r['status']) for r in rows])

    @app.post('/admin/utilisateurs/bulk')
    def admin_users_bulk():
        blocked = guard()
        if blocked:
            return blocked
        action = request.form.get('action')
        chosen = [int(value) for value in request.form.getlist('ids') if value.isdigit()]
        if not chosen:
            raise ValueError('Sélectionnez au moins un compte.')
        if action in ('ban', 'delete') and request.form.get('confirm') != '1':
            raise ValueError('Confirmez l’action groupée.')
        for user_id in chosen:
            if user_id == g.user['id']:
                continue
            if action == 'activate':
                query("UPDATE users SET status='active' WHERE id=%s", (user_id,))
            elif action == 'ban':
                query("UPDATE users SET status='banned' WHERE id=%s", (user_id,))
                query('DELETE FROM web_sessions WHERE user_id=%s', (user_id,))
            elif action == 'delete':
                query('DELETE FROM reservations WHERE member_id=%s OR event_id IN (SELECT id FROM events WHERE organizer_id=%s)', (user_id, user_id))
                query('DELETE FROM events WHERE organizer_id=%s', (user_id,))
                query('DELETE FROM users WHERE id=%s', (user_id,))
            else:
                raise ValueError('Action inconnue.')
        audit('users.bulk', 'user', ','.join(map(str, chosen)), action or '')
        flash('Action groupée enregistrée.', 'success')
        return redirect(url_for('admin_users'))

    @app.get('/admin/utilisateurs/<int:user_id>')
    def admin_user_detail(user_id):
        blocked = guard()
        if blocked:
            return blocked
        person = query('SELECT * FROM users WHERE id=%s', (user_id,), True)
        if not person:
            abort(404)
        person['roles'] = [row['name'] for row in query('SELECT r.name FROM roles r JOIN user_roles ur ON ur.role_id=r.id WHERE ur.user_id=%s', (user_id,))]
        return render_template(
            'admin_user.html', person=person,
            reservations=query('SELECT r.*, e.title FROM reservations r JOIN events e ON e.id=r.event_id WHERE r.member_id=%s ORDER BY r.reserved_at DESC LIMIT 30', (user_id,)),
            reviews=query('SELECT rv.*, e.title FROM reviews rv JOIN events e ON e.id=rv.event_id WHERE rv.author_id=%s ORDER BY rv.created_at DESC', (user_id,)),
            favorites=query('SELECT e.id, e.title FROM favorites f JOIN events e ON e.id=f.event_id WHERE f.user_id=%s', (user_id,)),
            follows=query('SELECT u.id, u.display_name FROM organizer_follows f JOIN users u ON u.id=f.organizer_id WHERE f.follower_id=%s', (user_id,)),
            interests=query('SELECT c.name FROM user_interests ui JOIN categories c ON c.id=ui.category_id WHERE ui.user_id=%s ORDER BY c.name', (user_id,)),
            history=query("SELECT * FROM audit_log WHERE actor_id=%s OR (entity_type='user' AND entity_id=%s) ORDER BY created_at DESC LIMIT 20", (user_id, str(user_id))),
            categories=query('SELECT id, name, icon FROM categories ORDER BY name'),
            selected={row['category_id'] for row in query('SELECT category_id FROM user_interests WHERE user_id=%s', (user_id,))},
        )

    @app.post('/admin/utilisateurs/<int:user_id>/fiche')
    def admin_user_save(user_id):
        blocked = guard()
        if blocked:
            return blocked
        name = text('display_name', 100)
        email = email_value()
        status = request.form.get('status', 'active')
        if status not in ('active', 'suspended', 'banned'):
            abort(400)
        roles = set(request.form.getlist('roles'))
        if not roles <= {'member', 'organizer', 'admin'}:
            abort(400)
        interests = [int(value) for value in request.form.getlist('interest_ids') if value.isdigit()]
        query('UPDATE users SET display_name=%s, email=%s, status=%s WHERE id=%s', (name, email, status, user_id))
        query('DELETE FROM user_roles WHERE user_id=%s', (user_id,))
        query('INSERT INTO user_roles(user_id, role_id) SELECT %s, id FROM roles WHERE name=ANY(%s)', (user_id, list(roles | {'member'})))
        query('DELETE FROM user_interests WHERE user_id=%s', (user_id,))
        if interests:
            query('INSERT INTO user_interests(user_id, category_id) SELECT %s, id FROM categories WHERE id = ANY(%s)', (user_id, interests))
        audit('user.update', 'user', user_id, email)
        flash('Compte mis à jour.', 'success')
        return redirect(url_for('admin_user_detail', user_id=user_id))

    @app.post('/admin/utilisateurs/<int:user_id>/mot-de-passe')
    def admin_user_password(user_id):
        blocked = guard()
        if blocked:
            return blocked
        if request.form.get('confirm') != '1':
            raise ValueError('Confirmez la réinitialisation.')
        password = request.form.get('password', '')
        if not 12 <= len(password) <= 128:
            raise ValueError('Le mot de passe doit contenir entre 12 et 128 caractères.')
        query('UPDATE users SET password_hash=%s WHERE id=%s', (generate_password_hash(password), user_id))
        query('DELETE FROM web_sessions WHERE user_id=%s', (user_id,))
        audit('user.password', 'user', user_id, 'Mot de passe réinitialisé')
        flash('Mot de passe réinitialisé.', 'success')
        return redirect(url_for('admin_user_detail', user_id=user_id))

    @app.post('/admin/utilisateurs/<int:user_id>/consulter')
    def admin_impersonate(user_id):
        blocked = guard()
        if blocked:
            return blocked
        from flask import session
        target = query("SELECT id, display_name, status FROM users WHERE id=%s", (user_id,), True)
        if not target or target['status'] != 'active' or target['id'] == g.user['id']:
            raise ValueError('Ce compte ne peut pas être consulté.')
        session['view_as'] = int(target['id'])
        audit('impersonate.start', 'user', target['id'], f'Consultation en tant que {target["display_name"]}')
        return redirect(url_for('home'))

    @app.post('/impersonation/stop')
    def stop_impersonation():
        from flask import session
        if not session.get('view_as'):
            return redirect(url_for('home'))
        target = g.user['id'] if g.user else None
        session.pop('view_as', None)
        if getattr(g, 'impersonator', None):
            audit('impersonate.stop', 'user', target, 'Fin de consultation')
        return redirect(url_for('admin'))

    @app.get('/admin/activites')
    def admin_events():
        blocked = guard()
        if blocked:
            return blocked
        term = request.args.get('q', '').strip()
        filters, args = ['true'], []
        if term:
            filters.append('e.title ILIKE %s ESCAPE %s')
            args.extend([like(term), '\\'])
        where = ' AND '.join(filters)
        rows = query(
            f'''SELECT e.id, e.title, e.status, e.starts_at, u.display_name AS organizer
                FROM events e JOIN users u ON u.id=e.organizer_id WHERE {where} ORDER BY e.id DESC LIMIT 50''',
            args,
        )
        return render_template('admin_events.html', rows=rows)

    @app.get('/admin/activites.csv')
    def admin_events_csv():
        blocked = guard()
        if blocked:
            return blocked
        rows = query('SELECT e.id, e.title, e.status, e.price_cents, u.display_name FROM events e JOIN users u ON u.id=e.organizer_id ORDER BY e.id')
        return csv_response('activites.csv', ['id', 'titre', 'statut', 'prix', 'organisateur'], [(r['id'], r['title'], r['status'], r['price_cents'], r['display_name']) for r in rows])

    @app.route('/admin/activites/<int:event_id>', methods=['GET', 'POST'])
    def admin_event_office(event_id):
        blocked = guard()
        if blocked:
            return blocked
        event = query('SELECT * FROM events WHERE id=%s', (event_id,), True)
        if not event:
            abort(404)
        if request.method == 'POST':
            title = text('title', 180)
            query(
                '''UPDATE events SET title=%s, description=%s, location=%s, city=%s, capacity=%s, price_cents=%s,
                   status=%s, cancellation_policy=%s, pinned=%s WHERE id=%s''',
                (
                    title, text('description', 10000), text('location', 200), request.form.get('city', '')[:80],
                    int(text('capacity')), money_cents(), request.form.get('status') if request.form.get('status') in ('draft', 'published', 'cancelled') else event['status'],
                    request.form.get('cancellation_policy') if request.form.get('cancellation_policy') in ('flexible', 'moderate', 'strict') else event['cancellation_policy'],
                    'pinned' in request.form, event_id,
                ),
            )
            audit('event.update', 'event', event_id, title)
            flash('Activité mise à jour.', 'success')
            return redirect(url_for('admin_event_office', event_id=event_id))
        people = query(
            '''SELECT u.display_name, r.status, t.code, t.checked_in_at FROM reservations r
               JOIN users u ON u.id=r.member_id LEFT JOIN tickets t ON t.reservation_id=r.id
               WHERE r.event_id=%s ORDER BY r.reserved_at''',
            (event_id,),
        )
        reviews = query('SELECT rv.*, u.display_name FROM reviews rv JOIN users u ON u.id=rv.author_id WHERE rv.event_id=%s', (event_id,))
        return render_template('admin_event.html', event=event, people=people, reviews=reviews)

    @app.get('/admin/activites/<int:event_id>/participants.csv')
    def admin_attendees_csv(event_id):
        blocked = guard()
        if blocked:
            return blocked
        rows = query(
            '''SELECT u.display_name, u.email, r.status, t.code FROM reservations r
               JOIN users u ON u.id=r.member_id LEFT JOIN tickets t ON t.reservation_id=r.id WHERE r.event_id=%s''',
            (event_id,),
        )
        return csv_response(f'participants-{event_id}.csv', ['nom', 'email', 'statut', 'billet'], [(r['display_name'], r['email'], r['status'], r['code']) for r in rows])

    @app.get('/admin/reservations')
    def admin_reservations():
        blocked = guard()
        if blocked:
            return blocked
        rows = query(
            '''SELECT r.*, u.display_name, u.email, e.title FROM reservations r
               JOIN users u ON u.id=r.member_id JOIN events e ON e.id=r.event_id
               ORDER BY r.reserved_at DESC LIMIT 50'''
        )
        return render_template('admin_reservations.html', rows=rows, events=query("SELECT id, title FROM events WHERE status='published' ORDER BY starts_at LIMIT 100"))

    @app.get('/admin/reservations.csv')
    def admin_reservations_csv():
        blocked = guard()
        if blocked:
            return blocked
        rows = query(
            '''SELECT r.id, u.email, e.title, r.status, r.refund_cents FROM reservations r
               JOIN users u ON u.id=r.member_id JOIN events e ON e.id=r.event_id ORDER BY r.id'''
        )
        return csv_response('reservations.csv', ['id', 'email', 'activite', 'statut', 'remboursement'], [(r['id'], r['email'], r['title'], r['status'], r['refund_cents']) for r in rows])

    @app.post('/admin/avis/<int:review_id>/texte')
    def admin_review_text(review_id):
        blocked = guard()
        if blocked:
            return blocked
        try:
            rating = int(request.form.get('rating', ''))
        except ValueError:
            rating = 0
        comment = request.form.get('comment', '').strip()
        if rating not in range(1, 6) or not 1 <= len(comment) <= 2000:
            raise ValueError('Note ou commentaire invalide.')
        query('UPDATE reviews SET rating=%s, comment=%s, hidden=%s WHERE id=%s', (rating, comment, 'hidden' in request.form, review_id))
        audit('review.update', 'review', review_id, comment[:80])
        flash('Avis modifié.', 'success')
        return redirect(url_for('admin') + '#avis')

    @app.get('/admin/avis.csv')
    def admin_reviews_csv():
        blocked = guard()
        if blocked:
            return blocked
        rows = query('SELECT rv.id, e.title, u.display_name, rv.rating, rv.comment, rv.hidden FROM reviews rv JOIN events e ON e.id=rv.event_id JOIN users u ON u.id=rv.author_id')
        return csv_response('avis.csv', ['id', 'activite', 'auteur', 'note', 'commentaire', 'masque'], [(r['id'], r['title'], r['display_name'], r['rating'], r['comment'], r['hidden']) for r in rows])

    @app.route('/admin/categories', methods=['GET', 'POST'])
    def admin_categories():
        blocked = guard()
        if blocked:
            return blocked
        if request.method == 'POST':
            name = text('name', 80)
            icon = text('icon', 16)
            if request.form.get('id', '').isdigit():
                query('UPDATE categories SET name=%s, icon=%s WHERE id=%s', (name, icon, int(request.form['id'])))
            else:
                query('INSERT INTO categories(name, icon) VALUES (%s, %s)', (name, icon))
            audit('category.save', 'category', name, icon)
            flash('Catégorie enregistrée.', 'success')
            return redirect(url_for('admin_categories'))
        return render_template('admin_categories.html', rows=query('SELECT * FROM categories ORDER BY name'))

    @app.route('/admin/notifications', methods=['GET', 'POST'])
    def admin_broadcast():
        blocked = guard()
        if blocked:
            return blocked
        if request.method == 'POST':
            title = text('title', 180)
            body = text('body', 2000)
            segment = request.form.get('segment', 'all')
            where = {
                'all': 'true',
                'organizers': "id IN (SELECT user_id FROM user_roles ur JOIN roles r ON r.id=ur.role_id WHERE r.name='organizer')",
                'unverified': 'email_verified_at IS NULL',
            }.get(segment, 'true')
            for person in query(f'SELECT id FROM users WHERE {where}'):
                query(
                    '''INSERT INTO notifications(user_id, kind, title, body, link) VALUES (%s, 'broadcast', %s, %s, '/notifications')''',
                    (person['id'], title, body),
                )
            audit('broadcast', 'notification', segment, title)
            flash('Message envoyé.', 'success')
            return redirect(url_for('admin_broadcast'))
        return render_template('admin_broadcast.html')

    @app.get('/admin/journal')
    def admin_audit():
        blocked = guard()
        if blocked:
            return blocked
        rows = query(
            '''SELECT a.*, u.display_name FROM audit_log a LEFT JOIN users u ON u.id=a.actor_id
               ORDER BY a.created_at DESC LIMIT 80'''
        )
        return render_template('admin_audit.html', rows=rows)

    @app.route('/admin/reglages', methods=['GET', 'POST'])
    def admin_settings():
        blocked = guard()
        if blocked:
            return blocked
        if request.method == 'POST':
            query(
                '''UPDATE site_settings SET site_name=%s, banner=%s, booking_cutoff_minutes=%s,
                   default_cancellation_policy=%s, heat_recent_weight=%s, heat_fill_weight=%s, heat_view_cap=%s
                   WHERE id=1''',
                (
                    text('site_name', 80), request.form.get('banner', '')[:280], int(request.form.get('booking_cutoff_minutes') or 0),
                    request.form.get('default_cancellation_policy') if request.form.get('default_cancellation_policy') in ('flexible', 'moderate', 'strict') else 'flexible',
                    int(request.form.get('heat_recent_weight') or 10), int(request.form.get('heat_fill_weight') or 1),
                    int(request.form.get('heat_view_cap') or 400),
                ),
            )
            listed = [int(v) for v in request.form.getlist('listed_ids') if v.isdigit()]
            pinned = {int(v) for v in request.form.getlist('pinned_ids') if v.isdigit()}
            for event_id in listed:
                query('UPDATE events SET pinned=%s WHERE id=%s', (event_id in pinned, event_id))
            audit('settings.update', 'settings', 1, request.form.get('banner', '')[:80])
            flash('Réglages enregistrés.', 'success')
            return redirect(url_for('admin_settings'))
        return render_template(
            'admin_settings.html', settings=query('SELECT * FROM site_settings WHERE id=1', one=True),
            featured=query("SELECT id, title, pinned FROM events WHERE status='published' AND ends_at>now() ORDER BY pinned DESC, starts_at LIMIT 30"),
        )

    @app.get('/admin/demandes')
    def admin_requests():
        blocked = guard()
        if blocked:
            return blocked
        rows = query('SELECT q.*, u.display_name, u.email FROM organizer_requests q JOIN users u ON u.id=q.user_id ORDER BY q.created_at DESC')
        return render_template('admin_requests.html', rows=rows)

    @app.post('/admin/demandes/<int:user_id>')
    def admin_request_decide(user_id):
        blocked = guard()
        if blocked:
            return blocked
        decision = request.form.get('decision')
        if decision == 'approved':
            query("INSERT INTO user_roles(user_id, role_id) SELECT %s, id FROM roles WHERE name='organizer' ON CONFLICT DO NOTHING", (user_id,))
        query('UPDATE organizer_requests SET status=%s WHERE user_id=%s', (decision, user_id))
        audit('organizer.request', 'user', user_id, decision or '')
        flash('Demande traitée.', 'success')
        return redirect(url_for('admin_requests'))

    @app.post('/account/demande-organisateur')
    def request_organizer():
        if not g.user:
            return redirect(url_for('login'))
        if 'organizer' in g.roles:
            raise ValueError('Vous êtes déjà organisateur.')
        query(
            '''INSERT INTO organizer_requests(user_id, message, status) VALUES (%s, %s, 'pending')
               ON CONFLICT (user_id) DO UPDATE SET message=EXCLUDED.message, status='pending' ''',
            (g.user['id'], request.form.get('message', '')[:500]),
        )
        flash('Demande envoyée.', 'success')
        return redirect(url_for('account'))
