import { PermissionDto, UserDto } from '../api/users.api';

/**
 * Vue d'un compte, telle que les écrans l'affichent.
 *
 * Elle se construit à partir de `UserDto`, qui porte les noms de champs du
 * backend. Cette séparation a une raison : le jour où un champ de l'API
 * change, l'erreur de compilation tombe dans `toUserView` et nulle part
 * ailleurs.
 *
 * **Ce qui a disparu de ce modèle.** Les versions précédentes portaient une
 * méthode de connexion (`authMethod`), un indicateur de double facteur et un
 * statut « invitation envoyée ». Aucun des trois n'existe dans l'API : le
 * cahier des charges exclut la connexion déléguée et le libre-service, et un
 * compte est créé directement avec son mot de passe par un administrateur. Les
 * conserver revenait à afficher des informations inventées.
 */
export interface UserView {
  readonly idUsers: number;
  readonly fullName: string;
  readonly email: string;
  /** Initiales affichées dans la pastille, faute de photo. */
  readonly initials: string;
  readonly status: AccountStatus;
  readonly memberSinceLabel: string;
  /** Dernière connexion observée, ou `null` si le compte ne s'est jamais connecté. */
  readonly lastSignInLabel: string | null;
  /** Codes des droits accordés. L'absence d'un code vaut refus. */
  readonly permissions: readonly string[];
}

/**
 * État d'un compte.
 *
 * Trois états et non deux, parce que la base en distingue trois :
 * `is_active` est l'état d'exploitation, réversible, et `deleted_at`
 * l'archivage, posé par-dessus cet état.
 */
export type AccountStatus = 'active' | 'suspended' | 'archived';

export const ACCOUNT_STATUS_LABELS: Readonly<Record<AccountStatus, string>> = {
  active: 'actif',
  suspended: 'suspendu',
  archived: 'archivé',
};

const MOIS_ET_ANNEE = new Intl.DateTimeFormat('fr-FR', { month: 'long', year: 'numeric' });
const DATE_ET_HEURE = new Intl.DateTimeFormat('fr-FR', {
  dateStyle: 'short',
  timeStyle: 'short',
});

function initiales(prenom: string, nom: string): string {
  return `${prenom.charAt(0)}${nom.charAt(0)}`.toUpperCase();
}

export function toUserView(dto: UserDto): UserView {
  return {
    idUsers: dto.id_users,
    fullName: `${dto.first_name} ${dto.last_name}`.trim(),
    email: dto.email,
    initials: initiales(dto.first_name, dto.last_name),
    status: dto.deleted_at !== null ? 'archived' : dto.is_active ? 'active' : 'suspended',
    memberSinceLabel: MOIS_ET_ANNEE.format(new Date(dto.created_at)),
    lastSignInLabel:
      dto.last_login_at === null ? null : DATE_ET_HEURE.format(new Date(dto.last_login_at)),
    permissions: dto.permissions,
  };
}

/**
 * Droit attribuable, tel que l'écran l'affiche.
 *
 * **Le catalogue des droits n'est pas écrit dans le frontend.** Il est lu par
 * `GET /api/v1/permissions`. La raison est une décision d'architecture : les
 * droits sont fins et propres à chaque module — `manage_users`,
 * `manage_permissions`, puis ceux des modules suivants — et la table
 * `permissions` est alimentée module par module, par migration. Un catalogue
 * recopié ici serait faux dès la migration suivante.
 */
export interface Permission {
  readonly code: string;
  readonly label: string;
  readonly description: string | null;
  readonly sortOrder: number;
}

export function toPermission(dto: PermissionDto): Permission {
  return {
    code: dto.code,
    label: dto.label,
    description: dto.description,
    sortOrder: dto.sort_order,
  };
}

/**
 * Résumé des droits, affiché sous le nom dans la liste.
 *
 * Remplace le rôle que la maquette affichait : F-22 impose qu'aucun rôle ne
 * soit figé dans le code, donc il n'y en a pas, et rien ne s'hérite.
 */
export function permissionSummary(
  user: UserView,
  catalogue: readonly Permission[],
): string {
  if (user.permissions.length === 0) return 'aucun droit';
  const libelles = catalogue
    .filter((droit) => user.permissions.includes(droit.code))
    .map((droit) => droit.label);
  return libelles.length > 0 ? libelles.join(' · ') : `${user.permissions.length} droits`;
}
