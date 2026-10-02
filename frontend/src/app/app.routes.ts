import { Routes } from '@angular/router';
import { AppShell } from './layout/app-shell/app-shell';

/**
 * Routes de l'application.
 *
 * Les URL sont en français : ce sont des libellés visibles par
 * l'utilisateur, au même titre qu'un titre d'écran. Les identifiants du
 * code, eux, restent en anglais.
 *
 * Les écrans encore à construire passent par `PendingScreen` : leur
 * route existe, ce qui garde la navigation vérifiable de bout en bout.
 * Les valeurs de `data` de ces routes sont liées aux entrées de
 * `PendingScreen` par `withComponentInputBinding()`, activé dans
 * `app.config.ts`.
 */
export const routes: Routes = [
  {
    path: 'connexion',
    title: 'Connexion · IAGORA',
    loadComponent: () => import('./features/auth/login/login').then((m) => m.Login),
  },
  {
    path: '',
    component: AppShell,
    children: [
      {
        path: 'tableau-de-bord',
        title: 'Tableau de bord · IAGORA',
        loadComponent: () =>
          import('./features/dashboard/overview/overview').then((m) => m.Overview),
      },
      {
        path: 'publications',
        title: 'Publications · IAGORA',
        loadComponent: () =>
          import('./features/publications/publication-list/publication-list').then(
            (m) => m.PublicationList,
          ),
      },
      {
        path: 'publications/nouvelle',
        title: 'Créer une publication · IAGORA',
        loadComponent: () =>
          import('./features/generation/publication-composer/publication-composer').then(
            (m) => m.PublicationComposer,
          ),
      },
      {
        path: 'publications/generer',
        title: 'Générer une publication · IAGORA',
        loadComponent: () =>
          import('./features/generation/publication-generator/publication-generator').then(
            (m) => m.PublicationGenerator,
          ),
      },
      {
        path: 'calendrier',
        title: 'Calendrier éditorial · IAGORA',
        loadComponent: () =>
          import('./features/calendar/editorial-calendar/editorial-calendar').then(
            (m) => m.EditorialCalendar,
          ),
      },

      {
        path: 'messages',
        title: 'Messages unifiés · IAGORA',
        loadComponent: () =>
          import('./features/messages/unified-inbox/unified-inbox').then((m) => m.UnifiedInbox),
      },

      {
        path: 'webinaires',
        title: 'Webinaires · IAGORA',
        loadComponent: () =>
          import('./features/webinars/webinar-list/webinar-list').then((m) => m.WebinarList),
      },
      {
        path: 'newsletter/envois',
        title: "Boîte d'envois · IAGORA",
        loadComponent: () =>
          import('./features/newsletter/send-log/send-log').then((m) => m.SendLog),
      },
      {
        path: 'newsletter/modeles',
        title: 'Modèles de mail · IAGORA',
        loadComponent: () =>
          import('./features/newsletter/mail-templates/mail-templates').then((m) => m.MailTemplates),
      },
      { path: 'newsletter', pathMatch: 'full', redirectTo: 'newsletter/envois' },

      {
        path: 'reseaux',
        title: 'Réseaux & plateformes · IAGORA',
        loadComponent: () =>
          import('./features/networks/network-list/network-list').then((m) => m.NetworkList),
      },

      /* ---------- écrans prévus, pages à construire ---------- */
      {
        path: 'historique',
        title: 'Historique des activités · IAGORA',
        data: {
          title: 'Historique des activités',
          trail: ['Mesurer', 'Historique des activités'],
          icon: 'history',
          mockup: '7b',
        },
        loadComponent: () =>
          import('./features/placeholder/pending-screen').then((m) => m.PendingScreen),
      },
      {
        path: 'notifications',
        title: 'Notifications · IAGORA',
        data: {
          title: 'Notifications',
          trail: ['Notifications'],
          icon: 'bell',
          mockup: '11a',
        },
        loadComponent: () =>
          import('./features/placeholder/pending-screen').then((m) => m.PendingScreen),
      },
      {
        path: 'utilisateurs',
        title: 'Habilitations et utilisateurs · IAGORA',
        loadComponent: () =>
          import('./features/admin/user-list/user-list').then((m) => m.UserList),
      },
      {
        path: 'parametres',
        title: 'Paramètres · IAGORA',
        data: {
          title: 'Paramètres',
          trail: ['Administrer', 'Paramètres'],
          icon: 'gear',
          mockup: 'non maquettée',
        },
        loadComponent: () =>
          import('./features/placeholder/pending-screen').then((m) => m.PendingScreen),
      },

      { path: '', pathMatch: 'full', redirectTo: 'tableau-de-bord' },
    ],
  },

  { path: '**', redirectTo: 'tableau-de-bord' },
];
