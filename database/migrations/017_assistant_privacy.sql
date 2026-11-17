BEGIN;
SELECT pg_advisory_xact_lock(2001);
DO $$
DECLARE body text;
BEGIN
SELECT content INTO body FROM legal_pages WHERE kind='privacy' AND published_at IS NOT NULL ORDER BY version DESC LIMIT 1;
IF body IS NOT NULL AND position('## Assistant IA DeepSeek' in body)=0 THEN
body := replace(body, 'centres d’intérêt, zone géographique choisie et choix facultatif d’autoriser un futur assistant à les utiliser. Cet assistant n’est pas en service dans cette version.', 'centres d’intérêt, zone géographique choisie et choix facultatif d’autoriser l’assistant à les utiliser. Leur envoi exige également une case dédiée dans le chat.');
body := replace(body, 'Case facultative relative à un futur assistant : consentement (article 6, paragraphe 1, point a), recueilli par une case non cochée par défaut. L’assistant n’est pas activé. Vous pouvez retirer ce choix depuis Mon espace, sans effet sur le reste du compte.', 'Assistant IA facultatif : vos messages sont transmis à DeepSeek seulement après activation de la case du chat, non cochée par défaut. Vos préférences exigent en plus votre autorisation dans Mon espace et dans le chat. Vous pouvez retirer ces choix à tout moment, sans effet sur le reste du compte.');
body := replace(body, 'Compteurs de limitation des tentatives : 15 minutes.', 'Compteurs de limitation : fenêtres de 15 minutes à 24 heures pour le chat ; les compteurs expirés sont supprimables par le nettoyage du projet.');
body := replace(body, 'L’hébergement retenu (Contabo, Allemagne) et l’envoi transactionnel (Brevo) sont situés dans l’Union européenne. Cette version du site n’organise pas de transfert de vos données vers un pays tiers. Aucun traceur publicitaire ou réseau social n’est déposé.', 'Le chat utilise l’API DeepSeek, un fournisseur extérieur à l’Union européenne. Son utilisation implique la transmission des messages et du contexte indiqué ci-dessous à ce fournisseur. Évitez toute donnée personnelle ou sensible dans vos messages. Les autres fonctions de Joinly restent utilisables sans le chat. Aucun traceur publicitaire ou réseau social n’est déposé.');
body := replace(body, 'consentement donné pour le futur assistant', 'choix donné pour l’assistant');
body := body || '

## Assistant IA DeepSeek
Le serveur envoie vos messages, un historique récent limité, les règles publiques de Joinly, une sélection d’activités publiques et la FAQ à l’API DeepSeek. Les intérêts et la zone choisie sont envoyés uniquement avec les deux autorisations décrites plus haut. Aucun nom, e-mail, identifiant de compte ou réservation privée n’est ajouté automatiquement au contexte.

Joinly ne conserve pas le texte des conversations dans sa base ni dans ses journaux applicatifs. L’historique reste en mémoire dans la page et disparaît quand vous la quittez ou cliquez sur Effacer. Effacer la page ne supprime pas les données déjà reçues par DeepSeek : leur traitement et leur conservation relèvent également des conditions du fournisseur (https://www.deepseek.com/privacy). Les réponses sont générées automatiquement et peuvent être inexactes. L’assistant ne réalise aucune réservation, annulation ou opération sur votre compte.';
INSERT INTO legal_pages(kind,version,content,published_at)
SELECT 'privacy',coalesce(max(version),0)+1,body,now() FROM legal_pages WHERE kind='privacy';
END IF;
END $$;
INSERT INTO schema_migrations(version) VALUES ('017_assistant_privacy');
COMMIT;
