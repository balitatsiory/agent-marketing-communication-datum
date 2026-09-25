"""Commentaires de la base : chaque table et chaque colonne se documente elle-même.

Générée à partir des attributs `comment` des modèles, pour que les deux ne divergent pas.
DataGrip, pgAdmin et psql les affichent directement.

Revision ID: 0005_commentaires
Revises: 0004_reseaux_valeurs
Create Date: 2026-09-25
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005_commentaires"
down_revision: str | None = "0004_reseaux_valeurs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (table, colonne ou None pour la table elle-même, commentaire)
COMMENTAIRES: list[tuple[str, str | None, str]] = [
    ("permissions", None, "Droits attribuables aux utilisateurs. Table de référence, alimentée par migration : créer, valider, publier, consulter, administrer."),
    ("permissions", "id_permissions", "Identifiant du droit."),
    ("permissions", "code", "Code technique utilisé par le code Python : create, review, publish, read, admin. Ne change jamais."),
    ("permissions", "label", "Libellé affiché dans l'interface. Modifiable librement."),
    ("permissions", "sort_order", "Ordre d'affichage dans les listes."),
    ("permissions", "created_at", "Date de création (UTC)."),
    ("permissions", "updated_at", "Date de dernière modification (UTC)."),
    ("platforms", None, "Réseaux sociaux connus et leurs règles. Table de référence : c'est le seul endroit à modifier pour changer de version d'API ou activer un nouveau réseau."),
    ("platforms", "id_platforms", "Identifiant du réseau."),
    ("platforms", "code", "Code technique : facebook, instagram, linkedin, tiktok, youtube. Ne change jamais."),
    ("platforms", "label", "Nom affiché dans l'interface."),
    ("platforms", "is_enabled", "Faux = réseau prévu au cahier des charges mais sans connecteur : l'API le refuse."),
    ("platforms", "api_base_url", "Adresse de l'API du réseau, par exemple https://graph.facebook.com."),
    ("platforms", "api_version", "Version d'API utilisée, par exemple v26.0. Modifiable sans toucher au code."),
    ("platforms", "max_caption_length", "Longueur maximale d'une légende, imposée par le réseau : 2 200 sur Instagram."),
    ("platforms", "sort_order", "Ordre d'affichage dans les listes."),
    ("platforms", "created_at", "Date de création (UTC)."),
    ("platforms", "updated_at", "Date de dernière modification (UTC)."),
    ("refresh_tokens", None, "Sessions ouvertes : une ligne par navigateur connecté. Existe pour pouvoir révoquer une session ; sans elle, la déconnexion serait sans effet côté serveur."),
    ("refresh_tokens", "id_refresh_tokens", "Identifiant de la session."),
    ("refresh_tokens", "id_users", "Utilisateur connecté. Ses sessions disparaissent avec son compte."),
    ("refresh_tokens", "token_hash", "Empreinte SHA-256 du jeton de renouvellement. Le jeton lui-même n'est jamais stocké ; l'empreinte est déterministe pour retrouver la session à partir du jeton reçu."),
    ("refresh_tokens", "expires_at", "Fin de validité de la session (UTC)."),
    ("refresh_tokens", "revoked_at", "Date de révocation (UTC) : déconnexion, ou renouvellement qui a remplacé ce jeton. Renseignée = le jeton ne vaut plus rien."),
    ("refresh_tokens", "user_agent", "Navigateur ou outil à l'origine de la session, pour s'y retrouver."),
    ("refresh_tokens", "created_at", "Date d'ouverture de la session (UTC)."),
    ("refresh_tokens", "updated_at", "Date de dernière modification (UTC)."),
    ("social_account_metrics", None, "Statistiques d'un compte, une ligne par jour. Une valeur vide signifie « non communiqué par le réseau », et non « zéro » : l'interface affiche alors « — »."),
    ("social_account_metrics", "id_social_account_metrics", "Identifiant de la mesure."),
    ("social_account_metrics", "id_social_accounts", "Compte mesuré. Ses mesures disparaissent avec lui."),
    ("social_account_metrics", "metric_date", "Jour mesuré. Une seule ligne par compte et par jour."),
    ("social_account_metrics", "followers", "Nombre d'abonnés à cette date. État, et non valeur du jour."),
    ("social_account_metrics", "profile_views", "Consultations du profil pendant la journée."),
    ("social_account_metrics", "reach", "Comptes uniques ayant vu un contenu pendant la journée. Indisponible en dessous de 100 abonnés sur Instagram."),
    ("social_account_metrics", "interactions", "J'aime, commentaires et partages cumulés sur la journée."),
    ("social_account_metrics", "posts_count", "Nombre de publications parues ce jour-là."),
    ("social_account_metrics", "collected_at", "Moment de la collecte (UTC). Les données de Meta ont jusqu'à 48 h de retard."),
    ("social_account_metrics", "raw", "Réponse brute du réseau. Permet de retrouver une valeur quand un indicateur est renommé, comme « impressions » devenu « views »."),
    ("social_account_metrics", "created_at", "Date de création (UTC)."),
    ("social_account_metrics", "updated_at", "Date de dernière modification (UTC)."),
    ("social_account_statuses", None, "États possibles d'un compte raccordé : connecté, à reconnecter, déconnecté. Table de référence."),
    ("social_account_statuses", "id_social_account_statuses", "Identifiant du statut."),
    ("social_account_statuses", "code", "Code technique : connected, needs_reconnect, disconnected. Ne change jamais."),
    ("social_account_statuses", "label", "Libellé affiché dans l'interface."),
    ("social_account_statuses", "sort_order", "Ordre d'affichage dans les listes."),
    ("social_account_statuses", "created_at", "Date de création (UTC)."),
    ("social_account_statuses", "updated_at", "Date de dernière modification (UTC)."),
    ("social_accounts", None, "Comptes officiels de DATUM Academy raccordés à IAGORA (page Facebook, compte Instagram). Détient les jetons d'accès chiffrés : sans eux, ni publication, ni messages, ni statistiques."),
    ("social_accounts", "id_social_accounts", "Identifiant du compte."),
    ("social_accounts", "id_platforms", "Réseau auquel appartient ce compte."),
    ("social_accounts", "id_social_account_statuses", "État courant : connecté, à reconnecter, déconnecté."),
    ("social_accounts", "id_social_accounts_parent", "Compte dont dépend celui-ci : un compte Instagram professionnel est rattaché à une page Facebook, et c'est le jeton de cette page qui sert."),
    ("social_accounts", "external_meta_id", "Identifiant du compte chez Meta (id de page ou de compte Instagram). Clé de tous les appels à l'API."),
    ("social_accounts", "name", "Nom du compte, par exemple Datum Academy."),
    ("social_accounts", "handle", "Nom d'utilisateur public, par exemple @datum.academy."),
    ("social_accounts", "access_token_encrypted", "Jeton d'accès chiffré (Fernet). Réversible, car il doit être renvoyé à Meta à chaque appel. Ne sort jamais de l'API et n'apparaît jamais dans les journaux."),
    ("social_accounts", "token_kind", "Nature du jeton : page, user ou system_user."),
    ("social_accounts", "token_expires_at", "Expiration du jeton (UTC). Vide si le jeton n'expire pas. Sert à prévenir avant la panne."),
    ("social_accounts", "scopes", "Droits réellement accordés au jeton. Sans eux, impossible d'expliquer pourquoi une statistique est absente : read_insights manquant, par exemple."),
    ("social_accounts", "last_checked_at", "Dernière vérification réussie du compte (UTC)."),
    ("social_accounts", "last_error", "Dernier message d'erreur renvoyé par le réseau, pour le diagnostic."),
    ("social_accounts", "created_at", "Date de raccordement (UTC)."),
    ("social_accounts", "updated_at", "Date de dernière modification (UTC)."),
    ("social_accounts", "deleted_at", "Date d'archivage (UTC). Renseignée = le compte disparaît des listes, mais les publications passées continuent d'y renvoyer."),
    ("user_permissions", None, "Quel utilisateur possède quel droit. Une personne peut en cumuler plusieurs, dans n'importe quelle combinaison : aucun rôle n'est figé."),
    ("user_permissions", "id_user_permissions", "Identifiant de l'attribution."),
    ("user_permissions", "id_users", "Utilisateur concerné. Supprimé avec lui."),
    ("user_permissions", "id_permissions", "Droit attribué."),
    ("user_permissions", "created_at", "Date d'attribution du droit (UTC)."),
    ("user_permissions", "updated_at", "Date de dernière modification (UTC)."),
    ("users", None, "Membres de l'équipe DATUM Academy qui utilisent IAGORA. Ni les prospects, ni les inscrits aux webinaires : ceux-là vivent ailleurs."),
    ("users", "id_users", "Identifiant de l'utilisateur."),
    ("users", "email", "Adresse e-mail, identifiant de connexion. Toujours stockée en minuscules."),
    ("users", "password_hash", "Empreinte bcrypt du mot de passe. Irréversible : le mot de passe n'est jamais stocké, ni récupérable."),
    ("users", "first_name", "Prénom."),
    ("users", "last_name", "Nom de famille."),
    ("users", "is_active", "Faux = compte suspendu temporairement : connexion refusée, mais le compte reste visible et réactivable."),
    ("users", "last_login_at", "Dernière connexion réussie (UTC). Vide si l'utilisateur ne s'est jamais connecté."),
    ("users", "created_at", "Date de création (UTC)."),
    ("users", "updated_at", "Date de dernière modification (UTC)."),
    ("users", "deleted_at", "Date d'archivage (UTC). Renseignée = le compte disparaît des listes, mais l'historique et les publications continuent d'y renvoyer."),]


def upgrade() -> None:
    for table, colonne, texte in COMMENTAIRES:
        echappe = texte.replace("'", "''")
        cible = f"{table}.{colonne}" if colonne else table
        mot = "COLUMN" if colonne else "TABLE"
        op.execute(f"COMMENT ON {mot} {cible} IS '{echappe}'")


def downgrade() -> None:
    for table, colonne, _ in COMMENTAIRES:
        cible = f"{table}.{colonne}" if colonne else table
        mot = "COLUMN" if colonne else "TABLE"
        op.execute(f"COMMENT ON {mot} {cible} IS NULL")
