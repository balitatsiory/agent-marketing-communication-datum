# Dictionnaire de données — IAGORA

> **Généré depuis la base**, à partir des commentaires PostgreSQL
> (`COMMENT ON TABLE` / `COMMENT ON COLUMN`), eux-mêmes déclarés dans les modèles.
> Les mêmes textes s'affichent dans DataGrip, pgAdmin et psql.
>
> Régénérer après une migration, depuis `backend/` :
> `.\venv\Scripts\python.exe -m app.cli db-doc > ..\IAdocs\base-de-donnees.md`

Tables documentées : **17** · colonnes : **172**.

> Les quatre tables du module Modèles IA (migration 0005) ne figurent pas
> encore ici : le générateur `app.cli db-doc` annoncé ci-dessus n'existe plus
> dans `backend/app/`, et cette page est tenue à la main depuis.

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

## Newsletter — comptes d'envoi

### `email_accounts`

Comptes d'envoi SMTP (IONOS et autres). Le mot de passe n'est pas ici : il vit chiffre dans email_account_credentials.

| Colonne | Type | Nul | Description |
|---|---|---|---|
| `id_email_accounts` | integer | non | Identifiant du compte d'envoi. |
| `label` | varchar(120) | non | Nom lisible du compte, affiche dans l'interface. |
| `host` | varchar(255) | non | Serveur SMTP sortant (ex: smtp.ionos.fr). |
| `port` | integer | non | 465 en SSL/TLS implicite, 587 en STARTTLS. |
| `security` | varchar(20) | non | ssl_tls (chiffre des l'ouverture) \| starttls (passage en TLS apres ouverture). |
| `username` | varchar(255) | non | Identifiant SMTP, toujours en minuscules. Chez IONOS, l'adresse de la boite. |
| `from_email` | varchar(255) | non | Adresse d'expedition, en minuscules. Le serveur la refuse si la boite ne la porte pas. |
| `from_name` | varchar(120) | oui | Nom affiche devant l'adresse d'expedition. |
| `reply_to_email` | varchar(255) | oui | Adresse de reponse, quand elle differe de l'expediteur. |
| `timeout_seconds` | integer | non | Delai d'attente d'une operation SMTP, en secondes. |
| `is_default` | boolean | non | Compte utilise par defaut pour les envois. Un seul a la fois. |
| `last_verified_at` | timestamptz | oui | Date de la derniere verification (UTC), reussie ou non. |
| `last_verify_ok` | boolean | oui | Resultat de la derniere verification. Vide si aucune n'a eu lieu. |
| `last_verify_message` | text | oui | Compte rendu de la derniere verification, affiche tel quel. |
| `id_users_created_by` | integer | oui | Utilisateur qui a enregistre le compte. |
| `id_users_changed_by` | integer | oui | Utilisateur de la derniere modification. |
| `created_at` | timestamptz | non | Date de creation (UTC). |
| `updated_at` | timestamptz | non | Date de derniere modification (UTC). |
| `deleted_at` | timestamptz | oui | Archivage du compte : il n'est plus propose aux envois. |

**Contraintes**

- `ck_email_accounts_ck_email_accounts_port` — CHECK (((port >= 1) AND (port <= 65535)))
- `ck_email_accounts_ck_email_accounts_security` — CHECK (((security)::text = ANY ((ARRAY['ssl_tls'::character varying, 'starttls'::character varying])::text[])))
- `ck_email_accounts_ck_email_accounts_timeout_seconds` — CHECK (((timeout_seconds >= 1) AND (timeout_seconds <= 120)))
- `fk_email_accounts_id_users_changed_by_users` — FOREIGN KEY (id_users_changed_by) REFERENCES users(id_users)
- `fk_email_accounts_id_users_created_by_users` — FOREIGN KEY (id_users_created_by) REFERENCES users(id_users)
- `pk_email_accounts` — PRIMARY KEY (id_email_accounts)
- `uq_email_accounts_defaut` — UNIQUE (is_default) WHERE is_default AND deleted_at IS NULL
- `uq_email_accounts_identifiant` — UNIQUE (host, port, username) WHERE deleted_at IS NULL

### `email_account_credentials`

Mots de passe des comptes d'envoi, chiffres par Fernet. Un changement cree une nouvelle ligne et marque la precedente remplacee.

| Colonne | Type | Nul | Description |
|---|---|---|---|
| `id_email_account_credentials` | integer | non | Identifiant de la delivrance de mot de passe. |
| `id_email_accounts` | integer | non | Compte d'envoi concerne. Ses mots de passe disparaissent avec lui. |
| `password_encrypted` | text | non | Chiffre par Fernet (TOKEN_ENCRYPTION_KEY). Le mot de passe en clair ne touche jamais le disque. |
| `password_masked` | varchar(40) | non | Apercu masque sans secret, pour que l'interface montre qu'il existe. |
| `obtained_at` | timestamptz | non | Date de saisie du mot de passe (UTC). |
| `superseded_at` | timestamptz | oui | Remplacement par un mot de passe plus recent. |
| `revoked_at` | timestamptz | oui | Retrait sans remplacement : le compte ne peut plus envoyer. |
| `id_users_created_by` | integer | oui | Utilisateur qui a saisi le mot de passe. |
| `created_at` | timestamptz | non | Date de creation (UTC). |

**Contraintes**

- `fk_email_account_credentials_id_email_accounts_email_accounts` — FOREIGN KEY (id_email_accounts) REFERENCES email_accounts(id_email_accounts) ON DELETE CASCADE
- `fk_email_account_credentials_id_users_created_by_users` — FOREIGN KEY (id_users_created_by) REFERENCES users(id_users)
- `pk_email_account_credentials` — PRIMARY KEY (id_email_account_credentials)
- `uq_email_account_credentials_actif` — UNIQUE (id_email_accounts) WHERE superseded_at IS NULL AND revoked_at IS NULL
- `trg_email_account_credentials_ajout_seul` — déclencheur : DELETE refusé. L'UPDATE reste permis, un mot de passe se remplace (`superseded_at`) ou se retire (`revoked_at`).

### `email_account_checks`

Historique des verifications d'un compte d'envoi : connexion authentifiee ou message de test. En ajout seul.

| Colonne | Type | Nul | Description |
|---|---|---|---|
| `id_email_account_checks` | integer | non | Identifiant de la verification. |
| `id_email_accounts` | integer | non | Compte verifie. Ses verifications disparaissent avec lui. |
| `kind` | varchar(20) | non | connection (connexion + authentification) \| test_message (message reellement envoye). |
| `is_ok` | boolean | non | Vrai si le serveur a accepte l'operation. |
| `message` | text | oui | Compte rendu en francais, affiche tel quel dans l'interface. |
| `recipient_email` | varchar(255) | oui | Destinataire du message de test. Vide pour un simple test de connexion. |
| `latency_ms` | integer | oui | Duree de l'echange avec le serveur, en millisecondes. |
| `checked_at` | timestamptz | non | Moment de la verification (UTC). |
| `id_users_checked_by` | integer | oui | Utilisateur qui a declenche la verification. |

**Contraintes**

- `ck_email_account_checks_ck_email_account_checks_kind` — CHECK (((kind)::text = ANY ((ARRAY['connection'::character varying, 'test_message'::character varying])::text[])))
- `fk_email_account_checks_id_email_accounts_email_accounts` — FOREIGN KEY (id_email_accounts) REFERENCES email_accounts(id_email_accounts) ON DELETE CASCADE
- `fk_email_account_checks_id_users_checked_by_users` — FOREIGN KEY (id_users_checked_by) REFERENCES users(id_users)
- `pk_email_account_checks` — PRIMARY KEY (id_email_account_checks)
- `trg_email_account_checks_ajout_seul` — déclencheur : UPDATE et DELETE refusés. Une vérification passée ne se réécrit pas.

## Newsletter — modèles de mail et envois

### `mail_categories`

Categories de courriel liees aux evenements. Elles classent a la fois les modeles et les envois : un envoi herite de la categorie de son modele.

| Colonne | Type | Nul | Description |
|---|---|---|---|
| `id_mail_categories` | integer | non | Identifiant de la categorie. |
| `code` | varchar(40) | non | Code technique lu par le code Python. Ne change jamais. |
| `label` | varchar(120) | non | Libelle affiche dans l'interface. |
| `note` | varchar(255) | non | Ce que la categorie sert a dire, affiche sous son titre. |
| `sort_order` | smallint | non | Ordre d'affichage : celui du cycle de vie d'un evenement. |
| `created_at` | timestamptz | non | Date de creation (UTC). |
| `updated_at` | timestamptz | non | Date de derniere modification (UTC). |

**Contraintes**

- `pk_mail_categories` — PRIMARY KEY (id_mail_categories)
- `uq_mail_categories_code` — UNIQUE (code)
- `uq_mail_categories_code` — UNIQUE (code) WHERE 

### `mail_templates`

Modeles de courriel. Le corps est insere dans la coquille commune : la banniere et la signature ne sont donc pas recopiees a chaque modele.

| Colonne | Type | Nul | Description |
|---|---|---|---|
| `id_mail_templates` | integer | non | Identifiant du modele. |
| `id_mail_categories` | integer | non | Categorie du modele. Les envois en heritent. |
| `name` | varchar(160) | non | Nom du modele dans la liste. |
| `subject` | varchar(200) | non | Objet du message, variables comprises. |
| `preheader` | varchar(255) | oui | Premiere ligne visible dans la liste de la boite de reception. |
| `body_html` | text | non | Corps du message, insere dans la coquille commune (banniere et signature). Les variables s'y ecrivent entre doubles accolades. |
| `variables_json` | jsonb | oui | Variables attendues par le modele, sans les accolades. |
| `status` | varchar(20) | non | draft (non proposable a l'envoi) \| published. |
| `version_label` | varchar(20) | non | Version courante, recopiee sur chaque envoi produit. |
| `is_standard` | boolean | non | Modele livre avec l'application, cree par l'installation des standards. |
| `id_users_created_by` | integer | oui | Utilisateur qui a cree le modele. |
| `id_users_changed_by` | integer | oui | Utilisateur de la derniere modification. |
| `created_at` | timestamptz | non | Date de creation (UTC). |
| `updated_at` | timestamptz | non | Date de derniere modification (UTC). |
| `deleted_at` | timestamptz | oui | Archivage : le modele disparait des listes, les envois y renvoient toujours. |

**Contraintes**

- `ck_mail_templates_ck_mail_templates_status` — CHECK (((status)::text = ANY ((ARRAY['draft'::character varying, 'published'::character varying])::text[])))
- `fk_mail_templates_id_mail_categories_mail_categories` — FOREIGN KEY (id_mail_categories) REFERENCES mail_categories(id_mail_categories)
- `fk_mail_templates_id_users_changed_by_users` — FOREIGN KEY (id_users_changed_by) REFERENCES users(id_users)
- `fk_mail_templates_id_users_created_by_users` — FOREIGN KEY (id_users_created_by) REFERENCES users(id_users)
- `pk_mail_templates` — PRIMARY KEY (id_mail_templates)
- `uq_mail_templates_name` — UNIQUE (deleted_at IS NULL) WHERE (deleted_at IS NULL)

### `mail_template_versions`

Historique des versions d'un modele, en ajout seul. Chaque enregistrement du modele y depose l'etat precedent.

| Colonne | Type | Nul | Description |
|---|---|---|---|
| `id_mail_template_versions` | integer | non | Identifiant de la version. |
| `id_mail_templates` | integer | non | Modele concerne. Ses versions disparaissent avec lui. |
| `label` | varchar(20) | non | Nom de la version (v1, v2...). |
| `subject` | varchar(200) | non | Objet, tel qu'a cette date. |
| `preheader` | varchar(255) | oui | Pre-entete, tel qu'a cette date. |
| `body_html` | text | non | Corps, tel qu'a cette date. |
| `change_note` | text | oui | Ce que cette version a change, saisi par l'auteur. |
| `id_users_created_by` | integer | oui | Utilisateur qui a enregistre la version. |
| `created_at` | timestamptz | non | Date de creation (UTC). |

**Contraintes**

- `fk_mail_template_versions_id_mail_templates_mail_templates` — FOREIGN KEY (id_mail_templates) REFERENCES mail_templates(id_mail_templates) ON DELETE CASCADE
- `fk_mail_template_versions_id_users_created_by_users` — FOREIGN KEY (id_users_created_by) REFERENCES users(id_users)
- `pk_mail_template_versions` — PRIMARY KEY (id_mail_template_versions)
- `uq_mail_template_versions_id_mail_templates` — UNIQUE (id_mail_templates, label)
- `uq_mail_template_versions_id_mail_templates` — UNIQUE (id_mail_templates, label) WHERE 

### `newsletter_send_statuses`

Etats d'un envoi : envoye, programme, envoye en partie, echec. L'etat est DEDUIT du resultat de l'envoi, jamais saisi.

| Colonne | Type | Nul | Description |
|---|---|---|---|
| `id_newsletter_send_statuses` | integer | non | Identifiant de l'etat. |
| `code` | varchar(40) | non | Code technique lu par le code Python. Ne change jamais. |
| `label` | varchar(120) | non | Libelle affiche dans l'interface. |
| `sort_order` | smallint | non | Ordre d'affichage des filtres. |
| `created_at` | timestamptz | non | Date de creation (UTC). |
| `updated_at` | timestamptz | non | Date de derniere modification (UTC). |

**Contraintes**

- `pk_newsletter_send_statuses` — PRIMARY KEY (id_newsletter_send_statuses)
- `uq_newsletter_send_statuses_code` — UNIQUE (code)
- `uq_newsletter_send_statuses_code` — UNIQUE (code) WHERE 

### `newsletter_sends`

Un envoi de newsletter : le message parti, le compte qui l'a expedie et ses cumuls de remise.

| Colonne | Type | Nul | Description |
|---|---|---|---|
| `id_newsletter_sends` | integer | non | Identifiant de l'envoi. |
| `id_mail_templates` | integer | oui | Modele utilise. Vide si le modele a ete archive depuis. |
| `id_mail_categories` | integer | non | Categorie, heritee du modele au moment de l'envoi. |
| `id_email_accounts` | integer | non | Compte d'envoi qui a expedie les messages. |
| `id_newsletter_send_statuses` | integer | non | Etat de l'envoi. |
| `subject` | varchar(200) | non | Objet reellement expedie, variables substituees. |
| `event_title` | varchar(200) | oui | Evenement auquel l'envoi se rattache. |
| `template_name_denormalized` | varchar(160) | non | Nom du modele AU MOMENT de l'envoi : le modele peut etre renomme depuis. |
| `template_version_denormalized` | varchar(20) | non | Version du modele au moment de l'envoi. |
| `recipient_count` | integer | non | Destinataires vises. |
| `delivered_count` | integer | non | Messages acceptes par le serveur d'envoi. C'est tout ce qu'un serveur SMTP rend : ni ouvertures ni clics ne transitent par lui. |
| `failure_note` | text | oui | Renseigne quand l'envoi a echoue, en tout ou partie. |
| `scheduled_at` | timestamptz | oui | Date prevue d'un envoi programme (UTC). |
| `sent_at` | timestamptz | oui | Moment ou l'envoi a ete tente (UTC). Vide tant qu'il est programme. |
| `id_users_created_by` | integer | oui | Utilisateur qui a declenche l'envoi. |
| `created_at` | timestamptz | non | Date de creation (UTC). |
| `updated_at` | timestamptz | non | Date de derniere modification (UTC). |

**Contraintes**

- `ck_newsletter_sends_ck_newsletter_sends_delivered_count` — CHECK ((delivered_count <= recipient_count))
- `fk_newsletter_sends_id_email_accounts_email_accounts` — FOREIGN KEY (id_email_accounts) REFERENCES email_accounts(id_email_accounts)
- `fk_newsletter_sends_id_mail_categories_mail_categories` — FOREIGN KEY (id_mail_categories) REFERENCES mail_categories(id_mail_categories)
- `fk_newsletter_sends_id_mail_templates_mail_templates` — FOREIGN KEY (id_mail_templates) REFERENCES mail_templates(id_mail_templates)
- `fk_newsletter_sends_id_users_created_by_users` — FOREIGN KEY (id_users_created_by) REFERENCES users(id_users)
- `fk_newsletter_sends_status` — FOREIGN KEY (id_newsletter_send_statuses) REFERENCES newsletter_send_statuses(id_newsletter_send_statuses)
- `pk_newsletter_sends` — PRIMARY KEY (id_newsletter_sends)

### `newsletter_send_recipients`

Detail par destinataire d'un envoi : accepte ou refuse, et le motif du refus. C'est de ces lignes que viennent les cumuls de l'envoi.

| Colonne | Type | Nul | Description |
|---|---|---|---|
| `id_newsletter_send_recipients` | integer | non | Identifiant de la ligne destinataire. |
| `id_newsletter_sends` | integer | non | Envoi concerne. Ses destinataires disparaissent avec lui. |
| `email` | varchar(255) | non | Adresse du destinataire, toujours en minuscules. |
| `display_name` | varchar(120) | oui | Nom du destinataire, utilise par la variable prenom. |
| `is_delivered` | boolean | non | Vrai si le serveur d'envoi a accepte le message pour cette adresse. |
| `error_message` | text | oui | Refus du serveur pour cette adresse, tel qu'il l'a formule. |
| `sent_at` | timestamptz | oui | Moment de la tentative pour cette adresse (UTC). |
| `created_at` | timestamptz | non | Date de creation (UTC). |

**Contraintes**

- `fk_newsletter_send_recipients_send` — FOREIGN KEY (id_newsletter_sends) REFERENCES newsletter_sends(id_newsletter_sends) ON DELETE CASCADE
- `pk_newsletter_send_recipients` — PRIMARY KEY (id_newsletter_send_recipients)
- `uq_newsletter_send_recipients_id_newsletter_sends` — UNIQUE (id_newsletter_sends, email)
- `uq_newsletter_send_recipients_id_newsletter_sends` — UNIQUE (id_newsletter_sends, email) WHERE
