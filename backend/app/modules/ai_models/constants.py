"""Constantes du module Modèles IA (OpenRouter)."""

MANAGE_AI_MODELS = "manage_ai_models"

KEY_KIND_MANAGEMENT = "management"
KEY_KIND_STANDARD = "standard"
KEY_KINDS = (KEY_KIND_MANAGEMENT, KEY_KIND_STANDARD)

PROVIDER_SORTS = ("price", "throughput", "latency", "exacto")

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
