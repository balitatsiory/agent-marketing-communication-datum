import { IconName } from '../../shared/icon/icon-set';

/** Entrée simple de la navigation : un lien vers un écran. */
export interface NavigationLink {
  readonly key: string;
  readonly label: string;
  readonly icon: IconName;
  readonly route: string;
  /** Effectif affiché en gris à droite du libellé. */
  readonly count?: string;
  /** Compteur mis en avant, sur fond plein — à réserver à ce qui réclame une action. */
  readonly badge?: string;
  /** Écran prévu mais pas encore construit. */
  readonly isPending?: boolean;
}

/**
 * Sous-menu repliable à l'intérieur d'une catégorie.
 *
 * Troisième niveau de la navigation : « Événements › Newsletter ›
 * Boîte d'envois ». Il reste le seul, et c'est volontaire — au-delà,
 * une barre latérale devient un labyrinthe.
 */
export interface NavigationSubGroup {
  readonly key: string;
  readonly label: string;
  readonly icon: IconName;
  readonly items: readonly NavigationLink[];
}

/** Enfant d'une catégorie : un lien, ou un sous-menu repliable. */
export type NavigationChild =
  | ({ readonly kind: 'link' } & NavigationLink)
  | ({ readonly kind: 'subgroup' } & NavigationSubGroup);

/** Catégorie repliable de premier niveau. */
export interface NavigationGroup {
  readonly key: string;
  readonly label: string;
  readonly icon: IconName;
  readonly items: readonly NavigationChild[];
}

/**
 * Une entrée de la barre latérale : soit un lien seul, soit une catégorie.
 *
 * C'est la variante 5b des maquettes : catégories repliables, sans
 * en-têtes de section.
 */
export type NavigationEntry =
  | ({ readonly type: 'link' } & NavigationLink)
  | ({ readonly type: 'group' } & NavigationGroup);
