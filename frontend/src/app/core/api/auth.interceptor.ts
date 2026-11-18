import { HttpErrorResponse, HttpInterceptorFn, HttpRequest } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, from, switchMap, throwError } from 'rxjs';

import { Session } from '../services/session';

/** Routes qui ne portent pas de jeton et ne doivent jamais en déclencher le renouvellement. */
const SANS_JETON = ['/auth/login', '/auth/refresh'];

/**
 * Pose le jeton d'accès, et le renouvelle une fois sur une réponse 401.
 *
 * Le renouvellement n'est tenté qu'UNE seule fois. S'il échoue, la session est
 * morte : on renvoie sur l'écran de connexion plutôt que de boucler.
 */
export const authInterceptor: HttpInterceptorFn = (requete, suivant) => {
  if (SANS_JETON.some((chemin) => requete.url.includes(chemin))) {
    return suivant(requete);
  }

  const session = inject(Session);
  const routeur = inject(Router);

  const avecJeton = (jeton: string | null): HttpRequest<unknown> =>
    jeton ? requete.clone({ setHeaders: { Authorization: `Bearer ${jeton}` } }) : requete;

  return suivant(avecJeton(session.token)).pipe(
    catchError((erreur: unknown) => {
      const estExpire = erreur instanceof HttpErrorResponse && erreur.status === 401;
      if (!estExpire) return throwError(() => erreur);

      return from(session.refresh()).pipe(
        switchMap((nouveauJeton) => {
          if (!nouveauJeton) {
            void routeur.navigate(['/connexion']);
            return throwError(() => erreur);
          }
          return suivant(avecJeton(nouveauJeton));
        }),
      );
    }),
  );
};
