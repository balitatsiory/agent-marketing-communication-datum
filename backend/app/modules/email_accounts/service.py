"""Règles métier du module Comptes d'envoi (SMTP).

Points clés de sécurité :
- Le mot de passe de boîte est chiffré par `encrypt_token` (Fernet) avant toute
  écriture, exactement comme les jetons de plateformes et les clés OpenRouter.
- `decrypt_token` n'est appelé qu'en mémoire, au moment exact d'ouvrir une
  session SMTP, et le clair ne quitte jamais `smtp_client`.
- Aucune réponse de l'API ne porte le mot de passe, même chiffré.
- Les journaux ne portent que des identifiants de lignes : ni mot de passe, ni
  adresse de destinataire.

Point clé de cohérence : la ligne d'historique et l'état courant du compte
(`last_verify_*`) sont écrits dans la MÊME transaction, par une seule fonction.
Un compte qui s'affiche « vérifié » sans ligne d'historique correspondante
n'existe donc pas.
"""

import logging
from datetime import UTC, datetime
from email.headerregistry import Address
from email.message import EmailMessage

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError, ConflictError, NotFoundError
from app.core.security import decrypt_token, encrypt_token
from app.modules.email_accounts import smtp_client
from app.modules.email_accounts.constants import (
    CHECK_CONNECTION,
    CHECK_TEST_MESSAGE,
    SECURITY_SSL_TLS,
)
from app.modules.email_accounts.models import (
    EmailAccount,
    EmailAccountCheck,
    EmailAccountCredential,
)
from app.modules.email_accounts.schemas import (
    EmailAccountCheckRead,
    EmailAccountCreate,
    EmailAccountPasswordSave,
    EmailAccountRead,
    EmailAccountTestMessage,
    EmailAccountUpdate,
    EmailAccountVerifyRead,
)
from app.modules.email_accounts.smtp_client import SmtpResult, SmtpTarget
from app.modules.users.models import User

logger = logging.getLogger(__name__)

# Un mot de passe n'a pas de préfixe reconnaissable comme une clé d'API : en
# montrer le moindre caractère serait un aveu sans utilité. L'aperçu dit
# seulement qu'un mot de passe est enregistré.
APERCU_MASQUE = "••••••••"

# Nombre de vérifications renvoyées par défaut : de quoi voir la dernière panne
# et ce qui l'a précédée, sans charger un historique entier.
VERIFICATIONS_PAR_DEFAUT = 20


def _normaliser_adresse(valeur: str) -> str:
    """Une adresse se compare en minuscules, comme `users.email`."""
    return valeur.strip().lower()


# ---------------------------------------------------------------------------
# Lecture
# ---------------------------------------------------------------------------


def _to_read(
    compte: EmailAccount,
    identifiant: EmailAccountCredential | None,
    auteur: User | None = None,
) -> EmailAccountRead:
    return EmailAccountRead(
        id_email_accounts=compte.id_email_accounts,
        label=compte.label,
        host=compte.host,
        port=compte.port,
        security=compte.security,  # type: ignore[arg-type]
        username=compte.username,
        from_email=compte.from_email,
        from_name=compte.from_name,
        reply_to_email=compte.reply_to_email,
        timeout_seconds=compte.timeout_seconds,
        is_default=compte.is_default,
        has_password=identifiant is not None,
        password_masked=identifiant.password_masked if identifiant is not None else None,
        password_obtained_at=identifiant.obtained_at if identifiant is not None else None,
        last_verified_at=compte.last_verified_at,
        last_verify_ok=compte.last_verify_ok,
        last_verify_message=compte.last_verify_message,
        created_by_name=auteur.nom_affiche if auteur is not None else None,
        created_at=compte.created_at,
        updated_at=compte.updated_at,
    )


async def _identifiant_actif(
    session: AsyncSession, id_email_accounts: int
) -> EmailAccountCredential | None:
    """Le mot de passe en cours d'un compte, s'il en a un."""
    return (
        await session.execute(
            select(EmailAccountCredential).where(
                EmailAccountCredential.id_email_accounts == id_email_accounts,
                EmailAccountCredential.superseded_at.is_(None),
                EmailAccountCredential.revoked_at.is_(None),
            )
        )
    ).scalar_one_or_none()


async def _charger(
    session: AsyncSession, id_email_accounts: int
) -> tuple[EmailAccount, User | None]:
    """Charge un compte non archivé et son créateur. Lève 404 sinon."""
    ligne = (
        await session.execute(
            select(EmailAccount, User)
            .outerjoin(User, User.id_users == EmailAccount.id_users_created_by)
            .where(
                EmailAccount.id_email_accounts == id_email_accounts,
                EmailAccount.deleted_at.is_(None),
            )
        )
    ).first()
    if ligne is None:
        raise NotFoundError("Compte d'envoi introuvable.")
    compte, auteur = ligne
    return compte, auteur


async def lister_comptes(session: AsyncSession) -> list[EmailAccountRead]:
    """Comptes d'envoi actifs, le compte par défaut en tête."""
    lignes = (
        await session.execute(
            select(EmailAccount, User)
            .outerjoin(User, User.id_users == EmailAccount.id_users_created_by)
            .where(EmailAccount.deleted_at.is_(None))
            .order_by(EmailAccount.is_default.desc(), EmailAccount.label)
        )
    ).all()
    comptes: list[EmailAccountRead] = []
    for compte, auteur in lignes:
        identifiant = await _identifiant_actif(session, compte.id_email_accounts)
        comptes.append(_to_read(compte, identifiant, auteur))
    return comptes


async def obtenir_compte(session: AsyncSession, id_email_accounts: int) -> EmailAccountRead:
    compte, auteur = await _charger(session, id_email_accounts)
    return _to_read(compte, await _identifiant_actif(session, id_email_accounts), auteur)


async def trouver_compte_par_defaut(session: AsyncSession) -> EmailAccountRead | None:
    """Le compte qui servira aux envois, ou `None` si aucun n'est configuré.

    C'est ce que lit la boîte d'envois pour afficher son bandeau.
    """
    ligne = (
        await session.execute(
            select(EmailAccount, User)
            .outerjoin(User, User.id_users == EmailAccount.id_users_created_by)
            .where(EmailAccount.deleted_at.is_(None), EmailAccount.is_default.is_(True))
        )
    ).first()
    if ligne is None:
        return None
    compte, auteur = ligne
    identifiant = await _identifiant_actif(session, compte.id_email_accounts)
    return _to_read(compte, identifiant, auteur)


async def lister_verifications(
    session: AsyncSession,
    id_email_accounts: int,
    limite: int = VERIFICATIONS_PAR_DEFAUT,
) -> list[EmailAccountCheckRead]:
    """Historique des vérifications d'un compte, la plus récente en tête."""
    await _charger(session, id_email_accounts)
    lignes = (
        await session.execute(
            select(EmailAccountCheck, User)
            .outerjoin(User, User.id_users == EmailAccountCheck.id_users_checked_by)
            .where(EmailAccountCheck.id_email_accounts == id_email_accounts)
            .order_by(EmailAccountCheck.checked_at.desc())
            .limit(limite)
        )
    ).all()
    return [
        EmailAccountCheckRead(
            id_email_account_checks=verification.id_email_account_checks,
            kind=verification.kind,  # type: ignore[arg-type]
            is_ok=verification.is_ok,
            message=verification.message,
            recipient_email=verification.recipient_email,
            latency_ms=verification.latency_ms,
            checked_at=verification.checked_at,
            checked_by_name=auteur.nom_affiche if auteur is not None else None,
        )
        for verification, auteur in lignes
    ]


# ---------------------------------------------------------------------------
# Écriture
# ---------------------------------------------------------------------------


async def _refuser_doublon(
    session: AsyncSession,
    host: str,
    port: int,
    username: str,
    sauf: int | None = None,
) -> None:
    """Deux fois le même identifiant sur le même serveur n'a pas de sens."""
    requete = select(EmailAccount.id_email_accounts).where(
        EmailAccount.deleted_at.is_(None),
        EmailAccount.host == host,
        EmailAccount.port == port,
        EmailAccount.username == username,
    )
    if sauf is not None:
        requete = requete.where(EmailAccount.id_email_accounts != sauf)
    if (await session.execute(requete)).first() is not None:
        raise ConflictError(f"Un compte d'envoi existe déjà pour {username} sur {host}:{port}.")


async def _retirer_les_autres_defauts(session: AsyncSession, sauf: int | None = None) -> None:
    """Libère la place du compte par défaut.

    Un index unique partiel interdit deux comptes par défaut : il faut donc
    retirer l'ancien AVANT de poser le nouveau, dans la même transaction.
    """
    requete = (
        update(EmailAccount)
        .where(EmailAccount.is_default.is_(True), EmailAccount.deleted_at.is_(None))
        .values(is_default=False)
    )
    if sauf is not None:
        requete = requete.where(EmailAccount.id_email_accounts != sauf)
    await session.execute(requete)
    await session.flush()


async def _un_compte_par_defaut_existe(session: AsyncSession) -> bool:
    return (
        await session.execute(
            select(EmailAccount.id_email_accounts).where(
                EmailAccount.deleted_at.is_(None), EmailAccount.is_default.is_(True)
            )
        )
    ).first() is not None


async def creer_compte(
    session: AsyncSession, donnees: EmailAccountCreate, par: User
) -> EmailAccountVerifyRead:
    """Enregistre un compte et son mot de passe chiffré, puis teste la connexion."""
    host = donnees.host.strip()
    username = _normaliser_adresse(donnees.username)
    await _refuser_doublon(session, host, donnees.port, username)

    # Le premier compte enregistré devient le compte d'envoi : sans cela, la
    # boîte d'envois resterait sans expéditeur alors qu'un compte existe.
    par_defaut = donnees.is_default or not await _un_compte_par_defaut_existe(session)
    if par_defaut:
        await _retirer_les_autres_defauts(session)

    compte = EmailAccount(
        label=donnees.label.strip(),
        host=host,
        port=donnees.port,
        security=donnees.security,
        username=username,
        from_email=_normaliser_adresse(donnees.from_email),
        from_name=(donnees.from_name or "").strip() or None,
        reply_to_email=(
            _normaliser_adresse(donnees.reply_to_email) if donnees.reply_to_email else None
        ),
        timeout_seconds=donnees.timeout_seconds,
        is_default=par_defaut,
        id_users_created_by=par.id_users,
        id_users_changed_by=par.id_users,
    )
    session.add(compte)
    await session.flush()

    clair = donnees.password
    session.add(
        EmailAccountCredential(
            id_email_accounts=compte.id_email_accounts,
            password_encrypted=encrypt_token(clair),
            password_masked=APERCU_MASQUE,
            obtained_at=datetime.now(UTC),
            id_users_created_by=par.id_users,
        )
    )
    await session.flush()

    resultat: SmtpResult | None = None
    if donnees.verify_immediately:
        resultat = await smtp_client.verify_connection(_cible(compte, clair))
        await _consigner(session, compte, CHECK_CONNECTION, resultat, None, par)

    await session.commit()
    await session.refresh(compte)
    identifiant = await _identifiant_actif(session, compte.id_email_accounts)
    logger.info("Compte d'envoi %s créé", compte.id_email_accounts)

    return EmailAccountVerifyRead(
        verified=resultat.ok if resultat is not None else False,
        message=(
            resultat.message
            if resultat is not None
            else "Compte enregistré, mot de passe chiffré en base. Connexion non testée."
        ),
        latency_ms=resultat.latency_ms if resultat is not None else 0,
        account=_to_read(compte, identifiant, par),
    )


async def modifier_compte(
    session: AsyncSession, id_email_accounts: int, donnees: EmailAccountUpdate, par: User
) -> EmailAccountRead:
    """Modifie les champs non secrets. Le mot de passe a sa propre route."""
    compte, _ = await _charger(session, id_email_accounts)
    champs = donnees.model_dump(exclude_unset=True)

    if "label" in champs and champs["label"] is not None:
        compte.label = str(champs["label"]).strip()
    if "host" in champs and champs["host"] is not None:
        compte.host = str(champs["host"]).strip()
    if "port" in champs and champs["port"] is not None:
        compte.port = int(champs["port"])
    if "security" in champs and champs["security"] is not None:
        compte.security = str(champs["security"])
    if "username" in champs and champs["username"] is not None:
        compte.username = _normaliser_adresse(str(champs["username"]))
    if "from_email" in champs and champs["from_email"] is not None:
        compte.from_email = _normaliser_adresse(str(champs["from_email"]))
    if "from_name" in champs:
        compte.from_name = (str(champs["from_name"] or "")).strip() or None
    if "reply_to_email" in champs:
        compte.reply_to_email = (
            _normaliser_adresse(str(champs["reply_to_email"])) if champs["reply_to_email"] else None
        )
    if "timeout_seconds" in champs and champs["timeout_seconds"] is not None:
        compte.timeout_seconds = int(champs["timeout_seconds"])

    # `no_autoflush` est indispensable ici : le compte porte déjà ses nouvelles
    # valeurs en mémoire, et sans cela le SELECT de contrôle les écrirait en
    # base AVANT de les avoir contrôlées. L'index unique partiel les refuserait,
    # et l'IntegrityError sortirait en 500 au lieu du 409 attendu.
    with session.no_autoflush:
        await _refuser_doublon(
            session, compte.host, compte.port, compte.username, sauf=compte.id_email_accounts
        )

    # Serveur, port, mode ou identifiant changés : la dernière vérification ne
    # dit plus rien de la configuration actuelle. Mieux vaut un compte « non
    # vérifié » qu'un feu vert périmé.
    if {"host", "port", "security", "username"} & champs.keys():
        compte.last_verified_at = None
        compte.last_verify_ok = None
        compte.last_verify_message = None

    compte.id_users_changed_by = par.id_users
    await session.commit()
    await session.refresh(compte)
    logger.info("Compte d'envoi %s modifié", compte.id_email_accounts)
    return _to_read(compte, await _identifiant_actif(session, compte.id_email_accounts), par)


async def remplacer_mot_de_passe(
    session: AsyncSession,
    id_email_accounts: int,
    donnees: EmailAccountPasswordSave,
    par: User,
) -> EmailAccountVerifyRead:
    """Chiffre un nouveau mot de passe et marque le précédent remplacé."""
    compte, auteur = await _charger(session, id_email_accounts)
    maintenant = datetime.now(UTC)

    await session.execute(
        update(EmailAccountCredential)
        .where(
            EmailAccountCredential.id_email_accounts == id_email_accounts,
            EmailAccountCredential.superseded_at.is_(None),
            EmailAccountCredential.revoked_at.is_(None),
        )
        .values(superseded_at=maintenant)
    )
    await session.flush()

    clair = donnees.password
    session.add(
        EmailAccountCredential(
            id_email_accounts=id_email_accounts,
            password_encrypted=encrypt_token(clair),
            password_masked=APERCU_MASQUE,
            obtained_at=maintenant,
            id_users_created_by=par.id_users,
        )
    )
    compte.id_users_changed_by = par.id_users

    # La dernière vérification parlait de l'ANCIEN mot de passe : la garder
    # afficherait un feu vert pour un secret qui n'est plus en service. Si une
    # vérification suit, `_consigner` repose ces trois champs juste après.
    compte.last_verified_at = None
    compte.last_verify_ok = None
    compte.last_verify_message = None
    await session.flush()

    resultat: SmtpResult | None = None
    if donnees.verify_immediately:
        resultat = await smtp_client.verify_connection(_cible(compte, clair))
        await _consigner(session, compte, CHECK_CONNECTION, resultat, None, par)

    await session.commit()
    await session.refresh(compte)
    logger.info("Mot de passe du compte d'envoi %s remplacé", id_email_accounts)

    return EmailAccountVerifyRead(
        verified=resultat.ok if resultat is not None else False,
        message=(
            resultat.message
            if resultat is not None
            else "Mot de passe chiffré en base. Connexion non testée."
        ),
        latency_ms=resultat.latency_ms if resultat is not None else 0,
        account=_to_read(compte, await _identifiant_actif(session, id_email_accounts), auteur),
    )


async def definir_par_defaut(
    session: AsyncSession, id_email_accounts: int, par: User
) -> EmailAccountRead:
    """Désigne le compte qui servira aux envois."""
    compte, auteur = await _charger(session, id_email_accounts)
    if await _identifiant_actif(session, id_email_accounts) is None:
        raise ApiError(
            "email_account_without_password",
            "Ce compte n'a pas de mot de passe actif : il ne pourrait rien envoyer.",
            409,
        )
    await _retirer_les_autres_defauts(session, sauf=id_email_accounts)
    compte.is_default = True
    compte.id_users_changed_by = par.id_users
    await session.commit()
    await session.refresh(compte)
    logger.info("Compte d'envoi %s désigné par défaut", id_email_accounts)
    return _to_read(compte, await _identifiant_actif(session, id_email_accounts), auteur)


async def archiver_compte(session: AsyncSession, id_email_accounts: int, par: User) -> None:
    """Archive le compte et révoque son mot de passe, dans la même transaction.

    Un compte archivé dont le mot de passe resterait actif laisserait un secret
    utilisable en base pour un compte que plus rien n'affiche.
    """
    compte, _ = await _charger(session, id_email_accounts)
    maintenant = datetime.now(UTC)

    await session.execute(
        update(EmailAccountCredential)
        .where(
            EmailAccountCredential.id_email_accounts == id_email_accounts,
            EmailAccountCredential.revoked_at.is_(None),
        )
        .values(revoked_at=maintenant)
    )
    compte.deleted_at = maintenant
    compte.is_default = False
    compte.id_users_changed_by = par.id_users
    await session.commit()
    logger.info("Compte d'envoi %s archivé", id_email_accounts)


# ---------------------------------------------------------------------------
# Échanges réels avec le serveur
# ---------------------------------------------------------------------------


def _cible(compte: EmailAccount, mot_de_passe: str) -> SmtpTarget:
    return SmtpTarget(
        host=compte.host,
        port=compte.port,
        security=compte.security,
        username=compte.username,
        password=mot_de_passe,
        timeout_seconds=compte.timeout_seconds,
    )


async def _mot_de_passe_en_clair(session: AsyncSession, id_email_accounts: int) -> str:
    """Déchiffre le mot de passe actif, le temps d'un échange SMTP."""
    identifiant = await _identifiant_actif(session, id_email_accounts)
    if identifiant is None:
        raise ApiError(
            "email_account_without_password",
            "Ce compte n'a pas de mot de passe actif. Enregistrez-en un avant de tester.",
            409,
        )
    return decrypt_token(identifiant.password_encrypted)


async def _consigner(
    session: AsyncSession,
    compte: EmailAccount,
    kind: str,
    resultat: SmtpResult,
    destinataire: str | None,
    par: User | None,
) -> None:
    """Écrit la ligne d'historique et met à jour l'état courant du compte.

    Les deux vont ensemble : c'est la règle des historiques du projet, et c'est
    ce qui garantit qu'un « vérifié le … » affiché est toujours justifié par une
    ligne qu'on peut relire.
    """
    session.add(
        EmailAccountCheck(
            id_email_accounts=compte.id_email_accounts,
            kind=kind,
            is_ok=resultat.ok,
            message=resultat.message,
            recipient_email=destinataire,
            latency_ms=resultat.latency_ms,
            checked_at=datetime.now(UTC),
            id_users_checked_by=par.id_users if par is not None else None,
        )
    )
    compte.last_verified_at = datetime.now(UTC)
    compte.last_verify_ok = resultat.ok
    compte.last_verify_message = resultat.message
    await session.flush()


async def verifier_compte(
    session: AsyncSession, id_email_accounts: int, par: User
) -> EmailAccountVerifyRead:
    """Teste la connexion et l'authentification. Aucun message n'est envoyé."""
    compte, auteur = await _charger(session, id_email_accounts)
    clair = await _mot_de_passe_en_clair(session, id_email_accounts)

    resultat = await smtp_client.verify_connection(_cible(compte, clair))
    await _consigner(session, compte, CHECK_CONNECTION, resultat, None, par)
    await session.commit()
    await session.refresh(compte)

    return EmailAccountVerifyRead(
        verified=resultat.ok,
        message=resultat.message,
        latency_ms=resultat.latency_ms,
        account=_to_read(compte, await _identifiant_actif(session, id_email_accounts), auteur),
    )


def _message_de_test(compte: EmailAccount, donnees: EmailAccountTestMessage) -> EmailMessage:
    """Compose le message de test : c'est une règle métier, pas du transport."""
    mode = "SSL/TLS" if compte.security == SECURITY_SSL_TLS else "STARTTLS"
    sujet = (donnees.subject or "").strip() or f"IAGORA — test du compte d'envoi « {compte.label} »"
    corps = (donnees.body or "").strip() or (
        "Ce message confirme que le compte d'envoi fonctionne.\n\n"
        f"Compte : {compte.label}\n"
        f"Serveur : {compte.host}:{compte.port} ({mode})\n"
        f"Expéditeur : {compte.from_email}\n\n"
        "Envoyé depuis IAGORA, plateforme de communication de Datum Academy."
    )

    message = EmailMessage()
    message["Subject"] = sujet
    # `Address` plutôt qu'un f-string : un nom affiché qui contient une virgule
    # — « Datum Academy, SARL » — produirait sinon deux adresses aux yeux du
    # serveur, et aiosmtplib tire l'expéditeur de l'enveloppe de cet en-tête.
    message["From"] = (
        Address(display_name=compte.from_name, addr_spec=compte.from_email)
        if compte.from_name
        else Address(addr_spec=compte.from_email)
    )
    message["To"] = donnees.recipient_email
    if compte.reply_to_email:
        message["Reply-To"] = compte.reply_to_email
    message.set_content(corps)
    return message


async def envoyer_message_de_test(
    session: AsyncSession,
    id_email_accounts: int,
    donnees: EmailAccountTestMessage,
    par: User,
) -> EmailAccountVerifyRead:
    """Envoie réellement un message, pour vérifier la chaîne de bout en bout.

    Le test de connexion dit que le serveur accepte l'authentification ; lui
    seul dit que le serveur accepte aussi d'expédier POUR cette adresse — c'est
    un refus courant chez IONOS quand l'expéditeur n'est pas la boîte.
    """
    compte, auteur = await _charger(session, id_email_accounts)
    clair = await _mot_de_passe_en_clair(session, id_email_accounts)
    destinataire = _normaliser_adresse(donnees.recipient_email)

    resultat = await smtp_client.send_message(
        _cible(compte, clair), _message_de_test(compte, donnees)
    )
    await _consigner(session, compte, CHECK_TEST_MESSAGE, resultat, destinataire, par)
    await session.commit()
    await session.refresh(compte)
    logger.info(
        "Message de test du compte d'envoi %s : %s",
        id_email_accounts,
        "accepté" if resultat.ok else "refusé",
    )

    return EmailAccountVerifyRead(
        verified=resultat.ok,
        message=resultat.message,
        latency_ms=resultat.latency_ms,
        account=_to_read(compte, await _identifiant_actif(session, id_email_accounts), auteur),
    )
