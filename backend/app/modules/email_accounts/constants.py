"""Constantes du module Comptes d'envoi (SMTP).

Les valeurs de `security` et de `kind` sont techniques et figées : elles sont
donc portées par un VARCHAR et un CHECK, et non par une table de référence.
"""

MANAGE_EMAIL_ACCOUNTS = "manage_email_accounts"

# Mode de chiffrement du transport.
# - ssl_tls   : la connexion est chiffrée dès son ouverture (SMTPS, port 465).
# - starttls  : la connexion s'ouvre en clair puis passe en TLS (port 587).
SECURITY_SSL_TLS = "ssl_tls"
SECURITY_STARTTLS = "starttls"
SECURITIES = (SECURITY_SSL_TLS, SECURITY_STARTTLS)

# Nature d'une vérification consignée dans l'historique.
CHECK_CONNECTION = "connection"
CHECK_TEST_MESSAGE = "test_message"
CHECK_KINDS = (CHECK_CONNECTION, CHECK_TEST_MESSAGE)

# Réglages IONOS, préremplis à la création d'un compte. Chez IONOS, le port 465
# chiffre dès l'ouverture de la connexion et c'est le mode recommandé ; le 587
# reste disponible pour les réseaux qui filtrent le 465.
IONOS_HOST = "smtp.ionos.fr"
PORT_SSL_TLS = 465
PORT_STARTTLS = 587

# Un serveur injoignable immobilise la requête HTTP le temps du délai d'attente :
# 20 secondes suffisent à une poignée de main TLS, et 120 est le plafond au-delà
# duquel le navigateur de l'utilisateur aurait de toute façon renoncé.
TIMEOUT_SECONDS_DEFAULT = 20
TIMEOUT_SECONDS_MIN = 1
TIMEOUT_SECONDS_MAX = 120

# Longueur minimale d'un mot de passe de boîte, en deçà de laquelle la saisie
# est manifestement une erreur.
PASSWORD_LENGTH_MIN = 6
PASSWORD_LENGTH_MAX = 512
