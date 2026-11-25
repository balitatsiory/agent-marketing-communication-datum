"""Module 07 Newsletter — modèles de mail et envois.

Six tables :
- `mail_categories` : référentiel des catégories de courriel (confirmation,
  rappel, modification, compte rendu, visionnage) ;
- `mail_templates` : les modèles, leur objet et leur corps HTML ;
- `mail_template_versions` : l'historique des versions, en ajout seul ;
- `newsletter_send_statuses` : référentiel des états d'un envoi ;
- `newsletter_sends` : un envoi, avec ses cumuls de remise ;
- `newsletter_send_recipients` : le détail par destinataire.

Insère également les droits `manage_mail_templates` (710) et `send_newsletters`
(720), les cinq catégories et les quatre états.

Pourquoi deux référentiels et un CHECK : les catégories et les états sont
AFFICHÉS avec un libellé et peuvent évoluer, ils ont donc leur table. L'état
d'un modèle (`draft` / `published`) est binaire, figé, et ne porte aucune règle
métier : un VARCHAR et un CHECK suffisent, comme `media.kind`.

Révision : 0010
Révision précédente : 0009
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TEMPLATE_STATUSES = ("draft", "published")

CATEGORIES = [
    (
        "registration_confirmation",
        "Confirmation d'inscription",
        "Envoye a la minute ou quelqu'un s'inscrit.",
        10,
    ),
    ("reminder", "Rappel", "Programme a J-7, J-1 et H-2 avant la seance.", 20),
    (
        "change_or_cancellation",
        "Modification ou annulation",
        "Declenche a la main : c'est une mauvaise nouvelle, elle se relit.",
        30,
    ),
    ("report", "Compte rendu", "Envoye dans les 48 h, avec les points cles de la seance.", 40),
    ("replay", "Visionnage", "Envoye des la mise en ligne de la rediffusion.", 50),
]

SEND_STATUSES = [
    ("sent", "Envoye", 10),
    ("scheduled", "Programme", 20),
    ("partial", "Envoye en partie", 30),
    ("failed", "Echec", 40),
]


def upgrade() -> None:
    # ----------------------------------------------------------------- référentiels
    op.create_table(
        "mail_categories",
        sa.Column(
            "id_mail_categories",
            sa.Integer,
            sa.Identity(always=False),
            nullable=False,
            comment="Identifiant de la categorie.",
        ),
        sa.Column(
            "code",
            sa.String(40),
            nullable=False,
            comment="Code technique lu par le code Python. Ne change jamais.",
        ),
        sa.Column(
            "label", sa.String(120), nullable=False, comment="Libelle affiche dans l'interface."
        ),
        sa.Column(
            "note",
            sa.String(255),
            nullable=False,
            comment="Ce que la categorie sert a dire, affiche sous son titre.",
        ),
        sa.Column(
            "sort_order",
            sa.SmallInteger,
            nullable=False,
            comment="Ordre d'affichage : celui du cycle de vie d'un evenement.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Date de creation (UTC).",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Date de derniere modification (UTC).",
        ),
        sa.PrimaryKeyConstraint("id_mail_categories", name="pk_mail_categories"),
        sa.UniqueConstraint("code", name="uq_mail_categories_code"),
        comment=(
            "Categories de courriel liees aux evenements. Elles classent a la fois "
            "les modeles et les envois : un envoi herite de la categorie de son modele."
        ),
    )

    op.create_table(
        "newsletter_send_statuses",
        sa.Column(
            "id_newsletter_send_statuses",
            sa.Integer,
            sa.Identity(always=False),
            nullable=False,
            comment="Identifiant de l'etat.",
        ),
        sa.Column(
            "code",
            sa.String(40),
            nullable=False,
            comment="Code technique lu par le code Python. Ne change jamais.",
        ),
        sa.Column(
            "label", sa.String(120), nullable=False, comment="Libelle affiche dans l'interface."
        ),
        sa.Column(
            "sort_order", sa.SmallInteger, nullable=False, comment="Ordre d'affichage des filtres."
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Date de creation (UTC).",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Date de derniere modification (UTC).",
        ),
        sa.PrimaryKeyConstraint("id_newsletter_send_statuses", name="pk_newsletter_send_statuses"),
        sa.UniqueConstraint("code", name="uq_newsletter_send_statuses_code"),
        comment=(
            "Etats d'un envoi : envoye, programme, envoye en partie, echec. "
            "L'etat est DEDUIT du resultat de l'envoi, jamais saisi."
        ),
    )

    # ----------------------------------------------------------------- modèles
    op.create_table(
        "mail_templates",
        sa.Column(
            "id_mail_templates",
            sa.Integer,
            sa.Identity(always=False),
            nullable=False,
            comment="Identifiant du modele.",
        ),
        sa.Column(
            "id_mail_categories",
            sa.Integer,
            nullable=False,
            comment="Categorie du modele. Les envois en heritent.",
        ),
        sa.Column("name", sa.String(160), nullable=False, comment="Nom du modele dans la liste."),
        sa.Column(
            "subject",
            sa.String(200),
            nullable=False,
            comment="Objet du message, variables comprises.",
        ),
        sa.Column(
            "preheader",
            sa.String(255),
            nullable=True,
            comment="Premiere ligne visible dans la liste de la boite de reception.",
        ),
        sa.Column(
            "body_html",
            sa.Text,
            nullable=False,
            comment=(
                "Corps du message, insere dans la coquille commune (banniere et "
                "signature). Les variables s'y ecrivent entre doubles accolades."
            ),
        ),
        sa.Column(
            "variables_json",
            postgresql.JSONB,
            nullable=True,
            comment="Variables attendues par le modele, sans les accolades.",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="draft",
            comment="draft (non proposable a l'envoi) | published.",
        ),
        sa.Column(
            "version_label",
            sa.String(20),
            nullable=False,
            server_default="v1",
            comment="Version courante, recopiee sur chaque envoi produit.",
        ),
        sa.Column(
            "is_standard",
            sa.Boolean,
            nullable=False,
            server_default=sa.false(),
            comment="Modele livre avec l'application, cree par l'installation des standards.",
        ),
        sa.Column(
            "id_users_created_by",
            sa.Integer,
            nullable=True,
            comment="Utilisateur qui a cree le modele.",
        ),
        sa.Column(
            "id_users_changed_by",
            sa.Integer,
            nullable=True,
            comment="Utilisateur de la derniere modification.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Date de creation (UTC).",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Date de derniere modification (UTC).",
        ),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Archivage : le modele disparait des listes, les envois y renvoient toujours.",
        ),
        sa.PrimaryKeyConstraint("id_mail_templates", name="pk_mail_templates"),
        sa.ForeignKeyConstraint(
            ["id_mail_categories"],
            ["mail_categories.id_mail_categories"],
            name="fk_mail_templates_id_mail_categories_mail_categories",
        ),
        sa.ForeignKeyConstraint(
            ["id_users_created_by"],
            ["users.id_users"],
            name="fk_mail_templates_id_users_created_by_users",
        ),
        sa.ForeignKeyConstraint(
            ["id_users_changed_by"],
            ["users.id_users"],
            name="fk_mail_templates_id_users_changed_by_users",
        ),
        sa.CheckConstraint(
            "status IN ('" + "', '".join(TEMPLATE_STATUSES) + "')",
            name="ck_mail_templates_status",
        ),
        comment=(
            "Modeles de courriel. Le corps est insere dans la coquille commune : "
            "la banniere et la signature ne sont donc pas recopiees a chaque modele."
        ),
    )
    op.create_index(
        "uq_mail_templates_name",
        "mail_templates",
        ["name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "mail_template_versions",
        sa.Column(
            "id_mail_template_versions",
            sa.Integer,
            sa.Identity(always=False),
            nullable=False,
            comment="Identifiant de la version.",
        ),
        sa.Column(
            "id_mail_templates",
            sa.Integer,
            nullable=False,
            comment="Modele concerne. Ses versions disparaissent avec lui.",
        ),
        sa.Column("label", sa.String(20), nullable=False, comment="Nom de la version (v1, v2...)."),
        sa.Column("subject", sa.String(200), nullable=False, comment="Objet, tel qu'a cette date."),
        sa.Column("preheader", sa.String(255), nullable=True, comment="Pre-entete, tel qu'a cette date."),
        sa.Column("body_html", sa.Text, nullable=False, comment="Corps, tel qu'a cette date."),
        sa.Column(
            "change_note",
            sa.Text,
            nullable=True,
            comment="Ce que cette version a change, saisi par l'auteur.",
        ),
        sa.Column(
            "id_users_created_by",
            sa.Integer,
            nullable=True,
            comment="Utilisateur qui a enregistre la version.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Date de creation (UTC).",
        ),
        sa.PrimaryKeyConstraint("id_mail_template_versions", name="pk_mail_template_versions"),
        sa.ForeignKeyConstraint(
            ["id_mail_templates"],
            ["mail_templates.id_mail_templates"],
            name="fk_mail_template_versions_id_mail_templates_mail_templates",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["id_users_created_by"],
            ["users.id_users"],
            name="fk_mail_template_versions_id_users_created_by_users",
        ),
        sa.UniqueConstraint(
            "id_mail_templates", "label", name="uq_mail_template_versions_id_mail_templates"
        ),
        comment=(
            "Historique des versions d'un modele, en ajout seul. Chaque "
            "enregistrement du modele y depose l'etat precedent."
        ),
    )

    # ----------------------------------------------------------------- envois
    op.create_table(
        "newsletter_sends",
        sa.Column(
            "id_newsletter_sends",
            sa.Integer,
            sa.Identity(always=False),
            nullable=False,
            comment="Identifiant de l'envoi.",
        ),
        sa.Column(
            "id_mail_templates",
            sa.Integer,
            nullable=True,
            comment="Modele utilise. Vide si le modele a ete archive depuis.",
        ),
        sa.Column(
            "id_mail_categories",
            sa.Integer,
            nullable=False,
            comment="Categorie, heritee du modele au moment de l'envoi.",
        ),
        sa.Column(
            "id_email_accounts",
            sa.Integer,
            nullable=False,
            comment="Compte d'envoi qui a expedie les messages.",
        ),
        sa.Column(
            "id_newsletter_send_statuses", sa.Integer, nullable=False, comment="Etat de l'envoi."
        ),
        sa.Column(
            "subject",
            sa.String(200),
            nullable=False,
            comment="Objet reellement expedie, variables substituees.",
        ),
        sa.Column(
            "event_title",
            sa.String(200),
            nullable=True,
            comment="Evenement auquel l'envoi se rattache.",
        ),
        sa.Column(
            "template_name_denormalized",
            sa.String(160),
            nullable=False,
            comment="Nom du modele AU MOMENT de l'envoi : le modele peut etre renomme depuis.",
        ),
        sa.Column(
            "template_version_denormalized",
            sa.String(20),
            nullable=False,
            comment="Version du modele au moment de l'envoi.",
        ),
        sa.Column(
            "recipient_count",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
            comment="Destinataires vises.",
        ),
        sa.Column(
            "delivered_count",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
            comment=(
                "Messages acceptes par le serveur d'envoi. C'est tout ce qu'un serveur "
                "SMTP rend : ni ouvertures ni clics ne transitent par lui."
            ),
        ),
        sa.Column(
            "failure_note",
            sa.Text,
            nullable=True,
            comment="Renseigne quand l'envoi a echoue, en tout ou partie.",
        ),
        sa.Column(
            "scheduled_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Date prevue d'un envoi programme (UTC).",
        ),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Moment ou l'envoi a ete tente (UTC). Vide tant qu'il est programme.",
        ),
        sa.Column(
            "id_users_created_by",
            sa.Integer,
            nullable=True,
            comment="Utilisateur qui a declenche l'envoi.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Date de creation (UTC).",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Date de derniere modification (UTC).",
        ),
        sa.PrimaryKeyConstraint("id_newsletter_sends", name="pk_newsletter_sends"),
        sa.ForeignKeyConstraint(
            ["id_mail_templates"],
            ["mail_templates.id_mail_templates"],
            name="fk_newsletter_sends_id_mail_templates_mail_templates",
        ),
        sa.ForeignKeyConstraint(
            ["id_mail_categories"],
            ["mail_categories.id_mail_categories"],
            name="fk_newsletter_sends_id_mail_categories_mail_categories",
        ),
        sa.ForeignKeyConstraint(
            ["id_email_accounts"],
            ["email_accounts.id_email_accounts"],
            name="fk_newsletter_sends_id_email_accounts_email_accounts",
        ),
        sa.ForeignKeyConstraint(
            ["id_newsletter_send_statuses"],
            ["newsletter_send_statuses.id_newsletter_send_statuses"],
            name="fk_newsletter_sends_status",
        ),
        sa.ForeignKeyConstraint(
            ["id_users_created_by"],
            ["users.id_users"],
            name="fk_newsletter_sends_id_users_created_by_users",
        ),
        sa.CheckConstraint(
            "delivered_count <= recipient_count", name="ck_newsletter_sends_delivered_count"
        ),
        comment=(
            "Un envoi de newsletter : le message parti, le compte qui l'a expedie "
            "et ses cumuls de remise."
        ),
    )
    op.create_index(
        "ix_newsletter_sends_id_email_accounts", "newsletter_sends", ["id_email_accounts"]
    )

    op.create_table(
        "newsletter_send_recipients",
        sa.Column(
            "id_newsletter_send_recipients",
            sa.Integer,
            sa.Identity(always=False),
            nullable=False,
            comment="Identifiant de la ligne destinataire.",
        ),
        sa.Column(
            "id_newsletter_sends",
            sa.Integer,
            nullable=False,
            comment="Envoi concerne. Ses destinataires disparaissent avec lui.",
        ),
        sa.Column(
            "email",
            sa.String(255),
            nullable=False,
            comment="Adresse du destinataire, toujours en minuscules.",
        ),
        sa.Column(
            "display_name",
            sa.String(120),
            nullable=True,
            comment="Nom du destinataire, utilise par la variable prenom.",
        ),
        sa.Column(
            "is_delivered",
            sa.Boolean,
            nullable=False,
            server_default=sa.false(),
            comment="Vrai si le serveur d'envoi a accepte le message pour cette adresse.",
        ),
        sa.Column(
            "error_message",
            sa.Text,
            nullable=True,
            comment="Refus du serveur pour cette adresse, tel qu'il l'a formule.",
        ),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Moment de la tentative pour cette adresse (UTC).",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Date de creation (UTC).",
        ),
        sa.PrimaryKeyConstraint(
            "id_newsletter_send_recipients", name="pk_newsletter_send_recipients"
        ),
        sa.ForeignKeyConstraint(
            ["id_newsletter_sends"],
            ["newsletter_sends.id_newsletter_sends"],
            name="fk_newsletter_send_recipients_send",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "id_newsletter_sends", "email", name="uq_newsletter_send_recipients_id_newsletter_sends"
        ),
        comment=(
            "Detail par destinataire d'un envoi : accepte ou refuse, et le motif "
            "du refus. C'est de ces lignes que viennent les cumuls de l'envoi."
        ),
    )

    for table in (
        "mail_categories",
        "newsletter_send_statuses",
        "mail_templates",
        "newsletter_sends",
    ):
        op.execute(
            f"CREATE TRIGGER trg_{table}_updated_at BEFORE UPDATE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
        )

    # L'historique des versions est en ajout seul, comme celui des verifications
    # du module Comptes d'envoi. `refuser_reecriture()` vient de la migration 0009.
    op.execute(
        "CREATE TRIGGER trg_mail_template_versions_ajout_seul "
        "BEFORE UPDATE OR DELETE ON mail_template_versions "
        "FOR EACH ROW EXECUTE FUNCTION refuser_reecriture()"
    )

    # ----------------------------------------------------------------- amorces
    for code, label, note, rang in CATEGORIES:
        op.execute(
            sa.text(
                "INSERT INTO mail_categories (code, label, note, sort_order) "
                "VALUES (:c, :l, :n, :r) ON CONFLICT (code) DO NOTHING"
            ).bindparams(c=code, l=label, n=note, r=rang)
        )

    for code, label, rang in SEND_STATUSES:
        op.execute(
            sa.text(
                "INSERT INTO newsletter_send_statuses (code, label, sort_order) "
                "VALUES (:c, :l, :r) ON CONFLICT (code) DO NOTHING"
            ).bindparams(c=code, l=label, r=rang)
        )

    op.execute(
        """
        INSERT INTO permissions (code, label, description, sort_order)
        VALUES
            ('manage_mail_templates', 'Gerer les modeles de mail',
             'Creer et modifier les modeles de courriel des evenements.', 710),
            ('send_newsletters', 'Envoyer les newsletters',
             'Declencher un envoi depuis un modele publie.', 720)
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM user_permissions
        WHERE id_permissions IN (
            SELECT id_permissions FROM permissions
            WHERE code IN ('manage_mail_templates', 'send_newsletters')
        )
        """
    )
    op.execute(
        "DELETE FROM permissions WHERE code IN ('manage_mail_templates', 'send_newsletters')"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_mail_template_versions_ajout_seul ON mail_template_versions"
    )
    for table in (
        "mail_categories",
        "newsletter_send_statuses",
        "mail_templates",
        "newsletter_sends",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table}")
    op.drop_table("newsletter_send_recipients")
    op.drop_index("ix_newsletter_sends_id_email_accounts", table_name="newsletter_sends")
    op.drop_table("newsletter_sends")
    op.drop_table("mail_template_versions")
    op.drop_index("uq_mail_templates_name", table_name="mail_templates")
    op.drop_table("mail_templates")
    op.drop_table("newsletter_send_statuses")
    op.drop_table("mail_categories")
