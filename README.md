<p align="center">
  <img src="logo.PNG" alt="Logo Joinly" width="640" />
</p>

# Joinly — par G1D Lab

**Découvrir des activités, réserver sa place et rencontrer de nouvelles personnes.**

Joinly est un projet de groupe porté par **G1D Lab**. Notre objectif est de
développer une application web full-stack de découverte et de réservation
d'activités, inspirée du principe de Meetup.

La plateforme permettra de réunir des personnes autour de centres d'intérêt
communs et de faciliter l'organisation d'événements : sorties, rencontres,
ateliers ou activités sportives et culturelles.

## État du projet

Le projet est en phase de conception. Ce dépôt contient actuellement la
présentation du projet et les premiers éléments de son identité visuelle.
Les fonctionnalités décrites ci-dessous constituent le périmètre envisagé ;
elles ne sont pas encore implémentées dans ce dépôt.

## Objectifs

- Faciliter la découverte d'activités correspondant aux envies des utilisateurs.
- Simplifier la réservation d'une place et le suivi de ses inscriptions.
- Permettre aux organisateurs de publier et de gérer leurs événements.
- Proposer une expérience accessible sur ordinateur et sur mobile.
- Réaliser une application complète reliant interface web, serveur et base de données.

## Fonctionnalités prévues

| Domaine | Fonctionnalités envisagées |
| --- | --- |
| Comptes utilisateurs | Inscription, connexion et gestion du profil. |
| Découverte | Liste des activités et recherche par catégorie, lieu ou date. |
| Détail d'une activité | Description, date, lieu, organisateur et places disponibles. |
| Réservations | Inscription à une activité, annulation et consultation de ses réservations. |
| Organisation | Création et modification d'événements, gestion des capacités et des participants. |
| Interface | Navigation adaptée aux écrans d'ordinateur et de mobile. |

## Parcours utilisateur envisagé

1. Découvrir les activités proposées.
2. Consulter les informations d'un événement.
3. Créer un compte ou se connecter.
4. Réserver une place, selon les disponibilités.
5. Retrouver ses inscriptions dans son espace personnel.
6. Participer à l'activité et rencontrer les autres participants.

## Architecture envisagée

Le projet sera organisé autour de trois composants :

- **Frontend** : interface de découverte, de réservation et de gestion des activités.
- **Backend / API** : authentification, règles de réservation et gestion des événements.
- **Base de données** : stockage des utilisateurs, des activités et des réservations.

Les technologies, la structure du code et les modalités de déploiement seront
précisées lorsque les choix techniques du groupe auront été validés.

## Identité visuelle

Le nom du produit est **Joinly** et celui de l'entreprise du projet est **G1D Lab**.
Les visuels explorent les thèmes de la rencontre, du lien et de la participation,
avec des formes humaines et des dégradés de bleu, violet, rose et orange.

| Fichier | Contenu |
| --- | --- |
| [logo.PNG](logo.PNG) | Logo Joinly avec symbole et nom, présenté en tête de ce README. |
| [logo1.PNG](logo1.PNG) | Planche de variantes et exemples d'utilisation de l'identité visuelle. |
| [logo2.PNG](logo2.PNG) | Symbole graphique seul. |

## Contenu du dépôt

```text
G1Dlab_joinly/
├── README.md
├── logo.PNG
├── logo1.PNG
└── logo2.PNG
```

## Récupérer le projet

```bash
git clone https://github.com/wabo822/G1Dlab_joinly.git
cd G1Dlab_joinly
```

Aucune application exécutable n'est encore présente. Les prérequis, variables
d'environnement, commandes d'installation, de lancement et de test seront
documentés ici avec l'ajout du code.

## Prochaines étapes

- [x] Ajouter les premiers visuels Joinly.
- [x] Présenter le projet et son périmètre dans le README.
- [ ] Valider le périmètre fonctionnel et les parcours utilisateurs.
- [ ] Choisir les technologies du frontend, du backend et de la base de données.
- [ ] Concevoir les maquettes et le modèle de données.
- [ ] Développer la découverte d'activités et la gestion des événements.
- [ ] Implémenter l'authentification et les réservations.
- [ ] Tester les parcours, notamment les capacités et les annulations.
- [ ] Déployer l'application et compléter la documentation technique.

## Travail en équipe

Pour chaque évolution, créer une branche dédiée, rédiger des commits explicites
et ouvrir une pull request pour permettre une revue par le groupe. Mettre à jour
ce README lorsque les choix techniques ou les instructions de lancement évoluent.

**Projet :** Joinly · **Entreprise du projet :** G1D Lab
