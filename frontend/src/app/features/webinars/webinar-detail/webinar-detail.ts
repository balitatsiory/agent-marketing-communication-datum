import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  input,
  output,
  signal,
  untracked,
} from '@angular/core';
import { DatePipe } from '@angular/common';
import { RouterLink } from '@angular/router';

import { toApiError } from '../../../core/api/api-error';
import {
  RegistrationDto,
  WebinarDetailDto,
  WebinarReferenceDto,
  WebinarsApi,
} from '../../../core/api/webinars.api';
import { Session } from '../../../core/services/session';
import { Dialog } from '../../../shared/dialog/dialog';
import { Icon } from '../../../shared/icon/icon';
import {
  ANOMALY_LABELS,
  dateBlock,
  durationLabel,
  longSchedule,
  publicFormUrl,
  statusModifier,
} from '../webinar-format';

type Tab = 'detail' | 'registrations' | 'publications';

const INSCRITS_PAR_PAGE = 10;

/** Réglages de la réunion Zoom, dans les mots de l'équipe. */
const ZOOM_SETTINGS: Readonly<Record<string, string>> = {
  waiting_room: 'Salle d’attente',
  join_before_host: 'Entrée avant l’hôte',
  mute_upon_entry: 'Micros coupés à l’entrée',
  host_video: 'Caméra de l’hôte',
  participant_video: 'Caméra des participants',
  auto_recording: 'Enregistrement',
  approval_type: 'Inscription',
  meeting_authentication: 'Authentification exigée',
  registrants_email_notification: 'Courriel aux inscrits',
};
const APPROBATION: Readonly<Record<number, string>> = {
  0: 'approbation automatique',
  1: 'approbation manuelle',
  2: 'non demandée',
};
const TYPES_ZOOM: Readonly<Record<number, string>> = {
  1: 'instantanée',
  2: 'programmée',
  3: 'récurrente sans horaire fixe',
  8: 'récurrente à horaire fixe',
};
const ENREGISTREMENT: Readonly<Record<string, string>> = {
  none: 'aucun',
  local: 'sur l’ordinateur',
  cloud: 'dans le cloud Zoom',
};

function valeurReglage(nom: string, valeur: string | number | boolean): string {
  if (nom === 'approval_type') return APPROBATION[Number(valeur)] ?? String(valeur);
  if (nom === 'auto_recording') return ENREGISTREMENT[String(valeur)] ?? String(valeur);
  if (typeof valeur === 'boolean') return valeur ? 'oui' : 'non';
  return String(valeur);
}

/**
 * Fiche d'un webinaire — pop-up de la maquette 12b.
 *
 * Une réunion Zoom est relue à l'ouverture : la fiche gardée en base
 * s'affiche tout de suite, la réponse de Zoom la remplace quand elle arrive.
 */
@Component({
  selector: 'app-webinar-detail',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, RouterLink, Dialog, Icon],
  templateUrl: './webinar-detail.html',
  styleUrl: './webinar-detail.scss',
})
export class WebinarDetailDialog {
  readonly id = input.required<number>();
  readonly closed = output<void>();
  /** La fiche a changé : la liste doit se relire. */
  readonly changed = output<void>();

  private readonly api = inject(WebinarsApi);
  private readonly session = inject(Session);

  protected readonly dateBlock = dateBlock;
  protected readonly durationLabel = durationLabel;
  protected readonly longSchedule = longSchedule;
  protected readonly statusModifier = statusModifier;
  protected readonly publicFormUrl = publicFormUrl;

  protected readonly canManage = computed(() => this.session.has('manage_webinars'));
  protected readonly canCreateMeetings = computed(() =>
    this.session.has('create_zoom_meetings'),
  );

  protected readonly webinar = signal<WebinarDetailDto | null>(null);
  protected readonly reference = signal<WebinarReferenceDto | null>(null);
  protected readonly tab = signal<Tab>('detail');
  protected readonly language = signal<'fr' | 'en'>('fr');
  protected readonly error = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);
  protected readonly busy = signal(false);
  /** Fiche en cours de relecture sur Zoom : une autre peut l'être en même temps. */
  private readonly refreshingId = signal<number | null>(null);
  protected readonly refreshing = computed(() => this.refreshingId() === this.id());
  /** Compte les écritures terminées : une relecture partie avant est périmée. */
  private writes = 0;
  protected readonly zoomError = signal<string | null>(null);
  protected readonly copied = signal<string | null>(null);
  protected readonly confirming = signal<'archive' | 'schedule' | null>(null);

  /* ---------- inscrits ---------- */

  protected readonly registrations = signal<readonly RegistrationDto[]>([]);
  protected readonly registrationPage = signal(1);
  protected readonly registrationPages = signal(0);
  protected readonly registrationTotal = signal(0);
  protected readonly erasing = signal<number | null>(null);
  protected readonly newRegistration = signal({
    email: '',
    first_name: '',
    last_name: '',
    has_newsletter_consent: false,
  });

  /* ---------- publications ---------- */

  protected readonly newLink = signal({ type_code: '', platform_code: '', url: '', label: '' });

  protected readonly publicationTypes = computed(() => {
    const passe = this.webinar()?.status_code === 'past';
    return (this.reference()?.publication_types ?? []).filter(
      (type) => passe || (type.code !== 'summary' && type.code !== 'replay'),
    );
  });

  protected readonly description = computed(() => {
    const fiche = this.webinar();
    if (!fiche) return null;
    return this.language() === 'en'
      ? fiche.description_en
      : (fiche.description ?? null);
  });

  protected readonly hasEnglish = computed(() => !!this.webinar()?.description_en);

  protected readonly zoomSettings = computed(() => {
    const reglages = this.webinar()?.zoom_meeting?.settings ?? {};
    return Object.entries(reglages)
      .filter(([nom]) => nom in ZOOM_SETTINGS)
      .map(([nom, valeur]) => ({ label: ZOOM_SETTINGS[nom], value: valeurReglage(nom, valeur) }));
  });

  /** L'export préfixe ses motifs par « a_valider : » ; le libellé le dit déjà. */
  protected readonly dateHint = computed(() =>
    this.webinar()?.date_hint?.replace(/^a_valider\s*:\s*/, ''),
  );

  protected readonly zoomType = computed(() => {
    const type = this.webinar()?.zoom_meeting?.type;
    return type ? (TYPES_ZOOM[type] ?? String(type)) : null;
  });

  protected readonly anomalies = computed(() =>
    (this.webinar()?.anomalies ?? []).map((code) => ANOMALY_LABELS[code] ?? code),
  );

  protected readonly bars = computed(() => {
    const serie = this.webinar()?.registration_series ?? [];
    const maximum = Math.max(1, ...serie.map((point) => point.count));
    return serie.map((point) => ({ ...point, share: point.count / maximum }));
  });

  /** Le format de l'adresse d'inscription dépend du mode choisi. */
  protected readonly registrationLink = computed(() => {
    const fiche = this.webinar();
    if (!fiche) return null;
    return fiche.form_slug ? publicFormUrl(fiche.form_slug) : fiche.registration_url;
  });

  constructor() {
    effect(() => {
      const id = this.id();
      untracked(() => void this.ouvrir(id));
    });
    void this.api
      .reference()
      .then((reference) => this.reference.set(reference))
      .catch((erreur) => this.error.set(toApiError(erreur).message));
  }

  private async ouvrir(id: number): Promise<void> {
    this.webinar.set(null);
    this.tab.set('detail');
    this.language.set('fr');
    this.error.set(null);
    this.notice.set(null);
    this.zoomError.set(null);
    this.confirming.set(null);
    try {
      const fiche = await this.api.get(id);
      if (this.id() !== id) return;
      this.webinar.set(fiche);
      if (fiche.external_zoom_meeting_id && fiche.id_zoom_accounts && this.canManage()) {
        void this.refreshFromZoom();
      }
    } catch (erreur) {
      this.error.set(toApiError(erreur).message);
    }
  }

  private async relire(): Promise<void> {
    const id = this.id();
    const fiche = await this.api.get(id);
    if (this.id() === id) this.webinar.set(fiche);
  }

  /** Exécute une écriture : un seul geste à la fois, l'erreur affichée telle quelle. */
  private async agir(geste: () => Promise<void>): Promise<void> {
    if (this.busy()) return;
    const id = this.id();
    this.busy.set(true);
    this.error.set(null);
    this.notice.set(null);
    try {
      await geste();
    } catch (erreur) {
      if (this.id() === id) this.error.set(toApiError(erreur).message);
    } finally {
      this.writes++;
      this.busy.set(false);
    }
  }

  protected async refreshFromZoom(): Promise<void> {
    const id = this.id();
    if (this.refreshingId() === id) return;
    const writes = this.writes;
    this.refreshingId.set(id);
    this.zoomError.set(null);
    try {
      const fiche = await this.api.refreshFromZoom(id);
      if (this.id() === id && this.writes === writes) this.webinar.set(fiche);
      this.changed.emit();
    } catch (erreur) {
      if (this.id() === id) this.zoomError.set(toApiError(erreur).message);
    } finally {
      if (this.refreshingId() === id) this.refreshingId.set(null);
    }
  }

  protected setTab(tab: Tab): void {
    this.tab.set(tab);
    this.error.set(null);
    this.notice.set(null);
    if (tab === 'registrations') void this.loadRegistrations(1);
    if (tab === 'publications') {
      this.newLink.update((lien) => ({
        ...lien,
        type_code: this.publicationTypes()[0]?.code ?? '',
      }));
    }
  }

  protected async copy(texte: string): Promise<void> {
    try {
      await navigator.clipboard.writeText(texte);
      this.copied.set(texte);
      setTimeout(() => this.copied.set(null), 1500);
    } catch {
      this.error.set('Copie impossible : sélectionnez l’adresse à la main.');
    }
  }

  /* ---------- fiche ---------- */

  protected schedule(): Promise<void> {
    const id = this.id();
    return this.agir(async () => {
      this.confirming.set(null);
      const fiche = await this.api.schedule(id);
      // La liste se relit même si une autre fiche a été ouverte entre-temps.
      this.changed.emit();
      if (this.id() !== id) return;
      this.webinar.set(fiche);
      this.notice.set('Webinaire validé.');
    });
  }

  protected archive(): Promise<void> {
    const id = this.id();
    return this.agir(async () => {
      await this.api.archive(id);
      this.changed.emit();
      if (this.id() === id) this.closed.emit();
    });
  }

  protected confirmDate(): Promise<void> {
    const id = this.id();
    return this.agir(async () => {
      const fiche = await this.api.update(id, { is_date_confirmed: true });
      this.changed.emit();
      if (this.id() === id) this.webinar.set(fiche);
    });
  }

  protected linkPage(idPage: number): Promise<void> {
    return this.agir(async () => {
      await this.api.linkPage(idPage, this.id());
      await this.relire();
      this.changed.emit();
    });
  }

  /* ---------- inscrits ---------- */

  protected async loadRegistrations(page: number): Promise<void> {
    try {
      const reponse = await this.api.registrations(this.id(), page, INSCRITS_PAR_PAGE);
      this.registrations.set(reponse.items);
      this.registrationPage.set(reponse.page);
      this.registrationPages.set(reponse.pages);
      this.registrationTotal.set(reponse.total);
    } catch (erreur) {
      this.error.set(toApiError(erreur).message);
    }
  }

  protected typeRegistration(champ: 'email' | 'first_name' | 'last_name', valeur: string): void {
    this.newRegistration.update((saisie) => ({ ...saisie, [champ]: valeur }));
  }

  protected setNewConsent(accord: boolean): void {
    this.newRegistration.update((saisie) => ({ ...saisie, has_newsletter_consent: accord }));
  }

  protected addRegistration(): Promise<void> {
    return this.agir(async () => {
      const ajoute = await this.api.addRegistration(this.id(), this.newRegistration());
      this.newRegistration.set({
        email: '',
        first_name: '',
        last_name: '',
        has_newsletter_consent: false,
      });
      this.notice.set(
        ajoute.zoom_error
          ? `Inscription enregistrée, mais refusée par Zoom : ${ajoute.zoom_error}`
          : 'Inscription enregistrée.',
      );
      await this.apresInscription(1);
    });
  }

  protected syncRegistrants(): Promise<void> {
    return this.agir(async () => {
      const bilan = await this.api.syncRegistrants(this.id());
      this.notice.set(
        `${bilan.found} inscrit(s) lu(s) sur Zoom, ${bilan.created} ajouté(s).`,
      );
      await this.apresInscription(1);
    });
  }

  protected toggleConsent(inscription: RegistrationDto): Promise<void> {
    return this.agir(async () => {
      await this.api.setConsent(
        this.id(),
        inscription.id_webinar_registrations,
        !inscription.has_newsletter_consent,
      );
      await this.apresInscription(this.registrationPage());
    });
  }

  protected retryZoom(inscription: RegistrationDto): Promise<void> {
    return this.agir(async () => {
      await this.api.pushToZoom(this.id(), inscription.id_webinar_registrations);
      await this.apresInscription(this.registrationPage());
    });
  }

  protected erase(inscription: RegistrationDto): Promise<void> {
    return this.agir(async () => {
      await this.api.anonymize(this.id(), inscription.id_webinar_registrations);
      this.erasing.set(null);
      await this.apresInscription(this.registrationPage());
    });
  }

  private async apresInscription(page: number): Promise<void> {
    await Promise.all([this.loadRegistrations(page), this.relire()]);
    this.changed.emit();
  }

  /* ---------- publications ---------- */

  protected typeLink(champ: 'type_code' | 'platform_code' | 'url' | 'label', valeur: string): void {
    this.newLink.update((lien) => ({ ...lien, [champ]: valeur }));
  }

  protected addLink(): Promise<void> {
    return this.agir(async () => {
      const saisie = this.newLink();
      await this.api.addPublicationLink(this.id(), {
        type_code: saisie.type_code,
        url: saisie.url.trim(),
        platform_code: saisie.platform_code || null,
        label: saisie.label.trim() || null,
      });
      this.newLink.set({ ...saisie, url: '', label: '' });
      await this.relire();
    });
  }

  protected removeLink(idLink: number): Promise<void> {
    return this.agir(async () => {
      await this.api.removePublicationLink(this.id(), idLink);
      await this.relire();
    });
  }
}
