/**
 * Réglages d'environnement — développement.
 *
 * `environment.production.ts` le remplace à la compilation de production, par
 * le `fileReplacements` déclaré dans angular.json.
 */
export const environment = {
  production: false,
  /**
   * 127.0.0.1 et non « localhost » : sous Windows, localhost résout d'abord
   * vers ::1 en IPv6, alors que l'API et la base n'écoutent qu'en IPv4.
   */
  apiBaseUrl: 'http://127.0.0.1:8000/api/v1',
} as const;
