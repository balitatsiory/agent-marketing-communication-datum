import { HttpErrorResponse } from '@angular/common/http';

/**
 * Enveloppe d'erreur de l'API.
 *
 * `code` est stable et en anglais : c'est lui qu'on teste. `message` est en
 * français et destiné à l'affichage. Jamais l'inverse.
 */
export interface ApiErrorBody {
  readonly error: {
    readonly code: string;
    readonly message: string;
  };
}

/** Erreur de l'API, mise à plat pour être utilisable dans un composant. */
export class ApiError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

const MESSAGE_RESEAU = "L'API est injoignable. Vérifier qu'elle est démarrée.";

/**
 * Convertit une erreur HTTP en `ApiError`.
 *
 * Le statut 0 ne vient pas du serveur : il signale que la requête n'est jamais
 * partie — API arrêtée, mauvaise adresse, ou refus CORS. Le dire explicitement
 * évite de chercher un bug applicatif là où il n'y en a pas.
 */
export function toApiError(erreur: unknown): ApiError {
  if (erreur instanceof ApiError) return erreur;

  if (erreur instanceof HttpErrorResponse) {
    if (erreur.status === 0) return new ApiError('network_error', MESSAGE_RESEAU, 0);

    const corps = erreur.error as Partial<ApiErrorBody> | null;
    if (corps?.error?.code) {
      return new ApiError(corps.error.code, corps.error.message, erreur.status);
    }
    return new ApiError('http_error', `Erreur ${erreur.status}.`, erreur.status);
  }

  return new ApiError('unknown_error', 'Une erreur inattendue est survenue.', 0);
}
