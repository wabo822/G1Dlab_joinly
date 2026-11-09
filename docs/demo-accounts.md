# Comptes de démonstration

Ces comptes remplissent le site pour une démonstration du projet étudiant. Les
adresses utilisent le domaine fictif `@demo.joinly.fr`. Les activités qu’ils
publient le précisent dans leur description : aucun rendez-vous réel n’est
organisé.

La commande ne supprime aucune donnée et ne modifie pas un compte déjà présent
(mot de passe, nom, rôles). Un second lancement ne crée pas de doublon.

## Commande

Depuis la racine du dépôt, une fois la migration `003_privacy` appliquée :

```bash
.venv/bin/flask --app app seed-demo
```

Variante équivalente :

```bash
.venv/bin/python scripts/seed_demo.py
.venv/bin/python scripts/seed.py --demo
```

La base visée est celle de `PGDATABASE` (par défaut `joinly`). Les mots de passe
sont hachés avec la même fonction que l’application (`werkzeug.security.generate_password_hash`).

## Identifiants

Un mot de passe par rôle. Tous font plus de 12 caractères.

| Rôle | Adresse | Mot de passe |
| --- | --- | --- |
| Administrateur | `admin.demo@demo.joinly.fr` | `Joinly-Admin-2026!` |
| Organisateur | voir la liste ci-dessous | `Joinly-Orga-2026!` |
| Participant | voir la liste ci-dessous | `Joinly-Membre-2026!` |

L’administrateur de démonstration s’appelle Camille Laurent. Il a les rôles
membre et administrateur. Il n’a pas le rôle organisateur : pour publier une
activité, utiliser un compte organisateur.

### Organisateurs

- `lea.moreau@demo.joinly.fr` — Léa Moreau
- `hugo.bernard@demo.joinly.fr` — Hugo Bernard
- `ines.benali@demo.joinly.fr` — Inès Benali
- `thomas.nguyen@demo.joinly.fr` — Thomas Nguyen
- `chloe.martin@demo.joinly.fr` — Chloé Martin

### Participants

Trente-quatre comptes, du type `marie.dupont@demo.joinly.fr` (Marie Dupont),
`lucas.petit@demo.joinly.fr`, `emma.rousseau@demo.joinly.fr`, et les autres
prénoms et noms définis dans `app/seed_demo.py`. Le mot de passe est le même
pour tous : `Joinly-Membre-2026!`.

## Contenu chargé

- Les catégories utiles au catalogue, sans écraser celles qui existent.
- Les questions de FAQ manquantes. Une réponse déjà en base n’est pas réécrite.
- Les textes légaux de référence, seulement s’il n’y a pas encore de version
  publiée ou si la version publiée contient encore un ancien texte de
  démonstration (« à renseigner », « Document de démonstration »).
- Environ 50 activités autour de Paris et de l’Île-de-France : à venir, passées,
  brouillons et deux annulations. Les dates sont calculées à partir du jour où
  la commande est lancée. Un second lancement conserve les dates déjà enregistrées.
- Des inscriptions confirmées, en dessous ou au niveau de la capacité, pour que
  les fiches affichent des taux de remplissage variés.

Il n’y a pas de tarif : le modèle des activités ne contient pas de prix. Toutes
les activités restent gratuites. Il n’y a pas non plus de table d’avis.

## À ne pas confondre

`scripts/seed.py` sans `--demo` prépare seulement les catégories, la FAQ, les
pages légales et, s’il n’existe aucun administrateur, le compte technique
`admin@joinly.test`. Son mot de passe aléatoire est écrit dans
`.local/initial-admin.txt`, qui n’est pas versionné. Ce n’est pas le compte
`admin.demo@demo.joinly.fr`.
