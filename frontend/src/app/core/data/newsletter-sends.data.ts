import { ElectronicSignature, NewsletterSend } from '../models/newsletter';

/**
 * Historique des envois — données statiques.
 *
 * Les envois se rattachent aux webinaires de `webinars.data.ts` : le
 * webinaire SEO du 15 septembre, celui sur le RAG du 8 octobre, le module
 * Kubernetes du 15 octobre.
 *
 * Contrairement aux modèles, les contenus portent ici des valeurs déjà
 * substituées : c'est ce qui est réellement parti.
 *
 * Seul l'acheminement est mesuré — destinataires, remis, rejets. Voir
 * `NewsletterSend.deliveredCount` pour la raison.
 *
 * À remplacer par `GET /api/v1/newsletter/sends`.
 */

const SIGNATURE: ElectronicSignature = {
  signedBy: "L'équipe communication",
  organisation: 'Datum Academy · Antananarivo',
  signedAt: '15 septembre 2026 à 08 h 02',
  fingerprint: 'DA-7F3B 91C4 2E08',
};

export const NEWSLETTER_SENDS: readonly NewsletterSend[] = [
  /* ---------- confirmations d'inscription ---------- */
  {
    id: 1,
    category: 'registrationConfirmation',
    subject: 'Votre place est réservée — Le RAG en pratique',
    eventTitle: 'Le RAG en pratique : quand ça marche, quand ça casse',
    templateName: "Confirmation d'inscription — webinaire",
    templateVersion: 'v3',
    sentAtLabel: "aujourd'hui, en continu",
    status: 'sent',
    recipientCount: 42,
    deliveredCount: 42,
    failureNote: null,
    content: {
      subject: 'Votre place est réservée — Le RAG en pratique',
      preheader: 'Votre lien de connexion et tout ce qu’il faut savoir avant la séance.',
      greeting: 'Bienvenue Mamadou,',
      paragraphs: [
        'Nous vous remercions de votre intérêt pour nos formations. Votre inscription au webinaire « Le RAG en pratique : quand ça marche, quand ça casse » est bien enregistrée.',
        "Voici votre lien d'accès personnel : gardez-le, il vous servira le jour de la séance. Inutile d'installer quoi que ce soit, tout se passe dans le navigateur.",
        'Un rappel vous parviendra la veille, puis deux heures avant le début.',
      ],
      details: [
        { label: 'Séance', value: 'Le RAG en pratique' },
        { label: 'Date', value: '8 octobre 2026 à 20:00 (GMT+3)' },
        { label: 'Durée', value: '1 h 30, questions comprises' },
        { label: 'Accès', value: 'navigateur, aucun logiciel à installer' },
      ],
      action: {
        label: 'Rejoindre la séance',
        url: 'datumacademy.com/fr/webinar/rag-en-pratique/acces/7f3b91c4',
      },
      closing: "À très vite — et si vous avez une question d'ici là, répondez simplement à ce message.",
      signature: SIGNATURE,
    },
  },
  {
    id: 2,
    category: 'registrationConfirmation',
    subject: 'Votre place est réservée — Kubernetes en production',
    eventTitle: 'Kubernetes en production : disséquer un premier incident',
    templateName: "Confirmation d'inscription — webinaire",
    templateVersion: 'v3',
    sentAtLabel: 'depuis le 24 sept.',
    status: 'sent',
    recipientCount: 18,
    deliveredCount: 18,
    failureNote: null,
    content: {
      subject: 'Votre place est réservée — Kubernetes en production',
      preheader: 'Votre lien de connexion et tout ce qu’il faut savoir avant la séance.',
      greeting: 'Bienvenue Hasina,',
      paragraphs: [
        'Nous vous remercions de votre intérêt pour nos formations. Votre inscription au webinaire « Kubernetes en production : disséquer un premier incident » est bien enregistrée.',
        "Voici votre lien d'accès personnel : gardez-le, il vous servira le jour de la séance.",
      ],
      details: [
        { label: 'Séance', value: 'Kubernetes en production' },
        { label: 'Date', value: '15 octobre 2026 à 18:30 (GMT+3)' },
        { label: 'Durée', value: '1 h, questions comprises' },
      ],
      action: {
        label: 'Rejoindre la séance',
        url: 'datumacademy.com/fr/webinar/kubernetes-premier-incident/acces/2e08b4',
      },
      closing: "À très vite — et si vous avez une question d'ici là, répondez simplement à ce message.",
      signature: SIGNATURE,
    },
  },
  {
    id: 3,
    category: 'registrationConfirmation',
    subject: 'Votre place est réservée — Les bases du SEO technique',
    eventTitle: 'Les bases du SEO technique',
    templateName: "Confirmation d'inscription — webinaire",
    templateVersion: 'v2',
    sentAtLabel: 'du 1er au 15 sept.',
    status: 'sent',
    recipientCount: 168,
    deliveredCount: 166,
    failureNote: null,
    content: {
      subject: 'Votre place est réservée — Les bases du SEO technique',
      preheader: 'Votre lien de connexion et tout ce qu’il faut savoir avant la séance.',
      greeting: 'Bienvenue Ndèye,',
      paragraphs: [
        'Nous vous remercions de votre intérêt pour nos formations. Votre inscription au webinaire « Les bases du SEO technique » est bien enregistrée.',
        "Voici votre lien d'accès personnel : gardez-le, il vous servira le jour de la séance.",
      ],
      details: [
        { label: 'Séance', value: 'Les bases du SEO technique' },
        { label: 'Date', value: '15 septembre 2026 à 20:00 (GMT+3)' },
        { label: 'Durée', value: '1 h 30, questions comprises' },
      ],
      action: {
        label: 'Rejoindre la séance',
        url: 'datumacademy.com/fr/webinar/bases-du-seo-technique/acces/91c42e',
      },
      closing: 'À très vite.',
      signature: SIGNATURE,
    },
  },

  /* ---------- rappels ---------- */
  {
    id: 4,
    category: 'reminder',
    subject: "C'est demain — Les bases du SEO technique",
    eventTitle: 'Les bases du SEO technique',
    templateName: 'Rappel J-1',
    templateVersion: 'v2',
    sentAtLabel: '14 sept., 09 h 00',
    status: 'sent',
    recipientCount: 166,
    deliveredCount: 165,
    failureNote: null,
    content: {
      subject: "C'est demain — Les bases du SEO technique",
      preheader: 'Votre lien de connexion, au cas où il se serait perdu.',
      greeting: 'Bonjour Ndèye,',
      paragraphs: [
        'Petit rappel : « Les bases du SEO technique » a lieu demain à 20:00.',
        "Votre lien d'accès est le même qu'à l'inscription. Vous pouvez arriver cinq minutes en avance, la salle ouvre à ce moment-là.",
      ],
      details: [
        { label: 'Demain', value: '20:00 (GMT+3)' },
        { label: 'Questions', value: 'posez-les dans le fil pendant la séance' },
      ],
      action: {
        label: 'Rejoindre la séance',
        url: 'datumacademy.com/fr/webinar/bases-du-seo-technique/acces/91c42e',
      },
      closing: 'À demain.',
      signature: SIGNATURE,
    },
  },
  {
    id: 5,
    category: 'reminder',
    subject: 'Dans deux heures — Les bases du SEO technique',
    eventTitle: 'Les bases du SEO technique',
    templateName: 'Rappel H-2',
    templateVersion: 'v1',
    sentAtLabel: '15 sept., 18 h 00',
    status: 'partial',
    recipientCount: 165,
    deliveredCount: 158,
    failureNote:
      '7 adresses rejetées par le fournisseur destinataire : boîtes pleines ou domaines expirés. Elles sont exclues des envois suivants.',
    content: {
      subject: 'Dans deux heures — Les bases du SEO technique',
      preheader: 'Un clic, et vous y êtes.',
      greeting: 'Bonjour Ndèye,',
      paragraphs: ['« Les bases du SEO technique » commence dans deux heures.'],
      details: [],
      action: {
        label: 'Rejoindre la séance',
        url: 'datumacademy.com/fr/webinar/bases-du-seo-technique/acces/91c42e',
      },
      closing: 'À tout à l’heure.',
      signature: SIGNATURE,
    },
  },
  {
    id: 6,
    category: 'reminder',
    subject: "C'est demain — Le RAG en pratique",
    eventTitle: 'Le RAG en pratique : quand ça marche, quand ça casse',
    templateName: 'Rappel J-1',
    templateVersion: 'v2',
    sentAtLabel: '7 oct., 09 h 00',
    status: 'scheduled',
    recipientCount: 42,
    deliveredCount: 0,
    failureNote: null,
    content: {
      subject: "C'est demain — Le RAG en pratique",
      preheader: 'Votre lien de connexion, au cas où il se serait perdu.',
      greeting: 'Bonjour Mamadou,',
      paragraphs: [
        'Petit rappel : « Le RAG en pratique » a lieu demain à 20:00.',
        "Votre lien d'accès est le même qu'à l'inscription.",
      ],
      details: [{ label: 'Demain', value: '20:00 (GMT+3)' }],
      action: {
        label: 'Rejoindre la séance',
        url: 'datumacademy.com/fr/webinar/rag-en-pratique/acces/7f3b91c4',
      },
      closing: 'À demain.',
      signature: SIGNATURE,
    },
  },
  {
    id: 7,
    category: 'reminder',
    subject: 'Dans deux heures — Le RAG en pratique',
    eventTitle: 'Le RAG en pratique : quand ça marche, quand ça casse',
    templateName: 'Rappel H-2',
    templateVersion: 'v1',
    sentAtLabel: '8 oct., 18 h 00',
    status: 'scheduled',
    recipientCount: 42,
    deliveredCount: 0,
    failureNote: null,
    content: {
      subject: 'Dans deux heures — Le RAG en pratique',
      preheader: 'Un clic, et vous y êtes.',
      greeting: 'Bonjour Mamadou,',
      paragraphs: ['« Le RAG en pratique » commence dans deux heures.'],
      details: [],
      action: {
        label: 'Rejoindre la séance',
        url: 'datumacademy.com/fr/webinar/rag-en-pratique/acces/7f3b91c4',
      },
      closing: 'À tout à l’heure.',
      signature: SIGNATURE,
    },
  },

  /* ---------- modifications et annulations ---------- */
  {
    id: 8,
    category: 'changeOrCancellation',
    subject: 'Changement de date — Kubernetes en production',
    eventTitle: 'Kubernetes en production : disséquer un premier incident',
    templateName: 'Report ou annulation de séance',
    templateVersion: 'v2',
    sentAtLabel: '29 sept., 14 h 20',
    status: 'sent',
    recipientCount: 18,
    deliveredCount: 18,
    failureNote: null,
    content: {
      subject: 'Changement de date — Kubernetes en production',
      preheader: 'La séance est déplacée. Votre inscription reste valable.',
      greeting: 'Bonjour Hasina,',
      paragraphs: [
        'Nous devons déplacer la séance « Kubernetes en production : disséquer un premier incident », initialement prévue le 8 octobre. Motif : indisponibilité de l’intervenant.',
        "Nous sommes désolés du dérangement. Votre inscription reste valable, vous n'avez rien à refaire : le même lien fonctionnera à la nouvelle date.",
        'Si ce nouveau créneau ne vous convient pas, répondez à ce message et nous vous inscrirons à la session suivante.',
      ],
      details: [
        { label: 'Date annulée', value: '8 octobre 2026, 18:30' },
        { label: 'Nouvelle date', value: '15 octobre 2026, 18:30' },
        { label: 'Votre lien', value: 'inchangé' },
      ],
      action: {
        label: 'Voir la nouvelle date',
        url: 'datumacademy.com/fr/webinar/kubernetes-premier-incident',
      },
      closing: 'Merci de votre compréhension.',
      signature: SIGNATURE,
    },
  },
  {
    id: 9,
    category: 'changeOrCancellation',
    subject: 'Séance annulée — Alternance data, mode d’emploi',
    eventTitle: "Alternance data : mode d'emploi pour les entreprises",
    templateName: 'Report ou annulation de séance',
    templateVersion: 'v1',
    sentAtLabel: '12 août, 11 h 05',
    status: 'sent',
    recipientCount: 31,
    deliveredCount: 31,
    failureNote: null,
    content: {
      subject: 'Séance annulée — Alternance data, mode d’emploi',
      preheader: "La séance n'aura pas lieu. Nous revenons vers vous à la rentrée.",
      greeting: 'Bonjour Tiana,',
      paragraphs: [
        "Nous devons annuler la séance « Alternance data : mode d'emploi pour les entreprises », initialement prévue le 20 août. Motif : effectif insuffisant à cette période.",
        'Nous sommes désolés du dérangement. Nous reprogrammerons cette séance à la rentrée et vous préviendrons en priorité.',
      ],
      details: [
        { label: 'Date annulée', value: '20 août 2026, 11:00' },
        { label: 'Nouvelle date', value: 'à définir' },
      ],
      action: null,
      closing: 'Merci de votre compréhension.',
      signature: SIGNATURE,
    },
  },

  /* ---------- comptes rendus ---------- */
  {
    id: 10,
    category: 'report',
    subject: 'Ce qu’il faut retenir — Les bases du SEO technique',
    eventTitle: 'Les bases du SEO technique',
    templateName: 'Compte rendu & points clés',
    templateVersion: 'v4',
    sentAtLabel: '17 sept., 10 h 00',
    status: 'sent',
    recipientCount: 166,
    deliveredCount: 165,
    failureNote: null,
    content: {
      subject: 'Ce qu’il faut retenir — Les bases du SEO technique',
      preheader: 'Les points clés de la séance, et le support à télécharger.',
      greeting: 'Merci Ndèye,',
      paragraphs: [
        'Vous étiez 96 à suivre « Les bases du SEO technique ». Merci pour vos questions, elles ont nourri la deuxième moitié de la séance.',
        "Voici ce qu’il faut en retenir : l'indexation passe avant tout le reste ; LCP, INP et CLS mesurent trois choses différentes et se corrigent différemment ; et la page la plus profonde de votre site en dit long sur votre maillage interne.",
        'Le support de présentation est disponible au téléchargement, annotations comprises.',
      ],
      details: [
        { label: 'Participants', value: '96' },
        { label: 'Support', value: 'PDF, 24 diapositives' },
      ],
      action: {
        label: 'Télécharger le support',
        url: 'datumacademy.com/fr/webinar/bases-du-seo-technique/support.pdf',
      },
      closing: 'Au plaisir de vous retrouver à une prochaine séance.',
      signature: SIGNATURE,
    },
  },
  {
    id: 11,
    category: 'report',
    subject: 'Ce qu’il faut retenir — Éthique des modèles génératifs',
    eventTitle: 'Éthique des modèles génératifs',
    templateName: 'Compte rendu & points clés',
    templateVersion: 'v4',
    sentAtLabel: '2 oct., 09 h 30',
    status: 'failed',
    recipientCount: 104,
    deliveredCount: 0,
    failureNote:
      "Envoi interrompu : le lien du support pointait vers un fichier absent. Aucun message n'est parti — corrigez le lien puis relancez.",
    content: {
      subject: 'Ce qu’il faut retenir — Éthique des modèles génératifs',
      preheader: 'Les points clés de la séance, et le support à télécharger.',
      greeting: 'Merci Rivo,',
      paragraphs: [
        'Vous étiez 61 à suivre « Éthique des modèles génératifs ».',
        'Voici ce qu’il faut en retenir : un biais d’entraînement ne se corrige pas par un message système ; l’attribution reste un problème ouvert ; et ce que l’on promet à un client doit tenir sans supervision humaine.',
      ],
      details: [{ label: 'Participants', value: '61' }],
      action: {
        label: 'Télécharger le support',
        url: 'datumacademy.com/fr/webinar/ethique-modeles-generatifs/support.pdf',
      },
      closing: 'Au plaisir de vous retrouver à une prochaine séance.',
      signature: SIGNATURE,
    },
  },

  /* ---------- visionnage ---------- */
  {
    id: 12,
    category: 'replay',
    subject: 'La rediffusion est en ligne — Les bases du SEO technique',
    eventTitle: 'Les bases du SEO technique',
    templateName: 'Rediffusion disponible',
    templateVersion: 'v2',
    sentAtLabel: '17 sept., 16 h 00',
    status: 'sent',
    recipientCount: 166,
    deliveredCount: 165,
    failureNote: null,
    content: {
      subject: 'La rediffusion est en ligne — Les bases du SEO technique',
      preheader: 'À regarder quand vous voulez, sans inscription.',
      greeting: 'Bonjour Ndèye,',
      paragraphs: [
        'La rediffusion de « Les bases du SEO technique » est disponible. Elle dure 1 h 12 et reprend la séance en entier, questions comprises.',
        'Aucune inscription n’est demandée pour la regarder : le lien suffit, et il reste valable sans limite de durée.',
      ],
      details: [
        { label: 'Durée', value: '1 h 12' },
        { label: 'Accès', value: 'libre, sans compte' },
      ],
      action: {
        label: 'Regarder la rediffusion',
        url: 'datumacademy.com/fr/replay/bases-du-seo-technique',
      },
      closing: 'Bon visionnage.',
      signature: SIGNATURE,
    },
  },
  {
    id: 13,
    category: 'replay',
    subject: 'La rediffusion est en ligne — Reconversion vers la data',
    eventTitle: 'Reconversion vers la data : par où commencer ?',
    templateName: 'Rediffusion disponible',
    templateVersion: 'v1',
    sentAtLabel: '19 juil., 10 h 00',
    status: 'sent',
    recipientCount: 196,
    deliveredCount: 193,
    failureNote: null,
    content: {
      subject: 'La rediffusion est en ligne — Reconversion vers la data',
      preheader: 'À regarder quand vous voulez.',
      greeting: 'Bonjour Rivo,',
      paragraphs: [
        'La rediffusion de « Reconversion vers la data : par où commencer ? » est disponible. Elle dure 1 h 12 et reprend la séance en entier.',
      ],
      details: [{ label: 'Durée', value: '1 h 12' }],
      action: {
        label: 'Regarder la rediffusion',
        url: 'datumacademy.com/fr/replay/reconversion-data',
      },
      closing: 'Bon visionnage.',
      signature: SIGNATURE,
    },
  },
  {
    id: 14,
    category: 'replay',
    subject: 'La rediffusion est en ligne — Éthique des modèles génératifs',
    eventTitle: 'Éthique des modèles génératifs',
    templateName: 'Rediffusion disponible',
    templateVersion: 'v2',
    sentAtLabel: '3 oct., 09 h 00',
    status: 'scheduled',
    recipientCount: 104,
    deliveredCount: 0,
    failureNote: null,
    content: {
      subject: 'La rediffusion est en ligne — Éthique des modèles génératifs',
      preheader: 'À regarder quand vous voulez, sans inscription.',
      greeting: 'Bonjour Rivo,',
      paragraphs: [
        'La rediffusion de « Éthique des modèles génératifs » est disponible. Elle dure 58 min et reprend la séance en entier, questions comprises.',
        'Aucune inscription n’est demandée pour la regarder.',
      ],
      details: [
        { label: 'Durée', value: '58 min' },
        { label: 'Accès', value: 'libre, sans compte' },
      ],
      action: {
        label: 'Regarder la rediffusion',
        url: 'datumacademy.com/fr/replay/ethique-modeles-generatifs',
      },
      closing: 'Bon visionnage.',
      signature: SIGNATURE,
    },
  },
];
