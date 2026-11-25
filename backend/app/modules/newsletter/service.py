"""Règles métier du module Newsletter : modèles de mail et envois.

Deux principes tiennent ce fichier :

- **Un envoi raconte ce qui s'est passé, destinataire par destinataire.** Les
  cumuls (`recipient_count`, `delivered_count`) sont DÉDUITS des lignes de
  `newsletter_send_recipients`, jamais saisis : un total qui ne correspond pas
  au détail serait invérifiable.
- **Le module ne touche ni au mot de passe ni au client SMTP.** Il compose ses
  messages et les confie au service du module Comptes d'envoi.
"""

import logging
from datetime import UTC, datetime
from email.headerregistry import Address
from email.message import EmailMessage
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError, ConflictError, NotFoundError
from app.core.pagination import Page, PageParams
from app.modules.email_accounts import service as comptes_envoi
from app.modules.email_accounts.schemas import EmailAccountRead
from app.modules.newsletter import renderer
from app.modules.newsletter.constants import (
    DESTINATAIRES_MAX,
    MODELES_STANDARDS,
    SEND_STATUS_FAILED,
    SEND_STATUS_PARTIAL,
    SEND_STATUS_SENT,
    TEMPLATE_STATUS_PUBLISHED,
    VALEURS_EXEMPLE,
)
from app.modules.newsletter.models import (
    MailCategory,
    MailTemplate,
    MailTemplateVersion,
    NewsletterSend,
    NewsletterSendRecipient,
    NewsletterSendStatus,
)
from app.modules.newsletter.schemas import (
    CompteRead,
    MailCategoryRead,
    MailTemplateCreate,
    MailTemplatePreviewRead,
    MailTemplateRead,
    MailTemplateUpdate,
    MailTemplateVersionRead,
    NewsletterSendCreate,
    NewsletterSendDetailRead,
    NewsletterSendRead,
    NewsletterSendRecipientRead,
    NewsletterStatsRead,
    SendStatusRead,
)
from app.modules.users.models import User

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Référentiels
# ---------------------------------------------------------------------------


async def lister_categories(session: AsyncSession) -> list[MailCategoryRead]:
    """Catégories, dans l'ordre du cycle de vie d'un événement."""
    lignes = (
        await session.execute(select(MailCategory).order_by(MailCategory.sort_order))
    ).scalars()
    return [MailCategoryRead.model_validate(ligne) for ligne in lignes]


async def lister_statuts(session: AsyncSession) -> list[SendStatusRead]:
    lignes = (
        await session.execute(
            select(NewsletterSendStatus).order_by(NewsletterSendStatus.sort_order)
        )
    ).scalars()
    return [SendStatusRead.model_validate(ligne) for ligne in lignes]


async def _categorie_par_code(session: AsyncSession, code: str) -> MailCategory:
    categorie = (
        await session.execute(select(MailCategory).where(MailCategory.code == code))
    ).scalar_one_or_none()
    if categorie is None:
        raise ApiError(
            "mail_category_unknown", f"Catégorie de courriel inconnue : « {code} ».", 422
        )
    return categorie


async def _statut_par_code(session: AsyncSession, code: str) -> NewsletterSendStatus:
    statut = (
        await session.execute(select(NewsletterSendStatus).where(NewsletterSendStatus.code == code))
    ).scalar_one()
    return statut


# ---------------------------------------------------------------------------
# Modèles de mail
# ---------------------------------------------------------------------------


def _modele_to_read(
    modele: MailTemplate, categorie: MailCategory, auteur: User | None, usages: int
) -> MailTemplateRead:
    return MailTemplateRead(
        id_mail_templates=modele.id_mail_templates,
        category_code=categorie.code,
        category_label=categorie.label,
        category_note=categorie.note,
        name=modele.name,
        subject=modele.subject,
        preheader=modele.preheader,
        body_html=modele.body_html,
        variables=list(modele.variables_json or []),
        status=modele.status,  # type: ignore[arg-type]
        version_label=modele.version_label,
        is_standard=modele.is_standard,
        usage_count=usages,
        created_by_name=auteur.nom_affiche if auteur is not None else None,
        created_at=modele.created_at,
        updated_at=modele.updated_at,
    )


async def _usages_par_modele(session: AsyncSession) -> dict[int, int]:
    """Nombre d'envois produits par chaque modèle."""
    lignes = (
        await session.execute(
            select(NewsletterSend.id_mail_templates, func.count())
            .where(NewsletterSend.id_mail_templates.is_not(None))
            .group_by(NewsletterSend.id_mail_templates)
        )
    ).all()
    return {int(id_modele): int(nombre) for id_modele, nombre in lignes if id_modele is not None}


async def _charger_modele(
    session: AsyncSession, id_mail_templates: int
) -> tuple[MailTemplate, MailCategory, User | None]:
    ligne = (
        await session.execute(
            select(MailTemplate, MailCategory, User)
            .join(MailCategory, MailCategory.id_mail_categories == MailTemplate.id_mail_categories)
            .outerjoin(User, User.id_users == MailTemplate.id_users_created_by)
            .where(
                MailTemplate.id_mail_templates == id_mail_templates,
                MailTemplate.deleted_at.is_(None),
            )
        )
    ).first()
    if ligne is None:
        raise NotFoundError("Modèle de mail introuvable.")
    modele, categorie, auteur = ligne
    return modele, categorie, auteur


async def lister_modeles(
    session: AsyncSession,
    params: PageParams,
    category_code: str | None = None,
    status: str | None = None,
    recherche: str | None = None,
) -> Page[MailTemplateRead]:
    """Modèles actifs, catégorie par catégorie."""
    conditions: list[Any] = [MailTemplate.deleted_at.is_(None)]
    if category_code:
        conditions.append(MailCategory.code == category_code)
    if status:
        conditions.append(MailTemplate.status == status)
    if recherche:
        motif = f"%{recherche.strip().lower()}%"
        conditions.append(
            func.lower(MailTemplate.name).like(motif) | func.lower(MailTemplate.subject).like(motif)
        )

    base = (
        select(MailTemplate, MailCategory, User)
        .join(MailCategory, MailCategory.id_mail_categories == MailTemplate.id_mail_categories)
        .outerjoin(User, User.id_users == MailTemplate.id_users_created_by)
        .where(*conditions)
    )
    total = (
        await session.execute(
            select(func.count())
            .select_from(MailTemplate)
            .join(MailCategory, MailCategory.id_mail_categories == MailTemplate.id_mail_categories)
            .where(*conditions)
        )
    ).scalar_one()

    lignes = (
        await session.execute(
            base.order_by(MailCategory.sort_order, MailTemplate.name)
            .offset(params.offset)
            .limit(params.size)
        )
    ).all()
    usages = await _usages_par_modele(session)
    items = [
        _modele_to_read(modele, categorie, auteur, usages.get(modele.id_mail_templates, 0))
        for modele, categorie, auteur in lignes
    ]
    return Page.build(items, int(total), params)


async def obtenir_modele(session: AsyncSession, id_mail_templates: int) -> MailTemplateRead:
    modele, categorie, auteur = await _charger_modele(session, id_mail_templates)
    usages = await _usages_par_modele(session)
    return _modele_to_read(modele, categorie, auteur, usages.get(id_mail_templates, 0))


async def _refuser_nom_pris(session: AsyncSession, nom: str, sauf: int | None = None) -> None:
    requete = select(MailTemplate.id_mail_templates).where(
        MailTemplate.deleted_at.is_(None), MailTemplate.name == nom
    )
    if sauf is not None:
        requete = requete.where(MailTemplate.id_mail_templates != sauf)
    if (await session.execute(requete)).first() is not None:
        raise ConflictError(f"Un modèle porte déjà le nom « {nom} ».")


async def creer_modele(
    session: AsyncSession, donnees: MailTemplateCreate, par: User
) -> MailTemplateRead:
    """Enregistre un modèle et sa première version."""
    categorie = await _categorie_par_code(session, donnees.category_code)
    nom = donnees.name.strip()
    await _refuser_nom_pris(session, nom)

    modele = MailTemplate(
        id_mail_categories=categorie.id_mail_categories,
        name=nom,
        subject=donnees.subject.strip(),
        preheader=(donnees.preheader or "").strip() or None,
        body_html=donnees.body_html,
        variables_json=renderer.variables_de(donnees.subject, donnees.body_html),
        status=donnees.status,
        version_label="v1",
        id_users_created_by=par.id_users,
        id_users_changed_by=par.id_users,
    )
    session.add(modele)
    await session.flush()
    _ajouter_version(session, modele, "Création du modèle.", par)
    await session.commit()
    await session.refresh(modele)
    logger.info("Modèle de mail %s créé", modele.id_mail_templates)
    return _modele_to_read(modele, categorie, par, 0)


def _ajouter_version(
    session: AsyncSession, modele: MailTemplate, note: str | None, par: User
) -> None:
    """Dépose l'état COURANT du modèle dans l'historique.

    L'historique est en ajout seul : une version déposée ne se corrige pas,
    elle se remplace par la suivante.
    """
    session.add(
        MailTemplateVersion(
            id_mail_templates=modele.id_mail_templates,
            label=modele.version_label,
            subject=modele.subject,
            preheader=modele.preheader,
            body_html=modele.body_html,
            change_note=note,
            id_users_created_by=par.id_users,
        )
    )


def _version_suivante(courante: str) -> str:
    """v1 → v2. Une étiquette illisible repart de v2 plutôt que d'échouer."""
    if courante.startswith("v") and courante[1:].isdigit():
        return f"v{int(courante[1:]) + 1}"
    return "v2"


async def modifier_modele(
    session: AsyncSession, id_mail_templates: int, donnees: MailTemplateUpdate, par: User
) -> MailTemplateRead:
    """Modifie un modèle. L'état précédent part dans l'historique des versions."""
    modele, categorie, auteur = await _charger_modele(session, id_mail_templates)
    champs = donnees.model_dump(exclude_unset=True)

    contenu_change = bool({"subject", "preheader", "body_html"} & champs.keys())

    if champs.get("category_code"):
        categorie = await _categorie_par_code(session, str(champs["category_code"]))
        modele.id_mail_categories = categorie.id_mail_categories
    if champs.get("name"):
        modele.name = str(champs["name"]).strip()
    if champs.get("subject"):
        modele.subject = str(champs["subject"]).strip()
    if "preheader" in champs:
        modele.preheader = (str(champs["preheader"] or "")).strip() or None
    if champs.get("body_html"):
        modele.body_html = str(champs["body_html"])
    if champs.get("status"):
        modele.status = str(champs["status"])

    modele.variables_json = renderer.variables_de(modele.subject, modele.body_html)
    modele.id_users_changed_by = par.id_users

    # Une version porte l'etat qu'elle a RENDU VIVANT : on incremente d'abord,
    # puis on enregistre le nouveau contenu sous la nouvelle etiquette. Deposer
    # l'etat precedent donnerait deux lignes « v1 », que l'unicite refuse.
    if contenu_change:
        modele.version_label = _version_suivante(modele.version_label)
        _ajouter_version(session, modele, donnees.change_note, par)

    with session.no_autoflush:
        await _refuser_nom_pris(session, modele.name, sauf=id_mail_templates)

    await session.commit()
    await session.refresh(modele)
    usages = await _usages_par_modele(session)
    logger.info("Modèle de mail %s modifié", id_mail_templates)
    return _modele_to_read(modele, categorie, auteur, usages.get(id_mail_templates, 0))


async def archiver_modele(session: AsyncSession, id_mail_templates: int, par: User) -> None:
    """Archive le modèle. Les envois produits continuent d'y renvoyer."""
    modele, _, _ = await _charger_modele(session, id_mail_templates)
    modele.deleted_at = datetime.now(UTC)
    modele.id_users_changed_by = par.id_users
    await session.commit()
    logger.info("Modèle de mail %s archivé", id_mail_templates)


async def lister_versions(
    session: AsyncSession, id_mail_templates: int
) -> list[MailTemplateVersionRead]:
    """Historique des versions, la plus récente en tête."""
    await _charger_modele(session, id_mail_templates)
    lignes = (
        await session.execute(
            select(MailTemplateVersion, User)
            .outerjoin(User, User.id_users == MailTemplateVersion.id_users_created_by)
            .where(MailTemplateVersion.id_mail_templates == id_mail_templates)
            # L'identifiant départage : `now()` vaut l'heure de la TRANSACTION,
            # donc deux versions écrites d'affilée portent la même date.
            .order_by(
                MailTemplateVersion.created_at.desc(),
                MailTemplateVersion.id_mail_template_versions.desc(),
            )
        )
    ).all()
    return [
        MailTemplateVersionRead(
            id_mail_template_versions=version.id_mail_template_versions,
            label=version.label,
            subject=version.subject,
            change_note=version.change_note,
            author_name=auteur.nom_affiche if auteur is not None else None,
            created_at=version.created_at,
        )
        for version, auteur in lignes
    ]


async def installer_les_standards(session: AsyncSession, par: User) -> list[MailTemplateRead]:
    """Installe les cinq modèles livrés avec l'application.

    Idempotent : un modèle standard déjà présent n'est ni recréé ni réécrit —
    il a pu être modifié depuis, et l'écraser perdrait ce travail.
    """
    crees: list[MailTemplateRead] = []
    for standard in MODELES_STANDARDS:
        existe = (
            await session.execute(
                select(MailTemplate.id_mail_templates).where(
                    MailTemplate.name == standard["name"], MailTemplate.deleted_at.is_(None)
                )
            )
        ).first()
        if existe is not None:
            continue

        categorie = await _categorie_par_code(session, standard["category"])
        corps = renderer.corps_standard(standard["fichier"])
        modele = MailTemplate(
            id_mail_categories=categorie.id_mail_categories,
            name=standard["name"],
            subject=standard["subject"],
            preheader=standard["preheader"],
            body_html=corps,
            variables_json=renderer.variables_de(standard["subject"], corps),
            status=TEMPLATE_STATUS_PUBLISHED,
            version_label="v1",
            is_standard=True,
            id_users_created_by=par.id_users,
            id_users_changed_by=par.id_users,
        )
        session.add(modele)
        await session.flush()
        _ajouter_version(session, modele, "Modèle standard installé.", par)
        crees.append(_modele_to_read(modele, categorie, par, 0))

    await session.commit()
    logger.info("Modèles standards : %s installé(s)", len(crees))
    return crees


def _valeurs_completees(variables: dict[str, str]) -> dict[str, str]:
    """Valeurs fournies, complétées par les valeurs d'exemple."""
    return {**VALEURS_EXEMPLE, **{k: v for k, v in variables.items() if v != ""}}


async def apercu_modele(
    session: AsyncSession, id_mail_templates: int, variables: dict[str, str]
) -> MailTemplatePreviewRead:
    """Le message tel qu'il partira, variables substituées."""
    modele, _, _ = await _charger_modele(session, id_mail_templates)
    valeurs = _valeurs_completees(variables)
    attendues = renderer.variables_de(modele.subject, modele.body_html)
    html_rendu = renderer.rendre_html(modele.body_html, modele.subject, modele.preheader, valeurs)
    return MailTemplatePreviewRead(
        subject=renderer.substituer(modele.subject, valeurs),
        preheader=renderer.substituer(modele.preheader or modele.subject, valeurs),
        html=html_rendu,
        text=renderer.rendre_texte(html_rendu),
        variables=attendues,
        missing_variables=[nom for nom in attendues if nom not in valeurs],
    )


# ---------------------------------------------------------------------------
# Envois
# ---------------------------------------------------------------------------


def _taux(delivered: int, targeted: int) -> int:
    return round(delivered / targeted * 100) if targeted else 0


def _envoi_to_read(
    envoi: NewsletterSend,
    categorie: MailCategory,
    statut: NewsletterSendStatus,
    auteur: User | None,
    compte: EmailAccountRead | None,
) -> NewsletterSendRead:
    tente = statut.code in (SEND_STATUS_SENT, SEND_STATUS_PARTIAL)
    rejets = max(0, envoi.recipient_count - envoi.delivered_count) if tente else 0
    return NewsletterSendRead(
        id_newsletter_sends=envoi.id_newsletter_sends,
        category_code=categorie.code,
        category_label=categorie.label,
        status_code=statut.code,
        status_label=statut.label,
        subject=envoi.subject,
        event_title=envoi.event_title,
        template_name=envoi.template_name_denormalized,
        template_version=envoi.template_version_denormalized,
        id_mail_templates=envoi.id_mail_templates,
        id_email_accounts=envoi.id_email_accounts,
        account_label=compte.label if compte else "Compte archivé",
        account_from_email=compte.from_email if compte else "—",
        recipient_count=envoi.recipient_count,
        delivered_count=envoi.delivered_count,
        bounce_count=rejets,
        delivery_rate=_taux(envoi.delivered_count, envoi.recipient_count) if tente else 0,
        failure_note=envoi.failure_note,
        scheduled_at=envoi.scheduled_at,
        sent_at=envoi.sent_at,
        created_by_name=auteur.nom_affiche if auteur is not None else None,
        created_at=envoi.created_at,
    )


async def _comptes_par_id(session: AsyncSession) -> dict[int, EmailAccountRead]:
    """Les comptes d'envoi, lus par le service du module qui les détient."""
    comptes = await comptes_envoi.lister_comptes(session)
    return {compte.id_email_accounts: compte for compte in comptes}


def _conditions_envois(
    id_email_accounts: int | None,
    category_code: str | None,
    status_code: str | None,
    recherche: str | None,
) -> list[Any]:
    conditions: list[Any] = []
    if id_email_accounts is not None:
        conditions.append(NewsletterSend.id_email_accounts == id_email_accounts)
    if category_code:
        conditions.append(MailCategory.code == category_code)
    if status_code:
        conditions.append(NewsletterSendStatus.code == status_code)
    if recherche:
        motif = f"%{recherche.strip().lower()}%"
        conditions.append(
            func.lower(NewsletterSend.subject).like(motif)
            | func.lower(NewsletterSend.template_name_denormalized).like(motif)
            | func.lower(func.coalesce(NewsletterSend.event_title, "")).like(motif)
        )
    return conditions


def _jointures(requete: Any) -> Any:
    """Pose les deux jointures communes aux requetes d'envois.

    Typee en `Any` a dessein : `Select` est un generique VARIADIQUE, et le
    traverser dans une fonction perd la liste de ses colonnes. L'ecrire
    precisement couterait plus cher que ce que ca rapporte ici.
    """
    return requete.join(
        MailCategory, MailCategory.id_mail_categories == NewsletterSend.id_mail_categories
    ).join(
        NewsletterSendStatus,
        NewsletterSendStatus.id_newsletter_send_statuses
        == NewsletterSend.id_newsletter_send_statuses,
    )


async def lister_envois(
    session: AsyncSession,
    params: PageParams,
    id_email_accounts: int | None = None,
    category_code: str | None = None,
    status_code: str | None = None,
    recherche: str | None = None,
) -> Page[NewsletterSendRead]:
    """Envois, du plus récent au plus ancien.

    `id_email_accounts` vide signifie « tous les comptes cumulés ».
    """
    conditions = _conditions_envois(id_email_accounts, category_code, status_code, recherche)

    total: int = (
        await session.execute(
            _jointures(select(func.count()).select_from(NewsletterSend)).where(*conditions)
        )
    ).scalar_one()

    lignes = (
        await session.execute(
            _jointures(select(NewsletterSend, MailCategory, NewsletterSendStatus, User))
            .outerjoin(User, User.id_users == NewsletterSend.id_users_created_by)
            .where(*conditions)
            .order_by(
                func.coalesce(NewsletterSend.sent_at, NewsletterSend.created_at).desc(),
                NewsletterSend.id_newsletter_sends.desc(),
            )
            .offset(params.offset)
            .limit(params.size)
        )
    ).all()

    comptes = await _comptes_par_id(session)
    items = [
        _envoi_to_read(envoi, categorie, statut, auteur, comptes.get(envoi.id_email_accounts))
        for envoi, categorie, statut, auteur in lignes
    ]
    return Page.build(items, int(total), params)


async def obtenir_envoi(
    session: AsyncSession, id_newsletter_sends: int
) -> NewsletterSendDetailRead:
    """Un envoi et le sort de chacun de ses destinataires."""
    ligne = (
        await session.execute(
            _jointures(select(NewsletterSend, MailCategory, NewsletterSendStatus, User))
            .outerjoin(User, User.id_users == NewsletterSend.id_users_created_by)
            .where(NewsletterSend.id_newsletter_sends == id_newsletter_sends)
        )
    ).first()
    if ligne is None:
        raise NotFoundError("Envoi introuvable.")
    envoi, categorie, statut, auteur = ligne

    destinataires = (
        await session.execute(
            select(NewsletterSendRecipient)
            .where(NewsletterSendRecipient.id_newsletter_sends == id_newsletter_sends)
            .order_by(
                NewsletterSendRecipient.is_delivered,
                NewsletterSendRecipient.email,
            )
        )
    ).scalars()

    comptes = await _comptes_par_id(session)
    fiche = _envoi_to_read(envoi, categorie, statut, auteur, comptes.get(envoi.id_email_accounts))
    return NewsletterSendDetailRead(
        **fiche.model_dump(),
        recipients=[
            NewsletterSendRecipientRead.model_validate(destinataire)
            for destinataire in destinataires
        ],
    )


async def statistiques(
    session: AsyncSession, id_email_accounts: int | None = None
) -> NewsletterStatsRead:
    """Chiffres d'en-tête, recalculés à la demande.

    Rien n'est mis en cache : le bouton « Actualiser » de l'écran doit pouvoir
    montrer l'effet d'un envoi fait à la seconde d'avant.
    """
    conditions = _conditions_envois(id_email_accounts, None, None, None)

    lignes = (
        await session.execute(
            _jointures(
                select(
                    NewsletterSendStatus.code,
                    func.count(),
                    func.sum(NewsletterSend.recipient_count),
                    func.sum(NewsletterSend.delivered_count),
                ).select_from(NewsletterSend)
            )
            .where(*conditions)
            .group_by(NewsletterSendStatus.code)
        )
    ).all()

    envois = 0
    tentes = 0
    vises = 0
    remis = 0
    a_reprendre = 0
    for code, nombre, destinataires, delivres in lignes:
        envois += int(nombre)
        if code in (SEND_STATUS_SENT, SEND_STATUS_PARTIAL):
            tentes += int(nombre)
            vises += int(destinataires or 0)
            remis += int(delivres or 0)
        if code in (SEND_STATUS_PARTIAL, SEND_STATUS_FAILED):
            a_reprendre += int(nombre)

    par_categorie = (
        await session.execute(
            _jointures(
                select(
                    MailCategory.code, MailCategory.label, func.count(), MailCategory.sort_order
                ).select_from(NewsletterSend)
            )
            .where(*conditions)
            .group_by(MailCategory.code, MailCategory.label, MailCategory.sort_order)
            .order_by(MailCategory.sort_order)
        )
    ).all()

    par_statut = (
        await session.execute(
            _jointures(
                select(
                    NewsletterSendStatus.code,
                    NewsletterSendStatus.label,
                    func.count(),
                    NewsletterSendStatus.sort_order,
                ).select_from(NewsletterSend)
            )
            .where(*conditions)
            .group_by(
                NewsletterSendStatus.code,
                NewsletterSendStatus.label,
                NewsletterSendStatus.sort_order,
            )
            .order_by(NewsletterSendStatus.sort_order)
        )
    ).all()

    return NewsletterStatsRead(
        sends=envois,
        attempted=tentes,
        targeted=vises,
        delivered=remis,
        bounced=max(0, vises - remis),
        delivery_rate=_taux(remis, vises),
        needing_attention=a_reprendre,
        by_category=[
            CompteRead(code=code, label=label, count=int(nombre))
            for code, label, nombre, _ in par_categorie
        ],
        by_status=[
            CompteRead(code=code, label=label, count=int(nombre))
            for code, label, nombre, _ in par_statut
        ],
        computed_at=datetime.now(UTC),
    )


def _message_pour(
    compte: EmailAccountRead,
    sujet: str,
    html_rendu: str,
    texte: str,
    destinataire: NewsletterSendRecipient,
) -> EmailMessage:
    """Compose le message d'un destinataire : texte d'abord, HTML en second.

    L'ordre compte : un client qui ne sait pas lire le HTML affiche la première
    partie. La version texte n'est donc pas un ornement, c'est le repli.
    """
    message = EmailMessage()
    message["Subject"] = sujet
    message["From"] = (
        Address(display_name=compte.from_name, addr_spec=compte.from_email)
        if compte.from_name
        else Address(addr_spec=compte.from_email)
    )
    message["To"] = (
        Address(display_name=destinataire.display_name, addr_spec=destinataire.email)
        if destinataire.display_name
        else Address(addr_spec=destinataire.email)
    )
    if compte.reply_to_email:
        message["Reply-To"] = Address(addr_spec=compte.reply_to_email)
    message.set_content(texte)
    message.add_alternative(html_rendu, subtype="html")
    return message


async def creer_envoi(
    session: AsyncSession, donnees: NewsletterSendCreate, par: User
) -> NewsletterSendDetailRead:
    """Envoie un modèle publié à une liste de destinataires.

    L'envoi part MESSAGE PAR MESSAGE, avec le prénom de chacun : une liste en
    copie cachée afficherait le même « Bonjour » à tout le monde et exposerait
    les adresses les unes aux autres.
    """
    modele, categorie, _ = await _charger_modele(session, donnees.id_mail_templates)
    if modele.status != TEMPLATE_STATUS_PUBLISHED:
        raise ApiError(
            "mail_template_not_published",
            "Ce modèle est un brouillon : publiez-le avant de l'envoyer.",
            409,
        )
    if len(donnees.recipients) > DESTINATAIRES_MAX:
        raise ApiError(
            "too_many_recipients",
            f"Un envoi est limité à {DESTINATAIRES_MAX} destinataires pour l'instant.",
            422,
        )

    compte = await _compte_expediteur(session, donnees.id_email_accounts)
    statut_initial = await _statut_par_code(session, SEND_STATUS_FAILED)
    valeurs = _valeurs_completees(donnees.variables)

    envoi = NewsletterSend(
        id_mail_templates=modele.id_mail_templates,
        id_mail_categories=categorie.id_mail_categories,
        id_email_accounts=compte.id_email_accounts,
        id_newsletter_send_statuses=statut_initial.id_newsletter_send_statuses,
        subject=renderer.substituer(modele.subject, valeurs),
        event_title=(donnees.event_title or "").strip() or None,
        template_name_denormalized=modele.name,
        template_version_denormalized=modele.version_label,
        recipient_count=len(donnees.recipients),
        id_users_created_by=par.id_users,
    )
    session.add(envoi)
    await session.flush()

    lignes: list[NewsletterSendRecipient] = []
    vues: set[str] = set()
    for brut in donnees.recipients:
        adresse = str(brut.email).strip().lower()
        if adresse in vues:
            continue
        vues.add(adresse)
        ligne = NewsletterSendRecipient(
            id_newsletter_sends=envoi.id_newsletter_sends,
            email=adresse,
            display_name=(brut.display_name or "").strip() or None,
        )
        session.add(ligne)
        lignes.append(ligne)
    envoi.recipient_count = len(lignes)
    await session.flush()

    messages = []
    for ligne in lignes:
        propres = dict(valeurs)
        if ligne.display_name:
            # Le prénom est le premier mot du nom saisi : « Mialy Rakoto » dit
            # « Bonjour Mialy », pas « Bonjour Mialy Rakoto ».
            propres["prenom"] = ligne.display_name.split()[0]
        html_rendu = renderer.rendre_html(
            modele.body_html, modele.subject, modele.preheader, propres
        )
        messages.append(
            _message_pour(
                compte,
                renderer.substituer(modele.subject, propres),
                html_rendu,
                renderer.rendre_texte(html_rendu),
                ligne,
            )
        )

    resultats = await comptes_envoi.envoyer_messages(session, compte.id_email_accounts, messages)

    maintenant = datetime.now(UTC)
    remis = 0
    premier_refus: str | None = None
    for ligne, resultat in zip(lignes, resultats, strict=True):
        ligne.is_delivered = resultat.ok
        ligne.error_message = None if resultat.ok else resultat.message
        ligne.sent_at = maintenant
        if resultat.ok:
            remis += 1
        elif premier_refus is None:
            premier_refus = resultat.message

    envoi.delivered_count = remis
    envoi.sent_at = maintenant
    envoi.failure_note = premier_refus
    code = (
        SEND_STATUS_SENT
        if remis == len(lignes) and remis > 0
        else SEND_STATUS_PARTIAL
        if remis > 0
        else SEND_STATUS_FAILED
    )
    statut = await _statut_par_code(session, code)
    envoi.id_newsletter_send_statuses = statut.id_newsletter_send_statuses

    await session.commit()
    logger.info(
        "Envoi %s : %s message(s) sur %s accepté(s)",
        envoi.id_newsletter_sends,
        remis,
        len(lignes),
    )
    return await obtenir_envoi(session, envoi.id_newsletter_sends)


async def _compte_expediteur(
    session: AsyncSession, id_email_accounts: int | None
) -> EmailAccountRead:
    """Le compte demandé, ou le compte d'envoi actif à défaut."""
    if id_email_accounts is not None:
        return await comptes_envoi.obtenir_compte(session, id_email_accounts)
    compte = await comptes_envoi.trouver_compte_par_defaut(session)
    if compte is None:
        raise ApiError(
            "email_account_missing",
            "Aucun compte d'envoi actif : configurez-en un avant d'envoyer.",
            409,
        )
    return compte
