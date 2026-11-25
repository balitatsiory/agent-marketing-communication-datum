"""Routes du module Newsletter. Aucune règle métier ici."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.deps import SessionDep
from app.core.pagination import Page, PageParams, page_params
from app.modules.newsletter import service
from app.modules.newsletter.constants import MANAGE_MAIL_TEMPLATES, SEND_NEWSLETTERS
from app.modules.newsletter.schemas import (
    MailCategoryRead,
    MailTemplateCreate,
    MailTemplatePreviewRead,
    MailTemplatePreviewRequest,
    MailTemplateRead,
    MailTemplateUpdate,
    MailTemplateVersionRead,
    NewsletterSendCreate,
    NewsletterSendDetailRead,
    NewsletterSendRead,
    NewsletterStatsRead,
    SendStatusRead,
)
from app.modules.users.deps import CurrentUser, require
from app.modules.users.models import User

router = APIRouter(prefix="/newsletter", tags=["newsletter"])

PageDep = Annotated[PageParams, Depends(page_params)]
RedacteurModeles = Annotated[User, Depends(require(MANAGE_MAIL_TEMPLATES))]
Expediteur = Annotated[User, Depends(require(SEND_NEWSLETTERS))]


# ---------------------------------------------------------------------------
# Référentiels
# ---------------------------------------------------------------------------


@router.get(
    "/categories",
    response_model=list[MailCategoryRead],
    summary="Lister les catégories de courriel",
)
async def lister_categories(session: SessionDep, _: CurrentUser) -> list[MailCategoryRead]:
    return await service.lister_categories(session)


@router.get(
    "/send-statuses",
    response_model=list[SendStatusRead],
    summary="Lister les états d'envoi",
)
async def lister_statuts(session: SessionDep, _: CurrentUser) -> list[SendStatusRead]:
    return await service.lister_statuts(session)


# ---------------------------------------------------------------------------
# Modèles de mail
# ---------------------------------------------------------------------------


@router.get(
    "/mail-templates",
    response_model=Page[MailTemplateRead],
    summary="Lister les modèles de mail",
)
async def lister_modeles(
    session: SessionDep,
    _: CurrentUser,
    params: PageDep,
    category_code: Annotated[str | None, Query(max_length=40)] = None,
    status_filtre: Annotated[str | None, Query(alias="status", max_length=20)] = None,
    recherche: Annotated[str | None, Query(alias="search", max_length=120)] = None,
) -> Page[MailTemplateRead]:
    return await service.lister_modeles(session, params, category_code, status_filtre, recherche)


@router.post(
    "/mail-templates",
    response_model=MailTemplateRead,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un modèle de mail",
)
async def creer_modele(
    corps: MailTemplateCreate,
    session: SessionDep,
    par: RedacteurModeles,
    reponse: Response,
) -> MailTemplateRead:
    modele = await service.creer_modele(session, corps, par)
    reponse.headers["Location"] = f"/api/v1/newsletter/mail-templates/{modele.id_mail_templates}"
    return modele


@router.post(
    "/mail-templates/install-standards",
    response_model=list[MailTemplateRead],
    summary="Installer les cinq modèles standards (sans écraser l'existant)",
)
async def installer_les_standards(
    session: SessionDep, par: RedacteurModeles
) -> list[MailTemplateRead]:
    return await service.installer_les_standards(session, par)


@router.get(
    "/mail-templates/{id_mail_templates}",
    response_model=MailTemplateRead,
    summary="Lire un modèle de mail",
)
async def obtenir_modele(
    id_mail_templates: int, session: SessionDep, _: CurrentUser
) -> MailTemplateRead:
    return await service.obtenir_modele(session, id_mail_templates)


@router.patch(
    "/mail-templates/{id_mail_templates}",
    response_model=MailTemplateRead,
    summary="Modifier un modèle (l'état précédent part dans l'historique)",
)
async def modifier_modele(
    id_mail_templates: int,
    corps: MailTemplateUpdate,
    session: SessionDep,
    par: RedacteurModeles,
) -> MailTemplateRead:
    return await service.modifier_modele(session, id_mail_templates, corps, par)


@router.delete(
    "/mail-templates/{id_mail_templates}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archiver un modèle de mail",
)
async def archiver_modele(
    id_mail_templates: int, session: SessionDep, par: RedacteurModeles
) -> None:
    await service.archiver_modele(session, id_mail_templates, par)


@router.get(
    "/mail-templates/{id_mail_templates}/versions",
    response_model=list[MailTemplateVersionRead],
    summary="Historique des versions d'un modèle",
)
async def lister_versions(
    id_mail_templates: int, session: SessionDep, _: CurrentUser
) -> list[MailTemplateVersionRead]:
    return await service.lister_versions(session, id_mail_templates)


@router.post(
    "/mail-templates/{id_mail_templates}/preview",
    response_model=MailTemplatePreviewRead,
    summary="Aperçu du message, variables substituées",
)
async def apercu_modele(
    id_mail_templates: int,
    corps: MailTemplatePreviewRequest,
    session: SessionDep,
    _: CurrentUser,
) -> MailTemplatePreviewRead:
    return await service.apercu_modele(session, id_mail_templates, corps.variables)


# ---------------------------------------------------------------------------
# Envois
# ---------------------------------------------------------------------------


@router.get(
    "/sends",
    response_model=Page[NewsletterSendRead],
    summary="Lister les envois (tous comptes, ou un seul)",
)
async def lister_envois(
    session: SessionDep,
    _: CurrentUser,
    params: PageDep,
    id_email_accounts: Annotated[int | None, Query()] = None,
    category_code: Annotated[str | None, Query(max_length=40)] = None,
    status_code: Annotated[str | None, Query(max_length=40)] = None,
    recherche: Annotated[str | None, Query(alias="search", max_length=120)] = None,
) -> Page[NewsletterSendRead]:
    return await service.lister_envois(
        session, params, id_email_accounts, category_code, status_code, recherche
    )


@router.get(
    "/sends/stats",
    response_model=NewsletterStatsRead,
    summary="Chiffres d'en-tête de la boîte d'envois, recalculés à la demande",
)
async def statistiques(
    session: SessionDep,
    _: CurrentUser,
    id_email_accounts: Annotated[int | None, Query()] = None,
) -> NewsletterStatsRead:
    return await service.statistiques(session, id_email_accounts)


@router.post(
    "/sends",
    response_model=NewsletterSendDetailRead,
    status_code=status.HTTP_201_CREATED,
    summary="Envoyer un modèle publié à une liste de destinataires",
)
async def creer_envoi(
    corps: NewsletterSendCreate,
    session: SessionDep,
    par: Expediteur,
    reponse: Response,
) -> NewsletterSendDetailRead:
    envoi = await service.creer_envoi(session, corps, par)
    reponse.headers["Location"] = f"/api/v1/newsletter/sends/{envoi.id_newsletter_sends}"
    return envoi


@router.get(
    "/sends/{id_newsletter_sends}",
    response_model=NewsletterSendDetailRead,
    summary="Lire un envoi et le sort de chaque destinataire",
)
async def obtenir_envoi(
    id_newsletter_sends: int, session: SessionDep, _: CurrentUser
) -> NewsletterSendDetailRead:
    return await service.obtenir_envoi(session, id_newsletter_sends)
