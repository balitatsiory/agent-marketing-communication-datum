import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';

import {
  PublicationDetailDto,
  PublicationsApi,
  ValidatorOptionDto,
} from '../../../core/api/publications.api';
import { SOCIAL_NETWORKS } from '../../../core/data/social-networks.data';
import { PUBLICATION_FORMAT_LABELS, PublicationStatus } from '../../../core/models/publication';
import { SocialNetworkCode } from '../../../core/models/social-network';
import { NotificationBadgeStore } from '../../../core/services/notification-badge-store';
import { Session } from '../../../core/services/session';
import { Topbar } from '../../../layout/topbar/topbar';
import { Icon } from '../../../shared/icon/icon';
import { NetworkLogo } from '../../../shared/network-logo/network-logo';
import { StatusBadge } from '../../../shared/status-badge/status-badge';

const KNOWN_NETWORKS = new Set<string>(SOCIAL_NETWORKS.map((n) => n.code));

@Component({
  selector: 'app-publication-detail',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, RouterLink, Topbar, Icon, NetworkLogo, StatusBadge],
  templateUrl: './publication-detail.html',
  styleUrl: './publication-detail.scss',
})
export class PublicationDetail implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly api = inject(PublicationsApi);
  private readonly badgeStore = inject(NotificationBadgeStore);
  protected readonly session = inject(Session);

  protected readonly formatLabels = PUBLICATION_FORMAT_LABELS;

  protected readonly publication = signal<PublicationDetailDto | null>(null);
  protected readonly validators = signal<readonly ValidatorOptionDto[]>([]);
  protected readonly isLoading = signal(true);
  protected readonly isSubmitting = signal(false);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);

  /* ---------- formulaires validation / commentaire / édition ---------- */
  protected readonly correctionComment = signal('');
  protected readonly approvalComment = signal('');
  protected readonly discussionComment = signal('');

  protected readonly isEditing = signal(false);
  protected readonly editTitle = signal('');
  protected readonly editCaption = signal('');
  protected readonly editValidatorId = signal<string>('');
  protected readonly resubmitNote = signal('');

  protected readonly trail = computed<readonly string[]>(() => {
    const pub = this.publication();
    return pub ? ['Publier', 'Publications', pub.title] : ['Publier', 'Publications', 'Détail'];
  });

  protected readonly latestCorrection = computed(() => {
    const events = this.publication()?.events ?? [];
    for (let i = events.length - 1; i >= 0; i--) {
      if (events[i].kind === 'changes_requested') return events[i];
    }
    return null;
  });

  protected readonly platformCaptionEntries = computed(() => {
    const map = this.publication()?.captions_by_platform;
    if (!map) return [];
    return Object.entries(map).filter(([, text]) => text.trim().length > 0);
  });

  protected readonly isAuthor = computed(() => {
    const me = this.session.user();
    const pub = this.publication();
    return me !== null && pub !== null && me.id_users === pub.id_users_author;
  });

  protected readonly canValidate = computed(() => {
    const status = this.publication()?.status_code;
    return status === 'review';
  });

  protected readonly canEditOrResubmit = computed(() => {
    const status = this.publication()?.status_code;
    return status === 'draft' || status === 'changes_requested';
  });

  protected readonly canPublishScheduled = computed(() => {
    const status = this.publication()?.status_code;
    return status === 'scheduled' || status === 'approved';
  });

  ngOnInit(): void {
    this.route.paramMap.subscribe((params) => {
      const id = Number(params.get('id'));
      if (!Number.isFinite(id) || id <= 0) {
        this.errorMessage.set('Identifiant de publication invalide.');
        this.isLoading.set(false);
        return;
      }
      void this.load(id);
    });
  }

  protected async load(id: number): Promise<void> {
    this.isLoading.set(true);
    this.errorMessage.set(null);
    try {
      const [detail, validatorList] = await Promise.all([
        this.api.get(id),
        this.api.validators().catch(() => [] as readonly ValidatorOptionDto[]),
      ]);
      this.publication.set(detail);
      this.validators.set(validatorList);
      this.syncEditFields(detail);
      void this.badgeStore.refresh();
    } catch {
      this.errorMessage.set('Impossible de charger cette publication.');
    } finally {
      this.isLoading.set(false);
    }
  }

  private syncEditFields(detail: PublicationDetailDto): void {
    this.editTitle.set(detail.title);
    this.editCaption.set(detail.caption);
    this.editValidatorId.set(detail.id_users_validator ? String(detail.id_users_validator) : '');
  }

  /* ---------- actions du cycle de validation ---------- */

  protected async suggestCorrection(): Promise<void> {
    const pub = this.publication();
    const comment = this.correctionComment().trim();
    if (!pub || !comment || this.isSubmitting()) return;

    this.isSubmitting.set(true);
    this.errorMessage.set(null);
    this.notice.set(null);
    try {
      const updated = await this.api.requestChanges(pub.id_publications, comment);
      this.publication.set(updated);
      this.syncEditFields(updated);
      this.correctionComment.set('');
      this.notice.set(
        `Correction suggérée envoyée à ${updated.author_name}. Une notification lui a été transmise.`,
      );
      void this.badgeStore.refresh();
    } catch {
      this.errorMessage.set("Impossible d'envoyer la suggestion de correction.");
    } finally {
      this.isSubmitting.set(false);
    }
  }

  protected async confirmAndPublish(publishNow: boolean): Promise<void> {
    const pub = this.publication();
    if (!pub || this.isSubmitting()) return;

    this.isSubmitting.set(true);
    this.errorMessage.set(null);
    this.notice.set(null);
    try {
      const updated = await this.api.approve(pub.id_publications, {
        publish_now: publishNow,
        comment: this.approvalComment().trim() || null,
      });
      this.publication.set(updated);
      this.syncEditFields(updated);
      this.approvalComment.set('');
      this.notice.set(
        publishNow
          ? `Publication confirmée et publiée ! ${updated.author_name} a été notifié.`
          : `Publication approuvée et programmée ! ${updated.author_name} a été notifié.`,
      );
      void this.badgeStore.refresh();
    } catch {
      this.errorMessage.set('Impossible de confirmer cette publication.');
    } finally {
      this.isSubmitting.set(false);
    }
  }

  protected async saveAndResubmit(): Promise<void> {
    const pub = this.publication();
    if (!pub || this.isSubmitting()) return;

    this.isSubmitting.set(true);
    this.errorMessage.set(null);
    this.notice.set(null);
    try {
      const validatorId = this.editValidatorId() ? Number(this.editValidatorId()) : null;
      await this.api.update(pub.id_publications, {
        title: this.editTitle().trim() || pub.title,
        caption: this.editCaption(),
        id_users_validator: validatorId,
      });
      const updated = await this.api.submit(pub.id_publications, {
        id_users_validator: validatorId,
        comment: this.resubmitNote().trim() || null,
      });
      this.publication.set(updated);
      this.syncEditFields(updated);
      this.isEditing.set(false);
      this.resubmitNote.set('');
      this.notice.set('Publication mise à jour et renvoyée à la validation. Le validateur a été notifié.');
      void this.badgeStore.refresh();
    } catch {
      this.errorMessage.set('Impossible de renvoyer la publication à la validation.');
    } finally {
      this.isSubmitting.set(false);
    }
  }

  protected async postComment(): Promise<void> {
    const pub = this.publication();
    const comment = this.discussionComment().trim();
    if (!pub || !comment || this.isSubmitting()) return;

    this.isSubmitting.set(true);
    this.errorMessage.set(null);
    try {
      const updated = await this.api.addComment(pub.id_publications, comment);
      this.publication.set(updated);
      this.discussionComment.set('');
      this.notice.set('Commentaire ajouté au fil de validation.');
    } catch {
      this.errorMessage.set("Impossible d'ajouter le commentaire.");
    } finally {
      this.isSubmitting.set(false);
    }
  }

  /* ---------- helpers affichage ---------- */

  protected isSocialNetwork(code: string): code is SocialNetworkCode {
    return KNOWN_NETWORKS.has(code);
  }

  protected stepState(step: 'draft' | 'review' | 'decision' | 'published'): 'done' | 'current' | 'todo' {
    const status: PublicationStatus | undefined = this.publication()?.status_code;
    if (!status) return 'todo';
    const order: Record<string, number> = {
      draft: 0,
      changes_requested: 1,
      review: 1,
      approved: 2,
      scheduled: 2,
      published: 3,
      partiallyPublished: 3,
    };
    const current = order[status] ?? 0;
    const idx = step === 'draft' ? 0 : step === 'review' ? 1 : step === 'decision' ? 2 : 3;
    if (idx < current) return 'done';
    if (idx === current) return 'current';
    return 'todo';
  }

  protected formatDateTime(iso: string | null): string {
    if (!iso) return 'Non définie';
    return new Date(iso).toLocaleDateString('fr-FR', {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  protected formatShortDateTime(iso: string): string {
    return new Date(iso).toLocaleString('fr-FR', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  protected formatGmt(iso: string | null): string | null {
    if (!iso) return null;
    const date = new Date(iso);
    return `${date.toLocaleDateString('fr-FR', {
      day: 'numeric',
      month: 'long',
      timeZone: 'UTC',
    })} à ${date.toISOString().slice(11, 16)} GMT`;
  }
}
