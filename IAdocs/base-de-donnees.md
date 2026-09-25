# Dictionnaire de données — IAGORA

> **Généré depuis la base**, à partir des commentaires PostgreSQL
> (`COMMENT ON TABLE` / `COMMENT ON COLUMN`), eux-mêmes déclarés dans les modèles.
> Les mêmes textes s'affichent dans DataGrip, pgAdmin et psql.
>
> Régénérer après une migration, depuis `backend/` :
> `.\venv\Scripts\python.exe -m app.cli db-doc > ..\IAdocs\base-de-donnees.md`

Tables documentées : **8** · colonnes : **73**.

## Utilisateurs et accès

### `users`

Membres de l'équipe DATUM Academy qui utilisent IAGORA. Ni les prospects, ni les inscrits aux webinaires : ceux-là vivent ailleurs.

| Colonne | Type | Nul | Description |
|---|---|---|---|
| `id_users` | bigint | non | Identifiant de l'utilisateur. |
| `email` | varchar(255) | non | Adresse e-mail, identifiant de connexion. Toujours stockée en minuscules. |
| `password_hash` | varchar(255) | non | Empreinte bcrypt du mot de passe. Irréversible : le mot de passe n'est jamais stocké, ni récupérable. |
| `first_name` | varchar(100) | non | Prénom. |
| `last_name` | varchar(100) | non | Nom de famille. |
| `is_active` | boolean | non | Faux = compte suspendu temporairement : connexion refusée, mais le compte reste visible et réactivable. |
| `last_login_at` | timestamptz | oui | Dernière connexion réussie (UTC). Vide si l'utilisateur ne s'est jamais connecté. |
| `created_at` | timestamptz | non | Date de création (UTC). |
| `updated_at` | timestamptz | non | Date de dernière modification (UTC). |
| `deleted_at` | timestamptz | oui | Date d'archivage (UTC). Renseignée = le compte disparaît des listes, mais l'historique et les publications continuent d'y renvoyer. |

**Contraintes**

- `pk_users` — PRIMARY KEY (id_users)
- `uq_users_email` — UNIQUE (email)

### `permissions`

Droits attribuables aux utilisateurs. Table de référence, alimentée par migration : créer, valider, publier, consulter, administrer.

| Colonne | Type | Nul | Description |
|---|---|---|---|
| `id_permissions` | bigint | non | Identifiant du droit. |
| `code` | varchar(30) | non | Code technique utilisé par le code Python : create, review, publish, read, admin. Ne change jamais. |
| `label` | varchar(100) | non | Libellé affiché dans l'interface. Modifiable librement. |
| `sort_order` | smallint | non | Ordre d'affichage dans les listes. |
| `created_at` | timestamptz | non | Date de création (UTC). |
| `updated_at` | timestamptz | non | Date de dernière modification (UTC). |

**Contraintes**

- `pk_permissions` — PRIMARY KEY (id_permissions)
- `uq_permissions_code` — UNIQUE (code)

### `user_permissions`

Quel utilisateur possède quel droit. Une personne peut en cumuler plusieurs, dans n'importe quelle combinaison : aucun rôle n'est figé.

| Colonne | Type | Nul | Description |
|---|---|---|---|
| `id_user_permissions` | bigint | non | Identifiant de l'attribution. |
| `id_users` | bigint | non | Utilisateur concerné. Supprimé avec lui. |
| `id_permissions` | bigint | non | Droit attribué. |
| `created_at` | timestamptz | non | Date d'attribution du droit (UTC). |
| `updated_at` | timestamptz | non | Date de dernière modification (UTC). |

**Contraintes**

- `fk_user_permissions_id_permissions_permissions` — FOREIGN KEY (id_permissions) REFERENCES permissions(id_permissions)
- `fk_user_permissions_id_users_users` — FOREIGN KEY (id_users) REFERENCES users(id_users) ON DELETE CASCADE
- `pk_user_permissions` — PRIMARY KEY (id_user_permissions)
- `uq_user_permissions_id_users` — UNIQUE (id_users, id_permissions)

### `refresh_tokens`

Sessions ouvertes : une ligne par navigateur connecté. Existe pour pouvoir révoquer une session ; sans elle, la déconnexion serait sans effet côté serveur.

| Colonne | Type | Nul | Description |
|---|---|---|---|
| `id_refresh_tokens` | bigint | non | Identifiant de la session. |
| `id_users` | bigint | non | Utilisateur connecté. Ses sessions disparaissent avec son compte. |
| `token_hash` | varchar(64) | non | Empreinte SHA-256 du jeton de renouvellement. Le jeton lui-même n'est jamais stocké ; l'empreinte est déterministe pour retrouver la session à partir du jeton reçu. |
| `expires_at` | timestamptz | non | Fin de validité de la session (UTC). |
| `revoked_at` | timestamptz | oui | Date de révocation (UTC) : déconnexion, ou renouvellement qui a remplacé ce jeton. Renseignée = le jeton ne vaut plus rien. |
| `user_agent` | varchar(255) | oui | Navigateur ou outil à l'origine de la session, pour s'y retrouver. |
| `created_at` | timestamptz | non | Date d'ouverture de la session (UTC). |
| `updated_at` | timestamptz | non | Date de dernière modification (UTC). |

**Contraintes**

- `fk_refresh_tokens_id_users_users` — FOREIGN KEY (id_users) REFERENCES users(id_users) ON DELETE CASCADE
- `pk_refresh_tokens` — PRIMARY KEY (id_refresh_tokens)
- `uq_refresh_tokens_token_hash` — UNIQUE (token_hash)

## Réseaux sociaux

### `platforms`

Réseaux sociaux connus et leurs règles. Table de référence : c'est le seul endroit à modifier pour changer de version d'API ou activer un nouveau réseau.

| Colonne | Type | Nul | Description |
|---|---|---|---|
| `id_platforms` | bigint | non | Identifiant du réseau. |
| `code` | varchar(20) | non | Code technique : facebook, instagram, linkedin, tiktok, youtube. Ne change jamais. |
| `label` | varchar(50) | non | Nom affiché dans l'interface. |
| `is_enabled` | boolean | non | Faux = réseau prévu au cahier des charges mais sans connecteur : l'API le refuse. |
| `api_base_url` | varchar(255) | oui | Adresse de l'API du réseau, par exemple https://graph.facebook.com. |
| `api_version` | varchar(10) | oui | Version d'API utilisée, par exemple v26.0. Modifiable sans toucher au code. |
| `max_caption_length` | integer | oui | Longueur maximale d'une légende, imposée par le réseau : 2 200 sur Instagram. |
| `sort_order` | smallint | non | Ordre d'affichage dans les listes. |
| `created_at` | timestamptz | non | Date de création (UTC). |
| `updated_at` | timestamptz | non | Date de dernière modification (UTC). |

**Contraintes**

- `pk_platforms` — PRIMARY KEY (id_platforms)
- `uq_platforms_code` — UNIQUE (code)

### `social_account_statuses`

États possibles d'un compte raccordé : connecté, à reconnecter, déconnecté. Table de référence.

| Colonne | Type | Nul | Description |
|---|---|---|---|
| `id_social_account_statuses` | bigint | non | Identifiant du statut. |
| `code` | varchar(30) | non | Code technique : connected, needs_reconnect, disconnected. Ne change jamais. |
| `label` | varchar(50) | non | Libellé affiché dans l'interface. |
| `sort_order` | smallint | non | Ordre d'affichage dans les listes. |
| `created_at` | timestamptz | non | Date de création (UTC). |
| `updated_at` | timestamptz | non | Date de dernière modification (UTC). |

**Contraintes**

- `pk_social_account_statuses` — PRIMARY KEY (id_social_account_statuses)
- `uq_social_account_statuses_code` — UNIQUE (code)

### `social_accounts`

Comptes officiels de DATUM Academy raccordés à IAGORA (page Facebook, compte Instagram). Détient les jetons d'accès chiffrés : sans eux, ni publication, ni messages, ni statistiques.

| Colonne | Type | Nul | Description |
|---|---|---|---|
| `id_social_accounts` | bigint | non | Identifiant du compte. |
| `id_platforms` | bigint | non | Réseau auquel appartient ce compte. |
| `id_social_account_statuses` | bigint | non | État courant : connecté, à reconnecter, déconnecté. |
| `id_social_accounts_parent` | bigint | oui | Compte dont dépend celui-ci : un compte Instagram professionnel est rattaché à une page Facebook, et c'est le jeton de cette page qui sert. |
| `external_meta_id` | varchar(64) | non | Identifiant du compte chez Meta (id de page ou de compte Instagram). Clé de tous les appels à l'API. |
| `name` | varchar(255) | non | Nom du compte, par exemple Datum Academy. |
| `handle` | varchar(100) | oui | Nom d'utilisateur public, par exemple @datum.academy. |
| `access_token_encrypted` | text | non | Jeton d'accès chiffré (Fernet). Réversible, car il doit être renvoyé à Meta à chaque appel. Ne sort jamais de l'API et n'apparaît jamais dans les journaux. |
| `token_kind` | varchar(20) | non | Nature du jeton : page, user ou system_user. |
| `token_expires_at` | timestamptz | oui | Expiration du jeton (UTC). Vide si le jeton n'expire pas. Sert à prévenir avant la panne. |
| `scopes` | jsonb | oui | Droits réellement accordés au jeton. Sans eux, impossible d'expliquer pourquoi une statistique est absente : read_insights manquant, par exemple. |
| `last_checked_at` | timestamptz | oui | Dernière vérification réussie du compte (UTC). |
| `last_error` | text | oui | Dernier message d'erreur renvoyé par le réseau, pour le diagnostic. |
| `created_at` | timestamptz | non | Date de raccordement (UTC). |
| `updated_at` | timestamptz | non | Date de dernière modification (UTC). |
| `deleted_at` | timestamptz | oui | Date d'archivage (UTC). Renseignée = le compte disparaît des listes, mais les publications passées continuent d'y renvoyer. |

**Contraintes**

- `fk_social_accounts_id_platforms_platforms` — FOREIGN KEY (id_platforms) REFERENCES platforms(id_platforms)
- `fk_social_accounts_id_social_accounts_parent_social_accounts` — FOREIGN KEY (id_social_accounts_parent) REFERENCES social_accounts(id_social_accounts)
- `fk_social_accounts_status` — FOREIGN KEY (id_social_account_statuses) REFERENCES social_account_statuses(id_social_account_statuses)
- `pk_social_accounts` — PRIMARY KEY (id_social_accounts)
- `uq_social_accounts_id_platforms` — UNIQUE (id_platforms, external_meta_id)

### `social_account_metrics`

Statistiques d'un compte, une ligne par jour. Une valeur vide signifie « non communiqué par le réseau », et non « zéro » : l'interface affiche alors « — ».

| Colonne | Type | Nul | Description |
|---|---|---|---|
| `id_social_account_metrics` | bigint | non | Identifiant de la mesure. |
| `id_social_accounts` | bigint | non | Compte mesuré. Ses mesures disparaissent avec lui. |
| `metric_date` | date | non | Jour mesuré. Une seule ligne par compte et par jour. |
| `followers` | integer | oui | Nombre d'abonnés à cette date. État, et non valeur du jour. |
| `profile_views` | integer | oui | Consultations du profil pendant la journée. |
| `reach` | integer | oui | Comptes uniques ayant vu un contenu pendant la journée. Indisponible en dessous de 100 abonnés sur Instagram. |
| `interactions` | integer | oui | J'aime, commentaires et partages cumulés sur la journée. |
| `posts_count` | integer | oui | Nombre de publications parues ce jour-là. |
| `collected_at` | timestamptz | non | Moment de la collecte (UTC). Les données de Meta ont jusqu'à 48 h de retard. |
| `raw` | jsonb | oui | Réponse brute du réseau. Permet de retrouver une valeur quand un indicateur est renommé, comme « impressions » devenu « views ». |
| `created_at` | timestamptz | non | Date de création (UTC). |
| `updated_at` | timestamptz | non | Date de dernière modification (UTC). |

**Contraintes**

- `fk_social_account_metrics_id_social_accounts_social_accounts` — FOREIGN KEY (id_social_accounts) REFERENCES social_accounts(id_social_accounts) ON DELETE CASCADE
- `pk_social_account_metrics` — PRIMARY KEY (id_social_account_metrics)
- `uq_social_account_metrics_id_social_accounts` — UNIQUE (id_social_accounts, metric_date)

