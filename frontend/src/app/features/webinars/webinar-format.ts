/** Mise en forme partagée par les écrans Webinaires. */
import { WebinarDto, WebinarStatusCode } from '../../core/api/webinars.api';

const MOIS_COURTS = [
  'JANV.',
  'FÉVR.',
  'MARS',
  'AVR.',
  'MAI',
  'JUIN',
  'JUIL.',
  'AOÛT',
  'SEPT.',
  'OCT.',
  'NOV.',
  'DÉC.',
];

/** Bloc de date de la maquette : mois, jour, jour de semaine (ou année). */
export interface DateBlock {
  readonly month: string;
  readonly day: string;
  readonly sub: string;
}

export function dateBlock(webinaire: WebinarDto): DateBlock | null {
  if (!webinaire.starts_at) {
    if (!webinaire.published_on) return null;
    // Sans date de séance, la fiche est classée à sa publication : on le dit.
    return {
      month: MOIS_COURTS[Number(webinaire.published_on.slice(5, 7)) - 1],
      day: '—',
      sub: `publié ${webinaire.published_on.slice(0, 4)}`,
    };
  }
  const date = new Date(webinaire.starts_at);
  // Sans heure connue, le jour se lit en UTC : un fuseau ne doit pas le décaler.
  const utc = !webinaire.is_time_known;
  const mois = utc ? date.getUTCMonth() : date.getMonth();
  const jour = utc ? date.getUTCDate() : date.getDate();
  const annee = utc ? date.getUTCFullYear() : date.getFullYear();
  return {
    month: MOIS_COURTS[mois],
    day: String(jour).padStart(2, '0'),
    sub:
      annee === new Date().getFullYear()
        ? date.toLocaleDateString('fr-FR', { weekday: 'long', timeZone: utc ? 'UTC' : undefined })
        : String(annee),
  };
}

/** « jeudi 8 octobre 2026 · 20:00 » dans le fuseau du navigateur. */
export function longSchedule(webinaire: {
  readonly starts_at: string | null;
  readonly is_time_known: boolean;
  readonly published_on?: string | null;
}): string {
  if (!webinaire.starts_at) {
    return webinaire.published_on
      ? `Date inconnue · publié vers ${monthLabel(webinaire.published_on.slice(0, 7))}`
      : 'Date à définir';
  }
  const date = new Date(webinaire.starts_at);
  const jour = date.toLocaleDateString('fr-FR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone: webinaire.is_time_known ? undefined : 'UTC',
  });
  const texte = jour.charAt(0).toUpperCase() + jour.slice(1);
  if (!webinaire.is_time_known) return texte;
  const heure = date.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
  return `${texte} · ${heure}`;
}

export function timeLabel(webinaire: WebinarDto): string {
  if (!webinaire.starts_at || !webinaire.is_time_known) return '—';
  return new Date(webinaire.starts_at).toLocaleTimeString('fr-FR', {
    hour: '2-digit',
    minute: '2-digit',
  });
}

/** 90 → « 1 h 30 », 60 → « 1 h », 45 → « 45 min ». */
export function durationLabel(minutes: number | null): string {
  if (!minutes) return '—';
  if (minutes < 60) return `${minutes} min`;
  const heures = Math.floor(minutes / 60);
  const reste = minutes % 60;
  return reste === 0 ? `${heures} h` : `${heures} h ${String(reste).padStart(2, '0')}`;
}

/** « 2024-03 » → « mars 2024 ». */
export function monthLabel(mois: string): string {
  return new Date(`${mois}-15T12:00:00Z`).toLocaleDateString('fr-FR', {
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  });
}

export function statusModifier(code: WebinarStatusCode): string {
  switch (code) {
    case 'scheduled':
      return 'status-scheduled';
    case 'past':
      return 'status-published';
    case 'cancelled':
      return 'status-failed';
    default:
      return 'status-draft';
  }
}

/** Adresse publique d'un formulaire d'inscription IAGORA. */
export function publicFormUrl(slug: string): string {
  return `${window.location.origin}/inscription/${slug}`;
}

/** Libellés des anomalies relevées par l'export du site. */
export const ANOMALY_LABELS: Readonly<Record<string, string>> = {
  flyer_sur_ancienne_arborescence: 'Flyer sur l’ancienne arborescence',
  aucune_date_exploitable: 'Aucune date exploitable',
  page_inscription_rapprochee_a_valider: 'Page d’inscription à valider',
  date_a_valider: 'Date à valider',
  contenu_fr_vide: 'Contenu français vide',
  aucune_categorie: 'Aucune catégorie',
  slug_non_normalise: 'Slug non normalisé',
  fiche_agregeant_plusieurs_evenements: 'Fiche regroupant plusieurs événements',
  champ_en_contient_du_francais: 'Texte anglais contenant du français',
  liens_de_telechargement_asymetriques_fr_en: 'Liens différents entre français et anglais',
  champ_en_contient_les_deux_langues: 'Texte anglais bilingue',
  titres_fr_en_incoherents: 'Titres français et anglais incohérents',
};
