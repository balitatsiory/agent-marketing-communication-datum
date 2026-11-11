import { MediaReference } from '../models/media-reference';

/**
 * Bibliothèque de médias de référence — données fictives.
 *
 * Aucune API n'existe encore pour les médias : ce fichier est la seule
 * source de données de la page, lue par `MediaReferenceStore`. Il sera
 * remplacé par l'appel réel quand le module backend sera écrit.
 *
 * Le jeu couvre chaque cas affiché : les trois rôles, les deux états de
 * description, et une personne représentée sans consentement recueilli.
 */
export const MEDIA_REFERENCES: readonly MediaReference[] = [
  {
    id: 9,
    fileName: 'oracle-image.jpg',
    role: 'asset',
    description:
      'Logo Oracle en lettres blanches sur fond rouge vif en gros plan, cadrage légèrement incliné.',
    descriptionStatus: 'reviewed',
    depictsPerson: false,
    consentCollected: false,
    previewUrl: 'flyers/oracle-image.jpg',
  },
  {
    id: 10,
    fileName: 'google-image.jpg',
    role: 'asset',
    description:
      'Logo « G » de Google en relief 3D aux quatre couleurs officielles (rouge, jaune, vert, bleu) sur fond blanc.',
    descriptionStatus: 'reviewed',
    depictsPerson: false,
    consentCollected: false,
    previewUrl: 'flyers/google-image.jpg',
  },
  {
    id: 11,
    fileName: 'aws-image.jpg',
    role: 'asset',
    description:
      'Logo Amazon Web Services (AWS) en bleu foncé avec la flèche sourire caractéristique sur fond blanc uni.',
    descriptionStatus: 'reviewed',
    depictsPerson: false,
    consentCollected: false,
    previewUrl: 'flyers/aws-image.jpg',
  },
  {
    id: 1,
    fileName: 'logo-aws.png',
    role: 'asset',
    description: 'Logo Amazon Web Services, lettrage sombre et flèche orange, fond transparent.',
    descriptionStatus: 'reviewed',
    depictsPerson: false,
    consentCollected: false,
    previewUrl: 'flyers/aws-1-1-direct.svg',
  },
  {
    id: 2,
    fileName: 'formateur-serge.jpg',
    role: 'asset',
    description:
      'Homme en chemise claire devant un tableau blanc, cadrage buste, lumière naturelle venant de la gauche.',
    descriptionStatus: 'reviewed',
    depictsPerson: true,
    consentCollected: true,
    previewUrl: 'flyers/webinar-seo-4-5.svg',
  },
  {
    id: 3,
    fileName: 'formatrice-hanta.jpg',
    role: 'asset',
    description:
      "Femme souriante devant un écran de code, cadrage buste, lumière chaude, arrière-plan flou d'open space.",
    descriptionStatus: 'ai-proposal',
    depictsPerson: true,
    consentCollected: false,
    previewUrl: 'flyers/webinar-seo-9-16.svg',
  },
  {
    id: 4,
    fileName: 'ambiance-campus-soir.jpg',
    role: 'style',
    description:
      'Bâtiment vitré à la tombée du jour, dominante bleu nuit, reflets ambrés, grain léger et contraste doux.',
    descriptionStatus: 'ai-proposal',
    depictsPerson: false,
    consentCollected: false,
    previewUrl: 'flyers/aws-9-16-v1.svg',
  },
  {
    id: 5,
    fileName: 'palette-charte-2026.png',
    role: 'style',
    description:
      'Nuancier de la charte : bleu pétrole, lavande pâle, gris clair. Aplats nets, aucune texture.',
    descriptionStatus: 'reviewed',
    depictsPerson: false,
    consentCollected: false,
    previewUrl: 'flyers/aws-4-5.svg',
  },
  {
    id: 6,
    fileName: 'gabarit-webinaire-carre.png',
    role: 'layout',
    description:
      'Format carré : titre en haut sur deux lignes, date en bandeau, portrait détouré à droite, logo en pied.',
    descriptionStatus: 'reviewed',
    depictsPerson: false,
    consentCollected: false,
    previewUrl: 'flyers/webinar-seo-1-1.svg',
  },
  {
    id: 7,
    fileName: 'gabarit-story-annonce.png',
    role: 'layout',
    description:
      'Format vertical 9:16 : grand chiffre centré, accroche courte dessous, zone vide en bas pour le lien.',
    descriptionStatus: 'ai-proposal',
    depictsPerson: false,
    consentCollected: false,
    previewUrl: 'flyers/aws-9-16-v2.svg',
  },
  {
    id: 8,
    fileName: 'promo-2025-remise-diplomes.jpg',
    role: 'style',
    description:
      'Groupe en toge sur des marches, lumière de fin de journée, tons chauds, profondeur de champ courte.',
    descriptionStatus: 'reviewed',
    depictsPerson: true,
    consentCollected: true,
    previewUrl: 'flyers/webinar-seo-16-9.svg',
  },
];

/**
 * Proposition de description simulée, en attendant l'appel de vision.
 *
 * Le vrai service lira l'image ; celui-ci ne connaît que son nom.
 */
export function simulatedAiDescription(fileName: string): string {
  return (
    `Image « ${fileName} » : sujet principal centré, fond uni et clair, ` +
    'lumière douce, aucun texte lisible. Description à compléter par la personne qui relit.'
  );
}
