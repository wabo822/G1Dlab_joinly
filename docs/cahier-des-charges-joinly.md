# Cahier des charges de Joinly

**Projet :** Joinly  
**Équipe :** G1D Lab  
**Version :** 0.2  
**Date :** 20 octobre 2026  
**Statut :** Proposition de cadrage à valider avec le tuteur et le client

## 1 Présentation du projet

Joinly est une application web de découverte et de réservation d’activités. Elle met en relation des personnes partageant des centres d’intérêt et des organisateurs proposant des sorties, rencontres, ateliers ou activités sportives et culturelles.

Le projet doit permettre de passer d’un site de présentation statique à une application complète, reliant une interface web, un serveur et une base de données. Le présent cahier des charges définit les besoins, le périmètre fonctionnel, les règles de gestion et les conditions de recette. Les exigences pédagogiques reprises du README conservent leurs priorités ; les propositions propres à Joinly restent soumises à validation.

### 1.1 Besoin auquel répond Joinly

Une personne souhaitant participer à une activité doit pouvoir trouver une proposition, comprendre son déroulement et réserver une place sans multiplier les échanges. L’organisateur doit pouvoir publier les informations utiles, limiter le nombre d’inscrits et retrouver les participants dans un même espace.

### 1.2 Publics concernés

- Les particuliers recherchant des activités et de nouvelles rencontres.
- Les organisateurs particuliers, associatifs ou professionnels souhaitant proposer un événement.
- Les administrateurs chargés des comptes, des droits et des contenus institutionnels.
- À terme, les commerces et lieux souhaitant présenter des activités ; cette extension reste à valider.

### 1.3 Objectifs et indicateurs de réussite

| Objectif | Vérification attendue |
| --- | --- |
| Faciliter la découverte | Un visiteur recherche une activité et consulte une fiche complète. |
| Simplifier la participation | Un membre réserve une place et retrouve son inscription après reconnexion. |
| Faciliter l’organisation | Un organisateur publie un événement et consulte ses inscriptions. |
| Garantir la cohérence des places | Deux demandes simultanées pour la dernière place ne créent pas de surréservation. |
| Livrer une application complète | Les données sont conservées en base et les droits sont contrôlés côté serveur. |
| Respecter le socle pédagogique | Chaque exigence de priorité élevée dispose d’une démonstration de recette concluante. |

## 2 État initial et références

Le dépôt de référence est [wabo822/G1Dlab_joinly](https://github.com/wabo822/G1Dlab_joinly). L’examen distant a porté sur le commit `865df9f72964251b8eabda0a308b18be70286052`, dont le message est « change style of the website ».

| Élément observé | État au moment du cadrage |
| --- | --- |
| Accueil | Maquette HTML en anglais avec catégories, exemples d’activités et présentation d’une offre destinée aux commerces. |
| Activités et présentation | Pages statiques en français, avec activités fictives. |
| Présentation graphique | CSS, logos et ressources graphiques présents. |
| Accès principal | Le fichier racine `index.html` redirige vers `joinly_front/index.html`. |
| Recherche, compte et réservation | Des liens ou formulaires sont visibles, mais aucun service correspondant n’est livré dans l’arborescence examinée. |
| Serveur et base de données | Aucun backend ni schéma de base de données livré dans l’arborescence examinée. |

Les liens vers `explore.html`, `activity.html`, `host.html`, `login.html`, `signup.html`, `business.html`, `venue.html` et `contact.html` désignent des pages absentes de cette version. Ils décrivent une intention de navigation et ne constituent pas des fonctionnalités opérationnelles.

Les annonces de profils vérifiés, de discussion de groupe, d’avis, de signalement et de blocage ne constituent pas des engagements acquis. Elles devront être développées après validation ou reformulées avant livraison. Le README fournit les 22 exigences pédagogiques et les pistes économiques ; leur transcription ne remplace pas la validation du document pédagogique d’origine par le tuteur.

## 3 Périmètre et priorités

### 3.1 Socle pédagogique

Les exigences de priorité **élevée** constituent le socle obligatoire indiqué dans le README. Les exigences de priorité **moyenne** et **faible** seront réalisées selon l’avancement et les arbitrages du tuteur et du client.

### 3.2 Proposition de première version métier

En complément du socle, la première version proposée couvre les activités gratuites : catalogue, fiche détaillée, création et modification d’événements, réservation, annulation et liste des participants. Cette boucle constitue la valeur principale de Joinly. Sa priorité est **proposée élevée**, mais reste à approuver ; elle ne remplace pas les obligations pédagogiques.

### 3.3 Extensions non incluses dans la première version proposée

Le paiement réel, les commissions, les abonnements, la location de matériel, les prestations complémentaires, la carte interactive, les événements récurrents, les avis, la vérification téléphonique et les fonctions de réseau social ne sont pas inclus dans cette première version proposée. Leur ajout nécessite une décision de périmètre, une estimation et des critères de recette dédiés.

### 3.4 Assistant IA ajouté au périmètre

À la demande de l'équipe le 20 octobre 2026, le chatbot entre dans le périmètre proposé avec une **priorité moyenne proposée**, après le socle obligatoire et le parcours de réservation. Il recommande des activités à partir du profil autorisé, répond aux questions sur Joinly à partir de contenus fixes ajoutés au prompt et permet des questions générales. Son périmètre et sa priorité restent à valider avec le client. Le prototype utilisera une API de modèle existant et du prompt engineering, sans entraînement. La cible d'exploitation est un modèle à poids ouverts hébergé sur l'infrastructure contrôlée du projet. Ces services ne sont pas encore implémentés dans le dépôt.

La messagerie, le forum, le multilingue et leurs fonctions d’administration restent inscrits dans le catalogue pédagogique à priorité faible. Les pages commerciales de la maquette ne rendent pas obligatoire un portail professionnel.

## 4 Acteurs et droits proposés

| Action | Visiteur | Membre participant | Organisateur | Administrateur |
| --- | --- | --- | --- | --- |
| Consulter les activités publiées et les pages publiques | Oui | Oui | Oui | Oui |
| Créer un compte et se connecter | Oui | Oui | Oui | Oui |
| Modifier un profil | Non | Le sien | Le sien | Gestion des comptes selon habilitation |
| Réserver ou annuler une place | Non | Pour lui-même | Pour lui-même | Intervention exceptionnelle à définir |
| Créer une activité | Non | Non | Oui | Selon habilitation à valider |
| Modifier ou annuler une activité | Non | Non | Ses activités uniquement | Modération à valider |
| Consulter la liste des inscrits | Non | Sa propre inscription | Ses activités uniquement | Selon habilitation |
| Administrer les comptes et les droits | Non | Non | Non | Oui |
| Administrer la FAQ et les pages légales | Non | Non | Non | Oui |
| Poser des questions à l'assistant | Informations publiques | Oui | Oui | Oui, sans accès privé supplémentaire via le chat |
| Obtenir des recommandations personnalisées | Préférences de session | Son profil, avec accord | Son profil, avec accord | Son profil, avec accord |
| Valider les contenus de contexte du chatbot | Non | Non | Non | Oui, selon habilitation |

Le rôle organisateur est proposé comme une habilitation ajoutée au compte membre. Son mode d’attribution reste à valider. Le rôle administrateur ne peut jamais être obtenu par une inscription publique ou par modification de son propre profil. Les contrôles sont effectués sur le serveur, y compris en cas d’appel direct à une URL ou à l’API.

## 5 Exigences fonctionnelles pédagogiques

Les identifiants permettent de relier les développements, les anomalies et les tests à une exigence. Les critères ci-dessous sont les conditions de recette proposées pour les fonctionnalités décrites dans le README.

| ID | Exigence | Priorité | Critère de recette |
| --- | --- | --- | --- |
| F01 | Page d’accueil | Élevée | Présenter Joinly et permettre d’accéder au catalogue, à l’inscription et à la connexion, sans lien principal cassé. |
| F02 | Inscription avec différents profils | Élevée | Créer un compte avec un courriel unique ; refuser les données invalides et toute attribution publique du rôle administrateur. |
| F03 | Authentification | Élevée | Permettre la connexion avec des identifiants valides, refuser les autres et invalider la session à la déconnexion. |
| F04 | Édition du profil | Élevée | Enregistrer les modifications autorisées et les retrouver après reconnexion ; interdire l’édition du profil d’un autre membre. |
| F05 | FAQ publique | Élevée | Afficher les questions et réponses publiées par l’administration. |
| F06 | CGU et mentions légales | Élevée | Rendre ces deux contenus accessibles depuis toutes les pages par le pied de page. |
| F07 | Recherche simple | Élevée | Rechercher sans distinction de casse dans le titre et la description des activités publiées ; afficher un état explicite sans résultat. |
| F08 | Administration des utilisateurs et droits | Élevée | Permettre à un administrateur habilité de consulter les comptes, modifier les habilitations et suspendre un compte ; refuser ces actions aux autres profils. |
| F09 | Administration de la FAQ | Élevée | Créer, modifier et retirer une entrée ; vérifier la mise à jour de la FAQ publique. |
| F10 | Administration des CGU | Élevée | Modifier et publier les CGU ; afficher la version publiée et sa date de mise à jour. |
| F11 | Administration des mentions légales | Élevée | Modifier et publier le contenu ; vérifier sa restitution sur la page publique. |
| F12 | Contact | Élevée | Proposer un moyen de contact opérationnel. Si un formulaire est retenu, valider ses champs, transmettre ou enregistrer la demande et confirmer sa prise en compte. |
| F13 | Mot de passe oublié | Moyenne | Envoyer un lien temporaire à usage unique ; refuser un lien expiré ou déjà utilisé, sans révéler si un courriel possède un compte. |
| F14 | Recherche avancée | Moyenne | Combiner au minimum catégorie, lieu et intervalle de dates ; réinitialiser les filtres et gérer l’absence de résultat. |
| F15 | Adaptation aux écrans | Moyenne | Permettre les parcours principaux à 375, 768 et 1440 pixels de largeur sans défilement horizontal du contenu principal. |
| F16 | Messagerie interne | Faible | Si retenue, permettre l’échange entre utilisateurs autorisés et refuser l’accès aux conversations d’autrui. |
| F17 | Forum | Faible | Si retenu, permettre de consulter des sujets, publier avec un compte et retrouver les réponses enregistrées. |
| F18 | Accessibilité renforcée | Faible | Si retenue, contrôler les parcours au clavier, les libellés, le focus, les textes alternatifs et la lisibilité selon une grille de recette convenue. |
| F19 | Site multilingue | Faible | Si retenu, proposer un changement de langue cohérent sur les pages du périmètre et définir un comportement pour les contenus non traduits. |
| F20 | Administration du forum | Faible | Si F17 est retenue, permettre la modération des sujets et messages par un administrateur habilité. |
| F21 | Administration de la messagerie | Faible | Si F16 est retenue, définir puis tester les actions de modération et les limites d’accès aux échanges privés. |
| F22 | Administration du rendu visuel | Faible | Si retenue, permettre l’édition des paramètres visuels autorisés sans injection de code ni rupture de navigation. |

La mention « Site multilangues (s’adapte aux handicaps) » rapportée dans le README devra être clarifiée : le multilingue et l’accessibilité sont deux exigences distinctes. Le niveau de priorité de F18 ne dispense pas de conserver les éléments HTML de base nécessaires à l’utilisation des formulaires et de la navigation.

## 6 Exigences propres à Joinly

**Priorité proposée : élevée pour J01 à J07, sous réserve de validation par le tuteur et le client.**

| ID | Fonction | Comportement et recette attendus |
| --- | --- | --- |
| J01 | Catalogue d’activités | Afficher uniquement les événements publiés à venir et leur disponibilité. Une liste vide affiche une explication. |
| J02 | Fiche détaillée | Afficher titre, description, catégorie, date et heure, lieu, organisateur, capacité, disponibilité et gratuité. Une activité inconnue affiche une erreur adaptée. |
| J03 | Création d’événement | L’organisateur saisit les champs obligatoires, enregistre un brouillon puis publie un événement valide. Une date passée ou une capacité non positive bloque la publication. |
| J04 | Modification et annulation | Seul le propriétaire habilité modifie son événement. Une annulation ferme les inscriptions et apparaît dans l’espace des membres déjà inscrits. |
| J05 | Réservation | Un membre connecté réserve une place disponible. Une confirmation est affichée après enregistrement ; un doublon ou un événement complet est refusé sans modifier le nombre de places. |
| J06 | Espace des inscriptions | Le membre consulte ses inscriptions à venir et annulées, puis annule une réservation admissible. La place est libérée une seule fois. |
| J07 | Gestion des participants | L’organisateur consulte les inscriptions confirmées de ses propres événements. La capacité restante correspond au nombre de réservations actives. |

### 6.1 Parcours participant

1. Accéder à l’accueil et rechercher une activité.
2. Ouvrir la fiche et vérifier la date, le lieu et les disponibilités.
3. Créer un compte ou se connecter si nécessaire.
4. Confirmer l’inscription ; le serveur vérifie la disponibilité.
5. Retrouver la réservation dans son espace personnel.
6. Annuler avant le début de l’activité selon les règles retenues.

### 6.2 Parcours organisateur

1. Se connecter avec l’habilitation organisateur.
2. Créer un brouillon et renseigner les informations obligatoires.
3. Publier l’événement, puis le retrouver dans le catalogue public.
4. Consulter les inscriptions et les places restantes.
5. Modifier ou annuler l’événement selon les règles de gestion.

### 6.3 Assistant IA contextualisé

**J08 à J12 : priorité moyenne proposée.** Le prototype utilise une API de
modèle existant et du prompt engineering, sans entraînement. Les textes courts
validés sont ajoutés directement au prompt. Il n'y a ni recherche documentaire
automatique ni index vectoriel : il ne s'agit pas d'un véritable RAG. Le terme
« contexte de projet » désigne ici la présentation de Joinly, l'aide, la FAQ et
les règles validées, pas un accès à tous les fichiers du dépôt.

| ID | Fonction | Comportement et recette attendus |
| --- | --- | --- |
| J08 | Conversation contextualisée | Accès depuis le catalogue et l'espace personnel. Répondre sur Joinly avec les textes validés fournis au prompt, indiquer l'aide source et signaler toute information absente. Un visiteur utilise seulement les informations publiques. |
| J09 | Recommandations selon le profil | Après accord du membre, utiliser ses préférences déclarées pour proposer au plus trois activités de la liste autorisée fournie au modèle, avec motif et lien. Vérifier côté serveur les identifiants et les disponibilités avant affichage. Sans résultat, l'indiquer sans inventer d'activité. |
| J10 | Questions générales | Répondre hors du contexte Joinly en identifiant clairement la réponse générale. Ne pas prétendre disposer d'informations Web en temps réel ni transformer une réponse générale en règle officielle du projet. |
| J11 | Contexte et permissions | Permettre à un administrateur habilité de valider et mettre à jour le contexte, via fichier de configuration versionné pour le prototype. Refuser le profil d'autrui, exclure mots de passe, secrets et documents privés, et désactiver l'utilisation du profil sur demande. |
| J12 | Intégration API puis cible locale | Placer l'appel au modèle derrière une interface serveur configurable. Tester les erreurs, délais et quotas. Préparer le passage à un modèle à poids ouverts local, avec validation distincte de la licence, du matériel, de la qualité et de l'absence d'appel externe silencieux. |

Parcours : ouvrir le chat, choisir l'usage éventuel de ses préférences, poser
une question puis consulter la réponse et les liens proposés. La sélection des
activités repose sur des filtres simples (intérêts, zone choisie, dates, budget,
places). Le modèle formule une explication à partir de cette sélection. Il ne
réserve pas, n'annule pas et ne modifie pas de données. La réservation habituelle
revérifie la capacité, qui peut avoir changé depuis la réponse.

**Limites du prototype :** contexte fixe et court, conversation temporaire de
session, aucune indexation de documents, aucun entraînement ou recherche Web.
Les démonstrations via API utilisent des profils fictifs et des textes publics
validés. Un historique permanent et un vrai RAG restent des extensions à chiffrer.
L'interface distingue information issue du contexte, recommandation et réponse
générale sans présenter les références comme une garantie d'exactitude.

## 7 Règles de gestion proposées

| ID | Règle |
| --- | --- |
| RG01 | Un courriel normalisé identifie un seul compte. Un compte suspendu ne peut ni ouvrir une session ni utiliser une session existante pour une action protégée. |
| RG02 | Chaque événement possède un organisateur propriétaire et une capacité entière strictement positive. |
| RG03 | Les événements ont les états brouillon, publié et annulé. Un événement terminé est identifié à partir de sa date de fin. |
| RG04 | Seul un événement publié, non annulé, non commencé et disposant d’une place peut être réservé. |
| RG05 | Une réservation correspond à un membre et une place. Un même membre ne possède qu’une réservation active par événement. Les réservations de groupe sont hors périmètre initial. |
| RG06 | La vérification de capacité et l’enregistrement d’une réservation forment une opération atomique côté serveur. Une contrainte d’unicité empêche les doublons actifs. |
| RG07 | Les places disponibles sont égales à la capacité moins les réservations confirmées. Elles ne deviennent jamais négatives. |
| RG08 | Un membre peut annuler avant le début de l’événement. Une nouvelle réservation après annulation est possible si les conditions restent remplies. |
| RG09 | Une capacité ne peut pas être réduite sous le nombre d’inscrits actifs. Un événement ayant des inscriptions est annulé et conservé dans l’historique plutôt que supprimé physiquement. |
| RG10 | L’annulation d’un événement ferme les réservations et annule les inscriptions actives de manière cohérente. Le participant voit le changement dans son espace. Un courriel automatique est une extension à chiffrer. |
| RG11 | Les changements de date ou de lieu après une inscription exigent une règle validée. En première version proposée, ils sont bloqués ; l’organisateur peut annuler puis publier un nouvel événement. |
| RG12 | Les coordonnées privées des participants ne sont pas exposées dans le catalogue ou les fiches publiques. L’organisateur ne voit que les informations nécessaires à l’accueil. |
| RG13 | Les instants sont enregistrés de manière cohérente et affichés avec le fuseau de l’événement. Le périmètre initial proposé utilise Europe/Paris. |

## 8 Données à gérer

Le modèle suivant constitue une base de conception ; le schéma physique sera validé après le choix de la base de données.

| Entité | Principales données | Relations et contraintes |
| --- | --- | --- |
| Utilisateur | Identifiant, nom affiché, courriel, empreinte du mot de passe, état, dates de création et modification | Courriel unique ; rôles attribués selon habilitation. |
| Préférences du membre | Centres d’intérêt, zone choisie, dates et budget facultatifs, accord d’utilisation par l’assistant | Liées au membre ; modifiables et non publiques. |
| Contexte de l’assistant | Textes courts validés, références d’aide, version et date | Configuration versionnée du prototype, sans base vectorielle. |
| Rôle | Identifiant, nom et permissions | Un compte peut cumuler les habilitations membre et organisateur. |
| Catégorie | Identifiant, libellé | Une catégorie peut regrouper plusieurs événements. |
| Événement | Identifiant, titre, description, catégorie, lieu, début, fin, fuseau, capacité, état, organisateur | Un propriétaire ; début antérieur à la fin ; capacité positive. |
| Réservation | Identifiant, membre, événement, état, date de réservation et date d’annulation | États confirmé et annulé ; unicité de la réservation active par couple membre et événement. |
| FAQ | Question, réponse, ordre et état de publication | Édition réservée à l’administration. |
| Page institutionnelle | Type, contenu, version, état et date de publication | CGU et mentions légales gérées séparément. |
| Demande de contact | Coordonnées de réponse, objet, message et date | À conserver seulement si le formulaire avec stockage est retenu. |

Le prix et les transactions seront ajoutés uniquement si les activités payantes entrent dans le périmètre. Les données fictives de démonstration doivent être identifiables et séparées des données d’utilisation réelle.

## 9 Exigences techniques et de qualité

### 9.1 Architecture et déploiement

L’application cible comprend un frontend, un backend assurant les règles métier et une base persistante. Le choix des langages, frameworks, moteurs de base et mécanismes de session reste à valider : aucun framework ne doit être présenté comme déjà retenu.

La configuration Hangar décrite dans le README sert actuellement la racine du dépôt depuis `/var/www/html`. La redirection racine doit rester opérationnelle tant que cette configuration est conservée. Avant de retenir le backend, l’équipe doit vérifier que l’hébergement autorise son exécution, l’accès à la base et la configuration des variables d’environnement. Le déploiement statique actuel ne démontre pas cette compatibilité.

Le dépôt doit fournir les instructions d’installation, les commandes de lancement, la configuration sans secret et la procédure de création ou de migration de la base. Le passage entre démonstration et exploitation réelle doit être explicitement identifié.

### 9.1.1 Service IA et migration locale

Flux du prototype : interface de chat, API serveur, composition du prompt avec
contexte fixe et données autorisées, appel au modèle externe, validation des
liens d'activités, réponse. La clé API ne parvient jamais au navigateur. Une
limite de taille du contexte, de requêtes et un délai maximal sont configurés
côté serveur. Leur valeur et le budget seront validés avant démonstration.

La cible d'exploitation remplace le fournisseur externe par un modèle à poids
ouverts exécuté sur une machine contrôlée par le projet. Aucun entraînement
spécifique n'est prévu. La licence d'utilisation, la mémoire, le matériel et
l'hébergement doivent faire l'objet d'un essai avant engagement. Hangar ne doit
pas être présumé compatible avec l'inférence locale. La migration sera acceptée
après vérification des réponses et des temps de réponse sur le même jeu de tests.

Cette cible réduit les transmissions vers un service de modèle tiers. Elle ne
garantit pas à elle seule l'absence de fuite : vérifier les accès, les flux réseau,
les journaux et les sauvegardes. Aucun basculement automatique non annoncé vers
une API externe n'est autorisé en mode local. Les messages et textes fournis au
modèle sont des données, jamais une autorisation de contourner les droits.

### 9.2 Sécurité et confidentialité

- Vérifier les données et les permissions côté serveur pour chaque opération protégée.
- Stocker les mots de passe avec une fonction de hachage adaptée aux mots de passe ; ne jamais les enregistrer en clair ni les retourner dans une réponse.
- Protéger les sessions, invalider les accès à la déconnexion et éviter d’exposer les secrets dans le navigateur, le dépôt ou les journaux.
- Utiliser des requêtes paramétrées et traiter les contenus utilisateurs pour prévenir l’injection de commandes et de scripts.
- Prévoir une limitation des tentatives de connexion et des envois de formulaire ; protéger les opérations contre les requêtes forgées selon le mécanisme d’authentification choisi.
- Utiliser HTTPS pour un déploiement accessible au public et limiter les messages d’erreur aux informations utiles.
- Définir les données collectées, leurs usages, leurs durées de conservation et la procédure de traitement des demandes relatives aux données personnelles avant une ouverture réelle.

Les textes juridiques, les durées de conservation et l’identité de l’exploitant devront être validés par le responsable du projet. Cette liste définit des exigences de conception ; elle ne constitue pas une certification juridique ou de sécurité.

### 9.3 Interface et cohérence éditoriale

La charte doit reprendre l’identité Joinly : logos, bleu principal, violet et accents corail, avec des contrastes lisibles. Les pages anciennes et nouvelles doivent partager une navigation cohérente. Les formulaires doivent présenter leurs libellés, les erreurs et les confirmations de manière compréhensible.

Le français est proposé comme langue de référence de la première livraison, à confirmer en raison de l’accueil actuellement rédigé en anglais. Le choix d’une langue principale ne rend pas obligatoire le multilingue. Les ressources externes, dont les polices, doivent disposer d’un repli utilisable.

Les liens doivent conduire à une page existante, être retirés ou être clairement présentés comme indisponibles. Une maquette ne doit pas promettre une vérification d’identité ou une équipe de modération opérationnelle avant leur mise en place.

### 9.4 Objectifs mesurables proposés

| Domaine | Objectif de recette proposé |
| --- | --- |
| Compatibilité | Exécuter le parcours principal sur Chrome, Firefox et Safari disponibles au moment de la recette ; consigner les versions testées. |
| Performance | Sur l’environnement de recette documenté, viser moins de 2 secondes pour 95 % des réponses de recherche et réservation, avec 1 000 événements et 20 utilisateurs simulés simultanés. Objectif à confirmer après choix de l’hébergement. |
| Persistance | Retrouver comptes, événements et réservations après redémarrage de l’application. |
| Fiabilité | Aucun dépassement de capacité ni doublon actif pendant les tests de concurrence. |
| Restauration | Réaliser une sauvegarde de la base de démonstration et vérifier sa restauration avant livraison. |

Ces valeurs sont des cibles proposées, pas des performances déjà mesurées. Les modalités de mesure et les capacités de l’hébergement doivent être approuvées avant leur contractualisation.

## 10 Modèle économique envisagé

Le modèle principal envisagé repose sur une commission sur les réservations d’activités payantes. La navigation, la recherche et l’inscription aux activités gratuites resteraient gratuites. Aucun taux, prix ou revenu prévisionnel n’est fixé à ce stade.

Les pistes complémentaires du README comprennent la location de matériel, les services supplémentaires, l’encadrement professionnel, les formules d’activité, Joinly Plus, l’abonnement organisateur Pro, le sponsoring, les offres d’entreprise, l’affiliation, les activités organisées par Joinly et les services ponctuels aux organisateurs. Elles constituent des perspectives économiques et non des obligations de la première livraison. Les commissions ne doivent pas être cumulées automatiquement sur une même vente.

Si le paiement entre ultérieurement dans le périmètre, une spécification devra préciser le prestataire, le fonctionnement en environnement de test, les états de paiement, les confirmations serveur, les annulations et les remboursements. Un simple retour vers une page de succès ne suffira pas à confirmer un paiement.

## 11 Organisation et planning proposé

Le calendrier ci-dessous décrit un ordre de réalisation, sans inventer de dates de remise ni de répartition nominative. Les responsables et échéances seront fixés avec le groupe.

| Phase | Travaux | Condition de passage |
| --- | --- | --- |
| 1 Cadrage | Valider les exigences, les rôles et les exclusions | Périmètre approuvé par le tuteur et le client. |
| 2 Conception | Maquettes, choix techniques, modèle de données et vérification de Hangar | Parcours et architecture réalisables sur l’hébergement retenu. |
| 3 Socle | Comptes, authentification, profil, contenus publics et administration obligatoire | Recette des exigences pédagogiques élevées concernées. |
| 4 Parcours métier | Catalogue, événements et réservations selon validation | Parcours participant et organisateur complets, capacités cohérentes. |
| 5 Compléments | Assistant IA par API et prompts contextualisés, essai du modèle local, autres priorités moyennes puis faibles | Aucun report du socle obligatoire sans arbitrage explicite. |
| 6 Livraison | Recette complète, corrections, déploiement et documentation | Aucun défaut bloquant sur le périmètre validé. |

Les évolutions doivent être préparées sur des branches dédiées, accompagnées de commits explicites et relues au moyen de pull requests conformément au README. Une modification de périmètre met à jour ce document et la liste de recette avant développement.

## 12 Plan de recette

Chaque exigence retenue de F01 à F22 et J01 à J12 doit disposer d’un résultat de recette, de la version testée et d’une preuve appropriée. Les scénarios suivants complètent ces critères avec les cas transversaux les plus importants.

| ID | Scénario | Résultat attendu |
| --- | --- | --- |
| R01 | Créer deux comptes avec le même courriel | Le second est refusé avec une erreur compréhensible. |
| R02 | Modifier directement l’identifiant d’un profil ou événement dans une requête | L’accès non autorisé est refusé côté serveur. |
| R03 | Rechercher un terme absent | Une liste vide expliquée apparaît sans erreur technique. |
| R04 | Publier avec une date passée ou une capacité nulle | La publication est bloquée et le champ concerné est identifié. |
| R05 | Réserver la dernière place depuis deux comptes simultanément | Une seule réservation est confirmée ; l’autre demande est refusée. |
| R06 | Envoyer deux fois une même réservation | Une seule inscription active et une seule place consommée. |
| R07 | Annuler deux fois la même réservation | Une seule place libérée et un état final cohérent. |
| R08 | Annuler un événement avec des inscrits | L’événement devient indisponible et les membres voient leurs inscriptions annulées. |
| R09 | Réduire une capacité sous le nombre d’inscrits | La modification est refusée sans altérer l’événement. |
| R10 | Accéder au back-office comme membre | L’accès est refusé sans exposer les informations administratives. |
| R11 | Publier une modification de FAQ, de CGU ou de mentions légales | La version publique correspond au contenu publié par l’administrateur. |
| R12 | Se déconnecter puis réutiliser la session précédente | Toute action protégée est refusée. |
| R13 | Redémarrer puis restaurer la base de démonstration | Les données attendues sont retrouvées et les réservations restent cohérentes. |
| R14 | Parcourir les liens et formulaires principaux | Aucune page manquante, confirmation trompeuse ou fonctionnalité fictive présentée comme opérationnelle. |
| R15 | Poser une question couverte puis absente du contexte Joinly | Restituer les règles fournies avec référence d'aide ; signaler l'absence d'information sans inventer une règle. |
| R16 | Demander des recommandations avec profil fictif, profil vide puis catalogue vide | Proposer au plus trois activités réellement éligibles avec motif et lien, demander les préférences manquantes ou indiquer l'absence de résultat. |
| R17 | Demander le profil d'autrui ou tenter de contourner les instructions par le chat | Aucun profil tiers, secret ou document privé n'est transmis au modèle ni exposé dans la réponse. |
| R18 | Poser une question générale et demander une réservation dans le chat | La réponse générale est identifiée ; aucune réservation ni modification n'est effectuée par le chatbot. |
| R19 | Simuler délai dépassé, panne, quota atteint et désactivation du profil | Afficher un repli compréhensible, conserver le site utilisable et exclure le profil du contexte après désactivation. |
| R20 | Exécuter le même jeu de questions en mode local et surveiller les flux sortants | Vérifier les critères de réponse convenus, les temps mesurés et l'absence de requête vers un fournisseur IA externe. Ce scénario valide la cible locale avant usage réel. |

La recette finale exige que toutes les fonctions de priorité élevée et les fonctions métier approuvées soient démontrables, que les anomalies bloquantes soient corrigées et que les limites restantes soient documentées. Une apparence conforme à la maquette ne suffit pas à valider une fonction dépendant du serveur ou de la base.

## 13 Livrables attendus

- Le cahier des charges validé et son historique de révision.
- Les maquettes et la description des parcours retenus.
- Le code source versionné du frontend et du backend.
- Les prompts, le contexte validé, le jeu de tests du chatbot et la configuration API/local sans secret, si le lot IA est approuvé.
- Le modèle de données, les scripts de création ou migration et un jeu de démonstration.
- Une version déployée sur l’hébergement retenu.
- Un guide d’installation et de déploiement sans secret.
- Un guide court pour les participants, organisateurs et administrateurs.
- Un bilan de recette reliant chaque exigence retenue à son résultat, avec les limites connues.

## 14 Risques et décisions à valider

| Sujet | Risque ou décision | Action proposée |
| --- | --- | --- |
| Périmètre trop large | Les fonctions commerciales et sociales peuvent retarder la réservation et le socle imposé. | Valider d’abord le socle et la boucle gratuite ; chiffrer les extensions séparément. |
| Hébergement | Hangar est documenté pour le site statique uniquement. | Vérifier l’exécution du serveur, la base, les sauvegardes et les secrets avant choix technique. |
| Priorités métier | Le document source ne fixe pas les priorités des fonctions propres à Joinly. | Faire approuver J01 à J07 et leur priorité proposée. |
| Profils et droits | Le mode d’accès au statut organisateur reste indéterminé. | Valider les habilitations et leur attribution avant de développer les écrans. |
| Langue | L’accueil est anglais tandis que les anciennes pages sont françaises. | Choisir une langue de référence puis harmoniser les textes. |
| Promesses de la maquette | Vérification, avis et modération sont annoncés sans service livré. | Retirer ou qualifier les promesses hors périmètre. |
| Pages institutionnelles | Les coordonnées de l’exploitant et les contenus définitifs ne sont pas fixés. | Faire fournir et valider les textes avant publication réelle. |
| Contact | Le canal de réception n’est pas décidé. | Choisir une adresse opérationnelle ou un formulaire avec destinataire ou stockage. |
| Paiement | La commission suppose un parcours supplémentaire avec traitement des échecs. | Confirmer son exclusion initiale ou rédiger une spécification dédiée. |
| Assistant IA | Qualité des réponses, budget API et capacité matérielle locale non mesurés. | Valider prompts, contexte fixe et jeu de tests ; utiliser des profils fictifs par API puis qualifier le modèle local avant exploitation. |
| Planning et moyens | Échéances, effectif disponible et budget ne sont pas fixés ici. | Renseigner les responsables, dates et coûts validés avant engagement. |

### Validation du cadrage

| Partie | Nom | Date | Décision et réserves |
| --- | --- | --- | --- |
| Équipe G1D Lab | À renseigner | À renseigner | À renseigner |
| Tuteur | À renseigner | À renseigner | À renseigner |
| Client | À renseigner | À renseigner | À renseigner |

Après validation, les décisions de périmètre et les règles de gestion approuvées remplacent les propositions correspondantes et donnent lieu à une nouvelle version du document.

### Historique de révision

- 0.2, 20 octobre 2026 : ajout de l’assistant IA contextualisé, recommandations selon le profil, prototype API et prompt engineering, cible de modèle local à poids ouverts. Un vrai RAG reste hors du prototype.
