import { ChangeDetectionStrategy, Component, computed, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { MAIL_TEMPLATES } from '../../../core/data/mail-templates.data';
import {
  MAIL_CATEGORY_LABELS,
  MAIL_CATEGORY_NOTES,
  MAIL_CATEGORY_ORDER,
  MailCategory,
  MailTemplate,
  TemplateVersion,
} from '../../../core/models/newsletter';
import { Topbar } from '../../../layout/topbar/topbar';
import { EmailPreview } from '../../../shared/email-preview/email-preview';
import { Icon } from '../../../shared/icon/icon';

/** Un groupe de la liste : une catégorie et ses modèles. */
interface TemplateGroup {
  readonly category: MailCategory;
  readonly label: string;
  readonly note: string;
  readonly templates: readonly MailTemplate[];
}

/**
 * Modèles de courriel, regroupés par catégorie.
 *
 * Chaque modèle garde son historique de versions ; l'aperçu montre le
 * rendu réel, variables non substituées — c'est justement ce qu'il faut
 * relire avant de publier une version.
 */
@Component({
  selector: 'app-mail-templates',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, Topbar, Icon, EmailPreview],
  templateUrl: './mail-templates.html',
  styleUrl: './mail-templates.scss',
})
export class MailTemplates {
  protected readonly trail: readonly string[] = ['Événements', 'Newsletter', 'Modèles de mail'];

  protected readonly categoryLabels = MAIL_CATEGORY_LABELS;
  protected readonly categoryNotes = MAIL_CATEGORY_NOTES;
  protected readonly categories = MAIL_CATEGORY_ORDER;

  private readonly all = signal<readonly MailTemplate[]>(MAIL_TEMPLATES);

  protected readonly categoryFilter = signal<MailCategory | null>(null);
  protected readonly selectedId = signal(MAIL_TEMPLATES[0].id);
  /** Version affichée dans l'aperçu : index dans `versions`. */
  protected readonly versionIndex = signal(0);

  protected readonly everything = this.all.asReadonly();

  protected readonly results = computed(() => {
    const category = this.categoryFilter();
    return category === null
      ? this.all()
      : this.all().filter((template) => template.category === category);
  });

  protected readonly groups = computed<readonly TemplateGroup[]>(() => {
    const results = this.results();
    return this.categories
      .map((category) => ({
        category,
        label: MAIL_CATEGORY_LABELS[category],
        note: MAIL_CATEGORY_NOTES[category],
        templates: results.filter((template) => template.category === category),
      }))
      .filter((group) => group.templates.length > 0);
  });

  protected readonly countByCategory = computed(() => {
    const counts = new Map<MailCategory, number>();
    for (const template of this.all()) {
      counts.set(template.category, (counts.get(template.category) ?? 0) + 1);
    }
    return counts;
  });

  /**
   * Modèle ouvert dans le volet d'aperçu.
   *
   * Si un filtre fait disparaître le modèle sélectionné, on bascule sur
   * le premier de la liste plutôt que de laisser un volet orphelin.
   */
  protected readonly selected = computed<MailTemplate | null>(() => {
    const results = this.results();
    if (results.length === 0) return null;
    return results.find((template) => template.id === this.selectedId()) ?? results[0];
  });

  /** Version dont l'aperçu est affiché. */
  protected readonly shownVersion = computed<TemplateVersion | null>(() => {
    const versions = this.selected()?.versions ?? [];
    return versions[this.versionIndex()] ?? versions[0] ?? null;
  });

  /** Vrai quand on regarde une version antérieure à celle en service. */
  protected readonly isViewingOldVersion = computed(() => {
    const version = this.shownVersion();
    return version !== null && !version.isCurrent;
  });

  /**
   * Entoure un nom de variable de ses accolades.
   *
   * Écrire `{{ '{{' }}` dans le gabarit ne marche pas : Angular lit les
   * accolades comme une interpolation avant même de rendre le texte, et
   * les entités HTML sont décodées trop tôt pour y échapper.
   */
  protected braced(variable: string): string {
    return `{{${variable}}}`;
  }

  protected countFor(category: MailCategory): number {
    return this.countByCategory().get(category) ?? 0;
  }

  protected toggleCategory(category: MailCategory): void {
    this.categoryFilter.update((current) => (current === category ? null : category));
  }

  protected select(template: MailTemplate): void {
    this.selectedId.set(template.id);
    this.versionIndex.set(0);
  }

  protected showVersion(index: number): void {
    this.versionIndex.set(index);
  }
}
