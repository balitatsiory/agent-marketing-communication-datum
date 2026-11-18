import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { Session } from '../services/session';

/**
 * Exige une session ouverte.
 *
 * Attend la restauration avant de décider : sans cela, un rechargement de page
 * sur un écran protégé renverrait vers la connexion alors que le jeton de
 * renouvellement est encore valable.
 */
export const authGuard: CanActivateFn = async () => {
  const session = inject(Session);
  const routeur = inject(Router);

  await session.restore();
  if (session.isSignedIn()) return true;
  return routeur.createUrlTree(['/connexion']);
};
