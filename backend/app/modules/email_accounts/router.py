"""Routes du module Comptes d'envoi (SMTP). Aucune règle métier ici."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.deps import SessionDep
from app.modules.email_accounts import service
from app.modules.email_accounts.constants import MANAGE_EMAIL_ACCOUNTS
from app.modules.email_accounts.schemas import (
    EmailAccountCheckRead,
    EmailAccountCreate,
    EmailAccountPasswordSave,
    EmailAccountRead,
    EmailAccountTestMessage,
    EmailAccountUpdate,
    EmailAccountVerifyRead,
)
from app.modules.users.deps import CurrentUser, require
from app.modules.users.models import User

router = APIRouter(prefix="/email-accounts", tags=["comptes-d-envoi"])

# La lecture est ouverte à tout utilisateur connecté : la boîte d'envois a
# besoin de savoir quel compte expédie, et cette fiche ne porte aucun secret.
# Toute écriture, et tout échange avec le serveur, demandent le droit.
GestionnaireEnvois = Annotated[User, Depends(require(MANAGE_EMAIL_ACCOUNTS))]


@router.get(
    "",
    response_model=list[EmailAccountRead],
    summary="Lister les comptes d'envoi SMTP (sans jamais le mot de passe)",
)
async def lister_comptes(session: SessionDep, _: CurrentUser) -> list[EmailAccountRead]:
    return await service.lister_comptes(session)


@router.get(
    "/default",
    response_model=EmailAccountRead | None,
    summary="Compte d'envoi actif, celui qui expédiera les courriels",
)
async def obtenir_compte_par_defaut(session: SessionDep, _: CurrentUser) -> EmailAccountRead | None:
    return await service.trouver_compte_par_defaut(session)


@router.post(
    "",
    response_model=EmailAccountVerifyRead,
    status_code=status.HTTP_201_CREATED,
    summary="Enregistrer un compte d'envoi (mot de passe chiffré) et tester la connexion",
)
async def creer_compte(
    corps: EmailAccountCreate,
    session: SessionDep,
    par: GestionnaireEnvois,
    reponse: Response,
) -> EmailAccountVerifyRead:
    resultat = await service.creer_compte(session, corps, par)
    reponse.headers["Location"] = f"/api/v1/email-accounts/{resultat.account.id_email_accounts}"
    return resultat


@router.get(
    "/{id_email_accounts}",
    response_model=EmailAccountRead,
    summary="Lire un compte d'envoi",
)
async def obtenir_compte(
    id_email_accounts: int, session: SessionDep, _: CurrentUser
) -> EmailAccountRead:
    return await service.obtenir_compte(session, id_email_accounts)


@router.patch(
    "/{id_email_accounts}",
    response_model=EmailAccountRead,
    summary="Modifier un compte d'envoi (serveur, port, mode, expéditeur)",
)
async def modifier_compte(
    id_email_accounts: int,
    corps: EmailAccountUpdate,
    session: SessionDep,
    par: GestionnaireEnvois,
) -> EmailAccountRead:
    return await service.modifier_compte(session, id_email_accounts, corps, par)


@router.post(
    "/{id_email_accounts}/password",
    response_model=EmailAccountVerifyRead,
    summary="Remplacer le mot de passe d'un compte d'envoi",
)
async def remplacer_mot_de_passe(
    id_email_accounts: int,
    corps: EmailAccountPasswordSave,
    session: SessionDep,
    par: GestionnaireEnvois,
) -> EmailAccountVerifyRead:
    return await service.remplacer_mot_de_passe(session, id_email_accounts, corps, par)


@router.post(
    "/{id_email_accounts}/verify",
    response_model=EmailAccountVerifyRead,
    summary="Tester la connexion SMTP (authentification réelle, aucun message envoyé)",
)
async def verifier_compte(
    id_email_accounts: int, session: SessionDep, par: GestionnaireEnvois
) -> EmailAccountVerifyRead:
    return await service.verifier_compte(session, id_email_accounts, par)


@router.post(
    "/{id_email_accounts}/test-message",
    response_model=EmailAccountVerifyRead,
    summary="Envoyer un message de test depuis ce compte",
)
async def envoyer_message_de_test(
    id_email_accounts: int,
    corps: EmailAccountTestMessage,
    session: SessionDep,
    par: GestionnaireEnvois,
) -> EmailAccountVerifyRead:
    return await service.envoyer_message_de_test(session, id_email_accounts, corps, par)


@router.post(
    "/{id_email_accounts}/default",
    response_model=EmailAccountRead,
    summary="Désigner ce compte comme compte d'envoi actif",
)
async def definir_par_defaut(
    id_email_accounts: int, session: SessionDep, par: GestionnaireEnvois
) -> EmailAccountRead:
    return await service.definir_par_defaut(session, id_email_accounts, par)


@router.get(
    "/{id_email_accounts}/checks",
    response_model=list[EmailAccountCheckRead],
    summary="Historique des vérifications d'un compte d'envoi",
)
async def lister_verifications(
    id_email_accounts: int,
    session: SessionDep,
    _: CurrentUser,
    limite: Annotated[int, Query(ge=1, le=200)] = service.VERIFICATIONS_PAR_DEFAUT,
) -> list[EmailAccountCheckRead]:
    return await service.lister_verifications(session, id_email_accounts, limite)


@router.delete(
    "/{id_email_accounts}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archiver un compte d'envoi et révoquer son mot de passe",
)
async def archiver_compte(
    id_email_accounts: int, session: SessionDep, par: GestionnaireEnvois
) -> None:
    await service.archiver_compte(session, id_email_accounts, par)
