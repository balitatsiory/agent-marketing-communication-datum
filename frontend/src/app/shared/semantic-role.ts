/**
 * Les cinq rôles de couleur du design system, plus un neutre.
 *
 * Un rôle dit ce qu'un élément *signifie*, jamais de quelle couleur
 * il est : c'est `styles/design-system/_roles.scss` qui fait la
 * correspondance avec la charte Datum. Un composant qui raisonne en
 * rôles reste juste si la charte change.
 *
 *   primary  l'action, le chemin principal
 *   success  ce qui est parti, validé, en ligne
 *   warning  ce qui attend une action humaine
 *   danger   ce qui a échoué ou expire
 *   info     un repère, une information sans urgence
 *   neutral  la même forme, sans signal
 */
export type SemanticRole = 'primary' | 'success' | 'warning' | 'danger' | 'info' | 'neutral';

/** Dans l'ordre d'importance décroissante. Utile pour les légendes. */
export const SEMANTIC_ROLES: readonly SemanticRole[] = [
  'primary',
  'success',
  'warning',
  'danger',
  'info',
  'neutral',
] as const;

/** Classe CSS qui pose `--hue` et `--tint` pour un rôle. */
export function roleClass(role: SemanticRole): string {
  return `role-${role}`;
}
