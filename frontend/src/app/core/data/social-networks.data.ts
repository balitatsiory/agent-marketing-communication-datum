import { SocialNetwork } from '../models/social-network';

/**
 * Comptes de réseaux de Datum Academy — données statiques.
 *
 * Les adresses de profil viennent de deux sources : celles fournies par
 * l'équipe, et celles lues sur le site public datumacademy.com. Elles
 * divergent pour Facebook — voir la note sur l'entrée concernée.
 *
 * Les liens sont écrits sous leur forme canonique. Une adresse passée
 * par la redirection `l.facebook.com/l.php?u=…` ne doit jamais être
 * conservée telle quelle : elle porte un identifiant de suivi `fbclid`
 * et une signature `h=` qui expire, donc un lien qui finit par casser.
 *
 * À remplacer par `GET /api/v1/social-accounts`.
 */
export const SOCIAL_NETWORKS: readonly SocialNetwork[] = [
  {
    code: 'instagram',
    label: 'Instagram',
    accountName: '@datum.academy',
    accountKind: 'Compte professionnel',
    isConnected: true,
    followerCount: 8420,
    deliveryCount: 72,
    publicationCount: 56,
    profileViewCount: 7980,
    followerHistory: [
      8180, 8186, 8191, 8199, 8204, 8212, 8219, 8228, 8241, 8256,
      8264, 8270, 8277, 8283, 8290, 8298, 8305, 8311, 8318, 8330,
      8349, 8362, 8371, 8379, 8386, 8392, 8399, 8406, 8413, 8420,
    ],
    profileUrl: 'https://www.instagram.com/datum.academy',
    lastSyncLabel: "aujourd'hui, 08 h 40",
    connectionNote: null,
  },
  {
    code: 'facebook',
    label: 'Facebook',
    accountName: 'Datum Academy',
    accountKind: 'Page',
    isConnected: true,
    followerCount: 6150,
    deliveryCount: 64,
    publicationCount: 42,
    profileViewCount: 6210,
    followerHistory: [
      6016, 6021, 6025, 6030, 6034, 6039, 6044, 6050, 6058, 6067,
      6072, 6076, 6080, 6084, 6089, 6093, 6097, 6101, 6106, 6113,
      6121, 6127, 6132, 6136, 6139, 6142, 6145, 6147, 6149, 6150,
    ],
    // Adresse fournie par l'équipe. Le site public renvoie, lui, vers
    // facebook.com/datumacademyfr : à arbitrer avant mise en production.
    profileUrl: 'https://www.facebook.com/profile.php?id=61593583736321',
    lastSyncLabel: "aujourd'hui, 08 h 40",
    connectionNote: null,
  },
  {
    code: 'linkedin',
    label: 'LinkedIn',
    accountName: 'Datum Academy',
    accountKind: 'Page entreprise',
    isConnected: true,
    followerCount: 3980,
    deliveryCount: 18,
    publicationCount: 18,
    profileViewCount: 2110,
    followerHistory: [
      3812, 3818, 3824, 3829, 3836, 3842, 3849, 3857, 3869, 3882,
      3889, 3894, 3899, 3903, 3908, 3913, 3918, 3922, 3928, 3937,
      3946, 3953, 3958, 3962, 3966, 3970, 3973, 3976, 3978, 3980,
    ],
    profileUrl: 'https://www.linkedin.com/company/datumacademy',
    lastSyncLabel: "aujourd'hui, 08 h 40",
    connectionNote: null,
  },
  {
    code: 'tiktok',
    label: 'TikTok',
    accountName: '@datumacademy',
    accountKind: 'Compte',
    isConnected: false,
    followerCount: 1240,
    deliveryCount: 12,
    publicationCount: 12,
    profileViewCount: 2130,
    followerHistory: [
      1232, 1233, 1234, 1235, 1236, 1237, 1238, 1239, 1240, 1240,
      1240, 1240, 1240, 1240, 1240, 1240, 1240, 1240, 1240, 1240,
      1240, 1240, 1240, 1240, 1240, 1240, 1240, 1240, 1240, 1240,
    ],
    // Aucune adresse communiquée : le bouton reste désactivé plutôt que
    // de pointer vers une page devinée.
    profileUrl: null,
    lastSyncLabel: '2 septembre',
    connectionNote:
      'Jeton expiré — les statistiques datent du 2 septembre. Reconnectez le compte pour reprendre la collecte.',
  },
];
