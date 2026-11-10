"""Idempotent demonstration data for a lived-in Joinly catalogue.

Passwords, display names and roles of existing accounts are left unchanged.
Nothing is deleted. Interests of the demonstration accounts and prices of the
demonstration activities are refreshed, so a database that already received
the seed picks up icons, interests, tariffs and the city derived from the
meeting place. Running the command twice
does not create duplicates.
"""
import hashlib
from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash
from zoneinfo import ZoneInfo

from app.legal_content import ensure_faqs, publish_legal_defaults

PARIS = ZoneInfo('Europe/Paris')
DEMO_DOMAIN = 'demo.joinly.fr'
DEMO_PASSWORDS = {
    'admin': 'Joinly-Admin-2026!',
    'organizer': 'Joinly-Orga-2026!',
    'member': 'Joinly-Membre-2026!',
}
DEMO_NOTE = (
    'Cette fiche est un exemple de démonstration du projet étudiant Joinly : '
    'aucun rendez-vous réel n’est organisé à cette adresse.'
)

# Keep icons aligned with database/migrations/004_interests_pricing.sql.
CATEGORIES = (
    ('Nature & plein air', '🌿'),
    ('Sport', '🏃'),
    ('Arts & culture', '🎨'),
    ('Jeux & rencontres', '🎲'),
    ('Cuisine', '🍳'),
    ('Musique', '🎵'),
    ('Photo & vidéo', '📸'),
    ('Bien-être', '🫧'),
    ('Langues & échanges', '💬'),
    ('Bénévolat', '🤝'),
    ('Football', '⚽'),
    ('Pique-nique', '🧺'),
    ('Randonnée', '🥾'),
    ('Lecture', '📚'),
    ('Jeux vidéo', '🎮'),
    ('Yoga', '🧘'),
    ('Tech', '💻'),
    ('Théâtre', '🎭'),
)

ORGANIZERS = (
    ('lea.moreau@demo.joinly.fr', 'Léa Moreau'),
    ('hugo.bernard@demo.joinly.fr', 'Hugo Bernard'),
    ('ines.benali@demo.joinly.fr', 'Inès Benali'),
    ('thomas.nguyen@demo.joinly.fr', 'Thomas Nguyen'),
    ('chloe.martin@demo.joinly.fr', 'Chloé Martin'),
)
ADMIN = ('admin.demo@demo.joinly.fr', 'Camille Laurent')
MEMBERS = (
    ('marie.dupont@demo.joinly.fr', 'Marie Dupont'),
    ('lucas.petit@demo.joinly.fr', 'Lucas Petit'),
    ('emma.rousseau@demo.joinly.fr', 'Emma Rousseau'),
    ('nathan.leroy@demo.joinly.fr', 'Nathan Leroy'),
    ('sofia.rossi@demo.joinly.fr', 'Sofia Rossi'),
    ('adam.diallo@demo.joinly.fr', 'Adam Diallo'),
    ('yanis.cohen@demo.joinly.fr', 'Yanis Cohen'),
    ('manon.laurent@demo.joinly.fr', 'Manon Laurent'),
    ('julien.morel@demo.joinly.fr', 'Julien Morel'),
    ('aicha.traore@demo.joinly.fr', 'Aïcha Traoré'),
    ('paul.girard@demo.joinly.fr', 'Paul Girard'),
    ('elena.popescu@demo.joinly.fr', 'Elena Popescu'),
    ('mehdi.amrani@demo.joinly.fr', 'Mehdi Amrani'),
    ('clara.fontaine@demo.joinly.fr', 'Clara Fontaine'),
    ('oscar.silva@demo.joinly.fr', 'Oscar Silva'),
    ('jeanne.blanc@demo.joinly.fr', 'Jeanne Blanc'),
    ('karim.haddad@demo.joinly.fr', 'Karim Haddad'),
    ('alice.chen@demo.joinly.fr', 'Alice Chen'),
    ('baptiste.roux@demo.joinly.fr', 'Baptiste Roux'),
    ('nina.kowalski@demo.joinly.fr', 'Nina Kowalski'),
    ('lina.becker@demo.joinly.fr', 'Lina Becker'),
    ('antoine.mercier@demo.joinly.fr', 'Antoine Mercier'),
    ('sarah.cohen@demo.joinly.fr', 'Sarah Cohen'),
    ('malik.kone@demo.joinly.fr', 'Malik Koné'),
    ('camille.dubois@demo.joinly.fr', 'Camille Dubois'),
    ('zoe.lambert@demo.joinly.fr', 'Zoé Lambert'),
    ('victor.alvarez@demo.joinly.fr', 'Victor Alvarez'),
    ('fatou.ndiaye@demo.joinly.fr', 'Fatou Ndiaye'),
    ('louis.marchand@demo.joinly.fr', 'Louis Marchand'),
    ('amelie.petit@demo.joinly.fr', 'Amélie Petit'),
    ('ibrahim.kone@demo.joinly.fr', 'Ibrahim Koné'),
    ('julie.renard@demo.joinly.fr', 'Julie Renard'),
    ('hanae.elfassi@demo.joinly.fr', 'Hanae El Fassi'),
    ('pierre.colin@demo.joinly.fr', 'Pierre Colin'),
)

INTEREST_SETS = (
    ('Nature & plein air', 'Photo & vidéo', 'Randonnée'),
    ('Cuisine', 'Jeux & rencontres', 'Pique-nique'),
    ('Arts & culture', 'Lecture', 'Théâtre'),
    ('Sport', 'Football', 'Bien-être'),
    ('Musique', 'Arts & culture', 'Jeux vidéo'),
    ('Langues & échanges', 'Cuisine', 'Tech'),
    ('Bien-être', 'Yoga', 'Nature & plein air'),
    ('Bénévolat', 'Pique-nique', 'Lecture'),
    ('Tech', 'Jeux vidéo', 'Photo & vidéo'),
    ('Théâtre', 'Musique', 'Football'),
)
# Euro cents. Missing titles stay free. Re-applied on every seed run.
PAID_PRICES = {
    'Aquarelle au square': 1800,
    'Tartes de saison': 2800,
    'Escalade loisir, première fois': 1500,
    'Sushis végétariens': 3200,
    'Initiation au bridge': 1200,
    'Découverte du ukulélé': 2000,
    'Yoga au parc': 800,
    'Escape game de salon': 1600,
    'Choux et éclairs': 3500,
    'Badminton loisir': 600,
}
AREAS = (
    'Paris',
    'Boulogne-Billancourt',
    'Issy-les-Moulineaux',
    'Vincennes',
    'Montreuil',
    'Versailles',
    'Saint-Denis',
    'Nanterre',
    'Créteil',
    'Neuilly-sur-Seine',
)

PRACTICAL = {
    'Nature & plein air': 'Prévoir des chaussures confortables et un peu d’eau. Le rythme reste modéré et le groupe s’attend au point de rendez-vous.',
    'Sport': 'Une tenue souple suffit. Le niveau annoncé est loisir : l’échauffement est inclus et personne n’est mis à l’écart.',
    'Arts & culture': 'Le matériel de base est mis en commun. Aucune expérience préalable n’est demandée.',
    'Jeux & rencontres': 'Les règles sont expliquées au début. Venir seul ou accompagné ne change rien : les tables sont mélangées.',
    'Cuisine': 'Les ingrédients sont prévus pour le groupe. Signaler une allergie à l’organisateur avant le jour J.',
    'Musique': 'Les instruments en trop petit nombre sont prêtés sur place. Débutants et personnes qui reprennent sont les bienvenus.',
    'Photo & vidéo': 'Un téléphone suffit. Quelques conseils de cadrage sont donnés en marchant, sans cours magistral.',
    'Bien-être': 'Apporter un tapis si vous en avez un. La séance peut être suivie sans expérience et sans performance à atteindre.',
    'Langues & échanges': 'Chacun parle à son niveau. L’idée est de pratiquer, pas de corriger chaque phrase.',
    'Bénévolat': 'Des gants sont disponibles. L’activité est bénévole et ne demande pas de compétence particulière.',
}

# title, category, location, day offset, hour, minute, duration minutes, capacity, status, pitch
ACTIVITIES = (
    ('Balade commentée au Luxembourg', 'Nature & plein air', 'Paris 5e · Jardin du Luxembourg, grille Médicis', 3, 10, 30, 120, 18, 'published', 'Une boucle à voix basse entre les allées et le verger, pour repérer les essences et laisser de la place aux conversations.'),
    ('Footing en petit groupe à Bercy', 'Sport', 'Paris 12e · Parc de Bercy, entrée rue de Bercy', 4, 9, 0, 60, 16, 'published', 'Quarante minutes à allure conversation, avec un tour de mise en route pour celles et ceux qui reprennent.'),
    ('Aquarelle au square', 'Arts & culture', 'Paris 6e · Square des Missions-Étrangères', 6, 14, 0, 150, 10, 'published', 'On peint ce qui est devant soi : une façade, un banc, un arbre. Le papier et les godets sont partagés.'),
    ('Grande soirée jeux', 'Jeux & rencontres', 'Paris 11e · Salle associative, rue de la Roquette', 5, 19, 0, 180, 14, 'published', 'Trois tables tournent entre jeux courts et parties plus longues. Les règles sont rappelées à chaque changement.'),
    ('Tartes de saison', 'Cuisine', 'Montreuil · Cuisine partagée, rue de Paris', 8, 11, 0, 180, 8, 'published', 'Pâte, garniture et cuisson : chacun repart avec une part et la méthode, sans chercher la pièce montée.'),
    ('Chorale ouverte', 'Musique', 'Vincennes · Salle municipale, avenue de Paris', 9, 18, 30, 120, 22, 'published', 'Deux voix, des partitions projetées et un morceau simple répété dans l’après-midi. Aucune audition.'),
    ('Photo au canal Saint-Martin', 'Photo & vidéo', 'Paris 10e · Écluse des Récollets', 2, 16, 0, 120, 12, 'published', 'Lumière de fin de journée sur les passerelles. On compare quelques cadrages, puis chacun garde ses photos.'),
    ('Yoga au parc', 'Bien-être', 'Paris 19e · Parc des Buttes-Chaumont', 7, 10, 0, 90, 15, 'published', 'Postures debout et au sol, à l’ombre si le temps le permet. La séance se termine par quelques minutes assises.'),
    ('Café langues français–anglais', 'Langues & échanges', 'Paris 3e · Café, rue de Bretagne', 11, 18, 30, 120, 10, 'published', 'On change de langue à la demie. Le thème du jour est affiché sur la table : quartier, travail, voyages.'),
    ('Collecte solidaire de quartier', 'Bénévolat', 'Paris 18e · Place Jules-Joffrin', 13, 10, 0, 120, 20, 'published', 'Tri de denrées et de livres déposés le matin. Les sacs préparés sont remis à l’association partenaire en fin de créneau.'),
    ('Oiseaux au lac de Créteil', 'Nature & plein air', 'Créteil · Lac de Créteil, promenade', 15, 9, 30, 120, 12, 'published', 'Jumelles en petit nombre à se prêter. On longe la rive nord sans quitter les chemins.'),
    ('Escalade loisir, première fois', 'Sport', 'Paris 19e · Gymnase, porte de la Villette', 10, 18, 0, 120, 8, 'published', 'Baudriers fournis par la salle. Le groupe reste sur le mur débutant, avec une personne qui assure.'),
    ('Lecture à voix haute', 'Arts & culture', 'Paris 13e · Parvis de la Bibliothèque François-Mitterrand', 14, 15, 0, 90, 16, 'published', 'Textes courts apportés par les participants ou piochés dans une sélection. On écoute, on ne commente pas le style.'),
    ('Initiation au bridge', 'Jeux & rencontres', 'Neuilly-sur-Seine · Club municipal, île de la Jatte', 16, 14, 30, 150, 12, 'published', 'Une donne commentée, puis des parties lentes. Les enchères sont expliquées au tableau avant de commencer.'),
    ('Sushis végétariens', 'Cuisine', 'Paris 15e · Local associatif, rue de la Convention', 18, 11, 0, 150, 8, 'published', 'Riz, légumes et pliage. Chacun prépare une boîte et laisse le plan de travail propre.'),
    ('Jam session acoustique', 'Musique', 'Paris 20e · Local, rue de Ménilmontant', 12, 19, 0, 150, 15, 'published', 'Guitares et voix, morceaux connus en tonalité simple. Les solos ne sont pas obligatoires.'),
    ('Portraits en lumière naturelle', 'Photo & vidéo', 'Paris 7e · Champ de Mars', 20, 16, 30, 120, 10, 'published', 'On se photographie à tour de rôle, à distance respectueuse des autres promeneurs. Les fichiers restent chez leur auteur.'),
    ('Marche méditative au Bois de Boulogne', 'Bien-être', 'Paris 16e · Lac inférieur', 17, 10, 0, 90, 14, 'published', 'Allure lente, silences compris. Le parcours fait le tour du lac sans quitter l’allée principale.'),
    ('Conversation en espagnol', 'Langues & échanges', 'Paris 9e · Café, rue des Martyrs', 21, 18, 30, 120, 10, 'published', 'Niveau intermédiaire bienvenu, débutants aussi. Un thème est proposé, personne n’est interrogé.'),
    ('Distribution de repas solidaires', 'Bénévolat', 'Saint-Denis · Parvis de la basilique', 19, 11, 30, 120, 18, 'published', 'Accueil, service et rangement. Les consignes sont données sur place par l’association qui cuisine.'),
    ('Boucle en forêt de Meudon', 'Nature & plein air', 'Meudon · Étang de Trivaux', 23, 10, 0, 180, 16, 'published', 'Environ huit kilomètres, dénivelé faible. Le groupe se reforme aux carrefours.'),
    ('Badminton loisir', 'Sport', 'Issy-les-Moulineaux · Gymnase, rue du Général-Leclerc', 22, 19, 0, 90, 8, 'published', 'Terrains partagés, rotations toutes les douze minutes. Les volants sont fournis.'),
    ('Croquis d’architecture', 'Arts & culture', 'Paris 4e · Place des Vosges', 25, 14, 0, 120, 12, 'published', 'Carnets ouverts sous les arcades. Quelques indications de perspective, puis chacun dessine à son rythme.'),
    ('Escape game de salon', 'Jeux & rencontres', 'Boulogne-Billancourt · Salle, rue de Silly', 24, 19, 0, 120, 8, 'published', 'Énigmes sur table, indices progressifs. Les équipes sont formées à l’arrivée pour mélanger les habitués et les nouveaux.'),
    ('Choux et éclairs', 'Cuisine', 'Versailles · Atelier, rue de la Paroisse', 27, 14, 0, 180, 8, 'published', 'Pâte à choux, cuisson et deux crèmes. Les fours sont partagés, les tabliers aussi.'),
    ('Découverte du ukulélé', 'Musique', 'Fontenay-sous-Bois · MJC, rue André-Tessier', 26, 15, 0, 120, 10, 'published', 'Quatre accords et une chanson connue. Des instruments sont prêtés pour la séance.'),
    ('Photo de rue à Belleville', 'Photo & vidéo', 'Paris 20e · Parc de Belleville', 28, 15, 30, 120, 12, 'published', 'Depuis le belvédère jusqu’aux escaliers. On parle du droit à l’image avant de photographier des passants.'),
    ('Étirements après le travail', 'Bien-être', 'Courbevoie · Parc de Bécon', 29, 18, 15, 60, 20, 'published', 'Quarante minutes debout et au sol, accessibles en tenue de ville. Pas de course avant la séance.'),
    ('Tandem français–arabe', 'Langues & échanges', 'Paris 11e · Café, rue Jean-Pierre-Timbaud', 31, 18, 30, 120, 8, 'published', 'Binômes qui tournent. Chacun apporte un mot ou une expression entendue dans la semaine.'),
    ('Atelier réparation de vélos', 'Bénévolat', 'Montreuil · Cour associative, rue de Rosny', 33, 10, 0, 180, 12, 'published', 'Crevaisons, freins et réglages simples. Les outils sont sur place ; venir avec son vélo si besoin.'),
    ('Pique-nique lecture au Montsouris', 'Nature & plein air', 'Paris 14e · Parc Montsouris', 35, 12, 0, 120, 20, 'published', 'Chacun apporte de quoi grignoter et un texte court à lire, ou seulement ses oreilles.'),
    ('Sortie rollers le long de la Marne', 'Sport', 'Nogent-sur-Marne · Bords de Marne', 38, 10, 30, 120, 14, 'published', 'Parcours plat, allure du plus lent. Protections recommandées, prêt de quelques casques.'),
    ('Herborisation au Parc floral', 'Nature & plein air', 'Vincennes · Parc floral de Paris', -5, 10, 0, 120, 14, 'published', 'Reconnaissance de quelques plantes de sous-bois, sans cueillette. Le groupe reste sur les allées ouvertes au public.'),
    ('Course relais amicale', 'Sport', 'Paris 16e · Pelouses extérieures de l’hippodrome d’Auteuil', -9, 9, 30, 90, 24, 'published', 'Équipes tirées au sort, distances courtes. L’objectif annoncé était de finir ensemble, pas le chronomètre.'),
    ('Street art de la Butte-aux-Cailles', 'Arts & culture', 'Paris 13e · Butte-aux-Cailles', -13, 15, 0, 120, 16, 'published', 'Parcours à pied commenté par un habitant du quartier. Aucune entrée de musée, seulement les murs visibles depuis la rue.'),
    ('Après-midi échecs', 'Jeux & rencontres', 'Paris 5e · Jardin du Luxembourg, près du kiosque', -3, 14, 0, 120, 12, 'published', 'Parties rapides et pendules souples. Les joueurs expérimentés ont pris le temps d’expliquer un coup.'),
    ('Cuisine syrienne à partager', 'Cuisine', 'Paris 18e · Cuisine partagée, rue du Poteau', -16, 11, 0, 180, 8, 'published', 'Mezzés et un plat de riz. Les recettes ont été distribuées à la fin, avec les proportions pour quatre.'),
    ('Répétition ouverte de chorale', 'Musique', 'Sceaux · Parvis de l’Orangerie', -20, 18, 0, 120, 30, 'published', 'Une heure d’écoute, puis les personnes volontaires ont rejoint les pupitres pour le refrain.'),
    ('Sortie photo nocturne', 'Photo & vidéo', 'Paris 1er · Pont Neuf', -7, 19, 30, 90, 10, 'published', 'Lumières de la Seine et stabilité du téléphone. Le groupe est resté sur les trottoirs, sans trépied encombrant.'),
    ('Sophrologie pour débutants', 'Bien-être', 'Nanterre · Parc du Chemin-de-l’Île', -11, 10, 30, 90, 12, 'published', 'Respiration et relâchement, assis ou allongé selon le confort de chacun. Aucune inscription à un cycle.'),
    ('Café allemand', 'Langues & échanges', 'Paris 6e · Café, rue de Rennes', -22, 18, 30, 120, 10, 'published', 'Discussion libre à partir d’un article court apporté par l’organisateur. Les débutants ont eu un binôme patient.'),
    ('Maraude solidaire', 'Bénévolat', 'Paris 10e · Place de la République', -28, 19, 0, 120, 16, 'published', 'Distribution préparée avec une association du quartier. Les bénévoles sont restés en binôme tout le long.'),
    ('Ramassage en forêt de Meudon', 'Nature & plein air', 'Clamart · Étang de la Garenne', -34, 10, 0, 120, 18, 'published', 'Gants et sacs fournis. Le ramassage s’est limité aux abords du chemin, sans sortir des zones autorisées.'),
    ('Tournoi de ping-pong', 'Sport', 'Vanves · Gymnase, rue Jean-Bleuzen', -40, 14, 0, 120, 12, 'published', 'Tableau à élimination douce : les personnes éliminées repartaient sur un second terrain loisir.'),
    ('Sentier et pause à Saint-Germain', 'Nature & plein air', 'Saint-Germain-en-Laye · Terrasse', 16, 10, 0, 150, 12, 'draft', 'Brouillon d’une boucle courte suivie d’une pause. Le lieu exact du regroupement reste à confirmer avant publication.'),
    ('Atelier calligraphie latine', 'Arts & culture', 'Paris 5e · Salle, rue Mouffetard', 18, 14, 0, 120, 8, 'draft', 'Brouillon : plumes et encre à prévoir. La salle n’est pas encore confirmée auprès de la mairie d’arrondissement.'),
    ('Basket loisir en extérieur', 'Sport', 'Paris 12e · Terrain, bois de Vincennes', 20, 17, 0, 90, 10, 'draft', 'Brouillon d’un créneau loisir. Le nombre de ballons disponibles doit encore être vérifié.'),
    ('Brunch partagé', 'Cuisine', 'Issy-les-Moulineaux · Salle, rue Danton', 22, 11, 0, 120, 14, 'draft', 'Brouillon : chacun apporterait un plat. La liste des allergènes sera demandée avant toute publication.'),
    ('Pique-nique au parc de Sceaux', 'Nature & plein air', 'Sceaux · Parc de Sceaux, grand canal', 9, 12, 0, 120, 25, 'cancelled', 'Le créneau a été annulé par l’organisateur. Aucun regroupement n’a lieu.'),
    ('Concert acoustique au bord de l’eau', 'Musique', 'Neuilly-sur-Seine · Île de la Jatte', 13, 17, 0, 120, 40, 'cancelled', 'Le concert prévu en plein air est annulé. Les inscriptions ouvertes ont été closes.'),
)


def _city(location):
    head = location.split('·')[0].strip()
    if head.lower().startswith('paris'):
        return 'Paris'
    return head[:80]


def _at(day_offset, hour, minute):
    moment = datetime.now(PARIS) + timedelta(days=day_offset)
    local = moment.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return local


def _fill_target(title, capacity, status):
    if status != 'published':
        return 0
    digest = hashlib.sha256(title.encode()).digest()
    if digest[1] % 7 == 0:
        ratio = 1
    elif digest[1] % 11 == 0:
        ratio = 0.2
    else:
        ratio = 0.35 + (digest[0] % 56) / 100
    return max(1, min(capacity, round(capacity * ratio)))


def _pick(member_ids, organizer_id, title, target):
    pool = [member_id for member_id in member_ids if member_id != organizer_id]
    if not pool or target <= 0:
        return []
    start = hashlib.sha256(title.encode()).digest()[2] % len(pool)
    return [pool[(start + offset) % len(pool)] for offset in range(min(target, len(pool)))]


def _ensure_user(conn, email, name, role, stats):
    row = conn.execute('SELECT id FROM users WHERE email=%s', (email,)).fetchone()
    if row:
        return row['id'], False
    user_id = conn.execute(
        'INSERT INTO users(email, display_name, password_hash) VALUES (%s, %s, %s) RETURNING id',
        (email, name, generate_password_hash(DEMO_PASSWORDS[role])),
    ).fetchone()['id']
    roles = ['member']
    if role == 'organizer':
        roles.append('organizer')
    elif role == 'admin':
        roles.append('admin')
    conn.execute(
        'INSERT INTO user_roles(user_id, role_id) SELECT %s, id FROM roles WHERE name = ANY(%s)',
        (user_id, roles),
    )
    stats['users_created'] += 1
    return user_id, True


def _preferences(conn, user_id, index, categories):
    names = [name for name in INTEREST_SETS[index % len(INTEREST_SETS)] if name in categories]
    conn.execute('DELETE FROM user_interests WHERE user_id=%s', (user_id,))
    for name in names:
        conn.execute(
            'INSERT INTO user_interests(user_id, category_id) VALUES (%s, %s) ON CONFLICT DO NOTHING',
            (user_id, categories[name]),
        )
    conn.execute(
        '''INSERT INTO member_preferences(user_id, interests, chosen_area, assistant_consent)
           VALUES (%s, %s, %s, %s)
           ON CONFLICT (user_id) DO UPDATE SET interests=EXCLUDED.interests''',
        (user_id, list(names), AREAS[index % len(AREAS)], index % 5 == 0),
    )


def _seed_reviews(conn, event_id, title, stats):
    row = conn.execute('SELECT status, ends_at FROM events WHERE id=%s', (event_id,)).fetchone()
    if not row or row['status'] != 'published' or row['ends_at'] > datetime.now(PARIS):
        return
    attendees = conn.execute(
        '''SELECT r.member_id FROM reservations r
           JOIN users u ON u.id = r.member_id
           WHERE r.event_id=%s AND r.status='confirmed' AND u.email LIKE %s''',
        (event_id, f'%@{DEMO_DOMAIN}'),
    ).fetchall()
    notes = (5, 5, 4, 4, 4, 3, 5, 3, 2, 4)
    comments = (
        'Très belle ambiance, j’y retournerai avec plaisir.',
        'Groupe bienveillant et rythme adapté aux débutants.',
        'Un peu court à mon goût, mais l’accueil était chaleureux.',
        'Lieu facile à trouver, consignes claires dès le début.',
        'J’ai rencontré des personnes vraiment sympathiques.',
        'Organisation simple et efficace, sans temps mort.',
        'Le thème annoncé correspondait bien à ce qui a été fait.',
        'Sortie conviviale, parfaite pour venir seul.',
        'J’ai appris deux ou trois choses sans me sentir perdu.',
        'Cadre agréable et groupe à taille humaine.',
        'Je recommande, surtout si l’on aime les activités tranquilles.',
        'Bonne humeur générale, je me suis senti à l’aise.',
        'Intéressant, même si le vent a un peu compliqué la fin.',
        'Une parenthèse réussie dans la semaine.',
        'On est repartis avec l’envie de revenir.',
    )
    for attendee in attendees:
        digest = hashlib.sha256(f'{title}:{attendee["member_id"]}'.encode()).digest()
        inserted = conn.execute(
            '''INSERT INTO reviews(event_id, author_id, rating, comment)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (event_id, author_id) DO NOTHING RETURNING id''',
            (event_id, attendee['member_id'], notes[digest[0] % len(notes)], comments[digest[1] % len(comments)]),
        ).fetchone()
        if inserted:
            stats['reviews_created'] += 1


def _seed_social(conn, organizer_ids, member_ids, stats):
    for index, member_id in enumerate(member_ids):
        targets = []
        first = organizer_ids[index % len(organizer_ids)]
        second = organizer_ids[(index + 2) % len(organizer_ids)]
        for organizer_id in (first, second):
            if organizer_id != member_id and organizer_id not in targets:
                targets.append(organizer_id)
        for organizer_id in targets:
            inserted = conn.execute(
                '''INSERT INTO organizer_follows(follower_id, organizer_id)
                   VALUES (%s, %s) ON CONFLICT DO NOTHING RETURNING follower_id''',
                (member_id, organizer_id),
            ).fetchone()
            if inserted:
                stats['follows_created'] += 1
    event_ids = [
        row['id'] for row in conn.execute(
            '''SELECT e.id FROM events e JOIN users u ON u.id = e.organizer_id
               WHERE u.email LIKE %s AND e.status = 'published' ORDER BY e.id''',
            (f'%@{DEMO_DOMAIN}',),
        ).fetchall()
    ]
    for index, member_id in enumerate(member_ids):
        if not event_ids:
            break
        for offset in (0, 5):
            event_id = event_ids[(index * 3 + offset) % len(event_ids)]
            inserted = conn.execute(
                '''INSERT INTO favorites(user_id, event_id) VALUES (%s, %s)
                   ON CONFLICT DO NOTHING RETURNING user_id''',
                (member_id, event_id),
            ).fetchone()
            if inserted:
                stats['favorites_created'] += 1


def seed_demo(conn):
    """Insert demo reference data. Requires a dict_row connection and migration 004."""
    stats = {
        'users_created': 0,
        'events_created': 0,
        'bookings_created': 0,
        'reviews_created': 0,
        'favorites_created': 0,
        'follows_created': 0,
        'faqs_created': 0,
        'legal_published': [],
    }
    with conn.transaction():
        stats['legal_published'] = publish_legal_defaults(conn, require_privacy=True)
        stats['faqs_created'] = ensure_faqs(conn)
        for name, icon in CATEGORIES:
            conn.execute(
                '''INSERT INTO categories(name, icon) VALUES (%s, %s)
                   ON CONFLICT (name) DO UPDATE SET icon=EXCLUDED.icon''',
                (name, icon),
            )
        categories = {
            row['name']: row['id']
            for row in conn.execute('SELECT id, name FROM categories').fetchall()
        }

        admin_id, _admin_created = _ensure_user(conn, ADMIN[0], ADMIN[1], 'admin', stats)
        _preferences(conn, admin_id, 0, categories)

        organizer_ids = []
        for index, (email, name) in enumerate(ORGANIZERS):
            user_id, _created = _ensure_user(conn, email, name, 'organizer', stats)
            organizer_ids.append(user_id)
            _preferences(conn, user_id, index + 1, categories)

        member_ids = []
        for index, (email, name) in enumerate(MEMBERS):
            user_id, _created = _ensure_user(conn, email, name, 'member', stats)
            member_ids.append(user_id)
            _preferences(conn, user_id, index + 3, categories)

        bookable = member_ids + organizer_ids

        for index, activity in enumerate(ACTIVITIES):
            title, category, location, day, hour, minute, duration, capacity, status, pitch = activity
            organizer_id = organizer_ids[index % len(organizer_ids)]
            existing = conn.execute(
                'SELECT id, capacity FROM events WHERE organizer_id=%s AND title=%s ORDER BY id LIMIT 1',
                (organizer_id, title),
            ).fetchone()
            if existing:
                event_id = existing['id']
                capacity = existing['capacity']
            else:
                starts = _at(day, hour, minute)
                ends = starts + timedelta(minutes=duration)
                description = f'{pitch}\n\n{PRACTICAL[category]}\n\n{DEMO_NOTE}'
                event_id = conn.execute(
                    '''INSERT INTO events(organizer_id, category_id, title, description, location,
                       starts_at, ends_at, capacity, status, price_cents)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id''',
                    (
                        organizer_id, categories[category], title, description, location,
                        starts, ends, capacity, status, PAID_PRICES.get(title, 0),
                    ),
                ).fetchone()['id']
                stats['events_created'] += 1
            conn.execute(
                'UPDATE events SET price_cents=%s, city=%s WHERE id=%s',
                (PAID_PRICES.get(title, 0), _city(location), event_id),
            )

            if status == 'cancelled':
                already = conn.execute(
                    'SELECT count(*) AS n FROM reservations WHERE event_id=%s',
                    (event_id,),
                ).fetchone()['n']
                if already:
                    continue
                for member_id in _pick(bookable, organizer_id, title, 3):
                    conn.execute(
                        '''INSERT INTO reservations(member_id, event_id, status, reserved_at, cancelled_at)
                           VALUES (%s, %s, 'cancelled', now(), now())''',
                        (member_id, event_id),
                    )
                    stats['bookings_created'] += 1
                continue

            target = _fill_target(title, capacity, status)
            if not target:
                continue
            confirmed = {
                row['member_id']
                for row in conn.execute(
                    "SELECT member_id FROM reservations WHERE event_id=%s AND status='confirmed'",
                    (event_id,),
                ).fetchall()
            }
            for member_id in _pick(bookable, organizer_id, title, target):
                if member_id in confirmed:
                    continue
                if len(confirmed) >= capacity:
                    break
                conn.execute(
                    'INSERT INTO reservations(member_id, event_id) VALUES (%s, %s)',
                    (member_id, event_id),
                )
                confirmed.add(member_id)
                stats['bookings_created'] += 1
            _seed_reviews(conn, event_id, title, stats)
        _seed_social(conn, organizer_ids, member_ids, stats)

        stats['demo_users'] = conn.execute(
            'SELECT count(*) AS n FROM users WHERE email LIKE %s',
            (f'%@{DEMO_DOMAIN}',),
        ).fetchone()['n']
        stats['demo_events'] = conn.execute(
            '''SELECT count(*) AS n FROM events e
               JOIN users u ON u.id = e.organizer_id
               WHERE u.email LIKE %s''',
            (f'%@{DEMO_DOMAIN}',),
        ).fetchone()['n']
    return stats
