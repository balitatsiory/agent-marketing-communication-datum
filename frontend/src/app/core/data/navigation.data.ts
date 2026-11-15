import { NavigationEntry } from '../models/navigation';

/**
 * Barre latérale — variante 5b des maquettes : catégories repliables,
 * sans en-têtes de section.
 *
 * « Tableau de bord » et « Inscriptions » restent absents : aucune
 * maquette ne leur correspond dans l'export v2.1.
 *
 * `isPending` marque les écrans dont la route existe mais dont la page
 * n'est pas encore construite.
 */
export const NAVIGATION: readonly NavigationEntry[] = [
  {
    type: 'link',
    key: 'dashboard',
    label: 'Tableau de bord',
    icon: 'chart',
    route: '/tableau-de-bord',
  },
  {
    type: 'group',
    key: 'publish',
    label: 'Publier',
    icon: 'megaphone',
    items: [
      { kind: 'link', key: 'compose', label: 'Créer une publication', icon: 'pencil', route: '/publications/nouvelle' },
      { kind: 'link', key: 'generate', label: 'Générer une publication', icon: 'sparkle', route: '/publications/generer' },
      { kind: 'link', key: 'publications', label: 'Publications', icon: 'files', route: '/publications', count: '24' },
      { kind: 'link', key: 'media-references', label: 'Médias de référence', icon: 'image', route: '/medias-de-reference', count: '8' },
    ],
  },
  {
    type: 'group',
    key: 'schedule',
    label: 'Programmer',
    icon: 'clock',
    items: [
      { kind: 'link', key: 'calendar', label: 'Calendrier', icon: 'calendar', route: '/calendrier', count: '8' },
    ],
  },
  {
    type: 'group',
    key: 'engage',
    label: 'Interagir',
    icon: 'chat',
    items: [
      { kind: 'link', key: 'messages', label: 'Messages unifiés', icon: 'chat', route: '/messages', badge: '12' },
    ],
  },
  {
    type: 'group',
    key: 'events',
    label: 'Événements',
    icon: 'cap',
    items: [
      {
        kind: 'subgroup',
        key: 'Webinaires',
        label: 'Webinaires',
        icon: 'video',
        items: [
          { key: 'sends', label: "Voir les webinaires", icon: 'files', route: '/webinaires' },
          { key: 'templates', label: 'Créer un webinaire', icon: 'pencil', route: '/webinaires/nouveau'},
        ],
      },
      {
        kind: 'subgroup',
        key: 'newsletter',
        label: 'Newsletter',
        icon: 'send',
        items: [
          { key: 'sends', label: "Boîte d'envois", icon: 'files', route: '/newsletter/envois', count: '14' },
          { key: 'templates', label: 'Modèles de mail', icon: 'pencil', route: '/newsletter/modeles', count: '6' },
        ],
      },
    ],
  },
  {
    type: 'group',
    key: 'measure',
    label: 'Mesurer',
    icon: 'chart',
    items: [
      { kind: 'link', key: 'networks', label: 'Réseaux & plateformes', icon: 'share', route: '/reseaux', count: '4' },
      { kind: 'link', key: 'activity', label: 'Historique des activités', icon: 'history', route: '/historique', isPending: true },
    ],
  },
  {
    type: 'link',
    key: 'notifications',
    label: 'Notifications',
    icon: 'bell',
    route: '/notifications',
    badge: '3',
    isPending: true,
  },
  {
    type: 'group',
    key: 'administer',
    label: 'Administrer',
    icon: 'sliders',
    items: [
      {
        kind: 'subgroup',
        key: 'Inteligence artificielle',
        label: 'Intelligence artificielle',
        icon: 'sparkle',
        items: [
          {  key: 'ai-models', label: 'Modèles IA', icon: 'sparkle', route: '/modeles-ia', count: '8' },
          {  key: 'prompt-system', label: 'Prompt système', icon: 'pencil', route: '/admin/prompts/system' },
          {  key: 'prompt-templates', label: 'Prompt templates', icon: 'files', route: '/admin/prompts/templates' },
            ],
      },
      { kind: 'link', key: 'users', label: 'Utilisateurs', icon: 'users', route: '/utilisateurs', count: '6' },
      { kind: 'link', key: 'settings', label: 'Paramètres', icon: 'gear', route: '/parametres', isPending: true },
      { kind: 'link', key: 'integrations', label: 'Gestion outils tierces', icon: 'sliders', route: '/admin/outils-tierces' },
    ],
  },
];
