# Développer et exécuter Joinly V1

## Architecture

Python 3.12, Flask, Jinja, PostgreSQL 16 et Gunicorn. Le serveur produit les pages
HTML et traite les formulaires ; aucune compilation JavaScript n’est nécessaire.
Les maquettes historiques restent dans `joinly_front/` et ne constituent pas
l’application fonctionnelle. Les nouvelles pages réutilisent le logo et la palette.

## Première installation Ubuntu

Depuis la racine du dépôt, avec PostgreSQL local :

```bash
sudo apt-get update
sudo apt-get install python3-venv postgresql postgresql-client
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
sudo python3 database/scripts/setup-local.py
sudo python3 scripts/migrate.py
```

`setup-local.py` initialise la migration 001 et refuse un `.env` ou une base
existante. Sur la machine déjà initialisée, **ne pas le relancer** : utiliser
seulement `scripts/migrate.py`, qui applique les versions absentes.

Ajouter à `.env` une `SECRET_KEY` aléatoire, différente du mot de passe de la
base. Exemple de génération (copier le résultat uniquement dans le fichier privé) :

```bash
python3 -c 'import secrets; print(secrets.token_hex(32))'
```

`.env.example` décrit toutes les variables. Conserver `.env` en mode 600 et hors
Git. Le compte `joinly_app` n’a pas de droit DDL ; seul l’administrateur local
applique les migrations avec le rôle propriétaire.

## Contenu initial et administrateur

Appliquer d’abord les migrations, dont `003_privacy` (politique de confidentialité)
et `004_interests_pricing` (icônes, centres d’intérêt, prix en centimes, compteur de consultations) :

```bash
sudo python3 scripts/migrate.py
sudo python3 scripts/migrate.py --database joinly_test   # si la base de tests existe déjà
```

Puis :

```bash
.venv/bin/python scripts/seed.py
# Jeu de démonstration réaliste et idempotent (comptes, activités, inscriptions).
.venv/bin/flask --app app seed-demo
# Équivalent :
.venv/bin/python scripts/seed.py --demo
```

`scripts/seed.py` ajoute les catégories, les questions de FAQ manquantes et les
textes légaux de référence s’ils sont absents ou s’ils contiennent encore un
ancien marqueur de démonstration (« à renseigner », « Document de démonstration »).
Une version déjà publiée et rédigée n’est pas remplacée. S’il n’existe aucun
administrateur, le script crée `admin@joinly.test` avec un mot de passe aléatoire
enregistré uniquement dans `.local/initial-admin.txt` (mode 600). Ce compte est
destiné au développement. Changer son e-mail et son mot de passe depuis
**Mon espace → E-mail et mot de passe** avant usage réel ; ce changement invalide
les sessions existantes.

`flask seed-demo` ajoute environ 40 comptes `@demo.joinly.fr`, une cinquantaine
d’activités en Île-de-France et des inscriptions. Il ne supprime rien et ne
change pas le mot de passe, le nom ou les rôles d’un compte déjà présent.
Il met à jour les centres d’intérêt des comptes de démonstration et le prix
des activités de démonstration (dix sont payantes, le reste est gratuit).
Le relancer ne crée pas de doublon. Les mots de passe et le détail des comptes
sont dans [docs/demo-accounts.md](demo-accounts.md).

La migration `005_lifecycle_search` ajoute `events.city`. Une activité est terminée lorsque `ends_at` est passé (saisie et affichage en Europe/Paris). Ce calcul est fait à chaque requête. `BOOKING_CUTOFF_MINUTES` (défaut 0) avance la fermeture des inscriptions avant le début. L’organisateur ne modifie plus les dates d’une activité terminée ; l’administrateur le fait sur la fiche.

Après la migration 004, un membre sans trois centres d’intérêt est renvoyé
vers `/interests` et ne peut pas réserver tant qu’il n’a pas choisi. Un
administrateur n’est pas soumis à ce passage. Une activité dont le prix est
supérieur à 0 € exige la confirmation « Paiement simulé — projet étudiant »
avant l’inscription. Aucune carte n’est collectée.

Pour créer explicitement un administrateur supplémentaire :

```bash
.venv/bin/flask --app app create-admin
```

Le mot de passe est demandé sans affichage. Un visiteur ne peut jamais choisir le
rôle administrateur. Un organisateur peut s’inscrire librement ; l’administrateur
peut ensuite retirer cette habilitation ou suspendre son compte.

Les pages légales livrées décrivent le projet étudiant : éditeur, hébergeur
Contabo (adresse de l’impressum), conditions d’utilisation et politique de
confidentialité. L’administration peut en publier une nouvelle version ; l’ancienne
reste en base. `PUBLIC_BASE_URL` sert aussi aux URL canoniques, aux balises
Open Graph et au fichier `sitemap.xml`.

## Lancement local

```bash
.venv/bin/gunicorn --workers 2 --bind 127.0.0.1:8000 'app:create_app()'
```

Ouvrir `http://127.0.0.1:8000` sur **la machine qui exécute le serveur**.
Pour développer avec rechargement automatique, utiliser `flask --app app run`
uniquement en local. Ne pas activer le débogueur sur une interface publique.

Si le serveur est distant, depuis votre ordinateur :

```bash
ssh -L 8000:127.0.0.1:8000 utilisateur@votre-serveur
```

Puis ouvrir `http://localhost:8000`. Le port 5432 reste local. Ni le port 8000
ni PostgreSQL ne sont ouverts sur Internet par les scripts du projet.

## Service persistant sur cette machine

Après initialisation et tests, depuis le dépôt :

```bash
sudo bash scripts/install-service.sh
sudo systemctl status joinly
```

Le script installe une copie de l’application sous `/opt/joinly/releases/`, pointe
`/opt/joinly/current` sur cette copie et démarre Gunicorn comme utilisateur système
`joinly`, sans connexion interactive. Les fichiers applicatifs restent détenus par
root. `/etc/joinly.env` est copié au premier lancement seulement, avec les droits
root:joinly 640. Le service utilise deux workers, une limite mémoire de 512 MiB,
un système de fichiers en lecture seule et un répertoire temporaire privé.

Pour une mise à jour : appliquer les migrations, exécuter les tests, puis relancer
le script. Les anciennes copies sont conservées pour inspection ou retour arrière
applicatif ; une migration de données peut nécessiter une procédure distincte.
Les dépendances Python sont partagées entre ces copies. Modifier explicitement
`/etc/joinly.env` si la configuration change, puis redémarrer le service.

```bash
sudo systemctl restart joinly
sudo journalctl -u joinly -n 50
curl http://127.0.0.1:8000/health
```

Arrêter un éventuel serveur de développement sur le port 8000 avant l’installation.
Le service est activé au démarrage et utilise les données de `joinly`, pas celles
de `joinly_test`.

## Mise en ligne et e-mails

La V1 est déployée sur **https://isep.wangjiahan.com** avec Nginx, un certificat
Let’s Encrypt et une redirection HTTP vers HTTPS. La configuration effective est
versionnée dans `deploy/isep.wangjiahan.com.nginx`. Certbot renouvelle le certificat
et un hook recharge Nginx. Les textes légaux restent à compléter. Hangar doit pouvoir relayer/exécuter Flask et accéder à PostgreSQL ;
son ancien hébergement de fichiers statiques ne suffit pas.

Le service utilise `TRUST_PROXY=1` uniquement derrière le Nginx local. Celui-ci
**remplace** `X-Forwarded-For` par l’adresse du client et `X-Forwarded-Proto` par
le protocole reçu. Flask ne fait confiance qu’à un saut pour ces deux valeurs ;
les en-têtes d’hôte transférés ne sont pas utilisés. `TRUSTED_HOSTS` est limité au
sous-domaine et aux noms locaux, `COOKIE_SECURE=1` et `PUBLIC_BASE_URL` désigne
l’origine HTTPS. Garder Gunicorn sur localhost et ne pas activer ce mode pour
un accès direct public. La configuration locale du dépôt conserve les valeurs
adaptées aux tests ; celle du service est dans `/etc/joinly.env`.

Le mot de passe oublié utilise SMTP avec STARTTLS, un lien aléatoire de 30 minutes
stocké sous forme de hachage et utilisable une seule fois. Renseigner :

- `SMTP_HOST`, `SMTP_PORT` (587 par défaut), `MAIL_FROM` ;
- `SMTP_USER` et `SMTP_PASSWORD` si nécessaires ;
- `PUBLIC_BASE_URL`, l’origine HTTPS officielle, sans suffixe de chemin.

Sans ces paramètres, la page explique que le service mail n’est pas configuré.
Les tests simulent l’envoi SMTP : aucun e-mail réel n’a été envoyé pendant la
recette. Une panne de transport est journalisée sans exposer les identifiants ou
les liens. Les pages retournent le même message pour les adresses existantes et
inconnues.

## Tests

Les tests utilisent **exclusivement `joinly_test`**, une base séparée contenant des
données jetables. Ne pas y mettre de données réelles. Le compte applicatif y a des
droits supplémentaires pour nettoyer les tables. Ne pas lancer deux suites en
parallèle sur cette même base.

```bash
.venv/bin/pip install -r requirements-dev.txt
sudo python3 scripts/setup-test-db.py  # une fois seulement
.venv/bin/python -m pytest -q
.venv/bin/playwright install --with-deps chromium
PGDATABASE=joinly_test .venv/bin/gunicorn --bind 127.0.0.1:8001 'app:create_app()'
# Dans un deuxième terminal (et avec la démo sur 8000 pour les captures) :
.venv/bin/python tests/browser_smoke.py
```

La suite navigateur réinitialise les données de `joinly_test`, exécute le parcours
organisateur/membre/administrateur, vérifie les largeurs 375/768/1440 et enregistre
les captures de la démo dans `.local/`. Elle n’écrit pas dans la base de démo.

## Données, maintenance et sécurité

Les mots de passe utilisent scrypt. Les sessions sont conservées côté serveur sous
forme de hachages de jetons, expirent après 12 heures et sont révoquées à la
déconnexion, suspension, modification des habilitations ou changement d’identifiants.
Les formulaires POST exigent un jeton CSRF. Les modèles échappent les textes saisis.
Les formulaires texte restent courts ; une image de couverture peut aller jusqu’à 2 Mo
(requête limitée à 3 Mo). En production, Nginx autorise `client_max_body_size 3m`
et les fichiers sont écrits dans `/var/lib/joinly/uploads` (`JOINLY_UPLOAD_DIR`),
dossier persistant hors des releases, accessible en écriture au service grâce à
`ReadWritePaths`. Les connexions, inscriptions, contacts et
réinitialisations disposent de limites de débit persistantes.

Toutes les écritures liées à la capacité verrouillent la ligne de l’événement dans
une transaction. Ne pas ajouter un autre chemin d’écriture des réservations sans
reprendre ce protocole. Les règles métier sont dans l’application : un accès SQL
administrateur peut les contourner. L’heure est stockée avec fuseau ; l’affichage
et la saisie utilisent Europe/Paris. Une heure inexistante lors du changement
d’heure est refusée ; une heure répétée est interprétée comme sa première occurrence.

Nettoyer périodiquement les jetons expirés :

```bash
.venv/bin/flask --app app cleanup
```

Aucune tâche de nettoyage ni sauvegarde automatique n’est installée. Avant mise
en production, définir fréquence, rétention et restauration testée. Exemple de
sauvegarde manuelle, avec permissions privées :

```bash
umask 077
sudo -u postgres pg_dump -Fc joinly > joinly.dump
```

Les demandes de contact sont enregistrées et consultables dans l’administration ;
elle ne les envoie pas automatiquement par mail. Les fonctionnalités sociales et l’assistant IA ne sont pas activés dans cette
version. Le prix est stocké en centimes ; la réservation payante ne fait
qu’enregistrer une confirmation simulée.

### Connecter Brevo sans exposer la clé

Créer le compte Brevo et terminer l’authentification du domaine et du sender
sur son tableau de bord. Récupérer le **SMTP login** et une **clé SMTP** (pas une
clé API) depuis https://app.brevo.com/settings/keys/smtp.

Sur le serveur, exécuter :

```bash
sudo python3 /root/joinly/scripts/configure-brevo.py
```

Le script demande login, adresse d’expédition vérifiée et clé masquée. Il vérifie
la connexion TLS et l’authentification avant de remplacer atomiquement les seuls
paramètres SMTP de `/etc/joinly.env`, puis redémarre Joinly. Il conserve les droits
du fichier et n’envoie aucun e-mail. La vérification de l’expéditeur et la livraison
réelle restent à tester depuis le parcours « Mot de passe oublié ». Ne pas mettre
la clé SMTP dans un message, une commande shell ou un fichier suivi par Git.
