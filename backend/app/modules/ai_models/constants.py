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
