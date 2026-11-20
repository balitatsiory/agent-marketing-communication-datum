"""Constantes et droits du module Publications."""

READ_PUBLICATIONS = "read_publications"
CREATE_PUBLICATIONS = "create_publications"
REVIEW_PUBLICATIONS = "review_publications"
PUBLISH_PUBLICATIONS = "publish_publications"
VALIDATE_OWN_PUBLICATIONS = "validate_own_publications"

# Statuts de publication (`publication_statuses`)
PUB_EN_ATTENTE = "pending_review"
PUB_A_CORRIGER = "needs_correction"
PUB_APPROUVEE = "approved"
PUB_PROGRAMMEE = "scheduled"
PUB_EN_COURS = "publishing"
PUB_PUBLIEE = "published"
PUB_PARTIELLE = "partially_published"
PUB_ECHEC = "failed"
PUB_ANNULEE = "cancelled"

# Statuts de cible (`delivery_statuses`)
CIBLE_ATTENTE_PROG = "awaiting_scheduling"
CIBLE_PROGRAMMEE = "scheduled"
CIBLE_EN_COURS = "publishing"
CIBLE_PUBLIEE = "published"
CIBLE_ECHEC = "failed"
CIBLE_ANNULEE = "cancelled"

# Événements publication (`publication_event_types`)
EVT_PUB_CREEE = "created_submitted"
EVT_PUB_APPROUVEE = "approved"
EVT_PUB_CORRECTION = "correction_requested"
EVT_PUB_ENVOI = "sent"
EVT_PUB_PUBLIEE = "published"
EVT_PUB_PARTIELLE = "partially_published"
EVT_PUB_ECHEC = "failed"

# Événements cible (`delivery_event_types`)
EVT_CIBLE_CREEE = "created"
EVT_CIBLE_ENVOI = "sent"
EVT_CIBLE_PUBLIEE = "published"
EVT_CIBLE_ECHEC = "failed"
