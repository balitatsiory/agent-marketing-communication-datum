"""Constantes du module Modèles IA (OpenRouter)."""

MANAGE_AI_MODELS = "manage_ai_models"

KEY_KIND_MANAGEMENT = "management"
KEY_KIND_STANDARD = "standard"
KEY_KIND_SANDBOX = "sandbox"
KEY_KINDS = (KEY_KIND_MANAGEMENT, KEY_KIND_STANDARD, KEY_KIND_SANDBOX)

SANDBOX_USE_CASES = (
    "publication_text",
    "image_generation",
    "message_rag",
)

PROMPT_KIND_SYSTEM = "system"
PROMPT_KIND_TEMPLATE = "template"
PROMPT_KINDS = (PROMPT_KIND_SYSTEM, PROMPT_KIND_TEMPLATE)

PROMPT_TASK_CODES = (
    "publication_description",
    "message_reply",
    "image_generation",
    "image_description",
    "rag_synthesis",
    "newsletter_content",
)

PROMPT_TASKS_META: tuple[dict[str, str], ...] = (
    {
        "code": "publication_description",
        "label": "Génération de description",
        "description": "Rédaction de descriptions et légendes pour publications LinkedIn, Facebook et Instagram.",
    },
    {
        "code": "message_reply",
        "label": "Génération de messages",
        "description": "Réponses prospects et apprenants sur la messagerie unifiée (WhatsApp, Messenger, DM).",
    },
    {
        "code": "image_generation",
        "label": "Génération & retouche d'image",
        "description": "Création de visuels réseaux sociaux et consignes de modification d'images.",
    },
    {
        "code": "image_description",
        "label": "Description d'image (Vision)",
        "description": "Analyse sémantique des médias de référence, chartes graphiques et textes alternatifs.",
    },
    {
        "code": "rag_synthesis",
        "label": "Synthèse Base de connaissances",
        "description": "Réponses documentaires strictement ancrées sur le syllabus et les règlements.",
    },
    {
        "code": "newsletter_content",
        "label": "Rédaction Newsletter",
        "description": "Création d'objets, chapeaux et contenus éditoriaux pour les envois email.",
    },
)

PROVIDER_SORTS = ("price", "throughput", "latency", "exacto")
REASONING_EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh")

TASK_TEXT_GENERATION = "text-generation"
TASK_IMAGE_DESCRIPTION = "image-description"
TASK_IMAGE_GENERATION = "image-generation"
TASK_RAG_EMBEDDING = "rag-embedding"

TASK_CODES = (
    TASK_TEXT_GENERATION,
    TASK_IMAGE_DESCRIPTION,
    TASK_IMAGE_GENERATION,
    TASK_RAG_EMBEDDING,
)

TASK_LABELS: dict[str, str] = {
    TASK_TEXT_GENERATION: "Génération de texte",
    TASK_IMAGE_DESCRIPTION: "Description d'image (Vision)",
    TASK_IMAGE_GENERATION: "Génération d'image",
    TASK_RAG_EMBEDDING: "RAG / Embedding",
}
