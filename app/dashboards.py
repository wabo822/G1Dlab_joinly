"""Organizer and admin dashboard queries."""
from app.charts import bar_chart, donut_chart, line_chart, stacked_bar

PERIODS = {'7': 7, '30': 30, '90': 90}


def period_days(args):
    return PERIODS.get((args.get('periode') or '30').strip(), 30)


def organizer_payload(query, owner_id, days):
    stats = query(
        '''SELECT
              (SELECT count(*) FROM events e WHERE e.organizer_id=%s) AS activities,
              (SELECT count(*) FROM events e WHERE e.organizer_id=%s AND e.status='published' AND e.ends_at>now()) AS upcoming,
              (SELECT count(*) FROM events e WHERE e.organizer_id=%s AND e.ends_at<=now()) AS past,
              (SELECT count(*) FROM reservations r JOIN events e ON e.id=r.event_id
                WHERE e.organizer_id=%s AND r.status='confirmed') AS reservations,
              COALESCE((SELECT SUM(e.view_count) FROM events e WHERE e.organizer_id=%s),0) AS views,
              COALESCE((SELECT SUM(e.capacity) FROM events e WHERE e.organizer_id=%s AND e.status<>'cancelled'),0) AS capacity,
              COALESCE((SELECT SUM((SELECT count(*) FROM reservations r WHERE r.event_id=e.id AND r.status='confirmed'))
                FROM events e WHERE e.organizer_id=%s AND e.status<>'cancelled'),0) AS filled,
              COALESCE((SELECT SUM(e.price_cents * (SELECT count(*) FROM reservations r WHERE r.event_id=e.id AND r.status='confirmed'))
                FROM events e WHERE e.organizer_id=%s),0) AS gross,
              COALESCE((SELECT SUM(r.refund_cents) FROM reservations r JOIN events e ON e.id=r.event_id
                WHERE e.organizer_id=%s),0) AS refunds,
              (SELECT count(*) FROM organizer_follows f WHERE f.organizer_id=%s) AS followers,
              (SELECT count(*) FROM favorites f JOIN events e ON e.id=f.event_id WHERE e.organizer_id=%s) AS favorites
           ''',
        (owner_id,) * 11,
        True,
    )
    rating = query(
        '''SELECT round(avg(rv.rating)::numeric, 1) AS avg, count(*) AS n
           FROM reviews rv JOIN events e ON e.id=rv.event_id
           WHERE e.organizer_id=%s AND NOT rv.hidden''',
        (owner_id,), True,
    )
    checkins = query(
        '''SELECT count(*) FILTER (WHERE r.status='confirmed') AS confirmed,
                  count(*) FILTER (WHERE r.status='confirmed' AND t.checked_in_at IS NOT NULL) AS checked
           FROM reservations r
           JOIN events e ON e.id=r.event_id
           LEFT JOIN tickets t ON t.reservation_id=r.id
           WHERE e.organizer_id=%s AND e.starts_at<=now()''',
        (owner_id,), True,
    )
    series = query(
        '''SELECT to_char(d::date, 'DD/MM') AS label,
                  (SELECT count(*) FROM reservations r JOIN events e ON e.id=r.event_id
                    WHERE e.organizer_id=%s AND r.status='confirmed'
                      AND (r.reserved_at AT TIME ZONE 'Europe/Paris')::date = d::date) AS n
           FROM generate_series(current_date - (%s::int - 1), current_date, interval '1 day') AS d''',
        (owner_id, days),
    )
    fills = query(
        '''SELECT e.title,
                  (SELECT count(*) FROM reservations r WHERE r.event_id=e.id AND r.status='confirmed') AS booked,
                  e.capacity
           FROM events e WHERE e.organizer_id=%s AND e.status<>'cancelled'
           ORDER BY e.starts_at DESC LIMIT 8''',
        (owner_id,),
    )
    categories = query(
        '''SELECT COALESCE(c.name, 'Sans catégorie') AS name, count(*) AS n
           FROM events e LEFT JOIN categories c ON c.id=e.category_id
           WHERE e.organizer_id=%s GROUP BY 1 ORDER BY n DESC, name''',
        (owner_id,),
    )
    attendance = query(
        '''SELECT to_char((e.starts_at AT TIME ZONE 'Europe/Paris')::date, 'DD/MM') AS label,
                  count(*) FILTER (WHERE t.checked_in_at IS NOT NULL) AS checked,
                  count(*) FILTER (WHERE t.checked_in_at IS NULL) AS missing
           FROM reservations r
           JOIN events e ON e.id=r.event_id
           LEFT JOIN tickets t ON t.reservation_id=r.id
           WHERE e.organizer_id=%s AND r.status='confirmed' AND e.starts_at<=now()
             AND e.starts_at > now() - make_interval(days => %s)
           GROUP BY 1, e.starts_at
           ORDER BY e.starts_at''',
        (owner_id, days),
    )
    top = query(
        '''SELECT e.id, e.title, e.view_count,
                  (SELECT count(*) FROM reservations r WHERE r.event_id=e.id AND r.status='confirmed') AS booked,
                  e.capacity
           FROM events e WHERE e.organizer_id=%s
           ORDER BY booked DESC, e.view_count DESC LIMIT 6''',
        (owner_id,),
    )
    recent = query(
        '''SELECT r.id, r.reserved_at, u.display_name, e.title, e.id AS event_id
           FROM reservations r
           JOIN users u ON u.id=r.member_id
           JOIN events e ON e.id=r.event_id
           WHERE e.organizer_id=%s AND r.status='confirmed'
           ORDER BY r.reserved_at DESC LIMIT 8''',
        (owner_id,),
    )
    reviews = query(
        '''SELECT rv.rating, rv.comment, rv.created_at, u.display_name, e.title, e.id AS event_id
           FROM reviews rv
           JOIN users u ON u.id=rv.author_id
           JOIN events e ON e.id=rv.event_id
           WHERE e.organizer_id=%s AND NOT rv.hidden
           ORDER BY rv.created_at DESC LIMIT 6''',
        (owner_id,),
    )
    upcoming = query(
        '''SELECT e.id, e.title, e.starts_at, e.location, e.capacity,
                  (SELECT count(*) FROM reservations r WHERE r.event_id=e.id AND r.status='confirmed') AS booked
           FROM events e
           WHERE e.organizer_id=%s AND e.status='published' AND e.ends_at>now()
           ORDER BY e.starts_at LIMIT 8''',
        (owner_id,),
    )
    capacity = int(stats['capacity'] or 0)
    filled = int(stats['filled'] or 0)
    confirmed = int(checkins['confirmed'] or 0)
    checked = int(checkins['checked'] or 0)
    return {
        'stats': stats,
        'rating': rating,
        'fill_rate': round(100 * filled / capacity) if capacity else 0,
        'checkin_rate': round(100 * checked / confirmed) if confirmed else 0,
        'net': int(stats['gross'] or 0) - int(stats['refunds'] or 0),
        'chart': line_chart([row['n'] for row in series] or [0], [row['label'] for row in series] or ['—']),
        'fill_chart': bar_chart(
            [round(100 * row['booked'] / row['capacity']) if row['capacity'] else 0 for row in fills] or [0],
            [row['title'] for row in fills] or ['—'],
            color='#7046e8', suffix=' %',
        ),
        'category_chart': donut_chart(
            [row['n'] for row in categories] or [0],
            [row['name'] for row in categories] or ['—'],
        ),
        'attendance_chart': stacked_bar(
            [row['checked'] for row in attendance] or [0],
            [row['missing'] for row in attendance] or [0],
            [row['label'] for row in attendance] or ['—'],
        ),
        'top': top,
        'recent': recent,
        'reviews': reviews,
        'upcoming': upcoming,
        'days': days,
    }


def admin_payload(query, days):
    kpis = query(
        '''SELECT
            (SELECT count(*) FROM users) AS users,
            (SELECT count(*) FROM users WHERE created_at > now() - make_interval(days => %s)) AS new_signups,
            (SELECT count(*) FROM users WHERE email_verified_at IS NOT NULL) AS verified,
            (SELECT count(*) FROM events WHERE status='published' AND ends_at>now()) AS active_events,
            (SELECT count(*) FROM events) AS events,
            (SELECT count(*) FROM reservations WHERE status='confirmed') AS reservations,
            (SELECT COALESCE(SUM(price_cents),0) FROM (
                SELECT e.price_cents * (SELECT count(*) FROM reservations r WHERE r.event_id=e.id AND r.status='confirmed') AS price_cents FROM events e
            ) s) AS revenue,
            (SELECT round(avg(rating)::numeric,1) FROM reviews WHERE NOT hidden) AS rating,
            (SELECT count(*) FROM contact_requests WHERE NOT resolved) AS pending,
            (SELECT count(*) FROM notifications WHERE created_at > now() - make_interval(days => %s)) AS notifications
        ''',
        (days, days), True,
    )
    users_total = int(kpis['users'] or 0)
    kpis = dict(kpis)
    kpis['verified_pct'] = round(100 * int(kpis['verified'] or 0) / users_total) if users_total else 0
    growth = query(
        '''SELECT to_char(d::date, 'DD/MM') AS label,
                  (SELECT count(*) FROM users u WHERE u.created_at::date = d::date) AS n
           FROM generate_series(current_date - (%s::int - 1), current_date, interval '1 day') AS d''',
        (days,),
    )
    reservations = query(
        '''SELECT to_char(d::date, 'DD/MM') AS label,
                  (SELECT count(*) FROM reservations r
                    WHERE r.status='confirmed' AND (r.reserved_at AT TIME ZONE 'Europe/Paris')::date = d::date) AS n
           FROM generate_series(current_date - (%s::int - 1), current_date, interval '1 day') AS d''',
        (days,),
    )
    by_category = query(
        '''SELECT COALESCE(c.name, 'Sans catégorie') AS name, count(*) AS n
           FROM events e LEFT JOIN categories c ON c.id=e.category_id
           GROUP BY 1 ORDER BY n DESC, name'''
    )
    by_status = query(
        '''SELECT status, count(*) AS n FROM events GROUP BY 1 ORDER BY n DESC'''
    )
    status_labels = {'published': 'Publié', 'draft': 'Brouillon', 'cancelled': 'Annulé'}
    top_organizers = query(
        '''SELECT u.id, u.display_name, count(e.id) AS events,
                  (SELECT count(*) FROM reservations r JOIN events ev ON ev.id=r.event_id
                    WHERE ev.organizer_id=u.id AND r.status='confirmed') AS bookings
           FROM users u
           JOIN events e ON e.organizer_id=u.id
           GROUP BY u.id, u.display_name
           ORDER BY bookings DESC, events DESC LIMIT 6'''
    )
    top_activities = query(
        '''SELECT e.id, e.title, e.view_count,
                  (SELECT count(*) FROM reservations r WHERE r.event_id=e.id AND r.status='confirmed') AS booked
           FROM events e ORDER BY booked DESC, e.view_count DESC LIMIT 6'''
    )
    feed = query(
        '''SELECT * FROM (
             SELECT r.reserved_at AS at, 'reservation' AS kind, u.display_name, e.title
             FROM reservations r JOIN users u ON u.id=r.member_id JOIN events e ON e.id=r.event_id
             WHERE r.status='confirmed'
             UNION ALL
             SELECT u.created_at, 'signup', u.display_name, NULL
             FROM users u
             UNION ALL
             SELECT rv.created_at, 'review', u.display_name, e.title
             FROM reviews rv JOIN users u ON u.id=rv.author_id JOIN events e ON e.id=rv.event_id
             WHERE NOT rv.hidden
           ) s ORDER BY at DESC LIMIT 12'''
    )
    return {
        'kpis': kpis,
        'signup_chart': line_chart([row['n'] for row in growth] or [0], [row['label'] for row in growth] or ['—']),
        'reservation_chart': line_chart(
            [row['n'] for row in reservations] or [0],
            [row['label'] for row in reservations] or ['—'],
            color='#1f7a4d',
        ),
        'category_chart': donut_chart(
            [row['n'] for row in by_category] or [0],
            [row['name'] for row in by_category] or ['—'],
        ),
        'status_chart': bar_chart(
            [row['n'] for row in by_status] or [0],
            [status_labels.get(row['status'], row['status']) for row in by_status] or ['—'],
            color='#c44b7a',
        ),
        'top_organizers': top_organizers,
        'top_activities': top_activities,
        'feed': feed,
        'days': days,
    }
