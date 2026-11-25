"""Constantes du module Newsletter."""

MANAGE_MAIL_TEMPLATES = "manage_mail_templates"
SEND_NEWSLETTERS = "send_newsletters"

# État d'un modèle : binaire, figé, sans règle métier attachée — d'où un CHECK
# plutôt qu'une table de référence (voir la migration 0010).
TEMPLATE_STATUS_DRAFT = "draft"
TEMPLATE_STATUS_PUBLISHED = "published"
TEMPLATE_STATUSES = (TEMPLATE_STATUS_DRAFT, TEMPLATE_STATUS_PUBLISHED)

# Codes des deux référentiels, tels que la migration 0010 les sème.
CATEGORY_REGISTRATION_CONFIRMATION = "registration_confirmation"
CATEGORY_REMINDER = "reminder"
CATEGORY_CHANGE_OR_CANCELLATION = "change_or_cancellation"
CATEGORY_REPORT = "report"
CATEGORY_REPLAY = "replay"

SEND_STATUS_SENT = "sent"
SEND_STATUS_SCHEDULED = "scheduled"
SEND_STATUS_PARTIAL = "partial"
SEND_STATUS_FAILED = "failed"

# Variables de la coquille : elles sont les mêmes pour tous les modèles, et
# c'est l'application qui les fournit — jamais l'utilisateur, modèle par modèle.
VARIABLES_COQUILLE = ("objet", "preheader", "baseline", "equipe", "adresse_postale", "contenu")

# Valeurs par défaut de la coquille. Elles valent pour tous les envois tant que
# la fiche de l'organisation n'existe pas en base.
VALEURS_COQUILLE: dict[str, str] = {
    "baseline": "Former, accompagner, transformer",
    "equipe": "L'équipe Datum Academy",
    "adresse_postale": "Antananarivo, Madagascar",
}

# Valeurs d'exemple de l'aperçu et du message de test. Les adresses sont sous
# `example.com`, réservé par l'IANA : un aperçu ne peut atteindre personne.
VALEURS_EXEMPLE: dict[str, str] = {
    "prenom": "Mialy",
    "titre_webinaire": "Piloter sa donnée sans équipe data",
    "date": "jeudi 11 décembre 2026",
    "heure": "14 h 00",
    "fuseau": "GMT+3",
    "duree": "1 h",
    "echeance": "demain",
    "lien_acces": "https://datumacademy.com/fr/webinaires/acces/exemple",
    "lien_rediffusion": "https://datumacademy.com/fr/webinaires/rediffusion/exemple",
    "lien_ressources": "https://datumacademy.com/fr/webinaires/supports/exemple",
    "nature_du_changement": "La séance change d'horaire",
    "detail_du_changement": "Le contenu et le lien d'accès restent les mêmes.",
    "ancienne_date": "mardi 9 décembre 2026 à 10 h 00",
    "points_cles": "Cadrer le besoin, choisir ses indicateurs, outiller sans se sur-équiper.",
    "duree_disponibilite": "pendant 90 jours",
}

# Les modèles standards, installés à la demande depuis l'écran Modèles de mail.
# Le corps de chacun vit dans `templates/corps/<code>.html` : du HTML dans un
# fichier .html se relit et se corrige, pas du HTML noyé dans du Python.
MODELES_STANDARDS: tuple[dict[str, str], ...] = (
    {
        "category": CATEGORY_REGISTRATION_CONFIRMATION,
        "name": "Confirmation d'inscription — webinaire",
        "subject": "Votre inscription à « {{titre_webinaire}} » est confirmée",
        "preheader": (
            "Votre lien d'accès personnel pour {{titre_webinaire}} — {{date}} à {{heure}}."
        ),
        "fichier": "registration_confirmation.html",
    },
    {
        "category": CATEGORY_REMINDER,
        "name": "Rappel — avant la séance",
        "subject": "{{echeance}} : « {{titre_webinaire}} »",
        "preheader": "Rendez-vous {{date}} à {{heure}}. Votre lien d'accès est inchangé.",
        "fichier": "reminder.html",
    },
    {
        "category": CATEGORY_CHANGE_OR_CANCELLATION,
        "name": "Modification ou annulation — séance",
        "subject": "Changement pour « {{titre_webinaire}} »",
        "preheader": "{{nature_du_changement}} — voici ce qu'il faut retenir.",
        "fichier": "change_or_cancellation.html",
    },
    {
        "category": CATEGORY_REPORT,
        "name": "Compte rendu — après la séance",
        "subject": "Compte rendu de « {{titre_webinaire}} »",
        "preheader": "Les points clés de la séance et les supports à télécharger.",
        "fichier": "report.html",
    },
    {
        "category": CATEGORY_REPLAY,
        "name": "Visionnage — rediffusion en ligne",
        "subject": "La rediffusion de « {{titre_webinaire}} » est disponible",
        "preheader": "À revoir quand vous voulez, {{duree_disponibilite}}.",
        "fichier": "replay.html",
    },
)

# Au-delà, un envoi immobiliserait la requête HTTP trop longtemps. Les lots plus
# gros demanderont une file d'attente, qui n'existe pas encore.
DESTINATAIRES_MAX = 200
