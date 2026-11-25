"""Ajout de la table `ai_prompts` pour gérer les Prompts système et Prompt templates.

Supporte le versionnage (`version_number`), l'affectation par tâche métier
(`task_code`) et la sélection d'un gabarit actif par défaut (`is_default`)
pour les écrans `/admin/prompts/system` et `/admin/prompts/templates`.

Note : sur une branche où la migration `0009` (Newsletter) est déjà présente,
adapter `down_revision = "0009"` avant d'exécuter `alembic upgrade head`.

Révision : 0010_ai_prompts
Révision précédente : 0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_ai_prompts"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROMPT_KINDS = ("system", "template")
PROMPT_TASK_CODES = (
    "publication_description",
    "message_reply",
    "image_generation",
    "image_description",
    "rag_synthesis",
    "newsletter_content",
)


def upgrade() -> None:
    op.create_table(
        "ai_prompts",
        sa.Column("id_ai_prompts", sa.Integer, sa.Identity(always=False), nullable=False),
        sa.Column(
            "prompt_kind",
            sa.String(20),
            nullable=False,
            comment="system (prompt systeme) | template (gabarit reutilisable).",
        ),
        sa.Column("task_code", sa.String(60), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("version_number", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("description", sa.String(300), nullable=True),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("id_users_created_by", sa.Integer, nullable=True),
        sa.Column("id_users_changed_by", sa.Integer, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id_ai_prompts", name="pk_ai_prompts"),
        sa.ForeignKeyConstraint(
            ["id_users_created_by"],
            ["users.id_users"],
            name="fk_ai_prompts_id_users_created_by_users",
        ),
        sa.ForeignKeyConstraint(
            ["id_users_changed_by"],
            ["users.id_users"],
            name="fk_ai_prompts_id_users_changed_by_users",
        ),
        sa.CheckConstraint(
            "prompt_kind IN ('" + "', '".join(PROMPT_KINDS) + "')",
            name="prompt_kind",
        ),
        sa.CheckConstraint(
            "task_code IN ('" + "', '".join(PROMPT_TASK_CODES) + "')",
            name="task_code",
        ),
        sa.CheckConstraint("version_number >= 1", name="version_positive"),
        comment=(
            "Prompts systeme et gabarits (templates) versionnes par tache metier IA. "
            "Au plus un gabarit actif par defaut par couple (prompt_kind, task_code)."
        ),
    )
    op.create_index(
        "uq_ai_prompts_defaut_actif",
        "ai_prompts",
        ["prompt_kind", "task_code"],
        unique=True,
        postgresql_where=sa.text("is_default IS TRUE AND deleted_at IS NULL"),
    )
    op.create_index(
        "ix_ai_prompts_kind_task",
        "ai_prompts",
        ["prompt_kind", "task_code"],
    )

    op.execute(
        "CREATE TRIGGER trg_ai_prompts_updated_at BEFORE UPDATE ON ai_prompts "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )

    # Amorçage initial de gabarits Datum Academy / IAGORA
    op.bulk_insert(
        sa.table(
            "ai_prompts",
            sa.column("prompt_kind", sa.String),
            sa.column("task_code", sa.String),
            sa.column("title", sa.String),
            sa.column("version_number", sa.Integer),
            sa.column("content", sa.Text),
            sa.column("description", sa.String),
            sa.column("is_default", sa.Boolean),
        ),
        [
            {
                "prompt_kind": "system",
                "task_code": "publication_description",
                "title": "Éditorial LinkedIn & Meta Datum Academy",
                "version_number": 1,
                "content": (
                    "Tu es le responsable éditorial de Datum Academy. Rédige des publications "
                    "engageantes, structurées et orientées conversion pour LinkedIn et Meta. "
                    "Ton : professionnel, accessible, concret. Longueur : 120 à 180 mots maximum "
                    "avec un appel à l'action clair."
                ),
                "description": "Prompt système principal pour la rédaction de descriptions de posts.",
                "is_default": True,
            },
            {
                "prompt_kind": "system",
                "task_code": "publication_description",
                "title": "Éditorial Court & Percutant (Instagram / Facebook)",
                "version_number": 2,
                "content": (
                    "Tu es community manager de Datum Academy. Rédige une légende courte "
                    "(60 à 100 mots), dynamique et aérée avec 3 points clés et 4 hashtags ciblés."
                ),
                "description": "Variante concise adaptée aux carrousels et Reels.",
                "is_default": False,
            },
            {
                "prompt_kind": "system",
                "task_code": "message_reply",
                "title": "Conseiller Pédagogique WhatsApp / Messenger",
                "version_number": 1,
                "content": (
                    "Tu es conseiller pédagogique Datum Academy sur WhatsApp et Messenger. "
                    "Réponds de manière chaleureuse, claire et concise (moins de 120 mots). "
                    "Utilise uniquement les informations vérifiées et propose un appel de 10 minutes."
                ),
                "description": "Ton rassurant pour la messagerie unifiée.",
                "is_default": True,
            },
            {
                "prompt_kind": "system",
                "task_code": "image_generation",
                "title": "Direction Artistique Datum Academy",
                "version_number": 1,
                "content": (
                    "Tu es directeur artistique senior chez Datum Academy. Produis ou retouche "
                    "des visuels modernes et lisibles sur mobile (bleu nuit #0F172A, indigo #4F46E5, "
                    "blanc pur), avec un contraste élevé et une mise en page épurée."
                ),
                "description": "Respect strict de la charte visuelle Datum Academy.",
                "is_default": True,
            },
            {
                "prompt_kind": "system",
                "task_code": "image_description",
                "title": "Analyste Vision & Accessibilité",
                "version_number": 1,
                "content": (
                    "Analyse objectivement l'image fournie : sujets principaux, palette chromatique, "
                    "ambiance, lisibilité mobile et texte alternatif SEO concis."
                ),
                "description": "Indexation des médias de référence.",
                "is_default": True,
            },
            {
                "prompt_kind": "system",
                "task_code": "rag_synthesis",
                "title": "Assistant Documentaire RAG Strict",
                "version_number": 1,
                "content": (
                    "Tu es l'assistant RAG de Datum Academy. Réponds UNIQUEMENT à partir des extraits "
                    "documentaires fournis, en citant chaque source entre crochets. Si l'information "
                    "est absente, indique-le explicitement sans extrapoler."
                ),
                "description": "Garantit zéro hallucination sur les règlements et syllabus.",
                "is_default": True,
            },
            {
                "prompt_kind": "template",
                "task_code": "publication_description",
                "title": "Lancement Nouvelle Cohorte / Formation",
                "version_number": 1,
                "content": (
                    "Rédige un post de lancement pour la formation « {{nom_formation}} » "
                    "(durée : {{duree}}, format : {{format}}). Cible : {{cible}}. "
                    "Mets en avant les bénéfices concrets et ajoute le lien {{lien_inscription}}."
                ),
                "description": "Gabarit paramétrable pour les ouvertures d'inscriptions.",
                "is_default": True,
            },
            {
                "prompt_kind": "template",
                "task_code": "message_reply",
                "title": "Réponse Demande Tarif & Prérequis",
                "version_number": 1,
                "content": (
                    "Réponds au message du prospect : « {{message_prospect}} » en t'appuyant sur "
                    "la fiche formation {{nom_formation}} (tarif : {{tarif}}, prérequis : {{prerequis}}) "
                    "et propose les créneaux : {{creneaux}}."
                ),
                "description": "Gabarit standard pour les questions commerciales entrantes.",
                "is_default": True,
            },
            {
                "prompt_kind": "template",
                "task_code": "image_generation",
                "title": "Flyer Annonce Atelier / Webinaire",
                "version_number": 1,
                "content": (
                    "Crée un visuel {{ratio}} annonçant l'événement « {{titre_evenement}} » "
                    "le {{date_evenement}}. Style : {{style_visuel}}, fond bleu nuit, accent indigo, "
                    "composition épurée adaptée au flux mobile."
                ),
                "description": "Gabarit de création visuelle pour webinaires et ateliers.",
                "is_default": True,
            },
        ],
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_ai_prompts_updated_at ON ai_prompts")
    op.drop_index("ix_ai_prompts_kind_task", table_name="ai_prompts")
    op.drop_index("uq_ai_prompts_defaut_actif", table_name="ai_prompts")
    op.drop_table("ai_prompts")
