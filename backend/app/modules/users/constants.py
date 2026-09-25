"""Droits attribuables à un utilisateur.

Le cahier des charges (F-22) ne fige aucun rôle : un administrateur attribue des
droits, un par un. Ces cinq codes sont donc la liste complète des permissions.
"""

from enum import StrEnum


class PermissionCode(StrEnum):
    """Codes techniques des droits. Ils ne changent jamais."""

    CREATE = "create"
    REVIEW = "review"
    PUBLISH = "publish"
    READ = "read"
    ADMIN = "admin"


# Libellés affichés dans l'interface, et ordre d'affichage.
PERMISSIONS: dict[PermissionCode, tuple[str, int]] = {
    PermissionCode.READ: ("Consulter", 1),
    PermissionCode.CREATE: ("Créer", 2),
    PermissionCode.REVIEW: ("Valider", 3),
    PermissionCode.PUBLISH: ("Publier", 4),
    PermissionCode.ADMIN: ("Administrer", 5),
}
