import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  input,
  signal,
} from '@angular/core';
import { Router, RouterLink } from '@angular/router';

import { toApiError } from '../../../core/api/api-error';
import {
  LinkMode,
  MeetingSettings,
  PublicationLinkCreate,
  RegistrationMode,
  RegistrationPageDto,
  WebinarDetailDto,
  WebinarInput,
  WebinarReferenceDto,
  WebinarsApi,
} from '../../../core/api/webinars.api';
import { ZoomAccountDto, ZoomAccountsApi } from '../../../core/api/zoom-accounts.api';
import { Session } from '../../../core/services/session';
import { Topbar } from '../../../layout/topbar/topbar';
import { Dialog } from '../../../shared/dialog/dialog';
import { Icon } from '../../../shared/icon/icon';
import { longSchedule } from '../webinar-format';

const DUREES = [30, 45, 60, 90] as const;
/** Fuseaux affichés par Zoom ; l'heure saisie, elle, est toujours en GMT. */
const FUSEAUX = [
  'UTC',
  'Africa/Dakar',
  'Africa/Casablanca',
  'Africa/Porto-Novo',
  'Europe/Paris',
  'Indian/Antananarivo',
] as const;
const MOT_DE_PASSE = /^[A-Za-z0-9@\-_*]{1,10}$/;

const REGLAGES_PAR_DEFAUT: MeetingSettings = {
  passcode: null,
  waiting_room: true,
  join_before_host: false,
  mute_upon_entry: true,
  host_video: true,
  participant_video: false,
  auto_recording: 'none',
  email_notification: true,
};

type BooleanSetting =
  | 'waiting_room'
  | 'join_before_host'
  | 'mute_upon_entry'
  | 'host_video'
  | 'participant_video'
  | 'email_notification';

/**
 * Nouveau webinaire, ou modification d'une fiche.
 *
 * - Un brouillon ne demande que le titre ; « Valider » exige catégorie, date,
 *   heure et lien (décisions du 11/11/2026).
 * - La date et l'heure se saisissent en GMT.
 * - Valider un webinaire « Zoom » crée la réunion sur le compte choisi. Une
 *   fois créée, titre, date, durée et lien se modifient sur zoom.us : IAGORA
 *   n'a pas le droit de les changer, et les grise.
 */
@Component({
  selector: 'app-webinar-editor',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, Topbar, Icon, Dialog],
  templateUrl: './webinar-editor.html',
  styleUrl: './webinar-editor.scss',
})
export class WebinarEditor implements OnInit {
  /** Identifiant de la fiche à modifier, lié à la route `webinaires/:id/modifier`. */
  readonly id = input<string>();

  private readonly api = inject(WebinarsApi);
  private readonly zoomApi = inject(ZoomAccountsApi);
  private readonly session = inject(Session);
  private readonly router = inject(Router);

  protected readonly durations = DUREES;
  protected readonly timezones = FUSEAUX;

  protected readonly canManage = computed(() => this.session.has('manage_webinars'));
  protected readonly canCreateMeetings = computed(() =>
    this.session.has('create_zoom_meetings'),
  );

  protected readonly reference = signal<WebinarReferenceDto | null>(null);
  protected readonly accounts = signal<readonly ZoomAccountDto[]>([]);
  protected readonly freePages = signal<readonly RegistrationPageDto[]>([]);
  protected readonly existing = signal<WebinarDetailDto | null>(null);
  protected readonly loading = signal(true);
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly isSummaryOpen = signal(false);

  /* ---------- saisie ---------- */

  protected readonly title = signal('');
  protected readonly description = signal('');
  protected readonly categories = signal<ReadonlySet<string>>(new Set());
  protected readonly date = signal('');
  protected readonly time = signal('');
  protected readonly duration = signal<number | null>(60);
  protected readonly timezone = signal<string>('UTC');
  protected readonly linkMode = signal<LinkMode>('zoom_auto');
  protected readonly accountId = signal<number | null>(null);
  protected readonly joinUrl = signal('');
  protected readonly settings = signal<MeetingSettings>(REGLAGES_PAR_DEFAUT);
  protected readonly registrationMode = signal<RegistrationMode>('none');
  protected readonly registrationUrl = signal('');
  protected readonly replayUrl = signal('');
  protected readonly links = signal<readonly PublicationLinkCreate[]>([]);
  protected readonly linkDraft = signal({ type_code: 'promotion', platform_code: '', url: '' });

  /** Date et heure telles que chargées : on ne renvoie qu'une date réellement changée. */
  private loadedDate = '';

  protected readonly isEditing = computed(() => this.existing() !== null);
  protected readonly isDraft = computed(
    () => !this.existing() || this.existing()!.status_code === 'draft',
  );
  protected readonly lockedByZoom = computed(
    () => !!this.existing()?.external_zoom_meeting_id,
  );

  protected readonly trail = computed<readonly string[]>(() => [
    'Événements',
    'Webinaires',
    this.isEditing() ? 'Modifier' : 'Nouveau webinaire',
  ]);

  protected readonly startsAt = computed(() => {
    if (!this.date() || !this.time()) return null;
    const instant = new Date(`${this.date()}T${this.time()}:00Z`);
    return Number.isNaN(instant.getTime()) ? null : instant;
  });

  protected readonly localLabel = computed(() => {
    const debut = this.startsAt();
    if (!debut) return null;
    const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    return `${longSchedule({ starts_at: debut.toISOString(), is_time_known: true })} (${zone})`;
  });

  protected readonly passcodeError = computed(() => {
    const saisi = this.settings().passcode;
    return !!saisi && !MOT_DE_PASSE.test(saisi);
  });

  /** Le code secret n'existe que pour une réunion Zoom : ailleurs il est masqué. */
  protected readonly blockingPasscode = computed(
    () => this.linkMode() === 'zoom_auto' && this.passcodeError(),
  );

  protected readonly canSave = computed(
    () => !!this.title().trim() && !this.blockingPasscode() && !this.busy(),
  );

  /** Une fiche déjà validée sans Zoom ne peut plus y passer : rien n'y créerait la réunion. */
  protected readonly zoomUnavailable = computed(
    () => !this.isDraft() && this.existing()?.link_mode === 'manual',
  );

  /** Ce qui manque pour valider, listé sous les boutons. */
  protected readonly missing = computed<readonly string[]>(() => {
    const manque: string[] = [];
    if (!this.title().trim()) manque.push('un titre');
    if (!this.categories().size) manque.push('au moins une catégorie');
    const debut = this.startsAt();
    if (!debut) manque.push('une date et une heure');
    else if (debut.getTime() <= Date.now()) manque.push('une date dans le futur');
    if (this.linkMode() === 'manual') {
      if (!/^https:\/\/\S+$/.test(this.joinUrl().trim())) {
        manque.push('un lien de visioconférence en https');
      }
    } else if (this.accountId() === null) {
      manque.push('un compte Zoom');
    }
    if (this.blockingPasscode()) manque.push('un code secret valide');
    if (this.registrationMode() === 'external' && !this.registrationUrl().trim()) {
      manque.push('l’adresse de la page d’inscription');
    }
    return manque;
  });

  protected readonly needsZoomRight = computed(
    () => this.linkMode() === 'zoom_auto' && !this.canCreateMeetings(),
  );

  protected readonly accountLabel = computed(
    () => this.accounts().find((c) => c.id_zoom_accounts === this.accountId())?.label ?? '—',
  );

  protected readonly registrationLabel = computed(
    () =>
      ({
        none: 'Aucune',
        zoom_page: 'Page d’inscription Zoom',
        iagora_form: 'Formulaire IAGORA (e-mail, prénom, nom)',
        external: 'Page existante',
      })[this.registrationMode()],
  );

  async ngOnInit(): Promise<void> {
    try {
      const [reference, accounts, pages] = await Promise.all([
        this.api.reference(),
        this.zoomApi.list(),
        this.api.registrationPages(),
      ]);
      this.reference.set(reference);
      this.accounts.set(accounts);
      this.freePages.set(pages.filter((page) => page.kind === 'external' && page.url));
      const brut = this.id();
      if (brut === undefined) {
        this.accountId.set(accounts[0]?.id_zoom_accounts ?? null);
      } else {
        this.remplir(await this.api.get(Number(brut)));
      }
    } catch (erreur) {
      this.error.set(toApiError(erreur).message);
    } finally {
      this.loading.set(false);
    }
  }

  private remplir(fiche: WebinarDetailDto): void {
    this.existing.set(fiche);
    this.title.set(fiche.title);
    this.description.set(fiche.description ?? '');
    this.categories.set(new Set(fiche.categories.map((c) => c.code)));
    const debut = fiche.starts_at ? new Date(fiche.starts_at).toISOString() : '';
    this.date.set(debut.slice(0, 10));
    this.time.set(debut && fiche.is_time_known ? debut.slice(11, 16) : '');
    this.loadedDate = `${this.date()}T${this.time()}`;
    this.duration.set(fiche.duration_minutes);
    this.timezone.set(fiche.timezone ?? 'UTC');
    this.linkMode.set(fiche.link_mode);
    this.accountId.set(fiche.id_zoom_accounts);
    this.joinUrl.set(fiche.join_url ?? '');
    this.settings.set(fiche.meeting_settings ?? REGLAGES_PAR_DEFAUT);
    this.registrationMode.set(fiche.registration_mode);
    this.registrationUrl.set(fiche.registration_url ?? '');
    this.replayUrl.set(fiche.replay_url ?? '');
  }

  /* ---------- saisie ---------- */

  protected toggleCategory(code: string): void {
    this.categories.update((choisies) => {
      const suite = new Set(choisies);
      if (!suite.delete(code)) suite.add(code);
      return suite;
    });
  }

  protected setDuration(valeur: string): void {
    const minutes = Number.parseInt(valeur, 10);
    this.duration.set(Number.isFinite(minutes) && minutes > 0 ? Math.min(minutes, 1440) : null);
  }

  protected setLinkMode(mode: LinkMode): void {
    this.linkMode.set(mode);
    if (mode === 'manual' && this.registrationMode() === 'zoom_page') {
      this.registrationMode.set('none');
    }
  }

  protected setSetting(nom: BooleanSetting, valeur: boolean): void {
    this.settings.update((reglages) => ({ ...reglages, [nom]: valeur }));
  }

  protected setPasscode(valeur: string): void {
    this.settings.update((reglages) => ({ ...reglages, passcode: valeur || null }));
  }

  protected setRecording(valeur: string): void {
    this.settings.update((reglages) => ({
      ...reglages,
      auto_recording: valeur as MeetingSettings['auto_recording'],
    }));
  }

  protected typeLink(champ: 'type_code' | 'platform_code' | 'url', valeur: string): void {
    this.linkDraft.update((lien) => ({ ...lien, [champ]: valeur }));
  }

  protected addLink(): void {
    const saisie = this.linkDraft();
    const url = saisie.url.trim();
    if (!/^https?:\/\/\S+$/.test(url) || this.links().some((lien) => lien.url === url)) return;
    this.links.update((liste) => [
      ...liste,
      { type_code: saisie.type_code, url, platform_code: saisie.platform_code || null, label: null },
    ]);
    this.linkDraft.set({ ...saisie, url: '' });
  }

  protected removeLink(url: string): void {
    this.links.update((liste) => liste.filter((lien) => lien.url !== url));
  }

  protected labelOf(liste: 'publication_types' | 'platforms', code: string | null): string {
    return this.reference()?.[liste].find((item) => item.code === code)?.label ?? code ?? '';
  }

  /* ---------- enregistrement ---------- */

  private saisie(): WebinarInput {
    const manuel = this.linkMode() === 'manual';
    const commun: WebinarInput = {
      category_codes: [...this.categories()],
      registration_mode: this.registrationMode(),
      ...(this.registrationMode() === 'external'
        ? { registration_url: this.registrationUrl().trim() || null }
        : {}),
      ...(this.isEditing() ? { replay_url: this.replayUrl().trim() || null } : {}),
    };
    if (this.lockedByZoom()) return commun;

    const dateChangee = `${this.date()}T${this.time()}` !== this.loadedDate;
    const debut = this.startsAt();
    return {
      ...commun,
      title: this.title().trim(),
      description: this.description().trim() || null,
      duration_minutes: this.duration(),
      timezone: this.timezone(),
      link_mode: this.linkMode(),
      id_zoom_accounts: manuel ? null : this.accountId(),
      join_url: manuel ? this.joinUrl().trim() || null : null,
      ...(manuel ? {} : { meeting_settings: this.settings() }),
      // Une date incomplète n'écrase pas celle qui est enregistrée.
      ...(!this.isEditing() || (dateChangee && (debut || (!this.date() && !this.time())))
        ? { starts_at: debut?.toISOString() ?? null }
        : {}),
    };
  }

  /** Crée ou met à jour, et garde la fiche : un second clic ne la double pas. */
  private async enregistrer(): Promise<WebinarDetailDto> {
    const courante = this.existing();
    const fiche = courante
      ? await this.api.update(courante.id_webinars, this.saisie())
      : await this.api.create({
          ...this.saisie(),
          publication_links: this.links(),
        });
    this.remplir(fiche);
    this.links.set([]);
    return fiche;
  }

  protected async save(): Promise<void> {
    if (!this.canSave()) return;
    if (this.date() !== '' && this.time() === '' && `${this.date()}T` !== this.loadedDate) {
      this.error.set('Saisissez aussi l’heure, ou effacez la date.');
      return;
    }
    this.busy.set(true);
    this.error.set(null);
    try {
      const fiche = await this.enregistrer();
      await this.router.navigate(['/webinaires'], { queryParams: { fiche: fiche.id_webinars } });
    } catch (erreur) {
      this.error.set(toApiError(erreur).message);
    } finally {
      this.busy.set(false);
    }
  }

  protected async validate(): Promise<void> {
    if (this.missing().length || this.needsZoomRight() || this.busy()) return;
    this.busy.set(true);
    this.error.set(null);
    try {
      const fiche = await this.enregistrer();
      await this.api.schedule(fiche.id_webinars);
      await this.router.navigate(['/webinaires'], { queryParams: { fiche: fiche.id_webinars } });
    } catch (erreur) {
      const motif = toApiError(erreur).message;
      this.error.set(
        this.existing() ? `Brouillon enregistré, mais non validé. ${motif}` : motif,
      );
    } finally {
      this.busy.set(false);
      this.isSummaryOpen.set(false);
    }
  }
}
