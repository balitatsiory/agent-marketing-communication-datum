/**
 * Forme d'une liste paginée renvoyée par l'API.
 *
 * Miroir exact de `Page[T]` côté backend. Aucune liste ne sort en tableau nu :
 * un tableau nu ne pourrait plus accueillir un total le jour où un écran en a
 * besoin.
 */
export interface Page<T> {
  readonly items: readonly T[];
  readonly total: number;
  readonly page: number;
  readonly size: number;
  readonly pages: number;
}

/** Paramètres de pagination, tels que l'API les attend. */
export interface PageQuery {
  readonly page?: number;
  readonly size?: number;
}
