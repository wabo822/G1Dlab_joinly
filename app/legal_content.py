"""Textes légaux de référence du projet étudiant et publication idempotente."""

PLACEHOLDER_MARKERS = (
    'Document de démonstration',
    'à renseigner',
    'restent à renseigner',
    'Prototype pédagogique Joinly',
    'à faire valider',
    'restent à valider',
)

FAQS = (
    (
        'Comment réserver une activité ?',
        'Créez un compte, ouvrez la fiche d’une activité à venir et choisissez « Réserver ma place ». L’inscription confirmée apparaît dans Mon espace.',
    ),
    (
        'Puis-je annuler mon inscription ?',
        'Oui, depuis Mon espace, tant que l’activité n’a pas commencé. La place redevient disponible pour une autre personne.',
    ),
    (
        'Les activités sont-elles payantes ?',
        'Non. Cette version de Joinly propose uniquement des activités gratuites. Aucun paiement n’est demandé ni enregistré.',
    ),
    (
        'Comment organiser une activité ?',
        'Choisissez le profil organisateur lors de l’inscription. Vous pouvez enregistrer un brouillon, puis le publier depuis l’espace organisateur.',
    ),
    (
        'Quelles informations voit l’organisateur ?',
        'L’organisateur voit le nom affiché et la date d’inscription des participants confirmés. Il ne voit pas leur adresse e-mail.',
    ),
    (
        'Joinly est-il un service commercial ?',
        'Non. Joinly est un projet étudiant réalisé dans le cadre du G1D Lab à l’ISEP. Le site sert à présenter et à faire fonctionner cette application de réservation.',
    ),
    (
        'Les activités affichées sont-elles toutes de vrais rendez-vous ?',
        'Les comptes de démonstration utilisent le domaine @demo.joinly.fr. Leurs activités sont des exemples : la fiche le précise et aucun déplacement n’est attendu. Une activité publiée par un autre compte suit les informations indiquées par son organisateur.',
    ),
    (
        'Quels cookies sont utilisés ?',
        'Uniquement un cookie de session, nécessaire à la connexion et à la protection des formulaires. Il n’y a pas de cookie de mesure d’audience ni de publicité. Le détail est dans la politique de confidentialité.',
    ),
    (
        'Comment exercer mes droits sur mes données ?',
        'Écrivez à contact@wangjiahan.com ou utilisez le formulaire de contact. Vous pouvez demander l’accès, la rectification ou l’effacement de vos données. Vous pouvez aussi introduire une réclamation auprès de la CNIL.',
    ),
)

LEGAL_TEXTS = {
    'legal_notice': """## Éditeur du site
Le site Joinly est édité dans le cadre d’un projet étudiant, et non par une société commerciale.

Éditeur : Joinly — projet étudiant réalisé dans le cadre du G1D Lab à l’ISEP, École d’ingénieurs du numérique.
Adresse de l’établissement : 10 rue de Vanves, 92130 Issy-les-Moulineaux, France.
Directeur de la publication : Jiahan Wang.
Contact : contact@wangjiahan.com.

## Hébergeur
Le site est hébergé par Contabo GmbH, Welfenstraße 22, 81541 München, Allemagne.
Cette adresse est celle publiée sur l’impressum de l’hébergeur (contabo.com). Registre : Amtsgericht München, HRB 180722.

## Objet du site
Joinly permet de découvrir des activités gratuites, de créer un compte, de réserver une place et, pour les organisateurs, de publier une activité. Le service est fourni à des fins pédagogiques, dans le cadre du cours G1D Lab.

Certaines fiches sont des exemples de démonstration. Elles sont associées à des comptes @demo.joinly.fr et le précisent dans leur description. Elles ne correspondent pas à un rendez-vous réel.

## Propriété intellectuelle
Les textes, le nom Joinly et les éléments graphiques du site sont utilisés pour ce projet étudiant. Sauf mention contraire, ils ne peuvent pas être repris pour un usage commercial sans accord préalable.

Les contenus déposés par les utilisateurs (titres, descriptions, messages) restent sous leur responsabilité. En les publiant, ils garantissent disposer des droits nécessaires et accordent au projet l’autorisation de les afficher sur le site le temps de leur publication.

## Responsabilité
Les informations publiées par les organisateurs le sont sous leur propre responsabilité. Joinly est un exercice pédagogique : le projet ne garantit pas qu’une activité aura lieu, ni l’exactitude des contenus saisis par les utilisateurs.

## Données personnelles
Le traitement des données personnelles est décrit dans la politique de confidentialité, accessible depuis le pied de page.

## Contact
Pour toute question relative au site, à un contenu ou à vos données : contact@wangjiahan.com, ou le formulaire de contact.""",

    'terms': """## Objet
Les présentes conditions d’utilisation régissent l’accès au site Joinly et l’usage des fonctions de compte, de recherche, de réservation et d’organisation d’activités.

Joinly est un projet étudiant réalisé dans le cadre du G1D Lab à l’ISEP, École d’ingénieurs du numérique, 10 rue de Vanves, 92130 Issy-les-Moulineaux. Il ne s’agit pas d’un service commercial. L’utilisation du site est gratuite.

## Acceptation
Créer un compte ou utiliser une fonction réservée aux personnes connectées vaut acceptation de ces conditions. Si vous ne les acceptez pas, n’utilisez pas ces fonctions. La simple consultation des pages publiques reste possible.

La version affichée sur cette page est la version en vigueur. La date de publication est indiquée en tête de page. Les versions antérieures sont conservées dans l’outil d’administration.

## Accès au service
Le site est fourni en l’état, dans le cadre d’un travail pédagogique. L’accès peut être interrompu pour maintenance, démonstration, correction ou fin du projet, sans indemnisation.

Certaines activités visibles dans le catalogue sont des exemples de démonstration. Leur description l’indique. Ne vous déplacez pas pour ces exemples.

## Compte
L’inscription demande une adresse e-mail, un nom affiché et un mot de passe d’au moins 12 caractères. Le mot de passe est enregistré sous forme de condensat, jamais en clair.

Deux profils peuvent être choisis à l’inscription : participant, ou participant et organisateur. Le rôle d’administrateur n’est pas proposé à l’inscription. Il est attribué séparément par une personne qui l’exerce déjà.

Vous êtes responsable de la confidentialité de votre mot de passe et des actions réalisées depuis votre compte. En cas de doute, modifiez-le depuis Mon espace ou utilisez la fonction « Mot de passe oublié » lorsque l’envoi d’e-mails est configuré.

Un compte peut être suspendu s’il sert à un usage contraire à ces conditions. La suspension coupe l’accès et révoque les sessions en cours.

## Activités et inscriptions
Les activités de cette version sont gratuites. Aucun paiement n’est proposé ni enregistré.

Une inscription confirmée correspond à une place. Elle est possible seulement si l’activité est publiée, n’a pas commencé et s’il reste une place. Une même personne ne peut pas réserver deux places confirmées pour la même activité.

Vous pouvez annuler votre inscription avant le début de l’activité. L’organisateur peut annuler l’activité : les inscriptions confirmées sont alors annulées. Après une inscription, la date et le lieu ne peuvent plus être modifiés.

Le nombre de places affiché est indicatif au moment de la consultation. La place n’est attribuée qu’au moment de la confirmation, afin d’éviter qu’une même place soit promise deux fois.

## Organisateurs
L’organisateur rédige une description sincère, indique un lieu et un horaire exacts (fuseau Europe/Paris) et ne publie pas une activité fictive sans le signaler clairement. Il ne collecte pas, via Joinly, d’autres données que celles prévues par le service.

Il voit le nom affiché des participants confirmés, pas leur adresse e-mail. Il ne réutilise pas ces noms en dehors de l’organisation de l’activité.

## Comportement attendu
Le nom affiché et les contenus publiés restent respectueux. Il est interdit de publier un contenu illicite, trompeur, diffamatoire, discriminatoire ou portant atteinte à la vie privée d’autrui, et d’usurper l’identité d’une autre personne.

Le projet peut retirer un contenu ou suspendre un compte en cas de manquement signalé.

## Propriété des contenus
Vous conservez la responsabilité des textes que vous publiez. Vous garantissez pouvoir les diffuser et vous autorisez leur affichage sur Joinly pendant leur publication.

## Données personnelles
Le détail des données collectées, des finalités, des durées et de vos droits figure dans la politique de confidentialité.

## Droit applicable
Ces conditions sont soumises au droit français. En cas de différend, une solution amiable peut être recherchée en écrivant à contact@wangjiahan.com avant toute autre démarche.

## Contact
Joinly — projet étudiant G1D Lab, ISEP, 10 rue de Vanves, 92130 Issy-les-Moulineaux.
Contact : contact@wangjiahan.com.""",

    'privacy': """## Responsable du traitement
Le responsable du traitement est Jiahan Wang, pour le projet étudiant Joinly réalisé dans le cadre du G1D Lab à l’ISEP, École d’ingénieurs du numérique, 10 rue de Vanves, 92130 Issy-les-Moulineaux.

Contact pour les données personnelles : contact@wangjiahan.com.

Joinly n’est pas une société commerciale. Cette politique décrit le fonctionnement réel de cette version du site.

## Données collectées
Selon votre usage, le site traite les données suivantes.

Compte : adresse e-mail, nom affiché, condensat du mot de passe, rôle (participant, organisateur, administrateur), état du compte (actif ou suspendu) et dates de création et de mise à jour.

Préférences, si vous les enregistrez : centres d’intérêt, zone géographique choisie et choix facultatif d’autoriser un futur assistant à les utiliser. Cet assistant n’est pas en service dans cette version.

Réservations : activité concernée, état (confirmée ou annulée) et dates d’inscription et d’annulation.

Activités publiées par un organisateur : titre, description, lieu, horaires, capacité, catégorie et état de publication.

Contact : nom, adresse e-mail, objet et message, ainsi que l’état de traitement de la demande.

Sécurité et fonctionnement : condensat du jeton de session, date d’expiration de la session, condensat d’un éventuel lien de réinitialisation du mot de passe, et compteurs techniques de limitation des tentatives (sans conserver l’adresse IP en clair).

Le site ne demande pas de données de paiement, de pièce d’identité, ni de données sensibles au sens de l’article 9 du RGPD.

## Finalités et bases légales
Création et gestion du compte, réservation, annulation et publication d’activités : exécution des conditions d’utilisation que vous acceptez en créant un compte (article 6, paragraphe 1, point b, du RGPD).

Réponse aux messages envoyés par le formulaire de contact : intérêt légitime à répondre aux demandes adressées au projet, ou mesures précontractuelles lorsque la demande porte sur l’usage du service (article 6, paragraphe 1, points f et b).

Sécurité du site, protection des formulaires, limitation des tentatives abusives et maintien de la session : intérêt légitime à protéger le service et les comptes (article 6, paragraphe 1, point f).

Mémorisation du choix « J’ai compris » du bandeau d’information sur les cookies, dans le stockage local du navigateur : intérêt légitime à ne pas réafficher cette information à chaque page (article 6, paragraphe 1, point f). Ce stockage n’est pas un cookie et ne sert pas au suivi.

Case facultative relative à un futur assistant : consentement (article 6, paragraphe 1, point a), recueilli par une case non cochée par défaut. L’assistant n’est pas activé. Vous pouvez retirer ce choix depuis Mon espace, sans effet sur le reste du compte.

Les activités de démonstration liées aux comptes @demo.joinly.fr sont des exemples pédagogiques. Leurs noms et adresses e-mail sont fictifs.

## Durées de conservation
Session de connexion : 12 heures, puis le jeton n’est plus accepté. Les jetons expirés peuvent être supprimés par la commande de nettoyage du projet.

Lien de réinitialisation du mot de passe : 30 minutes, et une seule utilisation. Le message n’est envoyé que si l’envoi d’e-mails est configuré.

Compteurs de limitation des tentatives : 15 minutes.

Compte, préférences, activités et réservations : pendant l’utilisation du compte, puis jusqu’à douze mois après la dernière connexion, ou plus tôt si vous demandez la suppression. La durée du projet pédagogique peut conduire à un effacement plus rapide, une fois l’évaluation terminée.

Messages de contact : douze mois après le dernier échange, puis suppression.

Contenus légaux publiés par l’administration : les versions successives sont conservées le temps du projet, car elles documentent ce qui était affiché.

Les mots de passe ne sont conservés que sous forme de condensat. En cas de suppression du compte, les données associées sont effacées ou dissociées de l’identité, sous réserve des éléments qu’une obligation légale imposerait de garder.

## Destinataires
Les données sont accessibles aux personnes qui administrent le projet étudiant, dans la limite de leur rôle. Un organisateur voit le nom affiché des participants confirmés à ses activités, pas leur adresse e-mail. Les autres participants ne voient pas la liste des inscrits.

L’hébergeur, Contabo GmbH (Welfenstraße 22, 81541 München, Allemagne), fournit le serveur sur lequel le site et la base de données sont exécutés. Il peut traiter des données techniques d’hébergement en tant que sous-traitant.

Brevo (envoi d’e-mails transactionnels) peut recevoir l’adresse e-mail du destinataire, l’adresse d’expédition et le contenu du message de réinitialisation du mot de passe, uniquement lorsque cette fonction est utilisée. Brevo agit comme sous-traitant pour cet envoi. Aucun e-mail commercial n’est adressé via ce canal. Si l’envoi n’est pas configuré, aucune donnée n’est transmise à Brevo.

Les données ne sont pas vendues, ni cédées à des régies publicitaires. Aucun outil de mesure d’audience tiers n’est intégré.

## Transferts hors de l’Union européenne
L’hébergement retenu (Contabo, Allemagne) et l’envoi transactionnel (Brevo) sont situés dans l’Union européenne. Cette version du site n’organise pas de transfert de vos données vers un pays tiers. Aucun traceur publicitaire ou réseau social n’est déposé.

## Cookies
Le site utilise uniquement des cookies strictement nécessaires, exemptés de consentement préalable. Ils ne servent ni à la publicité, ni à la mesure d’audience, ni au profilage.

Cookie de session, nommé « session » : il maintient la connexion après identification et porte le jeton qui protège les formulaires contre les envois frauduleux (CSRF). Durée : 12 heures. Attributs : HttpOnly, SameSite=Lax, et Secure lorsque le site est servi en HTTPS. Il n’est pas déposé pour suivre votre navigation d’un site à l’autre.

Aucun autre cookie n’est déposé par Joinly. Il n’y a pas de cookie analytics, publicitaire ou de réseau social.

Le bandeau d’information mémorise son fermeture dans le stockage local du navigateur (clé « joinly-cookie-notice »). Ce n’est pas un cookie. Vous pouvez l’effacer en nettoyant les données locales du site ; le bandeau s’affichera de nouveau.

## Vos droits
Vous disposez des droits d’accès, de rectification, d’effacement, de limitation, d’opposition et de portabilité, dans les conditions prévues par le RGPD. Vous pouvez retirer à tout moment le consentement donné pour le futur assistant. Vous pouvez aussi définir des directives relatives à la conservation de vos données après votre décès, conformément à la loi Informatique et Libertés.

Pour exercer ces droits : contact@wangjiahan.com ou le formulaire de contact. Une vérification d’identité peut être demandée lorsque la demande n’est pas faite depuis le compte concerné. Une réponse est apportée dans un délai d’un mois, prolongeable dans les cas prévus par le texte.

Vous pouvez aussi modifier votre nom affiché, vos préférences, votre adresse e-mail et votre mot de passe depuis Mon espace.

## Réclamation auprès de la CNIL
Si vous estimez que vos droits ne sont pas respectés, vous pouvez introduire une réclamation auprès de la Commission nationale de l’informatique et des libertés (CNIL), 3 place de Fontenoy, TSA 80715, 75334 Paris Cedex 07, www.cnil.fr.

## Contact
Jiahan Wang — Joinly, projet étudiant G1D Lab, ISEP, 10 rue de Vanves, 92130 Issy-les-Moulineaux.
contact@wangjiahan.com.""",
}


def privacy_kind_supported(conn):
    rows = conn.execute(
        """SELECT pg_get_constraintdef(oid) AS def
           FROM pg_constraint
           WHERE conrelid = 'legal_pages'::regclass AND contype = 'c'"""
    ).fetchall()
    return any('kind' in row['def'] and 'privacy' in row['def'] for row in rows)


def publish_legal_defaults(conn, require_privacy=False):
    """Publish a new version only when a text is missing or still a placeholder.

    Existing non-placeholder versions are left unchanged. Returns the kinds
    actually published.
    """
    if require_privacy and not privacy_kind_supported(conn):
        raise RuntimeError(
            'La migration 003_privacy doit être appliquée avant de publier la politique de confidentialité.'
        )
    published = []
    for kind, content in LEGAL_TEXTS.items():
        if kind == 'privacy' and not privacy_kind_supported(conn):
            continue
        current = conn.execute(
            '''SELECT content FROM legal_pages
               WHERE kind=%s AND published_at IS NOT NULL
               ORDER BY version DESC LIMIT 1''',
            (kind,),
        ).fetchone()
        if current and not any(marker in current['content'] for marker in PLACEHOLDER_MARKERS):
            continue
        version = conn.execute(
            'SELECT coalesce(max(version), 0) + 1 AS n FROM legal_pages WHERE kind=%s',
            (kind,),
        ).fetchone()['n']
        conn.execute(
            'INSERT INTO legal_pages(kind, version, content, published_at) VALUES (%s, %s, %s, now())',
            (kind, version, content),
        )
        published.append(kind)
    return published


def ensure_faqs(conn):
    """Insert missing default questions. Never edit or delete an existing answer."""
    created = 0
    for index, (question, answer) in enumerate(FAQS):
        if conn.execute('SELECT 1 FROM faqs WHERE question=%s', (question,)).fetchone():
            continue
        conn.execute(
            'INSERT INTO faqs(question, answer, sort_order, published) VALUES (%s, %s, %s, true)',
            (question, answer, index),
        )
        created += 1
    return created
