# Journal des modifications

## 2026-11-09 — Favoris, abonnements et profil organisateur

Chaque membre peut mettre une activité en favori et suivre un organisateur. Mon espace liste « Mes favoris » et « Organisateurs suivis ». La page publique `/organisateurs/<id>` montre les activités publiées, la note moyenne et le nombre d’abonnés.

### Fichiers

- `database/migrations/007_favorites_follows.sql` — tables `favorites` et `organizer_follows`.
- `app/__init__.py` — bascules, page publique, listes du compte, sitemap.
- `app/seed_demo.py` — favoris et abonnements des comptes `@demo.joinly.fr` seulement, sans doublon.
- `app/templates/detail.html`, `account.html`, `organizer_public.html`
- `tests/test_app.py`
- `CHANGELOG.md`

Cette pull request est empilée sur les avis (#5) et le cycle de vie (#4).

## 2026-11-09 — Avis et notes

Après la fin d’une activité, chaque participant dont l’inscription est encore confirmée peut laisser une note de 1 à 5 et un commentaire. Un seul avis par personne et par activité, modifiable. La moyenne et le nombre d’avis s’affichent sur les cartes et la fiche. L’administrateur peut masquer un avis : il sort alors de la moyenne et de la liste publique.

### Fichiers

- `database/migrations/006_reviews.sql` — table `reviews`.
- `app/__init__.py` — dépôt et modification d’un avis, moyenne, tri par note, modération.
- `app/seed_demo.py` — avis en français pour les activités de démonstration déjà terminées, uniquement depuis les comptes `@demo.joinly.fr`, sans doublon au second passage.
- `app/templates/detail.html`, `_cards.html`, `activities.html`, `admin.html` — affichage, formulaire et masquage.
- `tests/test_app.py` — règles d’avis et idempotence du jeu de démonstration.
- `CHANGELOG.md`, `README.md`.

## 2026-11-09 — Activités terminées, recherche et pagination

Une activité est « Terminée » dès que son heure de fin est passée, calculée en heure de Paris. Le catalogue par défaut, les recommandations et le classement ne la montrent plus. Elle reste accessible par son adresse, dans l’historique du participant, et dans le filtre « activités passées ».

### Comportement

- Le statut « Terminé » est calculé à l’affichage : `ends_at` est stocké en `timestamptz` et saisi en Europe/Paris. S’il manquait, la fin retenue serait la fin du jour de début (23:59:59, Paris). Aucune tâche planifiée ne change le statut.
- « Annulée » reste un statut enregistré, distinct d’une activité simplement passée.
- On ne peut plus réserver une activité terminée (contrôle serveur, bouton désactivé « Activité terminée »). Les inscriptions se ferment aussi quand l’activité est complète, ou `BOOKING_CUTOFF_MINUTES` minutes avant le début (0 par défaut : fermeture à l’heure de début).
- L’organisateur ne peut plus modifier les dates d’une activité terminée. Un administrateur le peut via « Corriger les dates » sur la fiche.
- L’historique de Mon espace liste les activités terminées et les inscriptions annulées.
- La recherche d’`/activities` reste dans l’URL : mot-clé (titre ou description), lieu, ville, catégorie, dates, prix (gratuit, payant, maximum), tri (date, popularité, prix) et pagination de 12. Le tri par note arrivera avec les avis.

### Migration

`005_lifecycle_search` : colonne `events.city` (80 caractères maximum, vide par défaut).

### Fichiers

- `database/migrations/005_lifecycle_search.sql` — ville de l’activité.
- `app/lifecycle.py` — fin d’activité, refus de réservation, libellé de phase.
- `app/__init__.py` — catalogue, recommandations, classement, historique, délai avant le début, correction de dates par l’administrateur.
- `app/seed_demo.py` — la ville des activités de démonstration est recalculée à partir du lieu.
- `app/templates/activities.html`, `_cards.html`, `detail.html`, `account.html`, `event_form.html`, `home.html`, `classement.html` — filtres, badges, historique.
- `tests/test_app.py` — activités passées, délai de réservation, recherche et pagination.
- `README.md`, `docs/developpement.md`, `docs/demo-accounts.md`, `database/README.md`, `.env.example` — cycle de vie et `BOOKING_CUTOFF_MINUTES`.

## 2026-11-09 — Centres d’intérêt, recommandations, classement et tarifs simulés

Les membres choisissent au moins trois centres d’intérêt, la page d’accueil s’en sert pour proposer des activités, un classement public mesure la popularité, et les activités peuvent afficher un prix en euros avec une confirmation de paiement simulée.

### Comportement

- À l’inscription, au moins trois catégories sont obligatoires. Le contrôle est fait côté serveur. Un compte déjà créé sans assez de centres d’intérêt est renvoyé vers le sélecteur après la connexion. Un administrateur peut passer cette étape.
- Les centres d’intérêt se modifient ensuite dans Mon espace, toujours avec le minimum de trois pour un membre ou un organisateur.
- « Recommandé pour vous » liste, pour une personne connectée, les activités publiées à venir de ses catégories (les complètes en dernier, puis les plus proches). Sans compte, ou si aucune activité ne correspond, la section montre un aperçu : une activité à venir par catégorie, complétée par les prochaines dates.
- « Tendances / Classement » classe les activités publiées à venir. Le score additionne les réservations confirmées des 30 derniers jours (× 10), le taux de remplissage (0 à 100) et les consultations de la fiche (plafonnées à 400). Les trois premiers rangs ont un badge.
- Chaque activité a un prix en centimes d’euro. 0 s’affiche « Gratuit ». L’organisateur le saisit dans le formulaire ; l’administrateur peut le corriger. Aucun paiement réel : une activité payante demande une confirmation libellée « Paiement simulé — projet étudiant », sans numéro de carte.
- Le jeu de démonstration reste idempotent. Il rafraîchit les icônes des catégories, les centres d’intérêt des comptes `@demo.joinly.fr` et les prix des activités de démonstration, y compris si ces lignes existaient déjà. Il ne change ni le mot de passe, ni le nom, ni les rôles d’un compte déjà présent.

### Migration

`004_interests_pricing` : colonne `categories.icon`, table `user_interests`, colonnes `events.price_cents` et `events.view_count`, catégories supplémentaires (Football, Pique-nique, Randonnée, Lecture, Jeux vidéo, Yoga, Tech, Théâtre) et droit d’accès de `joinly_app` sur `user_interests`.

### Fichiers

- `database/migrations/004_interests_pricing.sql` — schéma des intérêts, du prix et du compteur de consultations.
- `app/__init__.py` — sélecteur obligatoire, recommandations, classement, prix, paiement simulé, compteur de vues.
- `app/seed_demo.py` — icônes, intérêts des comptes de démonstration, dix activités payantes, mise à jour des lignes déjà présentes.
- `app/static/app.css` — puces de catégories, badges de rang, prix.
- `app/static/interests.js` — compteur et bouton inactif tant que le minimum n’est pas atteint (le serveur reste la règle).
- `app/templates/_interests.html` — grille de puces partagée.
- `app/templates/interests.html` — sélecteur après connexion.
- `app/templates/classement.html` — page Tendances / Classement.
- `app/templates/payment.html` — confirmation de paiement simulé.
- `app/templates/_cards.html`, `home.html`, `detail.html`, `activities.html`, `auth.html`, `account.html`, `event_form.html`, `organizer.html`, `admin.html`, `base.html` — prix, recommandations, classement, puces et navigation.
- `scripts/seed.py`, `scripts/seed_demo.py` — catégories avec icône ; la doc de la commande cite la migration 004.
- `tests/test_app.py` — intérêts obligatoires, recommandations, classement, vues, prix, paiement simulé, seed idempotent.
- `README.md`, `docs/demo-accounts.md`, `docs/developpement.md`, `database/README.md` — parcours, commande de seed et déploiement.

## 2026-11-09 — Pages légales, confidentialité, référencement et jeu de démonstration (pull request #2)

Livré sur `main` par la pull request #2 (`aa961b9`, « Finaliser les pages légales, le référencement et le jeu de démonstration »), avant les centres d’intérêt et les tarifs. Cette section est rétroactive : le dépôt n’avait pas encore de journal.

### Comportement

- Pages légales du projet étudiant : conditions d’utilisation, mentions légales (éditeur, hébergeur Contabo) et politique de confidentialité (cookies de session, Brevo, CNIL). Les anciens textes de démonstration (« à renseigner », « Document de démonstration ») ne sont plus affichés.
- Redirection permanente de `/privacy` vers `/legal/privacy`.
- Bandeau « Cookies nécessaires » : uniquement le cookie de session, sans mesure d’audience.
- `robots.txt` et `sitemap.xml` (pages publiques et activités publiées). URL canonique, Open Graph et favicon.
- Pages d’erreur plus explicites (400, 403, 404, 413, 429, 500) et ajustements visuels des gabarits.
- Jeu de démonstration idempotent : `flask --app app seed-demo`, environ 40 comptes `@demo.joinly.fr`, une cinquantaine d’activités en Île-de-France et des inscriptions. Un compte déjà présent n’est pas réécrit. Les identifiants sont dans `docs/demo-accounts.md`.
- Migration `003_privacy` : le type `privacy` est accepté dans `legal_pages`.

### Fichiers

- `app/legal_content.py` — textes légaux et FAQ de référence, publication seulement si la version en ligne est absente ou encore un marqueur de démonstration.
- `app/__init__.py` — routes légales, robots, sitemap, métadonnées, redirection, commande `seed-demo`.
- `app/seed_demo.py` — comptes, activités et inscriptions de démonstration.
- `scripts/seed.py`, `scripts/seed_demo.py` — contenu initial et option `--demo`.
- `database/migrations/003_privacy.sql` — contrainte `legal_pages.kind`.
- `app/static/app.css`, `app/static/cookies.js`, `app/static/favicon.svg` — bandeau cookies, favicon, finitions.
- `app/templates/base.html`, `legal.html`, `error.html`, `home.html`, `activities.html`, `detail.html`, `account.html`, `auth.html`, `admin.html`, `contact.html`, `faq.html`, `event_form.html`, `organizer.html`, `participants.html`, `_cards.html` — pied de page légal, SEO, pages d’erreur et présentation.
- `tests/test_app.py` — confidentialité, robots, sitemap, métadonnées et seed idempotent.
- `docs/demo-accounts.md`, `docs/developpement.md`, `database/README.md`, `README.md`, `.env.example` — commande de seed, `PUBLIC_BASE_URL` et rappel de la migration 003.
