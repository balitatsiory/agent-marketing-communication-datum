import { Routes } from '@angular/router';

import { authGuard } from './core/guards/auth-guard';
import { permissionGuard } from './core/guards/permission-guard';
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
  /* Formulaire public d'inscription : hors de la coquille, sans session. */
  {
    path: 'inscription/:slug',
    title: 'Inscription · Datum Academy',
    loadComponent: () =>
      import('./features/public-registration/public-registration').then(
        (m) => m.PublicRegistration,
      ),
  },
  {
    path: '',
    component: AppShell,
    // Tous les écrans de la coquille exigent une session ouverte.
    canActivate: [authGuard],
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
        path: 'publications/generer_v2',
        title: 'Générer une publication (v2) · IAGORA',
        loadComponent: () =>
          import('./features/generation/publication-generator-v2/publication-generator-v2').then(
            (m) => m.PublicationGeneratorV2,
          ),
      },

      {
        path: 'publications/:id',
        title: 'Détail de la publication · IAGORA',
        loadComponent: () =>
          import('./features/publications/publication-detail/publication-detail').then(
            (m) => m.PublicationDetail,
          ),
      },


      {
        path: 'medias',
        title: 'Médiathèque · IAGORA',
        canActivate: [permissionGuard('manage_media')],
        loadComponent: () =>
          import('./features/media/media-library/media-library').then((m) => m.MediaLibrary),
      },

      {
        path: 'medias-de-reference',
        title: 'Médias de référence · IAGORA',
        canActivate: [permissionGuard('manage_media_reference')],
        loadComponent: () =>
          import('./features/media-references/media-reference-list/media-reference-list').then(
            (m) => m.MediaReferenceList,
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
        path: 'webinaires/nouveau',
        title: 'Nouveau webinaire · IAGORA',
        canActivate: [permissionGuard('manage_webinars')],
        loadComponent: () =>
          import('./features/webinars/webinar-editor/webinar-editor').then(
            (m) => m.WebinarEditor,
          ),
      },


      {
        path: 'webinaires/:id/modifier',
        title: 'Modifier un webinaire · IAGORA',
        canActivate: [permissionGuard('manage_webinars')],
        loadComponent: () =>
          import('./features/webinars/webinar-editor/webinar-editor').then(
            (m) => m.WebinarEditor,
          ),
      },


      {
        path: 'webinaires/comptes-zoom',
        title: 'Comptes Zoom · IAGORA',
        canActivate: [permissionGuard('manage_zoom_accounts')],
        loadComponent: () =>
          import('./features/webinars/zoom-accounts/zoom-accounts').then(
            (m) => m.ZoomAccounts,
          ),
      },


      {
        path: 'webinaires',
        title: 'Webinaires · IAGORA',
        loadComponent: () =>
          import('./features/webinars/webinar-directory/webinar-directory').then(
            (m) => m.WebinarDirectory,
          ),
      },


      /* ---------- maquettes 12a / 12b, conservées pour démonstration ---------- */
      {
        path: 'webinaires_prototype/nouveau',
        title: 'Nouveau webinaire (prototype) · IAGORA',
        loadComponent: () =>
          import('./features/webinars/webinar-form/webinar-form').then(
            (m) => m.WebinarForm,
          ),
      },


      {
        path: 'webinaires_prototype/:id/modifier',
        title: 'Reprendre un brouillon (prototype) · IAGORA',
        loadComponent: () =>
          import('./features/webinars/webinar-form/webinar-form').then(
            (m) => m.WebinarForm,
          ),
      },


      {
        path: 'webinaires_prototype',
        title: 'Webinaires (prototype) · IAGORA',
        loadComponent: () =>
          import('./features/webinars/webinar-list/webinar-list').then(
            (m) => m.WebinarList,
          ),
      },


      {
        path: 'newsletter/envois',
        title: "Boîte d'envois · IAGORA",
        loadComponent: () =>
          import('./features/newsletter/send-list/send-list').then((m) => m.SendList),
      },


      {
        path: 'newsletter/envois_prototype',
        title: "Boîte d'envois (prototype) · IAGORA",
        loadComponent: () =>
          import('./features/newsletter/send-log/send-log').then((m) => m.SendLog),
      },


      {
        path: 'newsletter/modeles',
        title: 'Modèles de mail · IAGORA',
        loadComponent: () =>
          import('./features/newsletter/template-library/template-library').then(
            (m) => m.TemplateLibrary,
          ),
      },


      {
        path: 'newsletter/modeles_prototype',
        title: 'Modèles de mail (prototype) · IAGORA',
        loadComponent: () =>
          import('./features/newsletter/mail-templates/mail-templates').then((m) => m.MailTemplates),
      },


      {
        path: 'newsletter/comptes-envoi',
        title: "Comptes d'envoi · IAGORA",
        canActivate: [permissionGuard('manage_email_accounts')],
        loadComponent: () =>
          import('./features/newsletter/sender-accounts/sender-accounts').then(
            (m) => m.SenderAccounts,
          ),
      },


      { path: 'newsletter', pathMatch: 'full', redirectTo: 'newsletter/envois' },

      {
        path: 'reseaux/:id',
        title: 'Fiche compte réseau social · IAGORA',
        loadComponent: () =>
          import('./features/networks/network-detail/network-detail').then((m) => m.NetworkDetail),
      },
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
        loadComponent: () =>
          import('./features/notifications/notification-center/notification-center').then(
            (m) => m.NotificationCenter,
          ),
      },


      {
        path: 'modeles-ia',
        title: 'Modèles IA · IAGORA',
        loadComponent: () =>
          import('./features/admin/ai-models/ai-models').then((m) => m.AiModels),
      },

      {
        path: 'modeles-ia_v2',
        title: 'Modèles IA v2 (OpenRouter) · IAGORA',
        canActivate: [permissionGuard('manage_ai_models')],
        loadComponent: () =>
          import('./features/admin/ai-models-v2/ai-models-v2').then((m) => m.AiModelsV2),
      },

      {
        path: 'bac-a-sable-ia',
        title: 'Bac à sable IA · IAGORA',
        canActivate: [permissionGuard('manage_ai_models')],
        loadComponent: () =>
          import('./features/admin/ai-sandbox/ai-sandbox').then((m) => m.AiSandbox),
      },

      {
        path: 'admin/prompts/system',
        title: 'Prompts système · IAGORA',
        canActivate: [permissionGuard('manage_ai_models')],
        data: { kind: 'system' },
        loadComponent: () =>
          import('./features/admin/ai-prompts/ai-prompts').then((m) => m.AiPrompts),
      },

      {
        path: 'admin/prompts/templates',
        title: 'Prompt templates · IAGORA',
        canActivate: [permissionGuard('manage_ai_models')],
        data: { kind: 'template' },
        loadComponent: () =>
          import('./features/admin/ai-prompts/ai-prompts').then((m) => m.AiPrompts),
      },


      {
        path: 'parametres/modeles-ia',
        pathMatch: 'full',
        redirectTo: 'modeles-ia',
      },


      {
        path: 'utilisateurs',
        title: 'Habilitations et utilisateurs · IAGORA',
        canActivate: [permissionGuard('manage_users')],
        loadComponent: () =>
          import('./features/admin/user-list/user-list').then((m) => m.UserList),
      },

      {
        path: 'droits',
        title: 'Référentiel des droits · IAGORA',
        canActivate: [permissionGuard('manage_users')],
        loadComponent: () =>
          import('./features/admin/permission-list/permission-list').then(
            (m) => m.PermissionList,
          ),
      },

      {
        path: 'acces-refuse',
        title: 'Accès refusé · IAGORA',
        loadComponent: () =>
          import('./features/auth/access-denied/access-denied').then((m) => m.AccessDenied),
      },


      {
        path: 'profil',
        title: 'Profil · IAGORA',
        data: {
          title: 'Profil',
          trail: ['Mon compte', 'Profil'],
          icon: 'users',
          /* `mockup` est omis : « non maquettée » est déjà la valeur
             par défaut de PendingScreen. */
        },
        loadComponent: () =>
          import('./features/placeholder/pending-screen').then((m) => m.PendingScreen),
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
