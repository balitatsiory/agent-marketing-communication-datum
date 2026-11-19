/** Réglages d'environnement — production. */
export const environment = {
  production: true,
  /** Même origine que l'application : nginx relaie /api vers l'API. */
  apiBaseUrl: '/api/v1',
} as const;
