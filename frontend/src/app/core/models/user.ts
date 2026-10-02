/**
 * Droits attribuables à un compte.
 *
 * Les cinq codes viennent de `backend/app/modules/users/constants.py` et de
 * la migration `0002_droits`. Ils ne changent jamais.
 *
 * F-22 du cahier des charges : « Aucun rôle n'est figé dans le code : un
 * administrateur attribue les droits ». Il n'y a donc **pas de rôle** dans
 * IAGORA, et rien à hériter — chaque droit se coche compte par compte.
 */
export type PermissionCode = 'read' | 'create' | 'review' | 'publish' | 'admin';

/** Ordre d'affichage, repris de `PERMISSIONS` côté backend. */
export const PERMISSION_ORDER: readonly PermissionCode[] = [
  'read',
  'create',
  'review',
  'publish',
  'admin',
];

export const PERMISSION_LABELS: Readonly<Record<PermissionCode, string>> = {
  read: 'Consulter',
  create: 'Créer',
  review: 'Valider',
  publish: 'Publier',
  admin: 'Administrer',
};

/** Ce que chaque droit ouvre concrètement, avec sa référence au cahier des charges. */
export interface PermissionDescription {
  readonly summary: string;
  /** Référence de l'exigence qui fonde le droit. */
  readonly reference: string;
}

export const PERMISSION_DESCRIPTIONS: Readonly<
  Record<PermissionCode, PermissionDescription>
> = {
  read: {
    summary:
      'Voir les publications, le calendrier, les événements et les statistiques. Aucune modification possible.',
    reference: 'F-22',
  },
  create: {
    summary:
      'Rédiger et modifier des publications, générer des contenus, préparer des événements et des newsletters. Rien ne part sans validation.',
    reference: 'F-22 · OB-04',
  },
  review: {
    summary:
      "Approuver ou rejeter une publication avant son départ. Modifier le contenu d'une publication approuvée la renvoie en validation.",
    reference: 'F-07 · règle métier 2',
  },
  publish: {
    summary:
      'Déclencher le départ d’une publication approuvée, et annuler une publication programmée avant exécution.',
    reference: 'F-22 · NF-07',
  },
  admin: {
    summary:
      'Créer les comptes et attribuer les droits ; raccorder et reconnecter les comptes de plateformes.',
    reference: 'F-22 · F-23',
  },
};

/** État d'un compte. */
export type AccountStatus = 'active' | 'invited' | 'disabled';

export const ACCOUNT_STATUS_LABELS: Readonly<Record<AccountStatus, string>> = {
  active: 'actif',
  invited: 'invitation envoyée',
  disabled: 'désactivé',
};

/** Méthode de connexion. Conditionne la réinitialisation du mot de passe. */
export type AuthMethod = 'password' | 'google';

export const AUTH_METHOD_LABELS: Readonly<Record<AuthMethod, string>> = {
  password: 'Mot de passe',
  google: 'Google (SSO)',
};

/** Utilisateur de l'espace de pilotage. */
export interface User {
  readonly id: number;
  readonly fullName: string;
  readonly email: string;
  /** Initiales affichées dans la pastille, faute de photo. */
  readonly initials: string;
  readonly status: AccountStatus;
  readonly memberSinceLabel: string;
  readonly authMethod: AuthMethod;
  readonly hasTwoFactor: boolean;
  /** Dernière connexion observée, ou `null` pour une invitation en attente. */
  readonly lastSignInLabel: string | null;
  /** Droits accordés à ce compte. L'absence d'un code vaut refus. */
  readonly permissions: readonly PermissionCode[];
}

/**
 * Résumé des droits, affiché sous le nom dans la liste.
 *
 * Remplace le rôle que la maquette affichait : il n'y en a pas.
 */
export function permissionSummary(user: User): string {
  if (user.permissions.length === 0) return 'aucun droit';
  if (user.permissions.includes('admin')) return 'tous les droits';
  return PERMISSION_ORDER.filter((code) => user.permissions.includes(code))
    .map((code) => PERMISSION_LABELS[code])
    .join(' · ');
}

/* ============================================================
   Journal des modifications
   ============================================================ */

/** Nature d'une modification, pour la pastille du journal. */
export type AccountChangeKind = 'permission' | 'account' | 'security';

export const ACCOUNT_CHANGE_KIND_LABELS: Readonly<Record<AccountChangeKind, string>> = {
  permission: 'Droit',
  account: 'Compte',
  security: 'Sécurité',
};

/**
 * Une entrée du journal des modifications d'un compte.
 *
 * NF-02 et S-07 imposent de conserver auteur, date et résultat de toute
 * action sensible. Attribuer un droit en fait partie.
 */
export interface AccountChange {
  readonly id: number;
  /** Compte concerné. */
  readonly userId: number;
  readonly kind: AccountChangeKind;
  readonly summary: string;
  /** Précision facultative : ancienne valeur, motif, canal. */
  readonly detail: string | null;
  readonly authorName: string;
  readonly authorInitials: string;
  readonly atLabel: string;
}
