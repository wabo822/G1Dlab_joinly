# Recette de Joinly V1 — 6 novembre 2026

Première version du socle obligatoire et des activités gratuites. Tests effectués
sur PostgreSQL 16, Python 3.12 et Chromium. Les données des tests sont isolées dans
`joinly_test` ; les activités visibles dans la démo sont explicitement fictives.

| Exigence | Livraison / vérification |
| --- | --- |
| F01 Accueil | Nouvelle page reliée au catalogue réel, navigation principale vérifiée au navigateur. |
| F02 Inscription | Membre ou organisateur ; e-mail normalisé unique ; refus d’auto-attribution admin ; mots de passe hachés. |
| F03 Authentification | Connexion, déconnexion, expiration et révocation ; compte suspendu bloqué. |
| F04 Profil | Nom, centres d’intérêt, zone, consentement ; changement e-mail/mot de passe avec vérification du secret actuel. |
| F05 FAQ | Lecture des contenus publiés uniquement. |
| F06 CGU / mentions | Pages accessibles dans tous les pieds de page, version et date ; contenus initiaux de démonstration à valider. |
| F07 Recherche | Mot-clé dans titre/description, sans distinction de casse ; état vide. |
| F08 Administration comptes | Rôles, suspension et révocation des sessions ; interdiction de modifier ses propres droits. |
| F09 Administration FAQ | Création, modification, retrait de publication. |
| F10–F11 Pages légales | Édition et publication de versions conservées. |
| F12 Contact | Champs validés, stockage, confirmation et traitement en administration. |
| F13 Mot de passe oublié | Flux et transport SMTP simulé testés, token à usage unique et expirant ; service mail réel à configurer. |
| F14 Recherche avancée | Catégorie, lieu et dates combinables, réinitialisation et pagination. |
| F15 Responsive | Absence de débordement horizontal à 375/768/1440 px sur les pages principales et le back-office. |
| J01–J02 Catalogue / détail | Activités publiées futures, places réelles ; brouillons invisibles aux autres comptes. |
| J03 Organisation | Création, brouillon et publication avec validation des dates et capacités. |
| J04 Modifications / annulation | Propriétaire seulement ; dates/lieu bloqués après inscription ; annulation atomique des inscriptions. |
| J05 Réservation | Unicité et transaction ; deux tentatives concurrentes sur la dernière place donnent un seul succès. |
| J06 Espace membre | Historique, annulation avant le début et réinscription ; double annulation sans effet supplémentaire. |
| J07 Participants | Organisateur propriétaire uniquement ; pas d’adresse e-mail des participants exposée. |

## Résultats

- 18 tests automatisés de backend réussis, dont deux tests concurrents.
- Parcours navigateur : inscription organisateur → création/publication → inscription
  membre → réservation → liste des participants → annulation → contact → lecture
  administrative du message.
- Contrôle des mises en page à trois largeurs et absence d’erreur JavaScript.
- Contraintes SQL de la première migration déjà testées ; migrations 001 et 002
  appliquées sur la base de développement et sur la base isolée de tests.
- Connexion application et endpoint `/health` vérifiés.
- Audit des dépendances : aucune vulnérabilité connue signalée après mise à jour
  de Flask vers 3.1.3 et de python-dotenv vers 1.2.2.

## Limites explicites

Le chatbot J08–J12, la messagerie, le forum, le multilingue, le paiement et les
autres pistes économiques restent hors de cette première version. Aucune API IA
n’est appelée. Le consentement est conservé pour une intégration future.

Les contenus légaux et l’identité du responsable ne sont pas une validation
juridique ; le propriétaire du projet doit les compléter. La V1 est accessible en HTTPS sur `isep.wangjiahan.com`. Le test supplémentaire
valide les formulaires HTTPS derrière le proxy et le contrôle des hôtes.
SMTP, la politique de conservation et les sauvegardes automatiques restent à
configurer. Hangar continue de servir la
maquette jusqu’à adaptation de son déploiement.

Les tests responsives et les bonnes pratiques HTML ne constituent pas un audit
d’accessibilité complet. Le back-office liste tous les comptes et contacts, ce
qui convient au prototype ; pagination et audit administratif seront à compléter
pour une communauté importante.
