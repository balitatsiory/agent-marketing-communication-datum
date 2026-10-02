import { ElectronicSignature, MailTemplate } from '../models/newsletter';

/**
 * Modèles de courriel — données statiques.
 *
 * Les variables s'écrivent `{{prenom}}` et restent visibles dans
 * l'aperçu d'un modèle ; un envoi les porte déjà substituées.
 *
 * À remplacer par `GET /api/v1/mail-templates`.
 */

/** Signature apposée au pied de chaque modèle. Valeurs illustratives. */
const SIGNATURE: ElectronicSignature = {
  signedBy: "L'équipe communication",
  organisation: 'Datum Academy · Antananarivo',
  signedAt: '2 octobre 2026 à 09 h 14',
  fingerprint: 'DA-7F3B 91C4 2E08',
};

export const MAIL_TEMPLATES: readonly MailTemplate[] = [
  {
    id: 1,
    name: "Confirmation d'inscription — webinaire",
    category: 'registrationConfirmation',
    status: 'published',
    updatedAt: '28 sept. 2026',
    authorName: 'Sarah Lemoine',
    usageCount: 412,
    variables: ['prenom', 'titre_webinaire', 'date', 'heure', 'duree', 'lien_acces', 'lien_calendrier'],
    versions: [
      {
        label: 'v3',
        createdAt: '28 sept. 2026',
        authorName: 'Sarah Lemoine',
        change: "Ajout du lien d'ajout au calendrier et du rappel de durée",
        isCurrent: true,
      },
      {
        label: 'v2',
        createdAt: '12 août 2026',
        authorName: 'Yann Ravelo',
        change: 'Objet raccourci, préheader réécrit pour les aperçus mobiles',
        isCurrent: false,
      },
      {
        label: 'v1',
        createdAt: '3 mars 2026',
        authorName: 'Sarah Lemoine',
        change: 'Première version',
        isCurrent: false,
      },
    ],
    content: {
      subject: 'Votre place est réservée — {{titre_webinaire}}',
      preheader: 'Votre lien de connexion et tout ce qu’il faut savoir avant la séance.',
      greeting: 'Bienvenue {{prenom}},',
      paragraphs: [
        'Nous vous remercions de votre intérêt pour nos formations. Votre inscription au webinaire « {{titre_webinaire}} » est bien enregistrée.',
        "Voici votre lien d'accès personnel : gardez-le, il vous servira le jour de la séance. Inutile d'installer quoi que ce soit, tout se passe dans le navigateur.",
        'Un rappel vous parviendra la veille, puis deux heures avant le début.',
      ],
      details: [
        { label: 'Séance', value: '{{titre_webinaire}}' },
        { label: 'Date', value: '{{date}} à {{heure}} (GMT+3)' },
        { label: 'Durée', value: '{{duree}}, questions comprises' },
        { label: 'Accès', value: 'navigateur, aucun logiciel à installer' },
      ],
      action: { label: 'Rejoindre la séance', url: '{{lien_acces}}' },
      closing:
        "À très vite — et si vous avez une question d'ici là, répondez simplement à ce message.",
      signature: SIGNATURE,
    },
  },
  {
    id: 2,
    name: 'Rappel J-1',
    category: 'reminder',
    status: 'published',
    updatedAt: '14 sept. 2026',
    authorName: 'Yann Ravelo',
    usageCount: 286,
    variables: ['prenom', 'titre_webinaire', 'heure', 'lien_acces'],
    versions: [
      {
        label: 'v2',
        createdAt: '14 sept. 2026',
        authorName: 'Yann Ravelo',
        change: 'Objet rendu plus direct, programme déplacé dans le corps',
        isCurrent: true,
      },
      {
        label: 'v1',
        createdAt: '10 avr. 2026',
        authorName: 'Sarah Lemoine',
        change: 'Première version',
        isCurrent: false,
      },
    ],
    content: {
      subject: "C'est demain — {{titre_webinaire}}",
      preheader: 'Votre lien de connexion, au cas où il se serait perdu.',
      greeting: 'Bonjour {{prenom}},',
      paragraphs: [
        'Petit rappel : « {{titre_webinaire}} » a lieu demain à {{heure}}.',
        "Votre lien d'accès est le même qu'à l'inscription. Vous pouvez arriver cinq minutes en avance, la salle ouvre à ce moment-là.",
      ],
      details: [
        { label: 'Demain', value: '{{heure}} (GMT+3)' },
        { label: 'Questions', value: 'posez-les dans le fil pendant la séance' },
      ],
      action: { label: 'Rejoindre la séance', url: '{{lien_acces}}' },
      closing: 'À demain.',
      signature: SIGNATURE,
    },
  },
  {
    id: 3,
    name: 'Rappel H-2',
    category: 'reminder',
    status: 'draft',
    updatedAt: '1er oct. 2026',
    authorName: 'Sarah Lemoine',
    usageCount: 0,
    variables: ['prenom', 'titre_webinaire', 'lien_acces'],
    versions: [
      {
        label: 'v1',
        createdAt: '1er oct. 2026',
        authorName: 'Sarah Lemoine',
        change: 'Brouillon — version courte, pensée pour une lecture sur mobile',
        isCurrent: true,
      },
    ],
    content: {
      subject: 'Dans deux heures — {{titre_webinaire}}',
      preheader: 'Un clic, et vous y êtes.',
      greeting: 'Bonjour {{prenom}},',
      paragraphs: ['« {{titre_webinaire}} » commence dans deux heures.'],
      details: [],
      action: { label: 'Rejoindre la séance', url: '{{lien_acces}}' },
      closing: 'À tout à l’heure.',
      signature: SIGNATURE,
    },
  },
  {
    id: 4,
    name: 'Report ou annulation de séance',
    category: 'changeOrCancellation',
    status: 'published',
    updatedAt: '20 sept. 2026',
    authorName: 'Hery Rakoto',
    usageCount: 37,
    variables: ['prenom', 'titre_webinaire', 'ancienne_date', 'nouvelle_date', 'motif', 'lien_acces'],
    versions: [
      {
        label: 'v2',
        createdAt: '20 sept. 2026',
        authorName: 'Hery Rakoto',
        change: 'Motif rendu obligatoire, excuse déplacée en tête',
        isCurrent: true,
      },
      {
        label: 'v1',
        createdAt: '18 mai 2026',
        authorName: 'Hery Rakoto',
        change: 'Première version',
        isCurrent: false,
      },
    ],
    content: {
      subject: 'Changement de date — {{titre_webinaire}}',
      preheader: 'La séance est déplacée. Votre inscription reste valable.',
      greeting: 'Bonjour {{prenom}},',
      paragraphs: [
        'Nous devons déplacer la séance « {{titre_webinaire}} », initialement prévue le {{ancienne_date}}. Motif : {{motif}}.',
        "Nous sommes désolés du dérangement. Votre inscription reste valable, vous n'avez rien à refaire : le même lien fonctionnera à la nouvelle date.",
        'Si ce nouveau créneau ne vous convient pas, répondez à ce message et nous vous inscrirons à la session suivante.',
      ],
      details: [
        { label: 'Date annulée', value: '{{ancienne_date}}' },
        { label: 'Nouvelle date', value: '{{nouvelle_date}}' },
        { label: 'Votre lien', value: 'inchangé' },
      ],
      action: { label: 'Voir la nouvelle date', url: '{{lien_acces}}' },
      closing: 'Merci de votre compréhension.',
      signature: SIGNATURE,
    },
  },
  {
    id: 5,
    name: 'Compte rendu & points clés',
    category: 'report',
    status: 'published',
    updatedAt: '17 sept. 2026',
    authorName: 'Yann Ravelo',
    usageCount: 94,
    variables: ['prenom', 'titre_webinaire', 'nb_participants', 'points_cles', 'lien_support'],
    versions: [
      {
        label: 'v4',
        createdAt: '17 sept. 2026',
        authorName: 'Yann Ravelo',
        change: 'Points clés passés en liste, support ajouté en pièce liée',
        isCurrent: true,
      },
      {
        label: 'v3',
        createdAt: '2 juil. 2026',
        authorName: 'Sarah Lemoine',
        change: 'Remerciement personnalisé en ouverture',
        isCurrent: false,
      },
      {
        label: 'v2',
        createdAt: '14 avr. 2026',
        authorName: 'Yann Ravelo',
        change: 'Ajout du nombre de participants',
        isCurrent: false,
      },
      {
        label: 'v1',
        createdAt: '2 févr. 2026',
        authorName: 'Yann Ravelo',
        change: 'Première version',
        isCurrent: false,
      },
    ],
    content: {
      subject: 'Ce qu’il faut retenir — {{titre_webinaire}}',
      preheader: 'Les points clés de la séance, et le support à télécharger.',
      greeting: 'Merci {{prenom}},',
      paragraphs: [
        'Vous étiez {{nb_participants}} à suivre « {{titre_webinaire}} ». Merci pour vos questions, elles ont nourri la deuxième moitié de la séance.',
        'Voici ce qu’il faut en retenir : {{points_cles}}',
        'Le support de présentation est disponible au téléchargement, annotations comprises.',
      ],
      details: [
        { label: 'Participants', value: '{{nb_participants}}' },
        { label: 'Support', value: 'PDF, 24 diapositives' },
      ],
      action: { label: 'Télécharger le support', url: '{{lien_support}}' },
      closing: 'Au plaisir de vous retrouver à une prochaine séance.',
      signature: SIGNATURE,
    },
  },
  {
    id: 6,
    name: 'Rediffusion disponible',
    category: 'replay',
    status: 'published',
    updatedAt: '17 sept. 2026',
    authorName: 'Sarah Lemoine',
    usageCount: 118,
    variables: ['prenom', 'titre_webinaire', 'duree', 'lien_replay'],
    versions: [
      {
        label: 'v2',
        createdAt: '17 sept. 2026',
        authorName: 'Sarah Lemoine',
        change: 'Mention explicite : aucune inscription requise pour regarder',
        isCurrent: true,
      },
      {
        label: 'v1',
        createdAt: '22 mai 2026',
        authorName: 'Sarah Lemoine',
        change: 'Première version',
        isCurrent: false,
      },
    ],
    content: {
      subject: 'La rediffusion est en ligne — {{titre_webinaire}}',
      preheader: 'À regarder quand vous voulez, sans inscription.',
      greeting: 'Bonjour {{prenom}},',
      paragraphs: [
        'La rediffusion de « {{titre_webinaire}} » est disponible. Elle dure {{duree}} et reprend la séance en entier, questions comprises.',
        'Aucune inscription n’est demandée pour la regarder : le lien suffit, et il reste valable sans limite de durée.',
      ],
      details: [
        { label: 'Durée', value: '{{duree}}' },
        { label: 'Accès', value: 'libre, sans compte' },
      ],
      action: { label: 'Regarder la rediffusion', url: '{{lien_replay}}' },
      closing: 'Bon visionnage.',
      signature: SIGNATURE,
    },
  },
];
