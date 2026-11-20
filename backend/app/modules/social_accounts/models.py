"""Tables du module Comptes reseaux sociaux.

Dix tables. `social_platforms`, onzieme du module, vit dans le module
`platforms` : quatre modules la lisent, en faire la propriete d'un seul aurait
cree une dependance de tous vers lui.

Les contraintes, index et commentaires sont declares ici A L'IDENTIQUE de la
migration 0003 : `alembic check` echoue sur le moindre ecart.
"""

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

MODES_DE_CREDENTIAL = ("own", "inherited")
ISSUES_DE_PASSAGE = ("succeeded", "empty", "failed")
NATURES_DE_MESURE = ("stock", "flux")


class SocialAccountStatus(Base):
    """Etat d'un compte raccorde."""

    __tablename__ = "social_account_statuses"
    __table_args__ = (
        UniqueConstraint("code", name="uq_social_account_statuses_code"),
        {"comment": "Etats d'un compte raccorde : connecte, a reconnecter, deconnecte."},
    )

    id_social_account_statuses: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40))
    label: Mapped[str] = mapped_column(String(80))
    sort_order: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SocialAccountErrorCause(Base):
    """Cause de panne, dans le vocabulaire d'IAGORA."""

    __tablename__ = "social_account_error_causes"
    __table_args__ = (
        UniqueConstraint("code", name="uq_social_account_error_causes_code"),
        CheckConstraint(
            "id_social_account_statuses_target IS NULL OR writes_on_account",
            name="etat_vise_implique_ecriture",
        ),
        {
            "comment": (
                "Causes de panne d'un compte, dans le vocabulaire d'IAGORA et non "
                "dans celui des reseaux. La liste est ouverte : chaque cause "
                "designe l'etat ou elle place le compte, ce qui sort la regle "
                "« quand telle panne survient, fais ceci » du code des connecteurs."
            )
        },
    )

    id_social_account_error_causes: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40))
    label: Mapped[str] = mapped_column(String(120))
    recommended_action: Mapped[str] = mapped_column(
        String(255),
        comment="Phrase ecrite pour le charge de communication, pas pour un developpeur.",
    )
    writes_on_account: Mapped[bool] = mapped_column(
        Boolean,
        server_default=func.false(),
        comment="La panne remonte-t-elle jusqu'a la fiche du compte ?",
    )
    id_social_account_statuses_target: Mapped[int | None] = mapped_column(
        ForeignKey(
            "social_account_statuses.id_social_account_statuses",
            name="fk_social_account_error_causes_statuses_target",
        ),
        comment=(
            "Etat dans lequel cette panne place le compte. Nul pour une panne "
            "qui ne change pas l'etat. Sort la regle « quand telle panne "
            "survient, fais ceci » du code des connecteurs."
        ),
    )
    sort_order: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SocialAccount(Base):
    """Compte officiel de DATUM Academy raccorde a IAGORA."""

    __tablename__ = "social_accounts"
    __table_args__ = (
        Index(
            "uq_social_accounts_plateforme_externe",
            "id_social_platforms",
            "account_external_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        CheckConstraint(
            "credential_mode IN ('" + "', '".join(MODES_DE_CREDENTIAL) + "')",
            name="credential_mode",
        ),
        CheckConstraint(
            "credential_mode <> 'inherited' OR id_social_accounts_parent IS NOT NULL",
            name="heritage_exige_un_parent",
        ),
        CheckConstraint(
            "id_social_accounts_parent IS NULL OR id_social_accounts_parent <> id_social_accounts",
            name="parent_different_de_soi",
        ),
        {
            "comment": (
                "Comptes officiels de DATUM Academy raccordes a IAGORA. Les cles "
                "n'y sont plus : elles vivent dans social_account_tokens, une "
                "ligne par delivrance."
            )
        },
    )

    id_social_accounts: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_social_platforms: Mapped[int] = mapped_column(
        ForeignKey(
            "social_platforms.id_social_platforms", name="fk_social_accounts_id_social_platforms"
        )
    )
    id_social_account_statuses_current: Mapped[int] = mapped_column(
        ForeignKey(
            "social_account_statuses.id_social_account_statuses",
            name="fk_social_accounts_statuses_current",
        )
    )
    id_social_accounts_parent: Mapped[int | None] = mapped_column(
        ForeignKey("social_accounts.id_social_accounts", name="fk_social_accounts_parent"),
        comment=(
            "Compte dont celui-ci emprunte les cles : un compte Instagram "
            "rattache a sa page Facebook n'a aucune delivrance a son nom."
        ),
    )
    id_social_account_error_causes_current: Mapped[int | None] = mapped_column(
        ForeignKey(
            "social_account_error_causes.id_social_account_error_causes",
            name="fk_social_accounts_error_causes_current",
        )
    )
    account_external_id: Mapped[str] = mapped_column(
        String(120), comment="Identifiant du compte CHEZ le reseau, jamais celui d'IAGORA."
    )
    account_display_name: Mapped[str] = mapped_column(String(255))
    account_username: Mapped[str | None] = mapped_column(String(120))
    profile_url: Mapped[str | None] = mapped_column(
        String(512), comment="Adresse publique de la page ou du profil."
    )
    credential_mode: Mapped[str] = mapped_column(
        String(20), comment="own (cles a son nom) | inherited (cles du compte parent)."
    )
    current_error_message: Mapped[str | None] = mapped_column(
        Text, comment="Message brut du reseau, conserve pour le diagnostic."
    )
    id_users_created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id_users", name="fk_social_accounts_id_users_created_by_users")
    )
    id_users_changed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id_users", name="fk_social_accounts_id_users_changed_by_users")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SocialAccountToken(Base):
    """Une delivrance de cles. Une seule active par compte."""

    __tablename__ = "social_account_tokens"
    __table_args__ = (
        Index(
            "uq_social_account_tokens_actif",
            "id_social_accounts",
            unique=True,
            postgresql_where=text("superseded_at IS NULL AND revoked_at IS NULL"),
        ),
        {
            "comment": (
                "Une ligne par delivrance de cles. Un renouvellement cree une "
                "nouvelle ligne et marque la precedente remplacee : l'historique "
                "des autorisations fait partie de la tracabilite. Pas d'updated_at, "
                "la ligne est ecrite une fois."
            )
        },
    )

    id_social_account_tokens: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_social_accounts: Mapped[int] = mapped_column(
        ForeignKey(
            "social_accounts.id_social_accounts",
            name="fk_social_account_tokens_id_social_accounts",
        )
    )
    access_token_encrypted: Mapped[str] = mapped_column(
        Text, comment="Chiffre par Fernet. Le jeton en clair ne touche jamais le disque."
    )
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text)
    access_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refresh_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    granted_api_permissions_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, comment="Permissions reellement accordees par la plateforme."
    )
    token_kind: Mapped[str | None] = mapped_column(
        String(40),
        comment=(
            "Sorte de jeton chez la plateforme. Vocabulaire libre tant que le "
            "module 07 n'a pas branche les connecteurs."
        ),
    )
    obtained_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    superseded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="Remplacement par une delivrance plus recente."
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    id_users_created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id_users", name="fk_social_account_tokens_id_users_created_by_users"),
        comment=(
            "Rempli quand une personne a fait le parcours d'autorisation, vide "
            "quand la tache de fond a renouvele seule."
        ),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SocialPost(Base):
    """Post paru sur un reseau."""

    __tablename__ = "social_posts"
    __table_args__ = (
        UniqueConstraint(
            "id_social_accounts", "post_external_id", name="uq_social_posts_compte_externe"
        ),
        {
            "comment": (
                "Posts parus sur les reseaux. archived_on_platform_at est un geste "
                "humain, deleted_on_platform_at un constat fait lors d'un passage : "
                "les deux ne se confondent pas."
            )
        },
    )

    id_social_posts: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_social_accounts: Mapped[int] = mapped_column(
        ForeignKey("social_accounts.id_social_accounts", name="fk_social_posts_id_social_accounts")
    )
    post_external_id: Mapped[str] = mapped_column(
        String(255), comment="Identifiant du post CHEZ le reseau."
    )
    permalink: Mapped[str | None] = mapped_column(String(1024))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_on_platform_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="Retire de la plateforme par une personne."
    )
    id_users_archived_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id_users", name="fk_social_posts_id_users_archived_by_users")
    )
    deleted_on_platform_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="Constate absent lors d'un passage."
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SocialAccountStatisticType(Base):
    """Vocabulaire ferme des mesures."""

    __tablename__ = "social_account_statistic_types"
    __table_args__ = (
        UniqueConstraint("code", name="uq_social_account_statistic_types_code"),
        CheckConstraint("nature IN ('" + "', '".join(NATURES_DE_MESURE) + "')", name="nature"),
        CheckConstraint("nature <> 'stock' OR NOT is_summable", name="stock_non_cumulable"),
        {
            "comment": (
                "Vocabulaire ferme des mesures. Mesurer une statistique de plus "
                "ajoute une ligne de referentiel, non une colonne."
            )
        },
    )

    id_social_account_statistic_types: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40))
    label: Mapped[str] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(String(255))
    nature: Mapped[str] = mapped_column(String(10), comment="stock (ne s'additionne pas) | flux.")
    is_summable: Mapped[bool] = mapped_column(
        Boolean, comment="La mesure se cumule-t-elle d'un jour a l'autre ?"
    )
    sort_order: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SocialPlatformStatisticType(Base):
    """Quel reseau fournit quelle mesure."""

    __tablename__ = "social_platform_statistic_types"
    __table_args__ = (
        UniqueConstraint(
            "id_social_platforms",
            "id_social_account_statistic_types",
            name="uq_social_platform_statistic_types_couple",
        ),
        {
            "comment": (
                "Quel reseau fournit quelle mesure, et sous quel nom chez lui. "
                "Permet a l'ecran de distinguer « zero », « pas encore releve » et "
                "« ce reseau ne le fournit pas », et au collecteur de savoir quels "
                "appels faire sans liste codee en dur."
            )
        },
    )

    id_social_platform_statistic_types: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_social_platforms: Mapped[int] = mapped_column(
        ForeignKey(
            "social_platforms.id_social_platforms",
            name="fk_social_platform_statistic_types_plateforme",
        )
    )
    id_social_account_statistic_types: Mapped[int] = mapped_column(
        ForeignKey(
            "social_account_statistic_types.id_social_account_statistic_types",
            name="fk_social_platform_statistic_types_mesure",
        )
    )
    platform_metric_name: Mapped[str] = mapped_column(
        String(120), comment="Nom de la mesure CHEZ le reseau."
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SocialAccountStatistic(Base):
    """Un releve : un compte, un jour mesure, une lecture."""

    __tablename__ = "social_account_statistics"
    __table_args__ = (
        Index(
            "ix_social_account_statistics_dernier",
            "id_social_accounts",
            "metric_date",
            text("collected_at DESC"),
        ),
        {
            "comment": (
                "Un releve par compte, par jour mesure et par lecture. Actualiser "
                "en cours de journee n'ecrase rien : la valeur d'un jour est le "
                "releve le plus recent de ce jour. PAS d'unicite sur (compte, jour) "
                "pour cette raison."
            )
        },
    )

    id_social_account_statistics: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_social_accounts: Mapped[int] = mapped_column(
        ForeignKey(
            "social_accounts.id_social_accounts",
            name="fk_social_account_statistics_id_social_accounts",
        )
    )
    metric_date: Mapped[date] = mapped_column(Date, comment="Jour MESURE.")
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment=(
            "Instant de la LECTURE. Les deux different : les reseaux publient "
            "leurs chiffres avec retard et les corrigent apres coup."
        ),
    )
    raw_response_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, comment="Reponse brute du reseau, conservee telle quelle."
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SocialAccountStatisticValue(Base):
    """Une mesure relevee."""

    __tablename__ = "social_account_statistic_values"
    __table_args__ = (
        UniqueConstraint(
            "id_social_account_statistics",
            "id_social_account_statistic_types",
            name="uq_social_account_statistic_values_couple",
        ),
        {
            "comment": (
                "Une ligne par mesure relevee. L'ABSENCE de ligne veut dire « non "
                "mesure par le reseau », jamais zero : c'est pourquoi la valeur "
                "n'est pas nullable et qu'aucune ligne n'est creee a vide."
            )
        },
    )

    id_social_account_statistic_values: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_social_account_statistics: Mapped[int] = mapped_column(
        ForeignKey(
            "social_account_statistics.id_social_account_statistics",
            name="fk_social_account_statistic_values_releve",
        )
    )
    id_social_account_statistic_types: Mapped[int] = mapped_column(
        ForeignKey(
            "social_account_statistic_types.id_social_account_statistic_types",
            name="fk_social_account_statistic_values_type",
        )
    )
    value: Mapped[int] = mapped_column(
        BigInteger,
        comment="L'absence de ligne vaut « non mesure par le reseau », jamais zero.",
    )


class SocialAccountSync(Base):
    """Un passage du collecteur."""

    __tablename__ = "social_account_syncs"
    __table_args__ = (
        Index(
            "uq_social_account_syncs_en_cours",
            "id_social_accounts",
            "sync_kind",
            unique=True,
            postgresql_where=text("finished_at IS NULL"),
        ),
        CheckConstraint(
            "sync_outcome IS NULL OR sync_outcome IN ('" + "', '".join(ISSUES_DE_PASSAGE) + "')",
            name="sync_outcome",
        ),
        CheckConstraint(
            "(finished_at IS NULL) = (sync_outcome IS NULL)", name="issue_et_fin_ensemble"
        ),
        {
            "comment": (
                "Carnet des passages : quand IAGORA est alle chercher quelque "
                "chose, pour quel compte, et jusqu'ou il avait releve. La ligne "
                "nait au DEBUT du passage, pour qu'un processus tue laisse une "
                "trace. Trois issues, parce que « on y est alle, il n'y avait "
                "rien » n'est pas « on n'y est pas alle »."
            )
        },
    )

    id_social_account_syncs: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_social_accounts: Mapped[int] = mapped_column(
        ForeignKey(
            "social_accounts.id_social_accounts",
            name="fk_social_account_syncs_id_social_accounts",
        )
    )
    sync_kind: Mapped[str] = mapped_column(
        String(40), comment="Sorte de passage. Vocabulaire libre jusqu'au module 07."
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sync_outcome: Mapped[str | None] = mapped_column(String(20))
    covered_until_date: Mapped[date | None] = mapped_column(
        Date, comment="Jusqu'ou le releve est alle."
    )
    id_social_account_error_causes: Mapped[int | None] = mapped_column(
        ForeignKey(
            "social_account_error_causes.id_social_account_error_causes",
            name="fk_social_account_syncs_error_causes",
        )
    )
    retry_after: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="Instant avant lequel il est inutile de reessayer."
    )
    id_users_triggered_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id_users", name="fk_social_account_syncs_id_users_triggered_by_users")
    )
