import { ChangeDetectionStrategy, Component, computed, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { NEWSLETTER_SENDS } from '../../../core/data/newsletter-sends.data';
import {
  MAIL_CATEGORY_LABELS,
  MAIL_CATEGORY_NOTES,
  MAIL_CATEGORY_ORDER,
  MailCategory,
  NewsletterSend,
  SEND_STATUS_LABELS,
  SendStatus,
  bounceCount,
  deliveryRate,
  sendStatusModifier,
  wasAttempted,
} from '../../../core/models/newsletter';
import { Topbar } from '../../../layout/topbar/topbar';
import { EmailPreview } from '../../../shared/email-preview/email-preview';
import { Icon } from '../../../shared/icon/icon';

/** Un groupe de la liste : une catégorie et ses envois. */
interface CategoryGroup {
  readonly category: MailCategory;
  readonly label: string;
  readonly note: string;
  readonly sends: readonly NewsletterSend[];
}

/**
 * Boîte d'envois de la newsletter.
 *
 * L'historique est séparé par catégorie — confirmation d'inscription,
 * rappel, modification ou annulation, compte rendu, visionnage — parce
 * que ces courriels ne se relisent pas de la même façon : un rappel se
 * vérifie en volume, une annulation se relit une par une.
 *
 * Ouvrir un envoi montre ce qui est réellement parti, variables déjà
 * substituées.
 */
@Component({
  selector: 'app-send-log',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DecimalPipe, RouterLink, Topbar, Icon, EmailPreview],
  templateUrl: './send-log.html',
  styleUrl: './send-log.scss',
})
export class SendLog {
  protected readonly trail: readonly string[] = ['Événements', 'Newsletter', "Boîte d'envois"];

  protected readonly categoryLabels = MAIL_CATEGORY_LABELS;
  protected readonly categoryNotes = MAIL_CATEGORY_NOTES;
  protected readonly categories = MAIL_CATEGORY_ORDER;
  protected readonly statusLabels = SEND_STATUS_LABELS;
  protected readonly statuses: readonly SendStatus[] = ['sent', 'scheduled', 'partial', 'failed'];

  private readonly all = signal<readonly NewsletterSend[]>(NEWSLETTER_SENDS);

  /** `null` vaut « toutes les catégories ». */
  protected readonly categoryFilter = signal<MailCategory | null>(null);
  protected readonly statusFilter = signal<SendStatus | null>(null);
  protected readonly searchTerm = signal('');
  protected readonly opened = signal<NewsletterSend | null>(null);

  protected readonly everything = this.all.asReadonly();

  protected readonly results = computed<readonly NewsletterSend[]>(() => {
    const category = this.categoryFilter();
    const status = this.statusFilter();
    const term = this.searchTerm().trim().toLowerCase();

    return this.all().filter((send) => {
      if (category !== null && send.category !== category) return false;
      if (status !== null && send.status !== status) return false;
      if (!term) return true;
      return (
        send.subject.toLowerCase().includes(term) ||
        send.eventTitle.toLowerCase().includes(term) ||
        send.templateName.toLowerCase().includes(term)
      );
    });
  });

  /** Les envois retenus, regroupés par catégorie et dans l'ordre du cycle de vie. */
  protected readonly groups = computed<readonly CategoryGroup[]>(() => {
    const results = this.results();
    return this.categories
      .map((category) => ({
        category,
        label: MAIL_CATEGORY_LABELS[category],
        note: MAIL_CATEGORY_NOTES[category],
        sends: results.filter((send) => send.category === category),
      }))
      .filter((group) => group.sends.length > 0);
  });

  protected readonly countByCategory = computed(() => {
    const counts = new Map<MailCategory, number>();
    for (const send of this.all()) {
      counts.set(send.category, (counts.get(send.category) ?? 0) + 1);
    }
    return counts;
  });

  protected readonly countByStatus = computed(() => {
    const counts = new Map<SendStatus, number>();
    for (const send of this.all()) {
      counts.set(send.status, (counts.get(send.status) ?? 0) + 1);
    }
    return counts;
  });

  /** Chiffres d'en-tête, calculés sur les envois effectivement partis. */
  protected readonly totals = computed(() => {
    // Les cumuls ne portent que sur les envois tentés : mêler les envois
    // programmés y ferait chuter le taux de remise sans raison.
    const attempted = this.all().filter(wasAttempted);
    const targeted = attempted.reduce((sum, send) => sum + send.recipientCount, 0);
    const delivered = attempted.reduce((sum, send) => sum + send.deliveredCount, 0);
    return {
      sends: this.all().length,
      delivered,
      bounced: attempted.reduce((sum, send) => sum + bounceCount(send), 0),
      deliveryRate: targeted ? Math.round((delivered / targeted) * 100) : 0,
      needingAttention: this.all().filter(
        (send) => send.status === 'failed' || send.status === 'partial',
      ).length,
    };
  });

  protected readonly hasActiveFilters = computed(
    () =>
      this.categoryFilter() !== null ||
      this.statusFilter() !== null ||
      this.searchTerm().trim().length > 0,
  );

  protected countFor(category: MailCategory): number {
    return this.countByCategory().get(category) ?? 0;
  }

  protected countForStatus(status: SendStatus): number {
    return this.countByStatus().get(status) ?? 0;
  }

  protected modifierFor(status: SendStatus): string {
    return sendStatusModifier(status);
  }

  protected bouncesOf(send: NewsletterSend): number {
    return bounceCount(send);
  }

  protected deliveryRateOf(send: NewsletterSend): number {
    return deliveryRate(send);
  }

  protected wasAttemptedOf(send: NewsletterSend): boolean {
    return wasAttempted(send);
  }

  /** Recliquer le filtre actif le retire : c'est le seul moyen de revenir à « tout ». */
  protected toggleCategory(category: MailCategory): void {
    this.categoryFilter.update((current) => (current === category ? null : category));
  }

  protected toggleStatus(status: SendStatus): void {
    this.statusFilter.update((current) => (current === status ? null : status));
  }

  protected resetFilters(): void {
    this.categoryFilter.set(null);
    this.statusFilter.set(null);
    this.searchTerm.set('');
  }

  protected open(send: NewsletterSend): void {
    this.opened.set(send);
  }

  protected close(): void {
    this.opened.set(null);
  }
}
