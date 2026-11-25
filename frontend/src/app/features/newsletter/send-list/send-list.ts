import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { RouterLink } from '@angular/router';

import { toApiError } from '../../../core/api/api-error';
import { EmailAccountDto, EmailAccountsApi } from '../../../core/api/email-accounts.api';
import {
  MailCategoryDto,
  MailTemplateDto,
  NewsletterApi,
  NewsletterSendDetailDto,
  NewsletterSendDto,
  NewsletterStatsDto,
  SendStatusDto,
} from '../../../core/api/newsletter.api';
import { Session } from '../../../core/services/session';
import { Topbar } from '../../../layout/topbar/topbar';
import { Icon } from '../../../shared/icon/icon';

/** Un destinataire saisi : « Nom <adresse> » ou une adresse seule. */
interface Destinataire {
  readonly email: string;
  readonly display_name: string | null;
}

/**
 * Lit une saisie libre en destinataires.
 *
 * Une ligne par destinataire, parce qu'un nom peut contenir une virgule : la
 * séparer par virgules couperait « Rakoto, Mialy » en deux adresses.
 */
export function lireDestinataires(saisie: string): Destinataire[] {
  const vus = new Set<string>();
  const lignes: Destinataire[] = [];
  for (const brute of saisie.split('\n')) {
    const ligne = brute.trim();
    if (!ligne) continue;
    const avecNom = /^(.*?)<([^>]+)>$/.exec(ligne);
    const email = (avecNom ? avecNom[2] : ligne).trim().toLowerCase();
    const nom = avecNom ? avecNom[1].trim().replace(/^"|"$/g, '') : '';
    if (!email.includes('@') || vus.has(email)) continue;
    vus.add(email);
    lignes.push({ email, display_name: nom || null });
  }
  return lignes;
}

/**
 * Boîte d'envois, branchée sur l'API.
 *
 * Le compte d'envoi se choisit en tête : « Tous les comptes » cumule, un
 * compte précis isole ses envois et recalcule ses chiffres. Les chiffres ne
 * sont jamais mis en cache — le bouton Actualiser doit pouvoir montrer l'effet
 * d'un envoi fait à la seconde d'avant.
 */
@Component({
  selector: 'app-send-list',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, DecimalPipe, RouterLink, Topbar, Icon],
  templateUrl: './send-list.html',
  styleUrl: './send-list.scss',
})
export class SendList {
  private readonly api = inject(NewsletterApi);
  private readonly comptesApi = inject(EmailAccountsApi);
  private readonly session = inject(Session);

  protected readonly trail: readonly string[] = ['Événements', 'Newsletter', "Boîte d'envois"];

  protected readonly accounts = signal<readonly EmailAccountDto[]>([]);
  protected readonly categories = signal<readonly MailCategoryDto[]>([]);
  protected readonly statuses = signal<readonly SendStatusDto[]>([]);
  protected readonly templates = signal<readonly MailTemplateDto[]>([]);

  protected readonly stats = signal<NewsletterStatsDto | null>(null);
  protected readonly sends = signal<readonly NewsletterSendDto[]>([]);
  protected readonly total = signal(0);
  protected readonly pages = signal(0);
  protected readonly page = signal(1);
  protected readonly size = 20;

  /** `null` vaut « tous les comptes cumulés ». */
  protected readonly accountFilter = signal<number | null>(null);
  protected readonly categoryFilter = signal<string | null>(null);
  protected readonly statusFilter = signal<string | null>(null);
  protected readonly searchTerm = signal('');

  protected readonly opened = signal<NewsletterSendDetailDto | null>(null);
  protected readonly loading = signal(true);
  protected readonly refreshing = signal(false);
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly report = signal<{ ok: boolean; message: string } | null>(null);

  /** Formulaire d'envoi. `null` quand il est fermé. */
  protected readonly composer = signal<{
    id_mail_templates: number | null;
    id_email_accounts: number | null;
    event_title: string;
    recipients: string;
  } | null>(null);

  protected readonly canSend = computed(() => this.session.has('send_newsletters'));
  protected readonly canManageAccounts = computed(() =>
    this.session.has('manage_email_accounts'),
  );

  protected readonly activeAccount = computed(
    () => this.accounts().find((compte) => compte.is_default) ?? null,
  );

  protected readonly publishedTemplates = computed(() =>
    this.templates().filter((modele) => modele.status === 'published'),
  );

  protected readonly parsedRecipients = computed(() =>
    lireDestinataires(this.composer()?.recipients ?? ''),
  );

  protected readonly hasActiveFilters = computed(
    () =>
      this.categoryFilter() !== null ||
      this.statusFilter() !== null ||
      this.searchTerm().trim().length > 0,
  );

  constructor() {
    void this.initialiser();
  }

  private async initialiser(): Promise<void> {
    try {
      const [comptes, categories, statuts, modeles] = await Promise.all([
        this.comptesApi.list(),
        this.api.categories(),
        this.api.sendStatuses(),
        this.api.templates({ size: 100, status: 'published' }),
      ]);
      this.accounts.set(comptes);
      this.categories.set(categories);
      this.statuses.set(statuts);
      this.templates.set(modeles.items);
    } catch (erreur) {
      this.error.set(toApiError(erreur).message);
    }
    await this.recharger();
  }

  /** Recharge chiffres et liste ensemble : ils doivent parler du même instant. */
  protected async recharger(): Promise<void> {
    this.refreshing.set(true);
    this.error.set(null);
    try {
      const [stats, page] = await Promise.all([
        this.api.stats(this.accountFilter()),
        this.api.sends({
          page: this.page(),
          size: this.size,
          id_email_accounts: this.accountFilter(),
          category_code: this.categoryFilter(),
          status_code: this.statusFilter(),
          search: this.searchTerm().trim() || null,
        }),
      ]);
      this.stats.set(stats);
      this.sends.set(page.items);
      this.total.set(page.total);
      this.pages.set(page.pages);
    } catch (erreur) {
      this.error.set(toApiError(erreur).message);
    } finally {
      this.refreshing.set(false);
      this.loading.set(false);
    }
  }

  // -------------------------------------------------------------------------
  // Filtres et pagination
  // -------------------------------------------------------------------------

  protected async choisirCompte(valeur: string): Promise<void> {
    this.accountFilter.set(valeur === '' ? null : Number(valeur));
    this.page.set(1);
    await this.recharger();
  }

  protected async filtrerCategorie(code: string): Promise<void> {
    this.categoryFilter.update((courant) => (courant === code ? null : code));
    this.page.set(1);
    await this.recharger();
  }

  protected async filtrerStatut(code: string): Promise<void> {
    this.statusFilter.update((courant) => (courant === code ? null : code));
    this.page.set(1);
    await this.recharger();
  }

  protected async rechercher(terme: string): Promise<void> {
    this.searchTerm.set(terme);
    this.page.set(1);
    await this.recharger();
  }

  protected async reinitialiser(): Promise<void> {
    this.categoryFilter.set(null);
    this.statusFilter.set(null);
    this.searchTerm.set('');
    this.page.set(1);
    await this.recharger();
  }

  protected async allerPage(numero: number): Promise<void> {
    if (numero < 1 || (this.pages() > 0 && numero > this.pages())) return;
    this.page.set(numero);
    await this.recharger();
  }

  protected compteurCategorie(code: string): number {
    return this.stats()?.by_category.find((ligne) => ligne.code === code)?.count ?? 0;
  }

  protected compteurStatut(code: string): number {
    return this.stats()?.by_status.find((ligne) => ligne.code === code)?.count ?? 0;
  }

  // -------------------------------------------------------------------------
  // Détail d'un envoi
  // -------------------------------------------------------------------------

  protected async ouvrir(envoi: NewsletterSendDto): Promise<void> {
    this.error.set(null);
    try {
      this.opened.set(await this.api.send(envoi.id_newsletter_sends));
    } catch (erreur) {
      this.error.set(toApiError(erreur).message);
    }
  }

  protected fermer(): void {
    this.opened.set(null);
  }

  // -------------------------------------------------------------------------
  // Nouvel envoi
  // -------------------------------------------------------------------------

  protected ouvrirComposer(): void {
    if (this.busy()) return;
    this.report.set(null);
    this.composer.set({
      id_mail_templates: this.publishedTemplates()[0]?.id_mail_templates ?? null,
      id_email_accounts: this.accountFilter() ?? this.activeAccount()?.id_email_accounts ?? null,
      event_title: '',
      recipients: '',
    });
  }

  protected fermerComposer(): void {
    if (this.busy()) return;
    this.composer.set(null);
  }

  protected majComposer(champ: 'event_title' | 'recipients', valeur: string): void {
    this.composer.update((etat) => (etat === null ? etat : { ...etat, [champ]: valeur }));
  }

  protected majComposerId(
    champ: 'id_mail_templates' | 'id_email_accounts',
    valeur: string,
  ): void {
    this.composer.update((etat) =>
      etat === null ? etat : { ...etat, [champ]: valeur === '' ? null : Number(valeur) },
    );
  }

  /** Reprend les destinataires de l'envoi ouvert : on renvoie souvent au même monde. */
  protected reprendreLesDestinataires(): void {
    const envoi = this.opened();
    if (envoi === null) return;
    const lignes = envoi.recipients
      .map((ligne) => (ligne.display_name ? `${ligne.display_name} <${ligne.email}>` : ligne.email))
      .join('\n');
    this.composer.update((etat) => (etat === null ? etat : { ...etat, recipients: lignes }));
  }

  protected readonly envoiValide = computed(() => {
    const etat = this.composer();
    return etat !== null && etat.id_mail_templates !== null && this.parsedRecipients().length > 0;
  });

  protected async envoyer(): Promise<void> {
    const etat = this.composer();
    if (etat === null || etat.id_mail_templates === null || !this.envoiValide()) return;

    this.busy.set(true);
    this.error.set(null);
    this.report.set(null);
    try {
      const envoi = await this.api.createSend({
        id_mail_templates: etat.id_mail_templates,
        id_email_accounts: etat.id_email_accounts,
        event_title: etat.event_title.trim() || null,
        recipients: this.parsedRecipients(),
      });
      this.composer.set(null);
      this.report.set({
        ok: envoi.status_code === 'sent',
        message:
          envoi.status_code === 'sent'
            ? `Envoi accepté pour les ${envoi.delivered_count} destinataires.`
            : `${envoi.delivered_count} message(s) accepté(s) sur ${envoi.recipient_count}. ${envoi.failure_note ?? ''}`,
      });
      this.page.set(1);
      await this.recharger();
      this.opened.set(envoi);
    } catch (erreur) {
      this.error.set(toApiError(erreur).message);
    } finally {
      this.busy.set(false);
    }
  }

  // -------------------------------------------------------------------------
  // Affichage
  // -------------------------------------------------------------------------

  protected statutModifier(code: string): string {
    switch (code) {
      case 'sent':
        return 'status-published';
      case 'scheduled':
        return 'status-scheduled';
      case 'failed':
      case 'partial':
        return 'status-failed';
      default:
        return 'status-draft';
    }
  }

  /** Vrai quand l'envoi a réellement été tenté : sinon ni remis ni rejets. */
  protected tente(envoi: NewsletterSendDto): boolean {
    return envoi.status_code === 'sent' || envoi.status_code === 'partial';
  }
}
