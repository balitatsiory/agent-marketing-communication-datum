import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { Session } from '../services/session';

/**
 * Exige la détention d'un droit précis.
 *
 * S'ajoute après `authGuard` dans `canActivate` sans le dupliquer : la
 * restauration est tout de même attendue pour garantir que le profil et ses
 * droits sont chargés avant la vérification.
 */
export function permissionGuard(code: string): CanActivateFn {
  return async () => {
    const session = inject(Session);
    const routeur = inject(Router);

    await session.restore();
    if (session.has(code)) return true;
    return routeur.createUrlTree(['/acces-refuse']);
  };
}
