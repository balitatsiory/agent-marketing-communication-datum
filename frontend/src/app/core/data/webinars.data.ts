import { Webinar } from '../models/webinar';

/**
 * Webinaires — maquettes 12a et 12b, données statiques.
 *
 * Les événements reprennent ceux déjà cités ailleurs dans l'application :
 * le webinaire SEO du 15 septembre (dont les messages réclament le replay),
 * celui sur le RAG du 8 octobre annoncé dans les publications, et la
 * conférence sur l'éthique des modèles génératifs du 30 septembre.
 *
 * Seul le webinaire SEO porte un jeu complet de visuels et un compte
 * rendu : c'est celui qui sert de démonstration à la pop-up de
 * publication d'après-événement.
 *
 * À remplacer par `GET /api/v1/webinars`.
 */
export const WEBINARS: readonly Webinar[] = [
  {
    id: 1,
    title: 'Le RAG en pratique : quand ça marche, quand ça casse',
    status: 'scheduled',
    date: { month: 'OCT.', day: '08', weekday: 'jeudi' },
    schedule: 'Jeudi 8 octobre 2026 · 20:00 – 21:30 (GMT+3) · LinkedIn Live + Zoom',
    subtitle: 'Animé par Yann Ravelo · LinkedIn Live + Zoom',
    flags: [
      { label: 'Inscriptions ouvertes', modifier: 'status-published' },
      { label: '3 rappels programmés', modifier: 'status-scheduled' },
    ],
    description:
      "Une heure de démonstration sur un corpus réel, puis trente minutes de questions. On montre surtout les cas où la recherche augmentée échoue, et pourquoi : découpage trop fin, requêtes ambiguës, documents contradictoires.",
    topics: ['Intelligence artificielle', 'RAG', 'Français'],
    startTimeLabel: '20:00',
    durationLabel: '1 h 30',
    registrationCount: 42,
    attendeeCount: null,
    questionCount: null,
    registrationUrl: 'datumacademy.com/fr/webinar/rag-en-pratique-inscription',
    speakers: [
      { name: 'Yann Ravelo', initials: 'YR', role: 'hôte' },
      { name: 'Noro Andria', initials: 'NA', role: 'modération Q&R' },
    ],
    recentRegistrants: [
      { name: 'Mamadou Diallo', initials: 'MD', source: 'LinkedIn', when: 'il y a 22 min' },
      { name: 'Ndèye Kane', initials: 'NK', source: 'Formulaire', when: 'il y a 3 h' },
      { name: 'Soa Ranaivo', initials: 'SR', source: 'Instagram', when: 'hier' },
    ],
    reminders: [
      { label: 'J-7 · e-mail + LinkedIn', when: '1er oct.' },
      { label: 'J-1 · e-mail', when: '7 oct.' },
      { label: 'H-2 · Story Instagram', when: '8 oct.' },
    ],
    registrationSeries: [0, 1, 0, 2, 1, 0, 0, 3, 7, 5, 2, 1, 0, 1, 2, 1, 0, 0, 1, 4, 9, 6, 3, 2, 1, 0, 2, 3, 5, 4],
    promoVisuals: [],
    replay: null,
  },
  {
    id: 2,
    title: 'Kubernetes en production : disséquer un premier incident',
    status: 'scheduled',
    date: { month: 'OCT.', day: '15', weekday: 'jeudi' },
    schedule: 'Jeudi 15 octobre 2026 · 18:30 – 19:30 (GMT+3) · Zoom',
    subtitle: 'Animé par Hery Rakoto · Zoom',
    flags: [
      { label: 'Inscriptions ouvertes', modifier: 'status-published' },
      { label: 'Visuel de promo manquant', modifier: 'status-failed' },
    ],
    description:
      "Un cluster, une panne provoquée, et le cheminement complet du diagnostic : lecture des événements, logs, sondes de vivacité, et ce qu'il ne faut surtout pas redémarrer en premier.",
    topics: ['DevOps', 'Kubernetes', 'Français'],
    startTimeLabel: '18:30',
    durationLabel: '1 h',
    registrationCount: 18,
    attendeeCount: null,
    questionCount: null,
    registrationUrl: 'datumacademy.com/fr/webinar/kubernetes-premier-incident-inscription',
    speakers: [{ name: 'Hery Rakoto', initials: 'HR', role: 'hôte' }],
    recentRegistrants: [
      { name: 'Hasina Rabe', initials: 'HR', source: 'Instagram', when: 'il y a 7 h' },
      { name: 'Rivo Andriana', initials: 'RA', source: 'Formulaire', when: 'hier' },
    ],
    reminders: [
      { label: 'J-7 · e-mail', when: '8 oct.' },
      { label: 'J-1 · e-mail', when: '14 oct.' },
    ],
    registrationSeries: [0, 0, 1, 0, 0, 2, 1, 0, 1, 0, 0, 1, 2, 0, 1, 1, 0, 0, 2, 1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0],
    promoVisuals: [],
    replay: null,
  },
  {
    id: 3,
    title: "Alternance data : mode d'emploi pour les entreprises",
    status: 'draft',
    date: null,
    schedule: 'Date et animateur à définir',
    subtitle: 'Brouillon · date et animateur à définir',
    flags: [{ label: 'Brouillon', modifier: 'status-draft' }],
    description:
      "Format envisagé : une heure à destination des RH, sur le calendrier de l'alternance, les aides mobilisables et le suivi pédagogique.",
    topics: ['Alternance', 'Entreprises'],
    startTimeLabel: '—',
    durationLabel: '—',
    registrationCount: 0,
    attendeeCount: null,
    questionCount: null,
    registrationUrl: '—',
    speakers: [],
    recentRegistrants: [],
    reminders: [],
    registrationSeries: [],
    promoVisuals: [],
    replay: null,
  },

  /* ---------- passés ---------- */

  {
    id: 4,
    title: 'Les bases du SEO technique',
    status: 'past',
    date: { month: 'SEPT.', day: '15', weekday: 'mardi' },
    schedule: 'Mardi 15 septembre 2026 · 20:00 – 21:30 (GMT+3) · LinkedIn Live + Zoom',
    subtitle: 'Rediffusion disponible · 214 vues · 12 questions posées',
    flags: [{ label: 'Rediffusion prête', modifier: 'status-published' }],
    description:
      "Panorama de l'indexation, du maillage interne et des Core Web Vitals, sur le site d'une école prise comme cas d'école. Deux audits en direct, puis une session de questions.",
    topics: ['SEO', 'Performance web', 'Français'],
    startTimeLabel: '20:00',
    durationLabel: '1 h 12',
    registrationCount: 168,
    attendeeCount: 96,
    questionCount: 12,
    registrationUrl: 'datumacademy.com/fr/webinar/bases-du-seo-technique',
    speakers: [
      { name: 'Yann Ravelo', initials: 'YR', role: 'hôte' },
      { name: 'Sarah Lemoine', initials: 'SL', role: 'modération Q&R' },
    ],
    recentRegistrants: [
      { name: 'Ndèye Kane', initials: 'NK', source: 'LinkedIn', when: '15 sept.' },
      { name: 'Mamadou Diallo', initials: 'MD', source: 'Formulaire', when: '14 sept.' },
      { name: 'Tiana Randria', initials: 'TR', source: 'Facebook', when: '12 sept.' },
    ],
    reminders: [
      { label: 'J-7 · e-mail + LinkedIn', when: '8 sept.' },
      { label: 'J-1 · e-mail', when: '14 sept.' },
      { label: 'H-2 · Story Instagram', when: '15 sept.' },
    ],
    registrationSeries: [1, 2, 1, 3, 2, 1, 1, 4, 9, 7, 4, 2, 1, 2, 3, 2, 1, 1, 2, 6, 10, 8, 5, 3, 2, 1, 3, 5, 8, 6],
    promoVisuals: [
      {
        source: 'flyers/webinar-seo-16-9.svg',
        ratio: '16 / 9',
        label: 'Bannière 16:9',
        dimensions: '1920 × 1080',
        networks: ['linkedin', 'facebook'],
        alt: 'Bannière bleu pétrole annonçant le webinaire sur le SEO technique du 15 septembre',
      },
      {
        source: 'flyers/webinar-seo-4-5.svg',
        ratio: '4 / 5',
        label: 'Portrait 4:5',
        dimensions: '1080 × 1350',
        networks: ['instagram', 'facebook'],
        alt: 'Flyer portrait listant les trois sujets du webinaire SEO',
      },
      {
        source: 'flyers/webinar-seo-1-1.svg',
        ratio: '1 / 1',
        label: 'Carré 1:1',
        dimensions: '1080 × 1080',
        networks: ['instagram', 'linkedin'],
        alt: 'Flyer carré blanc annonçant le webinaire SEO',
      },
      {
        source: 'flyers/webinar-seo-9-16.svg',
        ratio: '9 / 16',
        label: 'Story 9:16',
        dimensions: '1080 × 1920',
        networks: ['instagram', 'tiktok'],
        alt: 'Story verticale annonçant le webinaire SEO',
      },
    ],
    replay: {
      thumbnail: 'flyers/webinar-seo-replay-16-9.svg',
      thumbnailAlt:
        "Miniature de la rediffusion : diapositive sur les Core Web Vitals, intervenant en médaillon",
      durationLabel: '1:12:04',
      viewCount: 214,
      url: 'datumacademy.com/fr/replay/bases-du-seo-technique',
      summary: [
        "Merci aux 96 personnes présentes mardi soir — et aux 12 qui ont posé des questions jusqu'à 21 h 40. 🙏",
        "On a passé l'heure à défaire une idée reçue : le SEO technique n'est pas une liste de cases à cocher, c'est un travail de diagnostic. Trois mesures, trois causes différentes, trois correctifs qui n'ont rien à voir entre eux.",
        'La rediffusion est en ligne, sans inscription, avec les deux audits faits en direct.',
      ],
      highlights: [
        "L'indexation avant tout le reste : une page non explorée ne se classe jamais",
        'Core Web Vitals — LCP, INP, CLS : ce que chaque mesure dit vraiment',
        'Maillage interne : la page la plus profonde de votre site est à combien de clics ?',
        'Les deux audits en direct, de la mesure au correctif',
      ],
      hashtags: ['#SEO', '#SEOtechnique', '#CoreWebVitals', '#Webinaire', '#DatumAcademy'],
    },
  },
  {
    id: 5,
    title: 'Éthique des modèles génératifs',
    status: 'past',
    date: { month: 'SEPT.', day: '30', weekday: 'mercredi' },
    schedule: 'Mercredi 30 septembre 2026 · 18:00 – 19:00 (GMT+3) · Zoom',
    subtitle: 'Rediffusion disponible · 88 vues',
    flags: [{ label: 'Compte rendu à rédiger', modifier: 'status-scheduled' }],
    description:
      "Avec Noro Andria, chercheuse en apprentissage automatique : biais d'entraînement, attribution, et ce que l'on peut raisonnablement promettre à un client.",
    topics: ['Intelligence artificielle', 'Éthique'],
    startTimeLabel: '18:00',
    durationLabel: '58 min',
    registrationCount: 104,
    attendeeCount: 61,
    questionCount: 7,
    registrationUrl: 'datumacademy.com/fr/webinar/ethique-modeles-generatifs',
    speakers: [{ name: 'Noro Andria', initials: 'NA', role: 'intervenante' }],
    recentRegistrants: [
      { name: 'Rivo Andriana', initials: 'RA', source: 'LinkedIn', when: '29 sept.' },
    ],
    reminders: [{ label: 'J-1 · e-mail', when: '29 sept.' }],
    registrationSeries: [0, 1, 2, 1, 0, 3, 5, 4, 2, 1, 0, 1, 3, 2, 1, 0, 2, 4, 6, 3, 2, 1, 1, 0, 2, 3, 1, 0, 1, 2],
    promoVisuals: [],
    replay: null,
  },
  {
    id: 6,
    title: 'Reconversion vers la data : par où commencer ?',
    status: 'past',
    date: { month: 'JUIL.', day: '17', weekday: 'jeudi' },
    schedule: 'Jeudi 17 juillet 2026 · 18:00 – 19:12 (GMT+3) · Zoom',
    subtitle: 'Rediffusion disponible · 142 vues · 19 questions posées',
    flags: [{ label: 'Publié', modifier: 'status-published' }],
    description:
      "Trois parcours de reconversion racontés par celles et ceux qui les ont faits, et le détail du test de positionnement.",
    topics: ['Reconversion', 'Data'],
    startTimeLabel: '18:00',
    durationLabel: '1 h 12',
    registrationCount: 196,
    attendeeCount: 112,
    questionCount: 19,
    registrationUrl: 'datumacademy.com/fr/webinar/reconversion-data',
    speakers: [{ name: 'Sarah Lemoine', initials: 'SL', role: 'hôte' }],
    recentRegistrants: [],
    reminders: [],
    registrationSeries: [2, 3, 1, 4, 6, 3, 2, 5, 8, 6, 3, 2, 4, 3, 2, 1, 3, 5, 7, 9, 6, 4, 3, 2, 4, 3, 2, 1, 2, 3],
    promoVisuals: [],
    replay: null,
  },
];
