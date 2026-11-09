# Journal des modifications

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
