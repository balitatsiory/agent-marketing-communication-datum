"""Formats d'entrée et de sortie du module Média."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MediaRead(BaseModel):
    """Un média de la bibliothèque.

    `url` ne vient pas de la base : elle est recomposée à la lecture à partir
    de la clé de stockage. La base ne garde jamais d'URL — une URL expire ou
    change de domaine, une clé non.
    """

    model_config = ConfigDict(from_attributes=True)

    id_media: int
    display_name: str
    file_type: str
    source: str
    size_bytes: int
    width: int | None
    height: int | None
    video_duration_seconds: int | None
    created_at: datetime
    deleted_at: datetime | None
    url: str = ""


class MediaRename(BaseModel):
    display_name: str = Field(min_length=1, max_length=255)


class MediaReferenceNatureRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    label: str
    description: str | None
    sort_order: int


class MediaReferenceRead(BaseModel):
    """Un média déclaré comme référence à la génération d'images."""

    model_config = ConfigDict(from_attributes=True)

    id_media_references: int
    id_media: int
    nature_code: str = ""
    label: str
    description: str | None
    is_active: bool
    created_at: datetime
    deleted_at: datetime | None


class MediaReferenceCreate(BaseModel):
    """Déclaration explicite : l'utilisateur désigne le média et sa nature.

    La ligne ne naît pas toute seule au dépôt — décision du 19 novembre 2026.
    """

    id_media: int
    nature_code: str = Field(min_length=1, max_length=40)
    label: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=4000)


class MediaReferenceImageReplace(BaseModel):
    """Nouvelle image d'une référence, désignée par son adresse sur le web.

    L'adresse sert à rapatrier le fichier puis n'est pas conservée.
    """

    url: str = Field(min_length=1, max_length=2048)


class MediaReferenceUpdate(BaseModel):
    """Modification partielle : seuls les champs fournis sont appliqués."""

    nature_code: str | None = Field(default=None, min_length=1, max_length=40)
    label: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=4000)
    is_active: bool | None = None
