"""Dialogue avec un serveur SMTP sortant.

C'est le seul fichier où un mot de passe de boîte existe en clair, et il n'y
existe que le temps d'un appel : il arrive en argument, part dans la poignée de
main, et n'est ni conservé ni journalisé.

Pourquoi `aiosmtplib` et non `smtplib` de la bibliothèque standard : `smtplib`
est bloquant. Un serveur lent y immobiliserait la boucle d'événements, donc
toutes les autres requêtes de l'API, et les règles du projet l'interdisent dans
du code `async`.

Les messages renvoyés sont en français et destinés à l'affichage : ce sont eux
que l'utilisateur lit quand sa connexion IONOS échoue, et le compte rendu doit
lui dire quoi corriger.
"""

import asyncio
import logging
import ssl
import time
from dataclasses import dataclass
from email.message import EmailMessage

import aiosmtplib

from app.modules.email_accounts.constants import SECURITY_SSL_TLS

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SmtpTarget:
    """Tout ce qu'il faut pour ouvrir une session authentifiée, mot de passe compris."""

    host: str
    port: int
    security: str
    username: str
    password: str
    timeout_seconds: int


@dataclass(frozen=True, slots=True)
class SmtpResult:
    """Résultat d'un échange avec le serveur, tel qu'il sera consigné et affiché."""

    ok: bool
    message: str
    latency_ms: int


def _nouvelle_session(cible: SmtpTarget) -> aiosmtplib.SMTP:
    """Prépare la session, selon le mode de chiffrement du compte.

    Les deux modes s'excluent : `use_tls` chiffre dès l'ouverture de la socket
    (c'est le port 465 d'IONOS), `start_tls` ouvre en clair puis négocie le
    passage en TLS (port 587). Les passer tous les deux fait lever `ValueError`
    à aiosmtplib — c'est la confusion la plus courante sur ce réglage.
    """
    implicite = cible.security == SECURITY_SSL_TLS
    return aiosmtplib.SMTP(
        hostname=cible.host,
        port=cible.port,
        username=cible.username,
        password=cible.password,
        use_tls=implicite,
        start_tls=not implicite,
        timeout=float(cible.timeout_seconds),
        # Le certificat du serveur est vérifié : c'est le défaut du contexte SSL
        # de Python, et on ne l'affaiblit pas. Un certificat refusé est une
        # alerte, pas un désagrément à contourner.
        tls_context=ssl.create_default_context(),
    )


def _compte_rendu_de_lerreur(erreur: Exception, cible: SmtpTarget) -> str:
    """Traduit l'échec en une phrase qui dit quoi corriger."""
    adresse = f"{cible.host}:{cible.port}"

    if isinstance(erreur, aiosmtplib.SMTPAuthenticationError):
        return (
            "Le serveur a refusé l'identifiant ou le mot de passe. Chez IONOS, "
            "l'identifiant est l'adresse complète de la boîte, et le mot de passe "
            "est celui de la boîte — pas celui du compte client."
        )
    if isinstance(erreur, aiosmtplib.SMTPConnectTimeoutError | asyncio.TimeoutError):
        return (
            f"Pas de réponse de {adresse} avant la fin du délai d'attente "
            f"({cible.timeout_seconds} s). Le port est peut-être filtré par le réseau."
        )
    if isinstance(erreur, ssl.SSLError):
        return (
            f"La négociation TLS avec {adresse} a échoué. Vérifier le mode : "
            "465 en SSL/TLS, 587 en STARTTLS — les deux ne sont pas interchangeables."
        )
    if isinstance(erreur, aiosmtplib.SMTPConnectError | OSError):
        return (
            f"{adresse} est injoignable. Vérifier le nom du serveur, le port et "
            "l'accès au réseau depuis la machine qui héberge l'API."
        )
    if isinstance(erreur, aiosmtplib.SMTPRecipientsRefused | aiosmtplib.SMTPResponseException):
        # Le serveur a parlé : son propre texte est plus précis que le nôtre.
        return f"Le serveur a refusé l'opération : {erreur}"
    return f"Échec de l'échange SMTP avec {adresse} : {erreur}"


async def verify_connection(cible: SmtpTarget) -> SmtpResult:
    """Ouvre une session, s'authentifie, referme. Aucun message n'est envoyé.

    C'est le test qu'on veut avant de confier des envois à un compte : il
    distingue un serveur injoignable d'un mot de passe refusé, sans écrire
    dans la boîte de qui que ce soit.
    """
    depart = time.monotonic()
    session = _nouvelle_session(cible)
    try:
        await session.connect()
        # `connect()` s'authentifie déjà quand un identifiant est fourni ;
        # NOOP vérifie que la session tient vraiment après l'authentification.
        await session.noop()
    # Tout échec est un RÉSULTAT à afficher, pas une panne de l'API : un mot de
    # passe refusé ou un port filtré se lisent dans le compte rendu.
    except Exception as erreur:
        logger.info("Test de connexion SMTP échoué sur %s:%s", cible.host, cible.port)
        return SmtpResult(
            ok=False,
            message=_compte_rendu_de_lerreur(erreur, cible),
            latency_ms=_millisecondes_depuis(depart),
        )
    else:
        return SmtpResult(
            ok=True,
            message=(
                f"Connexion authentifiée sur {cible.host}:{cible.port} "
                f"({'SSL/TLS' if cible.security == SECURITY_SSL_TLS else 'STARTTLS'})."
            ),
            latency_ms=_millisecondes_depuis(depart),
        )
    finally:
        await _fermer(session)


async def send_message(cible: SmtpTarget, message: EmailMessage) -> SmtpResult:
    """Envoie un message déjà composé. Le contenu ne vient jamais d'ici."""
    depart = time.monotonic()
    session = _nouvelle_session(cible)
    try:
        await session.connect()
        await session.send_message(message)
    # Même raison que pour le test de connexion : l'échec est un résultat.
    except Exception as erreur:
        logger.info("Envoi SMTP échoué sur %s:%s", cible.host, cible.port)
        return SmtpResult(
            ok=False,
            message=_compte_rendu_de_lerreur(erreur, cible),
            latency_ms=_millisecondes_depuis(depart),
        )
    else:
        return SmtpResult(
            ok=True,
            message="Le serveur a accepté le message.",
            latency_ms=_millisecondes_depuis(depart),
        )
    finally:
        await _fermer(session)


async def send_messages(cible: SmtpTarget, messages: list[EmailMessage]) -> list[SmtpResult]:
    """Envoie un lot de messages sur UNE SEULE connexion.

    Un envoi de cent destinataires ouvrirait cent sessions TLS s'il passait par
    `send_message` : la poignée de main coûte plus cher que le message. On
    ouvre donc une fois, on envoie tout, on referme.

    Le résultat est rendu message par message, dans l'ordre reçu : un
    destinataire refusé n'interrompt pas les suivants, et chacun garde le motif
    que le serveur lui a opposé.
    """
    depart = time.monotonic()
    session = _nouvelle_session(cible)
    try:
        await session.connect()
    except Exception as erreur:
        # La connexion n'a pas abouti : aucun message n'est parti, et le même
        # compte rendu vaut pour tous.
        logger.info("Connexion SMTP échouée sur %s:%s", cible.host, cible.port)
        compte_rendu = _compte_rendu_de_lerreur(erreur, cible)
        duree = _millisecondes_depuis(depart)
        await _fermer(session)
        return [SmtpResult(ok=False, message=compte_rendu, latency_ms=duree) for _ in messages]

    resultats: list[SmtpResult] = []
    try:
        for message in messages:
            un_depart = time.monotonic()
            try:
                await session.send_message(message)
            except Exception as erreur:
                resultats.append(
                    SmtpResult(
                        ok=False,
                        message=_compte_rendu_de_lerreur(erreur, cible),
                        latency_ms=_millisecondes_depuis(un_depart),
                    )
                )
            else:
                resultats.append(
                    SmtpResult(
                        ok=True,
                        message="Le serveur a accepté le message.",
                        latency_ms=_millisecondes_depuis(un_depart),
                    )
                )
    finally:
        await _fermer(session)
    return resultats


async def _fermer(session: aiosmtplib.SMTP) -> None:
    """Referme la session sans jamais faire échouer l'opération appelante.

    Un QUIT refusé par un serveur qui a déjà coupé n'apprend rien à
    l'utilisateur : le résultat de l'échange est déjà établi.

    `close()` est dans un `finally` parce qu'un QUIT refusé lève AVANT
    qu'aiosmtplib ne ferme le transport : sans cela, la socket resterait
    ouverte à chaque serveur qui répond mal au congé.
    """
    try:
        await session.quit()
    except Exception:
        logger.debug("Fermeture SMTP sans réponse du serveur", exc_info=True)
    finally:
        session.close()


def _millisecondes_depuis(depart: float) -> int:
    return int((time.monotonic() - depart) * 1000)
