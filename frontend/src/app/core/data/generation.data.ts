import {
  GenerationBrief,
  GenerationProposal,
  RetouchMessage,
  VisualVersion,
} from '../models/generation';

/**
 * Jeu de génération statique — maquettes 4a et 4a1.
 *
 * Le sujet (formation cloud AWS) et les trois angles viennent de la
 * maquette ; les visuels sont de vrais flyers servis depuis
 * `public/flyers/`. À remplacer par `POST /api/v1/generation`.
 */

/** Brief pré-rempli à l'ouverture de l'écran. */
export const DEFAULT_BRIEF: GenerationBrief = {
  subject: 'Les avantages du cours cloud AWS',
  context:
    "Formation cloud AWS en ligne : bénéfices concrets (coûts à l'usage, scalabilité, certification). Public : devs juniors et reconversion.",
  tone: 'inspiring',
  format: 'reel',
  networks: new Set(['facebook', 'instagram']),
  language: 'Français',
  includeHashtags: true,
};

/** Générations restantes sur le quota du mois. */
export const REMAINING_GENERATIONS = 12;

export const PROPOSALS: readonly GenerationProposal[] = [
  {
    id: 1,
    title: 'Proposition 1',
    angle: 'inspirant',
    paragraphs: [
      "Le cloud AWS, ce n'est plus une option — c'est un accélérateur. ☁️",
      "Notre formation vous fait passer de « j'en ai entendu parler » à « je déploie en production » : facturation à l'usage, mise à l'échelle automatique, haute disponibilité multi-régions, et une préparation directe à la certification Solutions Architect.",
      'Prochaine session le 21 septembre · 12 places · lien en bio 👇',
    ],
    hashtags: [
      '#AWS',
      '#cloudcomputing',
      '#formationcloud',
      '#devops',
      '#certificationAWS',
      '#reconversionIT',
    ],
    extraHashtagCount: 6,
    visual: {
      source: 'flyers/aws-4-5.svg',
      ratio: '4 / 5',
      dimensions: '1080 × 1350',
      alt: 'Flyer bleu nuit et orange annonçant la formation Cloud AWS du 21 septembre',
    },
  },
  {
    id: 2,
    title: 'Proposition 2',
    angle: 'court & direct',
    paragraphs: [
      "3 raisons de passer au cloud AWS : payer à l'usage, scaler en un clic, dormir tranquille.",
      'Formation complète → lien en bio.',
    ],
    hashtags: ['#AWS', '#cloud', '#formation'],
    extraHashtagCount: 0,
    visual: {
      source: 'flyers/aws-1-1-direct.svg',
      ratio: '1 / 1',
      dimensions: '1080 × 1080',
      alt: 'Flyer blanc listant trois raisons de passer au cloud AWS',
    },
  },
  {
    id: 3,
    title: 'Proposition 3',
    angle: 'question / engagement',
    paragraphs: [
      "Serveur qui tombe un vendredi soir : déjà vécu ? 😅 Sur AWS, la mise à l'échelle automatique s'en occupe.",
      'Racontez-nous votre pire panne en commentaire.',
    ],
    hashtags: ['#AWS', '#devops', '#communauté'],
    extraHashtagCount: 0,
    visual: {
      source: 'flyers/aws-1-1-question.svg',
      ratio: '1 / 1',
      dimensions: '1080 × 1080',
      alt: "Flyer sombre montrant un pic de charge le vendredi soir absorbé par la mise à l'échelle",
    },
  },
];

/**
 * Versions successives du visuel dans la pop-up de retouche, de la plus
 * récente à la plus ancienne — c'est l'ordre d'affichage des pastilles.
 */
export const VISUAL_VERSIONS: readonly VisualVersion[] = [
  {
    label: 'v3',
    change: 'palette bleu nuit / orange AWS',
    visual: {
      source: 'flyers/aws-9-16-v3.svg',
      ratio: '9 / 16',
      dimensions: '1080 × 1920',
      alt: 'Visuel vertical bleu nuit et orange pour la formation Cloud AWS',
    },
  },
  {
    label: 'v2',
    change: 'contraste du texte renforcé',
    visual: {
      source: 'flyers/aws-9-16-v2.svg',
      ratio: '9 / 16',
      dimensions: '1080 × 1920',
      alt: 'Visuel vertical clair avec un voile sombre sous le texte',
    },
  },
  {
    label: 'v1',
    change: null,
    visual: {
      source: 'flyers/aws-9-16-v1.svg',
      ratio: '9 / 16',
      dimensions: '1080 × 1920',
      alt: 'Premier visuel vertical généré à partir du brief',
    },
  },
];

/** Palette appliquée au visuel courant. */
export const APPLIED_PALETTE: readonly string[] = ['#232F3E', '#FF9900', '#FFFFFF'];

/** Conversation de retouche déjà entamée, du plus ancien au plus récent. */
export const RETOUCH_CONVERSATION: readonly RetouchMessage[] = [
  { author: 'system', text: 'image générée à partir du brief' },
  {
    author: 'user',
    text: 'Utilise la palette de couleurs de notre marque : bleu nuit #232F3E et orange #FF9900.',
  },
  {
    author: 'assistant',
    text: "J'ai régénéré le visuel avec cette palette (v3) : fond bleu nuit, accents orange.",
    actions: ['Garder v3', 'Revenir à v2'],
  },
  { author: 'user', text: 'Ajoute notre logo en bas à droite.' },
];

/** Raccourcis de retouche proposés sous la conversation. */
export const RETOUCH_SUGGESTIONS: readonly string[] = [
  'Autre palette',
  'Plus lumineux',
  'Recadrer 9:16',
];
