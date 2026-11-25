import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { RouterLink } from '@angular/router';

import { toApiError } from '../../../core/api/api-error';
import {
  MailCategoryDto,
  MailTemplateDto,
  MailTemplatePreviewDto,
  MailTemplateStatus,
  MailTemplateVersionDto,
  NewsletterApi,
} from '../../../core/api/newsletter.api';
import { Session } from '../../../core/services/session';
import { Topbar } from '../../../layout/topbar/topbar';
import { Icon } from '../../../shared/icon/icon';

/** Ce que le formulaire tient entre l'ouverture et l'enregistrement. */
interface Brouillon {
  category_code: string;
  name: string;
  subject: string;
  preheader: string;
  body_html: string;
  status: MailTemplateStatus;
  change_note: string;
}

const CORPS_VIDE = `          <tr>
            <td class="px" style="padding:36px 32px 0 32px;font-family:'Poppins','Segoe UI',Arial,sans-serif;">
              <div class="h-title" style="font-size:22px;line-height:30px;font-weight:600;color:#073C4E;">
                Bonjour {{prenom}},
              </div>
            </td>
          </tr>

          <tr>
            <td class="px" style="padding:18px 32px 36px 32px;font-family:'Poppins','Segoe UI',Arial,sans-serif;font-size:14.5px;line-height:24px;color:#44525A;">
              Votre texte ici.
            </td>
          </tr>`;

/**
 * Modèles de mail, branchés sur l'API.
 *
 * Un modèle ne porte que son CORPS : la bannière et la signature viennent de
 * la coquille commune, côté serveur. L'aperçu montre donc le message entier,
 * tel qu'il partira — c'est la seule façon de relire ce qu'on publie.
 */
@Component({
  selector: 'app-template-library',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, RouterLink, Topbar, Icon],
  templateUrl: './template-library.html',
  styleUrl: './template-library.scss',
})
export class TemplateLibrary {
  private readonly api = inject(NewsletterApi);
  private readonly session = inject(Session);
  private readonly sanitizer = inject(DomSanitizer);

  protected readonly trail: readonly string[] = ['Événements', 'Newsletter', 'Modèles de mail'];

  protected readonly categories = signal<readonly MailCategoryDto[]>([]);
  protected readonly templates = signal<readonly MailTemplateDto[]>([]);
  protected readonly total = signal(0);
  protected readonly pages = signal(0);
  protected readonly page = signal(1);
  protected readonly size = 20;

  protected readonly categoryFilter = signal<string | null>(null);
  protected readonly statusFilter = signal<MailTemplateStatus | null>(null);
  protected readonly searchTerm = signal('');

  protected readonly selectedId = signal<number | null>(null);
  protected readonly versions = signal<readonly MailTemplateVersionDto[]>([]);
  protected readonly preview = signal<MailTemplatePreviewDto | null>(null);
  protected readonly previewOpen = signal(false);

  protected readonly loading = signal(true);
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);

  protected readonly draft = signal<Brouillon | null>(null);
  protected readonly editing = signal<number | null>(null);

  protected readonly canManage = computed(() => this.session.has('manage_mail_templates'));

  protected readonly selected = computed(() => {
    const id = this.selectedId();
    return id === null ? null : (this.templates().find((t) => t.id_mail_templates === id) ?? null);
  });

  /** Les modèles de la page, regroupés par catégorie, dans l'ordre du cycle de vie. */
  protected readonly groups = computed(() =>
    this.categories()
      .map((category) => ({
        category,
        templates: this.templates().filter((t) => t.category_code === category.code),
      }))
      .filter((groupe) => groupe.templates.length > 0),
  );

  /**
   * L'aperçu est servi dans une iframe en bac à sable : c'est du HTML de
   * courriel, pas du HTML d'application. Sans `sandbox`, il partagerait
   * l'origine de l'application.
   */
  protected readonly previewHtml = computed<SafeHtml | null>(() => {
    const apercu = this.preview();
    return apercu ? this.sanitizer.bypassSecurityTrustHtml(apercu.html) : null;
  });

  constructor() {
    void this.initialiser();
  }

  private async initialiser(): Promise<void> {
    try {
      this.categories.set(await this.api.categories());
    } catch (erreur) {
      this.error.set(toApiError(erreur).message);
    }
    await this.recharger();
  }

  protected async recharger(): Promise<void> {
    this.loading.set(true);
    this.error.set(null);
    try {
      const page = await this.api.templates({
        page: this.page(),
        size: this.size,
        category_code: this.categoryFilter(),
        status: this.statusFilter(),
        search: this.searchTerm().trim() || null,
      });
      this.templates.set(page.items);
      this.total.set(page.total);
      this.pages.set(page.pages);

      const courant = this.selectedId();
      const existe = page.items.some((t) => t.id_mail_templates === courant);
      const id = existe ? courant : (page.items[0]?.id_mail_templates ?? null);
      if (id !== courant) {
        this.selectedId.set(id);
        this.versions.set([]);
        this.preview.set(null);
      }
      if (id !== null) await this.chargerDetail(id);
    } catch (erreur) {
      this.error.set(toApiError(erreur).message);
    } finally {
      this.loading.set(false);
    }
  }

  private async chargerDetail(id: number): Promise<void> {
    try {
      const [versions, apercu] = await Promise.all([this.api.versions(id), this.api.preview(id)]);
      // Le modèle a pu changer pendant l'appel : on n'écrase que si c'est
      // toujours celui qui est ouvert.
      if (this.selectedId() !== id) return;
      this.versions.set(versions);
      this.preview.set(apercu);
    } catch (erreur) {
      if (this.selectedId() === id) this.error.set(toApiError(erreur).message);
    }
  }

  protected async select(id: number): Promise<void> {
    if (this.selectedId() === id) return;
    this.selectedId.set(id);
    this.versions.set([]);
    this.preview.set(null);
    await this.chargerDetail(id);
  }

  // -------------------------------------------------------------------------
  // Filtres et pagination
  // -------------------------------------------------------------------------

  protected async filtrerCategorie(code: string | null): Promise<void> {
    this.categoryFilter.update((courant) => (courant === code ? null : code));
    this.page.set(1);
    await this.recharger();
  }

  protected async filtrerStatut(statut: MailTemplateStatus | null): Promise<void> {
    this.statusFilter.update((courant) => (courant === statut ? null : statut));
    this.page.set(1);
    await this.recharger();
  }

  protected async rechercher(terme: string): Promise<void> {
    this.searchTerm.set(terme);
    this.page.set(1);
    await this.recharger();
  }

  protected async allerPage(numero: number): Promise<void> {
    if (numero < 1 || (this.pages() > 0 && numero > this.pages())) return;
    this.page.set(numero);
    await this.recharger();
  }

  // -------------------------------------------------------------------------
  // Écriture
  // -------------------------------------------------------------------------

  protected async installerLesStandards(): Promise<void> {
    this.busy.set(true);
    this.error.set(null);
    try {
      await this.api.installStandards();
      await this.recharger();
    } catch (erreur) {
      this.error.set(toApiError(erreur).message);
    } finally {
      this.busy.set(false);
    }
  }

  protected ouvrirCreation(): void {
    if (this.busy()) return;
    this.editing.set(null);
    this.draft.set({
      category_code: this.categoryFilter() ?? this.categories()[0]?.code ?? '',
      name: '',
      subject: '',
      preheader: '',
      body_html: CORPS_VIDE,
      status: 'draft',
      change_note: '',
    });
  }

  protected ouvrirModification(modele: MailTemplateDto): void {
    if (this.busy()) return;
    this.editing.set(modele.id_mail_templates);
    this.draft.set({
      category_code: modele.category_code,
      name: modele.name,
      subject: modele.subject,
      preheader: modele.preheader ?? '',
      body_html: modele.body_html,
      status: modele.status,
      change_note: '',
    });
  }

  protected fermerFormulaire(): void {
    if (this.busy()) return;
    this.draft.set(null);
    this.editing.set(null);
  }

  protected majBrouillon(champ: keyof Brouillon, valeur: string): void {
    this.draft.update((brouillon) =>
      brouillon === null ? brouillon : { ...brouillon, [champ]: valeur },
    );
  }

  protected readonly formulaireValide = computed(() => {
    const brouillon = this.draft();
    if (brouillon === null) return false;
    return (
      brouillon.category_code.length > 0 &&
      brouillon.name.trim().length > 0 &&
      brouillon.subject.trim().length > 0 &&
      brouillon.body_html.trim().length > 0
    );
  });

  protected async enregistrer(): Promise<void> {
    const brouillon = this.draft();
    if (brouillon === null || !this.formulaireValide()) return;

    this.busy.set(true);
    this.error.set(null);
    try {
      const id = this.editing();
      if (id === null) {
        const cree = await this.api.createTemplate({
          category_code: brouillon.category_code,
          name: brouillon.name.trim(),
          subject: brouillon.subject.trim(),
          preheader: brouillon.preheader.trim() || null,
          body_html: brouillon.body_html,
          status: brouillon.status,
        });
        this.selectedId.set(cree.id_mail_templates);
      } else {
        await this.api.updateTemplate(id, {
          category_code: brouillon.category_code,
          name: brouillon.name.trim(),
          subject: brouillon.subject.trim(),
          preheader: brouillon.preheader.trim() || null,
          body_html: brouillon.body_html,
          status: brouillon.status,
          change_note: brouillon.change_note.trim() || null,
        });
      }
      this.draft.set(null);
      this.editing.set(null);
      await this.recharger();
    } catch (erreur) {
      this.error.set(toApiError(erreur).message);
    } finally {
      this.busy.set(false);
    }
  }

  /** Publier rend le modèle envoyable ; dépublier le retire des envois. */
  protected async basculerPublication(modele: MailTemplateDto): Promise<void> {
    this.busy.set(true);
    this.error.set(null);
    try {
      await this.api.updateTemplate(modele.id_mail_templates, {
        status: modele.status === 'published' ? 'draft' : 'published',
      });
      await this.recharger();
    } catch (erreur) {
      this.error.set(toApiError(erreur).message);
    } finally {
      this.busy.set(false);
    }
  }

  protected async archiver(modele: MailTemplateDto): Promise<void> {
    this.busy.set(true);
    this.error.set(null);
    try {
      await this.api.archiveTemplate(modele.id_mail_templates);
      if (this.selectedId() === modele.id_mail_templates) this.selectedId.set(null);
      await this.recharger();
    } catch (erreur) {
      this.error.set(toApiError(erreur).message);
    } finally {
      this.busy.set(false);
    }
  }

  // -------------------------------------------------------------------------
  // Affichage
  // -------------------------------------------------------------------------

  protected statutModifier(statut: MailTemplateStatus): string {
    return statut === 'published' ? 'status-published' : 'status-draft';
  }

  protected statutLisible(statut: MailTemplateStatus): string {
    return statut === 'published' ? 'Publié' : 'Brouillon';
  }
}
