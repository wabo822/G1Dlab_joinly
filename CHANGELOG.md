# Journal des modifications

## 2026-11-10 — Carte des activités

La politique de référent passe de `same-origin` à `strict-origin-when-cross-origin` (en-tête Flask et balise meta), pour que les tuiles reçoivent l’origine `https://isep.wangjiahan.com/`. Les tuiles officielles `tile.openstreetmap.org` renvoyaient sinon l’image « Access blocked / 403 » dans le navigateur. La carte utilise les tuiles d’OSM France (`{s}.tile.openstreetmap.fr/osmfr`), qui restent accessibles avec ou sans référent, avec l’attribution « © OpenStreetMap contributors © OSM France ». Les tuiles raster publiques CARTO exigent désormais une clé API et n’ont pas été adoptées. La CSP `img-src` autorise OSM France (et conserve OSM.org). La configuration nginx du site principal ne change pas : le `Referrer-Policy: no-referrer` existant ne concerne que l’aperçu privé, pas l’application.

### Fichiers

- `app/static/map.js`, `app/__init__.py`, `app/templates/base.html`, `tests/test_app.py`, `CHANGELOG.md`


## 2026-11-10 — Cartes du classement

Sur la couverture, le rang n’est plus une barre colorée qui recouvre la catégorie. C’est un petit badge rond en haut à gauche (or, argent, bronze pour les trois premiers, fond neutre ensuite). La catégorie est une pastille en haut à droite. La date et l’heure tiennent dans un bloc lisible en bas à gauche. Les formes décoratives semi-transparentes sont masquées dès qu’une photo de couverture est présente ; l’attribution automatique des photos ne change pas. Même composant sur l’accueil, l’exploration, les recommandations et les pages organisateur.

### Fichiers

- `app/templates/_cards.html`, `app/static/app.css`, `tests/test_app.py`, `CHANGELOG.md`


## 2026-11-09 — Photos Unsplash

`scripts/fetch_unsplash_covers.py` lit `UNSPLASH_ACCESS_KEY` dans l’environnement (la clé n’est pas versionnée). Il cherche 13 photos paysage par catégorie, déclenche `download_location` une fois par photo, et reste en dessous de 50 requêtes par heure : il attend la fenêtre suivante plutôt que de dépasser le plafond. La fiche d’une activité montre « Photo : nom sur Unsplash » avec les liens `utm_source=joinly_isep&utm_medium=referral`. Les crédits sont dans `docs/image-credits.md` et `app/static/covers/credits.json`.

### Fichiers

- `scripts/fetch_unsplash_covers.py`
- `app/covers.py`, `app/templates/detail.html`, `tests/test_app.py`
- `app/static/covers/**`, `docs/image-credits.md`, `README.md`, `CHANGELOG.md`

Empilée sur les photographies Wikimedia (#17).

## 2026-11-09 — Photographies de couverture

Les 13 visuels de chaque catégorie sont des photographies distinctes, recadrées en WebP 1200×675 sous 150 Ko. Les API Unsplash et Pexels répondent 401 sans clé : `scripts/fetch_covers.py` interroge Wikimedia Commons, au plus 40 requêtes par heure, et reprend depuis `instance/cover-fetch.json` au lieu de s’arrêter quand le budget horaire est atteint. Les crédits (URL, auteur, licence) sont dans `docs/image-credits.md`. L’attribution automatique par hash ne change pas.

### Fichiers

- `scripts/fetch_covers.py`, `scripts/generate_covers.py`
- `app/static/covers/**`, `docs/image-credits.md`, `README.md`, `CHANGELOG.md`

Empilée sur l’administration (#16).

## 2026-11-09 — Administration complète

L’administration a une barre latérale. Le tableau de bord affiche les comptes, les activités ouvertes, les réservations, le revenu simulé, la note et les messages en attente. Les listes de comptes, d’activités, de réservations et d’avis se filtrent et s’exportent en CSV. L’admin modifie le texte et la note d’un avis, bannit en lot, consulte un compte (bandeau « Consultation en tant que », journalisé), règle l’annonce, le délai de réservation, les poids du classement et les activités à la une. Une demande pour devenir organisateur se traite dans la même zone.

### Fichiers

- `database/migrations/015_admin.sql` — réglages, journal, demandes, statut banni, activités épinglées, types de notification.
- `app/admin_office.py`, `app/__init__.py`
- `app/templates/admin_base.html` et gabarits `admin_*.html`, `admin.html`, `base.html`, `home.html`, `account.html`
- `app/static/app.css`, `tests/test_app.py`, `CHANGELOG.md`

Empilée sur le tableau de bord organisateur (#15).

## 2026-11-09 — Tableau de bord organisateur

`/organizer/tableau` résume les consultations, le taux de remplissage, le revenu simulé (prix des inscriptions confirmées moins les remboursements), la note moyenne, les activités les plus suivies et un graphique SVG des réservations confirmées des 30 derniers jours.

### Fichiers

- `app/charts.py`, `app/__init__.py`, `app/templates/dashboard.html`, `organizer.html`
- `tests/test_app.py`, `CHANGELOG.md`

Empilée sur le partage (#14).

## 2026-11-09 — Partage et affiche

La fiche propose de copier le lien, d’ouvrir WhatsApp, X, Facebook, LinkedIn ou un e-mail, et le partage natif du téléphone quand il existe. Une affiche PNG (titre, date, lieu, prix, illustration, QR) se télécharge. Les balises Open Graph et Twitter utilisent l’image de couverture en URL absolue, ce qui sert aussi aux aperçus WeChat. La police est Source Sans 3, licence SIL OFL, dans `app/fonts/`.

### Fichiers

- `app/posters.py`, `app/static/share.js`, `app/fonts/`
- `app/__init__.py`, `app/templates/base.html`, `detail.html`
- `tests/test_app.py`, `CHANGELOG.md`

Empilée sur Google (#13).

## 2026-11-09 — Connexion Google

« Continuer avec Google » apparaît sur la connexion et l’inscription seulement si `GOOGLE_CLIENT_ID` et `GOOGLE_CLIENT_SECRET` sont définis. Le bouton est sinon absent et `/auth/google` répond 404. Le callback `/auth/google/callback` vérifie `state` et `nonce` (Authlib pour l’échange de jeton). Une adresse déjà vérifiée par Google relie le compte existant ou en crée un déjà confirmé, puis envoie vers les centres d’intérêt s’il en manque. Le `sub` Google est stocké.

Console Google Cloud : origine `https://isep.wangjiahan.com`, redirection `https://isep.wangjiahan.com/auth/google/callback`.

### Fichiers

- `database/migrations/014_google.sql` — `users.google_sub`.
- `app/__init__.py`, `app/templates/auth.html`, `requirements.txt` (`Authlib==1.6.5`)
- `.env.example`, `docs/developpement.md`, `tests/test_app.py`, `CHANGELOG.md`

Empilée sur les remboursements (#12).

## 2026-11-09 — Annulation et remboursement simulé

Chaque activité a une politique : flexible (intégral jusqu’à 24 h avant, sinon 0), modérée (intégral jusqu’à 72 h, sinon 50 %), stricte (aucun remboursement). Le montant calculé est affiché avant l’annulation et enregistré comme « Remboursement simulé ». Le billet est invalidé, la place se libère, l’organisateur est prévenu et le participant reçoit un e-mail. Si l’organisateur annule l’activité, le remboursement simulé est intégral. L’administrateur peut saisir un remboursement manuel, avec confirmation.

### Fichiers

- `database/migrations/013_cancellation_refunds.sql`
- `app/lifecycle.py`, `app/__init__.py`, `app/seed_demo.py`
- `app/templates/detail.html`, `payment.html`, `account.html`, `event_form.html`, `admin.html`
- `tests/test_app.py`, `CHANGELOG.md`

Empilée sur les billets (#11).

## 2026-11-09 — Billets et contrôle QR

Chaque réservation confirmée reçoit un jeton imprévisible et un code court `JOIN-XXXX-XX`. Le billet est dans Mon espace, avec un QR code. L’organisateur de l’activité, et l’administrateur, ouvrent « Contrôle des billets » : saisie du code ou scan (BarcodeDetector, sinon html5-qrcode). Un billet ne passe qu’une fois ; l’organisateur peut annuler le contrôle. Une inscription annulée invalide le billet. La migration crée les billets déjà dus, sans e-mail. Le jeu de démonstration marque contrôlés une partie des billets passés.

### Fichiers

- `database/migrations/012_tickets.sql`, `app/tickets.py`
- `app/__init__.py`, `app/seed_demo.py`, `app/static/checkin.js`
- `app/templates/tickets.html`, `checkin.html`, `participants.html`, `account.html`
- `requirements.txt` — `qrcode==8.2`
- `tests/test_app.py`, `CHANGELOG.md`

Empilée sur la confirmation e-mail (#10).

## 2026-11-09 — Code de confirmation à l’inscription

L’inscription envoie un code à 6 chiffres. Le compte reste non confirmé tant que le code n’est pas saisi. Ordre : inscription, code, centres d’intérêt, accueil. Le code est haché, expire en 15 minutes, accepte 5 essais, et un renvoi attend 60 secondes. Sans SMTP, le code est écrit dans le journal (`Verification code for …`) et dans `dev_outbox`. L’e-mail est en français, avec l’en-tête Joinly. `MAIL_FROM` de production : `noreply@wangjiahan.com`.

La migration marque vérifiés les comptes déjà présents, y compris la démonstration. Les nouveaux comptes de démonstration sont créés déjà vérifiés.

### Fichiers

- `database/migrations/011_email_verification.sql`
- `app/notify.py`, `app/__init__.py`, `app/seed_demo.py`
- `app/templates/auth.html`
- `tests/test_app.py`, `.env.example`, `CHANGELOG.md`

Empilée sur les notifications (#9).

## 2026-11-09 — Notifications et rappels

Une cloche indique le nombre de notifications non lues. Une réservation confirmée, un changement, une annulation, un rappel 24 h avant, une nouvelle activité d’un organisateur suivi et un nouvel avis créent une notification. La confirmation, le changement, l’annulation et le rappel partent aussi par le SMTP déjà configuré (Brevo). Un échec d’envoi est journalisé et ne fait pas échouer la requête. Sans SMTP, le message est écrit dans `dev_outbox` et dans le journal.

`flask --app app send-reminders` est idempotent (`reservations.reminder_sent_at`). Exemple de planification, non installé par le script de service :

```bash
sudo cp deploy/joinly-reminders.service deploy/joinly-reminders.timer /etc/systemd/system/
sudo systemctl enable --now joinly-reminders.timer
```

### Fichiers

- `database/migrations/010_notifications.sql` — `notifications`, `dev_outbox`, `reservations.reminder_sent_at`.
- `app/notify.py`, `app/__init__.py` — création, cloche, commande.
- `app/templates/base.html`, `notifications.html`, `app/static/app.css`
- `deploy/joinly-reminders.service`, `deploy/joinly-reminders.timer`
- `tests/test_app.py`, `CHANGELOG.md`

Empilée sur la carte (#8).

## 2026-11-09 — Carte OpenStreetMap

La fiche d’une activité qui a une latitude et une longitude affiche une carte Leaflet (CDN unpkg) sur le fond OpenStreetMap. La politique de sécurité autorise ces ressources. Les activités de démonstration reçoivent les coordonnées réelles de leur lieu en Île-de-France, y compris si elles existaient déjà.

### Fichiers

- `database/migrations/009_coordinates.sql` — `events.latitude`, `events.longitude`.
- `app/__init__.py` — saisie des coordonnées et en-tête CSP.
- `app/static/map.js`, `app/static/app.css`, `app/templates/detail.html`, `event_form.html`
- `app/seed_demo.py` — coordonnées des lieux de démonstration.
- `tests/test_app.py`, `CHANGELOG.md`

Empilée sur la bibliothèque d’images (#7).

## 2026-11-09 — Illustrations de couverture

Chaque activité a une image. Si l’organisateur n’en envoie pas, une illustration de la catégorie est choisie avec un hash stable de l’identifiant : changer de catégorie change l’image. Treize visuels originaux par catégorie (18 catégories) sont dans le dépôt. L’administrateur voit la bibliothèque et peut forcer une image, ou revenir à l’automatique.

Les photos Unsplash ou Pexels n’ont pas été téléchargées : leurs API de recherche exigent une clé, et inventer les crédits aurait été faux. Le détail est dans `docs/image-credits.md`.

### Fichiers

- `database/migrations/008_covers.sql` — `events.cover_image`.
- `app/covers.py`, `scripts/generate_covers.py`, `app/static/covers/**`, `docs/image-credits.md`
- `app/__init__.py` — affichage, envoi, service `/media`, page d’administration.
- `app/templates/event_form.html`, `_cards.html`, `detail.html`, `admin_covers.html`, `app/static/app.css`
- `requirements.txt` — Pillow 11.3.0.
- `deploy/joinly.service`, `deploy/isep.wangjiahan.com.nginx`, `scripts/install-service.sh`, `.env.example`, `.gitignore`
- `tests/test_app.py`, `CHANGELOG.md`, `README.md`

Les fichiers envoyés vivent dans `JOINLY_UPLOAD_DIR` (en production `/var/lib/joinly/uploads`, hors des releases). Le service a `ReadWritePaths` sur ce dossier, propriétaire `joinly:joinly`, mode 750.

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
