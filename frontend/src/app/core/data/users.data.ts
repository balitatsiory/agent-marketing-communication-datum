import { AccountChange, User } from '../models/user';

/**
 * Comptes de l'espace Datum Academy — données statiques.
 *
 * Aucun rôle : chaque compte porte sa propre liste de droits, comme
 * l'impose F-22. À remplacer par `GET /api/v1/users`.
 */
export const USERS: readonly User[] = [
  {
    id: 1,
    fullName: 'Sarah Lemoine',
    email: 'sarah.lemoine@datum-academy.fr',
    initials: 'SL',
    status: 'active',
    memberSinceLabel: 'mars 2025',
    authMethod: 'google',
    hasTwoFactor: true,
    lastSignInLabel: "aujourd'hui, 09 h 12",
    permissions: ['read', 'create', 'review', 'publish', 'admin'],
  },
  {
    id: 2,
    fullName: 'Hery Rakoto',
    email: 'hery.rakoto@datum-academy.fr',
    initials: 'HR',
    status: 'active',
    memberSinceLabel: 'mars 2025',
    authMethod: 'google',
    hasTwoFactor: true,
    lastSignInLabel: 'hier, 17 h 48',
    permissions: ['read', 'create', 'review', 'publish', 'admin'],
  },
  {
    id: 3,
    fullName: 'Yann Ravelo',
    email: 'yann.ravelo@datum-academy.fr',
    initials: 'YR',
    status: 'active',
    memberSinceLabel: 'septembre 2025',
    authMethod: 'password',
    hasTwoFactor: true,
    lastSignInLabel: "aujourd'hui, 07 h 30",
    permissions: ['read', 'create', 'review'],
  },
  {
    id: 4,
    fullName: 'Noro Andria',
    email: 'noro.andria@datum-academy.fr',
    initials: 'NA',
    status: 'active',
    memberSinceLabel: 'janvier 2026',
    authMethod: 'password',
    hasTwoFactor: false,
    lastSignInLabel: 'il y a 3 jours',
    permissions: ['read', 'create'],
  },
  {
    id: 5,
    fullName: 'Mialy Rasoa',
    email: 'mialy.rasoa@datum-academy.fr',
    initials: 'MR',
    status: 'invited',
    memberSinceLabel: 'invitée le 29 sept. 2026',
    authMethod: 'password',
    hasTwoFactor: false,
    lastSignInLabel: null,
    permissions: ['read', 'create'],
  },
  {
    id: 6,
    fullName: 'Faniry Be',
    email: 'faniry.be@datum-academy.fr',
    initials: 'FB',
    status: 'disabled',
    memberSinceLabel: 'avril 2025',
    authMethod: 'password',
    hasTwoFactor: false,
    lastSignInLabel: '12 juin 2026',
    permissions: ['read'],
  },
];

/** Utilisateur connecté tant que l'authentification n'est pas branchée. */
export const CURRENT_USER: User = USERS[0];

/**
 * Journal des modifications, du plus récent au plus ancien.
 *
 * NF-02 et S-07 : auteur, date et résultat conservés pour toute action
 * sensible. Attribuer un droit en fait partie.
 *
 * À remplacer par `GET /api/v1/users/{id}/changes`.
 */
export const ACCOUNT_CHANGES: readonly AccountChange[] = [
  {
    id: 1,
    userId: 1,
    kind: 'security',
    summary: 'Double authentification activée',
    detail: 'Application mobile, confirmée par code',
    authorName: 'Sarah Lemoine',
    authorInitials: 'SL',
    atLabel: "aujourd'hui, 09 h 14",
  },
  {
    id: 2,
    userId: 1,
    kind: 'permission',
    summary: 'Droit « Administrer » accordé',
    detail: 'Reprise de la gestion des comptes de plateformes',
    authorName: 'Hery Rakoto',
    authorInitials: 'HR',
    atLabel: '12 sept. 2026, 11 h 02',
  },
  {
    id: 3,
    userId: 1,
    kind: 'account',
    summary: 'Compte créé',
    detail: 'Invitation envoyée à sarah.lemoine@datum-academy.fr',
    authorName: 'Hery Rakoto',
    authorInitials: 'HR',
    atLabel: '3 mars 2025, 09 h 40',
  },

  {
    id: 4,
    userId: 3,
    kind: 'permission',
    summary: 'Droit « Publier » retiré',
    detail: 'Les départs passent désormais par l’équipe communication',
    authorName: 'Sarah Lemoine',
    authorInitials: 'SL',
    atLabel: '28 sept. 2026, 15 h 26',
  },
  {
    id: 5,
    userId: 3,
    kind: 'permission',
    summary: 'Droit « Valider » accordé',
    detail: null,
    authorName: 'Sarah Lemoine',
    authorInitials: 'SL',
    atLabel: '14 sept. 2026, 10 h 11',
  },
  {
    id: 6,
    userId: 3,
    kind: 'security',
    summary: 'Mot de passe réinitialisé',
    detail: 'Lien envoyé par courriel, valable 2 h',
    authorName: 'Hery Rakoto',
    authorInitials: 'HR',
    atLabel: '2 sept. 2026, 08 h 55',
  },
  {
    id: 7,
    userId: 3,
    kind: 'account',
    summary: 'Compte créé',
    detail: null,
    authorName: 'Sarah Lemoine',
    authorInitials: 'SL',
    atLabel: '8 sept. 2025, 14 h 20',
  },

  {
    id: 8,
    userId: 2,
    kind: 'permission',
    summary: 'Droit « Administrer » accordé',
    detail: 'Compte fondateur',
    authorName: 'Sarah Lemoine',
    authorInitials: 'SL',
    atLabel: '3 mars 2025, 09 h 45',
  },

  {
    id: 9,
    userId: 4,
    kind: 'permission',
    summary: 'Droit « Créer » accordé',
    detail: 'Prépare les supports des webinaires',
    authorName: 'Sarah Lemoine',
    authorInitials: 'SL',
    atLabel: '15 janv. 2026, 16 h 30',
  },
  {
    id: 10,
    userId: 4,
    kind: 'account',
    summary: 'Compte créé',
    detail: null,
    authorName: 'Hery Rakoto',
    authorInitials: 'HR',
    atLabel: '15 janv. 2026, 16 h 28',
  },

  {
    id: 11,
    userId: 5,
    kind: 'account',
    summary: 'Invitation envoyée',
    detail: 'Relancée une fois le 1er oct.',
    authorName: 'Sarah Lemoine',
    authorInitials: 'SL',
    atLabel: '29 sept. 2026, 10 h 05',
  },

  {
    id: 12,
    userId: 6,
    kind: 'account',
    summary: 'Compte désactivé',
    detail: 'Fin de contrat — droits conservés en lecture pour l’historique',
    authorName: 'Hery Rakoto',
    authorInitials: 'HR',
    atLabel: '30 juin 2026, 18 h 00',
  },
  {
    id: 13,
    userId: 6,
    kind: 'permission',
    summary: 'Droits « Créer » et « Publier » retirés',
    detail: null,
    authorName: 'Hery Rakoto',
    authorInitials: 'HR',
    atLabel: '30 juin 2026, 17 h 58',
  },
];
