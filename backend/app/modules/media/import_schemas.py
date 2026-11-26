"""Format du fichier d'organisations dont les logos sont repris.

Les clés du fichier sont en français : elles sont lues par alias. Les champs
sans colonne en base (rôle, site, remarque…) sont ignorés à la lecture.
"""

from typing import Any

from pydantic import BaseModel, Field

# Le code entre dans la clé de stockage : minuscules, chiffres et tirets simples.
ORGANISATION_CODE_PATTERN = r"^[a-z0-9]+(-[a-z0-9]+)*$"


class OrganisationLogo(BaseModel):
    """Une organisation et l'adresse de son logo."""

    code: str = Field(max_length=100, pattern=ORGANISATION_CODE_PATTERN)
    name: str = Field(alias="nom", min_length=1, max_length=120)
    logo_url: str = Field(alias="logo", min_length=1)
    alt: str | None = Field(default=None, max_length=4000)
    declared_dimensions: str | None = Field(default=None, alias="dimensions")
    key_template: str | None = Field(default=None, alias="cle_r2_modele")


class OrganisationsExport(BaseModel):
    """Le fichier entier. Chaque entrée est validée à part, pour n'écarter qu'elle."""

    announced_count: int | None = Field(default=None, alias="nombre")
    organisations: list[dict[str, Any]]
