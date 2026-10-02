import { Conversation } from '../models/conversation';

/** Boîte de réception de Meta, vers laquelle renvoyer quand la fenêtre de 24 h est fermée. */
const META_INBOX_URL = 'https://business.facebook.com/latest/inbox';

/**
 * File unifiée — maquette 10a, données statiques.
 *
 * Douze conversations portant toutes sur les webinaires et les formations
 * de Datum Academy, et accrochées aux publications de
 * `publications.data.ts` : le webinaire SEO du 15 septembre, celui sur le
 * RAG du 8 octobre, la formation Cloud AWS, le module Kubernetes, les
 * portes ouvertes du 10 octobre et la certification Oracle.
 *
 * Les ancienneté sont écrites en clair plutôt que calculées : sur un jeu
 * figé, une date relative à l'horloge dériverait au fil des jours et
 * finirait par mentir.
 *
 * À remplacer par `GET /api/v1/messages`.
 */
export const CONVERSATIONS: readonly Conversation[] = [
  {
    id: 1,
    authorName: 'Mamadou Diallo',
    initials: 'MD',
    network: 'linkedin',
    channel: 'directMessage',
    age: '22 min',
    origin: 'LinkedIn · message privé · Antananarivo',
    flag: { label: 'Réponse à valider', tone: 'ai' },
    isReplyWindowClosed: false,
    isRead: false,
    messages: [
      {
        text: "Bonjour, j'ai vu passer votre webinaire sur le SEO technique. Y a-t-il un replay ? Et la formation Cloud AWS, quel rythme hebdomadaire pour quelqu'un qui travaille à temps plein ?",
        at: "Aujourd'hui 08 h 51",
      },
    ],
    draft: {
      paragraphs: [
        'Bonjour Mamadou, merci de votre message.',
        "Le replay du webinaire « Les bases du SEO technique » est disponible : je vous envoie le lien par message. Il reste accessible sans limite de durée une fois que vous avez créé votre compte.",
        'Pour la formation Cloud AWS, comptez 12 à 15 h par semaine, avec des cours en direct le soir (19 h – 21 h) et le samedi matin. Tout est enregistré, donc suivable en différé.',
        'Souhaitez-vous que je vous transmette le programme détaillé de la session du 21 septembre ?',
      ],
      quickActions: [
        'Variante plus courte',
        'Ajouter le lien du replay',
        "Transférer à l'admission",
      ],
    },
  },
  {
    id: 2,
    authorName: 'fatou.sarr_',
    initials: 'FS',
    network: 'instagram',
    channel: 'directMessage',
    age: '1 j',
    origin: 'Instagram · message privé',
    flag: { label: 'Hors délai', tone: 'late' },
    isReplyWindowClosed: true,
    isRead: false,
    platformInboxUrl: META_INBOX_URL,
    messages: [
      {
        text: "Le module Kubernetes en production, c'est combien d'heures par semaine ?",
        at: 'Hier 07 h 40',
      },
    ],
    draft: null,
  },
  {
    id: 3,
    authorName: 'Orange Madagascar — RH',
    initials: 'OM',
    network: 'facebook',
    channel: 'directMessage',
    age: '3 h',
    origin: 'Facebook · message privé · compte partenaire',
    flag: { label: 'Priorité partenaire', tone: 'priority' },
    isReplyWindowClosed: false,
    isRead: false,
    messages: [
      {
        text: "Bonjour, nous souhaiterions inscrire six collaborateurs au webinaire du 8 octobre sur le RAG. Existe-t-il un tarif de groupe, et une version intra-entreprise de la formation ?",
        at: "Aujourd'hui 06 h 10",
      },
    ],
    draft: {
      paragraphs: [
        'Bonjour, merci de votre intérêt.',
        "Le webinaire du 8 octobre est gratuit, quel que soit le nombre d'inscrits : il suffit d'inscrire chaque participant pour qu'il reçoive son lien.",
        "Nous proposons bien une version intra-entreprise de la formation, adaptée à vos propres jeux de données, à partir de six participants. Je transmets votre demande à notre responsable partenariats, qui vous recontactera sous 48 h.",
      ],
      quickActions: [
        'Ajouter la grille intra-entreprise',
        'Transférer aux partenariats',
        'Proposer un créneau',
      ],
    },
  },
  {
    id: 4,
    authorName: '@aboubakr.tech',
    initials: 'AB',
    network: 'tiktok',
    channel: 'comment',
    age: '5 h',
    origin: 'TikTok · commentaire sous « Trois minutes pour comprendre le RAG »',
    flag: { label: 'Réponse limitée · audit', tone: 'neutral' },
    isReplyWindowClosed: false,
    isRead: true,
    messages: [
      {
        text: "La formation Cloud AWS est ouverte aux profils non informaticiens ?",
        at: "Aujourd'hui 04 h 02",
      },
    ],
    draft: {
      paragraphs: [
        "Oui — un tiers de la dernière promotion venait d'une reconversion. Le module d'entrée reprend les bases réseau et système, aucune expérience préalable n'est demandée.",
        'Détails et test de positionnement en bio.',
      ],
      quickActions: ['Variante plus courte', 'Ajouter le lien du test'],
    },
  },
  {
    id: 5,
    authorName: 'Ndèye Kane',
    initials: 'NK',
    network: 'linkedin',
    channel: 'comment',
    age: '6 h',
    origin: 'LinkedIn · commentaire sous « Webinaire — les bases du SEO technique »',
    flag: { label: 'Réponse type disponible', tone: 'neutral' },
    isReplyWindowClosed: false,
    isRead: true,
    messages: [
      {
        text: 'Le replay du webinaire de juillet est-il disponible quelque part ?',
        at: "Aujourd'hui 03 h 15",
      },
    ],
    draft: {
      paragraphs: [
        'Bonjour Ndèye, oui : tous nos replays sont réunis dans la médiathèque, accessible après création d’un compte gratuit.',
        'Le lien est en commentaire épinglé sous la publication.',
      ],
      quickActions: ['Ajouter le lien médiathèque', 'Épingler ce commentaire'],
    },
  },
  {
    id: 6,
    authorName: 'Hasina Rabe',
    initials: 'HR',
    network: 'instagram',
    channel: 'directMessage',
    age: '7 h',
    origin: 'Instagram · message privé',
    flag: { label: 'Réponse à valider', tone: 'ai' },
    isReplyWindowClosed: false,
    isRead: false,
    messages: [
      {
        text: "Bonjour ! Est-ce que je peux suivre le module Kubernetes sans avoir fait le module Docker avant ?",
        at: "Aujourd'hui 02 h 30",
      },
    ],
    draft: {
      paragraphs: [
        'Bonjour Hasina,',
        "Le module Kubernetes suppose de savoir construire et lancer une image : sans le module Docker, la première séance risque d'être rude.",
        "Deux solutions : suivre le module Docker en autonomie avant le 15 octobre (environ 8 h), ou décaler votre inscription à la session de janvier. Je peux vous réserver une place dans l'une ou l'autre.",
      ],
      quickActions: ['Proposer la session de janvier', 'Envoyer le prérequis Docker'],
    },
  },
  {
    id: 7,
    authorName: '@datum.alumni',
    initials: 'DA',
    network: 'instagram',
    channel: 'mention',
    age: '9 h',
    origin: 'Instagram · mention en story',
    flag: { label: 'Mention', tone: 'neutral' },
    isReplyWindowClosed: false,
    isRead: true,
    messages: [
      {
        text: "Vous a mentionné dans une story : « Deuxième webinaire Datum de la semaine, et toujours aussi concret. Merci @datum.academy 🙏 »",
        at: "Aujourd'hui 00 h 48",
      },
    ],
    draft: null,
  },
  {
    id: 8,
    authorName: 'Tiana Randria',
    initials: 'TR',
    network: 'facebook',
    channel: 'comment',
    age: '11 h',
    origin: 'Facebook · commentaire sous « Portes ouvertes — samedi 10 octobre »',
    flag: { label: 'Réponse à valider', tone: 'ai' },
    isReplyWindowClosed: false,
    isRead: false,
    messages: [
      {
        text: "Faut-il s'inscrire pour les portes ouvertes du 10 octobre, ou on peut venir directement ?",
        at: 'Hier 22 h 05',
      },
    ],
    draft: {
      paragraphs: [
        'Bonjour Tiana, aucune inscription nécessaire : venez quand vous voulez entre 9 h et 17 h.',
        "Si vous souhaitez passer le test de positionnement sur place, mieux vaut arriver avant 15 h — c'est la dernière session de la journée.",
      ],
      quickActions: ['Variante plus courte', 'Ajouter le plan d’accès'],
    },
  },
  {
    id: 9,
    authorName: '@koto.dev',
    initials: 'KD',
    network: 'tiktok',
    channel: 'comment',
    age: '14 h',
    origin: 'TikTok · commentaire sous « Teaser — salon du numérique »',
    flag: { label: 'Réponse limitée · audit', tone: 'neutral' },
    isReplyWindowClosed: false,
    isRead: true,
    messages: [
      {
        text: 'Combien coûte la certification Solutions Architect ?',
        at: 'Hier 19 h 12',
      },
    ],
    draft: null,
  },
  {
    id: 10,
    authorName: 'Rivo Andriana',
    initials: 'RA',
    network: 'linkedin',
    channel: 'directMessage',
    age: '1 j',
    origin: 'LinkedIn · message privé',
    flag: { label: 'Réponse type disponible', tone: 'neutral' },
    isReplyWindowClosed: false,
    isRead: true,
    messages: [
      {
        text: "Peut-on obtenir une attestation de participation après un webinaire ? Mon employeur la demande pour le plan de formation.",
        at: 'Hier 14 h 36',
      },
    ],
    draft: {
      paragraphs: [
        'Bonjour Rivo,',
        "Oui : une attestation nominative est envoyée automatiquement sous 72 h à toute personne ayant suivi au moins 45 minutes du direct. Elle mentionne la durée et le programme, ce qui suffit en général pour un plan de formation.",
        "Si vous avez suivi le replay plutôt que le direct, dites-le moi : l'attestation se délivre alors à la demande.",
      ],
      quickActions: ['Renvoyer une attestation', 'Transférer à l’administration'],
    },
  },
  {
    id: 11,
    authorName: 'Soa Ranaivo',
    initials: 'SR',
    network: 'instagram',
    channel: 'comment',
    age: '1 j',
    origin: 'Instagram · commentaire sous « Trois minutes pour comprendre le RAG »',
    flag: { label: 'Réponse à valider', tone: 'ai' },
    isReplyWindowClosed: false,
    isRead: false,
    messages: [
      {
        text: 'Le webinaire du 8 octobre sur le RAG est à quelle heure ? Et il dure combien de temps ?',
        at: 'Hier 11 h 20',
      },
    ],
    draft: {
      paragraphs: [
        'Bonjour Soa — rendez-vous le 8 octobre à 20 h, pour 1 h 30 : une heure de démonstration et trente minutes de questions.',
        'Lien d’inscription en bio, et replay envoyé le lendemain à tous les inscrits.',
      ],
      quickActions: ['Variante plus courte', 'Ajouter le lien d’inscription'],
    },
  },
  {
    id: 12,
    authorName: 'Faniry Rakoto',
    initials: 'FR',
    network: 'facebook',
    channel: 'directMessage',
    age: '2 j',
    origin: 'Facebook · message privé',
    flag: { label: 'Hors délai', tone: 'late' },
    isReplyWindowClosed: true,
    isRead: false,
    platformInboxUrl: META_INBOX_URL,
    messages: [
      {
        text: "J'ai raté la session d'octobre de la formation Cloud AWS. Y en a-t-il une en novembre ?",
        at: 'Mardi 16 h 02',
      },
    ],
    draft: null,
  },
];
