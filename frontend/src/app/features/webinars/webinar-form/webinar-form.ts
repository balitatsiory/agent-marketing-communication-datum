import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  input,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import {
  DURATION_PRESETS,
  MEETING_PUBLICATION_TYPE_LABELS,
  MeetingLinkMode,
  REMINDER_RULES,
  WEBINAR_CATEGORIES,
  Webinar,
  WebinarFlag,
  WebinarPublicationLink,
} from '../../../core/models/webinar';
import { PublicationStore } from '../../../core/services/publication-store';
import { WebinarStore } from '../../../core/services/webinar-store';
import { Topbar } from '../../../layout/topbar/topbar';
import { Icon } from '../../../shared/icon/icon';
import { StatusBadge } from '../../../shared/status-badge/status-badge';

/** Un rappel tel que l'aperçu le montre : calculé, jamais saisi. */
interface ReminderPreview {
  readonly label: string;
  /** Échéance en GMT, ou `null` tant que la date du webinaire manque. */
  readonly when: string | null;
  /** Vrai quand l'échéance est déjà passée : le rappel ne partira pas (F-13). */
  readonly isSkipped: boolean;
}

const MONTHS = [
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

/**
 * Nouveau webinaire / reprise d'un brouillon.
 *
 * Décisions de conception du 11 novembre 2026 :
 *
 * - Un brouillon ne demande que le titre. Date, catégorie et lien de
 *   visioconférence ne deviennent obligatoires qu'à « Valider ».
 * - La date et l'heure se saisissent en GMT, sans sélecteur de fuseau ; la
 *   conversion dans le fuseau de l'utilisateur s'affiche à côté. Zoom
 *   n'accepte pas « GMT » comme identifiant : l'intégration enverra `UTC`.
 * - Description et durée sont facultatives (colonnes NULL).
 * - Les rappels suivent un paramètre global : l'écran les montre en lecture
 *   seule, calculés à partir de la date.
 * - Un champ qui n'a pas lieu d'être est grisé, jamais masqué.
 *
 * Rien n'est réellement créé : ni webinaire côté serveur, ni lien Zoom.
 */
@Component({
  selector: 'app-webinar-form',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, RouterLink, Topbar, Icon, StatusBadge],
  templateUrl: './webinar-form.html',
  styleUrl: './webinar-form.scss',
})
export class WebinarForm implements OnInit {
  /** Identifiant du brouillon à reprendre, lié à la route `webinaires/:id/modifier`. */
  readonly id = input<string>();

  private readonly store = inject(WebinarStore);
  private readonly publicationStore = inject(PublicationStore);
  private readonly router = inject(Router);

  protected readonly categoriesList = WEBINAR_CATEGORIES;
  protected readonly durationPresets = DURATION_PRESETS;
  protected readonly typeLabels = MEETING_PUBLICATION_TYPE_LABELS;

  /* ---------- saisie ---------- */

  protected readonly editingId = signal<number | null>(null);
  protected readonly title = signal('');
  protected readonly description = signal('');
  protected readonly categories = signal<ReadonlySet<string>>(new Set());
  /** Date et heure saisies en GMT. */
  protected readonly date = signal('');
  protected readonly time = signal('');
  /** Durée en minutes ; `null` quand elle n'est pas renseignée. */
  protected readonly duration = signal<number | null>(null);
  protected readonly linkMode = signal<MeetingLinkMode>('zoom_auto');
  protected readonly manualUrl = signal('');
  protected readonly registrationUrl = signal('');
  protected readonly linkedIds = signal<ReadonlySet<number>>(new Set());

  protected readonly isSummaryOpen = signal(false);

  protected readonly isEditing = computed(() => this.editingId() !== null);
  protected readonly trail = computed<readonly string[]>(() => [
    'Événements',
    'Webinaires',
    this.isEditing() ? 'Reprendre un brouillon' : 'Nouveau webinaire',
  ]);

  /* ---------- calculs ---------- */

  /** Début du webinaire en UTC, ou `null` tant que la date ou l'heure manque. */
  protected readonly startsAt = computed(() => parseUtc(this.date(), this.time()));

  protected readonly endsAt = computed(() => {
    const start = this.startsAt();
    const minutes = this.duration();
    return start && minutes ? new Date(start.getTime() + minutes * 60_000) : null;
  });

  /** La même heure dans le fuseau du navigateur : évite un décalage de plusieurs heures. */
  protected readonly localLabel = computed(() => {
    const start = this.startsAt();
    if (!start) return null;
    const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    const text = start.toLocaleString('fr-FR', {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
      hour: '2-digit',
      minute: '2-digit',
    });
    return `${text} (${zone})`;
  });

  protected readonly gmtLabel = computed(() => {
    const start = this.startsAt();
    return start ? `${longDate(start)} à ${hhmm(start)} GMT` : null;
  });

  /** Ce que le Calendrier prévoit déjà ce jour-là : un repère, jamais un blocage. */
  protected readonly calendarHint = computed(() => {
    const day = this.date();
    if (!day) return 'Choisissez une date pour voir ce que le Calendrier prévoit ce jour-là.';
    const publications = this.publicationStore
      .everything()
      .filter((item) => item.status !== 'withdrawn' && item.scheduledAt?.startsWith(day)).length;
    const webinars = this.store
      .everything()
      .filter((item) => item.id !== this.editingId() && item.startsAtUtc?.startsWith(day)).length;
    if (publications + webinars === 0) return 'Rien de prévu ce jour-là dans le Calendrier.';
    return `Ce jour-là : ${publications} publication${publications > 1 ? 's' : ''} programmée${
      publications > 1 ? 's' : ''
    }, ${webinars} webinaire${webinars > 1 ? 's' : ''}. Aucun blocage.`;
  });

  protected readonly reminders = computed<readonly ReminderPreview[]>(() => {
    const start = this.startsAt();
    return REMINDER_RULES.map((rule) => {
      if (!start) return { label: rule.label, when: null, isSkipped: false };
      const at = new Date(start.getTime() - rule.minutesBefore * 60_000);
      return {
        label: rule.label,
        when: `${shortDate(at)} · ${hhmm(at)} GMT`,
        isSkipped: at.getTime() <= Date.now(),
      };
    });
  });

  protected readonly categoriesText = computed(() => [...this.categories()].join(', '));

  protected readonly plannedReminders = computed(
    () => this.reminders().filter((reminder) => reminder.when && !reminder.isSkipped).length,
  );

  /** Publications que l'on peut associer ; une publication retirée n'a plus rien à promouvoir. */
  protected readonly publications = computed(() =>
    this.publicationStore.everything().filter((item) => item.status !== 'withdrawn'),
  );

  protected readonly linkedPublications = computed(() =>
    this.publications().filter((item) => this.linkedIds().has(item.id)),
  );

  /** Le brouillon ne demande que le titre. */
  protected readonly canSaveDraft = computed(() => this.title().trim().length > 0);

  /** Ce qui manque pour valider, listé sous les boutons. */
  protected readonly missing = computed<readonly string[]>(() => {
    const missing: string[] = [];
    if (!this.title().trim()) missing.push('un titre');
    if (this.categories().size === 0) missing.push('au moins une catégorie');
    if (!this.date() || !this.time()) {
      missing.push('une date et une heure');
    } else if (this.startsAt() === null) {
      missing.push('une date valide');
    } else if (this.startsAt()!.getTime() <= Date.now()) {
      missing.push('une date dans le futur');
    }
    if (this.linkMode() === 'manual' && !/^https:\/\/\S+$/.test(this.manualUrl().trim())) {
      missing.push('un lien de visioconférence en https');
    }
    return missing;
  });

  protected readonly canContinue = computed(() => this.missing().length === 0);

  /* ---------- actions ---------- */

  ngOnInit(): void {
    const raw = this.id();
    if (raw === undefined) return;
    const existing = this.store.findById(Number(raw));
    if (!existing || existing.status !== 'draft') {
      void this.router.navigateByUrl('/webinaires');
      return;
    }
    this.editingId.set(existing.id);
    this.title.set(existing.title);
    this.description.set(existing.description);
    this.categories.set(
      new Set((existing.categories ?? []).filter((name) => WEBINAR_CATEGORIES.includes(name))),
    );
    if (existing.startsAtUtc) {
      this.date.set(existing.startsAtUtc.slice(0, 10));
      this.time.set(existing.startsAtUtc.slice(11, 16));
    }
    this.duration.set(existing.durationMinutes ?? null);
    this.linkMode.set(existing.meetingLink?.mode ?? 'zoom_auto');
    this.manualUrl.set(existing.meetingLink?.url ?? '');
    this.registrationUrl.set(existing.registrationUrl === '—' ? '' : existing.registrationUrl);
    this.linkedIds.set(new Set((existing.linkedPublications ?? []).map((link) => link.publicationId)));
  }

  protected toggleCategory(name: string): void {
    this.categories.update((current) => toggle(current, name));
  }

  protected setDuration(value: number | string | null): void {
    const minutes = typeof value === 'string' ? Number.parseInt(value, 10) : value;
    this.duration.set(minutes !== null && Number.isFinite(minutes) && minutes > 0 ? minutes : null);
  }

  /** Un second clic sur la durée déjà choisie la retire : elle est facultative. */
  protected choosePreset(minutes: number): void {
    this.duration.update((current) => (current === minutes ? null : minutes));
  }

  protected toggleLinked(id: number): void {
    this.linkedIds.update((current) => toggle(current, id));
  }

  protected openSummary(): void {
    if (this.canContinue()) this.isSummaryOpen.set(true);
  }

  protected closeSummary(): void {
    this.isSummaryOpen.set(false);
  }

  protected saveDraft(): void {
    if (this.canSaveDraft()) this.commit('draft');
  }

  protected validate(): void {
    if (this.canContinue()) this.commit('scheduled');
  }

  private commit(status: 'draft' | 'scheduled'): void {
    const webinar = this.build(status);
    this.store.save(webinar);

    if (status === 'draft') {
      this.store.notice.set(
        `Brouillon « ${webinar.title} » enregistré — simulation, rien n'a été envoyé.`,
      );
    } else {
      const zoom =
        this.linkMode() === 'zoom_auto' ? 'lien Zoom créé à la validation' : 'lien fourni à la main';
      const count = this.plannedReminders();
      this.store.notice.set(
        `Webinaire « ${webinar.title} » programmé — ${zoom}, ${count} rappel${count > 1 ? 's' : ''} prévu${
          count > 1 ? 's' : ''
        }. Simulation : rien n'a été créé sur Zoom ni envoyé.`,
      );
    }

    this.isSummaryOpen.set(false);
    void this.router.navigateByUrl('/webinaires');
  }

  /** Assemble la fiche telle que la liste l'attend. */
  private build(status: 'draft' | 'scheduled'): Webinar {
    const start = this.startsAt();
    const end = this.endsAt();
    const minutes = this.duration();
    const categories = [...this.categories()];
    const links: WebinarPublicationLink[] = [...this.linkedIds()].map((publicationId) => ({
      publicationId,
      type: 'promotion',
    }));
    const reminders =
      status === 'scheduled'
        ? this.reminders()
            .filter((reminder) => reminder.when && !reminder.isSkipped)
            .map((reminder) => ({ label: `${reminder.label} · e-mail`, when: reminder.when! }))
        : [];
    const flags: WebinarFlag[] =
      status === 'draft'
        ? [{ label: 'Brouillon', modifier: 'status-draft' }]
        : [
            {
              label: `${reminders.length} rappel${reminders.length > 1 ? 's' : ''} programmé${
                reminders.length > 1 ? 's' : ''
              }`,
              modifier: 'status-scheduled',
            },
          ];

    return {
      id: this.editingId() ?? this.store.nextId(),
      title: this.title().trim(),
      status,
      date: start
        ? {
            month: MONTHS[start.getUTCMonth()],
            day: String(start.getUTCDate()).padStart(2, '0'),
            weekday: start.toLocaleDateString('fr-FR', { weekday: 'long', timeZone: 'UTC' }),
          }
        : null,
      schedule: start
        ? `${capitalize(longDate(start))} · ${hhmm(start)}${end ? ` – ${hhmm(end)}` : ''} GMT · Zoom`
        : 'Date à définir',
      subtitle:
        status === 'draft'
          ? start
            ? 'Brouillon · Zoom'
            : 'Brouillon · date à définir'
          : `Zoom · ${categories.join(', ')}`,
      flags,
      description: this.description().trim(),
      topics: categories,
      startTimeLabel: start ? `${hhmm(start)} GMT` : '—',
      durationLabel: minutes ? formatMinutes(minutes) : '—',
      registrationCount: 0,
      attendeeCount: null,
      questionCount: null,
      registrationUrl: this.registrationUrl().trim() || '—',
      speakers: [],
      recentRegistrants: [],
      reminders,
      registrationSeries: [],
      promoVisuals: [],
      replay: null,
      startsAtUtc: start ? start.toISOString() : null,
      durationMinutes: minutes,
      categories,
      meetingLink: {
        mode: this.linkMode(),
        url: this.linkMode() === 'manual' ? this.manualUrl().trim() : null,
      },
      linkedPublications: links,
    };
  }
}

/** Date UTC à partir d'un jour (AAAA-MM-JJ) et d'une heure (HH:MM) saisis. */
function parseUtc(date: string, time: string): Date | null {
  const day = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date);
  const hour = /^(\d{2}):(\d{2})$/.exec(time);
  if (!day || !hour) return null;
  const value = new Date(Date.UTC(+day[1], +day[2] - 1, +day[3], +hour[1], +hour[2]));
  return Number.isNaN(value.getTime()) ? null : value;
}

function hhmm(date: Date): string {
  return `${String(date.getUTCHours()).padStart(2, '0')}:${String(date.getUTCMinutes()).padStart(2, '0')}`;
}

/** « mardi 8 décembre 2026 » */
function longDate(date: Date): string {
  return date.toLocaleDateString('fr-FR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  });
}

/** « 7 décembre » */
function shortDate(date: Date): string {
  return date.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', timeZone: 'UTC' });
}

function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** 90 → « 1 h 30 », 60 → « 1 h », 45 → « 45 min » — comme les fiches existantes. */
function formatMinutes(minutes: number): string {
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest === 0 ? `${hours} h` : `${hours} h ${String(rest).padStart(2, '0')}`;
}

/** Ajoute ou retire une valeur, en renvoyant un nouvel ensemble. */
function toggle<T>(current: ReadonlySet<T>, value: T): ReadonlySet<T> {
  const next = new Set(current);
  if (!next.delete(value)) next.add(value);
  return next;
}
