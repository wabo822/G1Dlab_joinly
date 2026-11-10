# PostgreSQL — développement local

PostgreSQL est le moteur retenu pour Joinly. Cette première installation utilise
PostgreSQL 16 fourni par Ubuntu 24.04. Le backend Flask de la V1 utilise ce schéma ; voir `docs/developpement.md`.

## Installation sur une machine Ubuntu vierge

Depuis la racine du dépôt :

```bash
sudo apt-get update
sudo apt-get install postgresql postgresql-client
sudo python3 database/scripts/setup-local.py
```

Le script crée la base `joinly`, le propriétaire sans connexion `joinly_owner`,
un compte applicatif `joinly_app` sans droits de création de tables et les tables.
Il génère un mot de passe aléatoire dans `.env`, accessible uniquement au
propriétaire du fichier (mode 600), et exclu de Git. `.env.example` décrit les
variables à fournir au futur backend. Ne jamais les exposer dans le frontend.
Le script refuse une base, un rôle ou un `.env` déjà existant. En cas d'échec
partiel, diagnostiquer l'état avant toute relance ; ne pas supprimer une base
existante pour contourner ce contrôle.

PostgreSQL doit écouter uniquement sur localhost. L'installation actuelle a été
vérifiée sur `127.0.0.1:5432` et `[::1]:5432`. Pour un outil graphique distant,
utiliser un tunnel SSH ; ne pas ouvrir le port de la base sur Internet.

Connexion locale (depuis la racine, avec les droits de lecture du `.env`) :

```bash
set -a
. ./.env
set +a
psql
```

Les variables PG* sont reconnues par `psql` ; le framework du backend pourra
nécessiter sa propre configuration. Une future installation Hangar nécessitera
une vérification de sa connectivité avec la base : l'installation sur cette
machine ne connecte pas automatiquement le site hébergé ailleurs.

## Modèle initial

- `users`, `roles`, `user_roles` : comptes et rôles cumulables.
- `member_preferences` : préférences privées, consentement IA désactivé par défaut.
- `categories`, `events`, `reservations` : catalogue et historique des réservations.
- `faqs`, `legal_pages` : contenus administrables et versions des textes légaux.
- `schema_migrations` : suivi de la version appliquée.

Seuls les trois rôles sont préremplis. Aucun compte, activité ou mot de passe
utilisateur de démonstration n'est créé. Le backend devra produire des hachages
de mots de passe adaptés à l'authentification ; la base ne les calcule pas.
Les instants utilisent `timestamptz`, la connexion utilise UTC et le fuseau des
événements est limité à Europe/Paris pour ce prototype.

## Garanties et travail restant

Le schéma impose courriel normalisé unique, clés étrangères, capacité positive,
fin après début, cohérence annulation/date et unicité d'une réservation active
par membre et événement. Les événements avec historique ne peuvent pas être
supprimés. Les champs `updated_at` sont entretenus par des déclencheurs.

Les règles RG01–RG12 sont désormais appliquées par le backend Flask : contrôle
des comptes et rôles, confidentialité, activité publiée future, limites de
capacité, annulation et protection des dates/lieux après inscription.

Toutes les mutations de réservation et de capacité verrouillent la même ligne
d’événement avec `SELECT ... FOR UPDATE`, dans une transaction. Les tests de la
V1 vérifient la dernière place et l’annulation concurrente. Ces garanties métier
ne sont pas imposées à un administrateur écrivant directement en SQL.

La migration `005_lifecycle_search` ajoute `events.city`. Le fait qu’une activité
soit terminée n’est pas stocké : l’application compare `ends_at` à l’instant
présent, en Europe/Paris.

La migration `002_web` ajoute sessions, demandes de contact, limites de débit et
jetons de réinitialisation. La migration `003_privacy` autorise le type
`privacy` dans `legal_pages`. La migration `004_interests_pricing` ajoute
`categories.icon`, la table `user_interests`, `events.price_cents` (0 = gratuit)
et `events.view_count`. L’encaissement réel et l’historique IA restent hors schéma :
l’application ne fait que simuler la confirmation d’un prix.

## Vérification et migrations

```bash
sudo -u postgres psql -X -v ON_ERROR_STOP=1 -d joinly < database/tests/constraints.sql
```

Le test vérifie les courriels dupliqués, la capacité nulle, les doubles inscriptions,
la réinscription après annulation et la conservation de l'historique. Il annule
ses données de test à la fin. Les séquences peuvent néanmoins avancer.

`001_initial.sql` s'applique une seule fois à une base vide et dans une transaction.
Pour toute évolution, ajouter une nouvelle migration numérotée, exécutée comme
propriétaire via l'administrateur local, puis enregistrer sa version. `scripts/migrate.py` applique les migrations
absentes via l’administrateur local. Ne pas modifier rétroactivement
une migration déjà appliquée.

## Sauvegarde manuelle

```bash
sudo -u postgres pg_dump -Fc joinly > joinly.dump
```

Stocker les sauvegardes hors du dépôt, avec un accès restreint. Avant une mise en
production, automatiser les sauvegardes et tester leur restauration dans une
base distincte. Les rôles et secrets doivent être gérés séparément des sauvegardes
logiques de la base.
