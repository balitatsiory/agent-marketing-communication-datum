import { SocialNetworkCode } from './social-network';

/** Où en est le webinaire dans son cycle de vie. */
export type WebinarStatus = 'draft' | 'scheduled' | 'past';

/** Pastille affichée sur la fiche d'un webinaire. */
export interface WebinarFlag {
  readonly label: string;
  /** Classe de statut partagée, voir `styles/_components.scss`. */
  readonly modifier: 'status-published' | 'status-scheduled' | 'status-draft' | 'status-failed';
}

/** Bloc de date, à gauche de la fiche. */
export interface WebinarDate {
  /** Mois abrégé en capitales, p. ex. « SEPT. ». */
  readonly month: string;
  readonly day: string;
  readonly weekday: string;
}

/** Un visuel décliné pour un format de publication donné. */
export interface WebinarVisual {
  readonly source: string;
  /** Valeur CSS d'`aspect-ratio`. */
  readonly ratio: string;
  /** Format tel qu'on le nomme dans l'outil, p. ex. « Story 9:16 ». */
  readonly label: string;
  readonly dimensions: string;
  /** Réseaux auxquels ce format est destiné. */
  readonly networks: readonly SocialNetworkCode[];
  readonly alt: string;
}

/** Une personne inscrite, affichée dans la liste des derniers inscrits. */
export interface Registrant {
  readonly name: string;
  readonly initials: string;
  /** Origine de l'inscription, p. ex. « LinkedIn » ou « Formulaire ». */
  readonly source: string;
  readonly when: string;
}

/** Un intervenant du webinaire. */
export interface Speaker {
  readonly name: string;
  readonly initials: string;
  readonly role: string;
}

/** Un rappel programmé avant l'événement. */
export interface Reminder {
  readonly label: string;
  readonly when: string;
}

/** Tout ce qui n'existe qu'une fois le webinaire passé. */
export interface WebinarReplay {
  /** Miniature façon capture de l'enregistrement. */
  readonly thumbnail: string;
  readonly thumbnailAlt: string;
  readonly durationLabel: string;
  readonly viewCount: number;
  readonly url: string;
  /** Compte rendu rédigé, prêt à publier. */
  readonly summary: readonly string[];
  /** Points saillants, repris en liste dans la publication. */
  readonly highlights: readonly string[];
  readonly hashtags: readonly string[];
}

/** Un webinaire, à venir, en brouillon ou passé. */
export interface Webinar {
  readonly id: number;
  readonly title: string;
  readonly status: WebinarStatus;
  readonly date: WebinarDate | null;
  /** Ligne complète sous le titre dans la pop-up. */
  readonly schedule: string;
  /** Ligne grise sous le titre dans la liste. */
  readonly subtitle: string;
  readonly flags: readonly WebinarFlag[];
  readonly description: string;
  readonly topics: readonly string[];
  readonly startTimeLabel: string;
  readonly durationLabel: string;
  readonly registrationCount: number;
  /** Présents le jour J — seulement pour un webinaire passé. */
  readonly attendeeCount: number | null;
  readonly questionCount: number | null;
  readonly registrationUrl: string;
  readonly speakers: readonly Speaker[];
  readonly recentRegistrants: readonly Registrant[];
  readonly reminders: readonly Reminder[];
  /** Inscriptions quotidiennes sur 30 jours, pour le graphique. */
  readonly registrationSeries: readonly number[];
  /** Déclinaisons du visuel de promotion. */
  readonly promoVisuals: readonly WebinarVisual[];
  readonly replay: WebinarReplay | null;

  /* ---- champs ajoutés par la création d'un webinaire (décisions du 11/11/2026) ----
     Facultatifs : les webinaires de démonstration ne les portent pas. */

  /** Début en UTC (ISO 8601). Vide tant que le brouillon n'a pas de date. */
  readonly startsAtUtc?: string | null;
  /** Durée en minutes. Vide quand elle est inconnue (colonne NULL). */
  readonly durationMinutes?: number | null;
  /** Catégories thématiques (`meeting_theme_categories`). */
  readonly categories?: readonly string[];
  /** Lien de visioconférence : créé sur Zoom ou fourni à la main. */
  readonly meetingLink?: { readonly mode: MeetingLinkMode; readonly url: string | null };
  /** Publications associées (`meeting_publications`). */
  readonly linkedPublications?: readonly WebinarPublicationLink[];
}

/** Filtres de la barre de pastilles, en haut de l'écran. */
export type WebinarFilter = 'all' | 'scheduled' | 'draft' | 'past';

export const WEBINAR_FILTER_LABELS: Readonly<Record<WebinarFilter, string>> = {
  all: 'Tous',
  scheduled: 'À venir',
  draft: 'Brouillon',
  past: 'Passés',
};

/* ---------- création d'un webinaire (décisions du 11/11/2026) ---------- */

/** Rôle d'une publication par rapport à un événement — `meeting_publication_types`. */
export type MeetingPublicationType = 'promotion' | 'summary' | 'replay' | 'other';

export const MEETING_PUBLICATION_TYPE_LABELS: Readonly<Record<MeetingPublicationType, string>> = {
  promotion: 'Promotion du webinaire',
  summary: 'Compte rendu',
  replay: 'Rediffusion',
  other: 'Autre',
};

/**
 * Types de publication proposés selon le statut de l'événement lié.
 *
 * Avant la séance : promotion ou autre ; compte rendu et rediffusion
 * n'existent qu'après. « Autre » reste possible dans les deux cas.
 */
export function publicationTypesFor(status: WebinarStatus): readonly MeetingPublicationType[] {
  return status === 'past' ? ['summary', 'replay', 'other'] : ['promotion', 'other'];
}

/** Une ligne de `meeting_publications` : un couple (événement, publication) et son type. */
export interface WebinarPublicationLink {
  readonly publicationId: number;
  readonly type: MeetingPublicationType;
}

/** Comment le lien de visioconférence est obtenu. */
export type MeetingLinkMode = 'zoom_auto' | 'manual';

/** Valeurs de départ de `meeting_theme_categories` — la catégorie « All » est exclue. */
export const WEBINAR_CATEGORIES: readonly string[] = ['AI and BIG DATA', 'Programs Presentation'];

/** Durées proposées en un clic ; la saisie libre reste possible. */
export const DURATION_PRESETS: readonly number[] = [30, 45, 60, 90];

/**
 * Délais de rappel — paramètre global (`newsletter_reminder_schedules`).
 *
 * Exprimés en minutes avant le début : 1440 = exactement 24 h, pas « la
 * veille à telle heure ». Ils ne se saisissent pas webinaire par webinaire.
 */
export const REMINDER_RULES: readonly { readonly minutesBefore: number; readonly label: string }[] = [
  { minutesBefore: 1440, label: '24 h avant' },
  { minutesBefore: 60, label: '1 h avant' },
];
