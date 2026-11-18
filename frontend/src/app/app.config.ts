import { provideHttpClient, withInterceptors } from '@angular/common/http';
import {
  ApplicationConfig,
  LOCALE_ID,
  provideBrowserGlobalErrorListeners,
  provideZoneChangeDetection,
} from '@angular/core';
import { registerLocaleData } from '@angular/common';
import localeFr from '@angular/common/locales/fr';
import { provideRouter, withComponentInputBinding, withInMemoryScrolling } from '@angular/router';

import { authInterceptor } from './core/api/auth.interceptor';
import { routes } from './app.routes';

// Nombres et dates en français : séparateur de milliers par espace insécable,
// mois et jours en toutes lettres.
registerLocaleData(localeFr);

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    // Le passage en « zoneless » (provideZonelessChangeDetection) est resté
    // séparé : le faire en même temps que le branchement de l'API mélangerait
    // deux changements à risque, et un écran qui ne se rafraîchit plus ne
    // dirait pas lequel des deux est en cause.
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideHttpClient(withInterceptors([authInterceptor])),
    provideRouter(
      routes,
      // Lie les `data` de route aux entrées des composants : c'est ce qui
      // alimente `PublicationComposer.mode` et `PendingScreen`.
      withComponentInputBinding(),
      withInMemoryScrolling({ scrollPositionRestoration: 'top' }),
    ),
    { provide: LOCALE_ID, useValue: 'fr' },
  ],
};
