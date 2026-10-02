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
}

/** Filtres de la barre de pastilles, en haut de l'écran. */
export type WebinarFilter = 'all' | 'scheduled' | 'draft' | 'past';

export const WEBINAR_FILTER_LABELS: Readonly<Record<WebinarFilter, string>> = {
  all: 'Tous',
  scheduled: 'À venir',
  draft: 'Brouillon',
  past: 'Passés',
};
