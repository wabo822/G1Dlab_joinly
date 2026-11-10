BEGIN;
SELECT pg_advisory_xact_lock(2001);
DO $$
DECLARE body text;
BEGIN
SELECT content INTO body FROM legal_pages WHERE kind='privacy' AND published_at IS NOT NULL ORDER BY version DESC LIMIT 1;
IF body IS NOT NULL AND position('## Connexions MCP' in body)=0 THEN
body := replace(body, 'Aucun nom, e-mail, identifiant de compte ou réservation privée n’est ajouté automatiquement au contexte.', 'Aucun nom, e-mail ou identifiant de compte n’est ajouté automatiquement au contexte. Si vous cochez l’autorisation des inscriptions dans le chat, l’assistant peut transmettre à DeepSeek les activités, dates et états de vos propres inscriptions. Cette autorisation permet également de préparer une réservation ; sa validation exige une confirmation distincte sur Joinly.');
body := replace(body, 'L’assistant ne réalise aucune réservation, annulation ou opération sur votre compte.', 'L’assistant peut préparer une demande de réservation. Une place n’est attribuée qu’après votre confirmation sur le site. Il ne réalise pas d’annulation ni de paiement réel.');
body := body || '

## Connexions MCP
Vous pouvez créer dans Mon espace un jeton d’accès personnel pour un client MCP. Les permissions publiques, la lecture de vos inscriptions et la préparation de réservations sont distinctes. Le client et son fournisseur d’IA peuvent recevoir les données que vous autorisez : consultez leurs conditions avant de les connecter. Le jeton est affiché une fois, conservé sous forme de condensat et révocable depuis Mon espace. Il expire après 30 jours et cesse de fonctionner si vos identifiants changent.

Les propositions de réservation sont liées à votre compte, valables 15 minutes et contiennent un récapitulatif de l’activité. La commande de nettoyage supprime les propositions et accès expirés ou révoqués depuis plus de 30 jours. Les inscriptions confirmées restent soumises à la durée de conservation des réservations. Aucun historique des conversations MCP n’est enregistré par Joinly.';
INSERT INTO legal_pages(kind,version,content,published_at)
SELECT 'privacy',coalesce(max(version),0)+1,body,now() FROM legal_pages WHERE kind='privacy';
END IF;
END $$;
INSERT INTO schema_migrations(version) VALUES ('019_mcp_privacy');
COMMIT;
