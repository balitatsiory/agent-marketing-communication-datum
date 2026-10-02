import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { ICON_SET, IconName } from './icon-set';

/**
 * Icône monochrome.
 *
 * Les tracés viennent de `ICON_SET` et sont injectés tels quels : ce sont
 * des constantes du code source, jamais une saisie utilisateur, d'où le
 * `bypassSecurityTrustHtml`.
 *
 * Exemple : `<app-icon name="bell" size="sm" />`
 */
@Component({
  selector: 'app-icon',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <svg
      class="ico"
      [class.ico-sm]="size() === 'sm'"
      [class.ico-lg]="size() === 'lg'"
      viewBox="0 0 24 24"
      aria-hidden="true"
      [innerHTML]="paths()"
    ></svg>
  `,
  styles: `
    :host { display: inline-flex; flex: none; }
  `,
})
export class Icon {
  private readonly sanitizer = inject(DomSanitizer);

  readonly name = input.required<IconName>();
  readonly size = input<'sm' | 'md' | 'lg'>('md');

  protected readonly paths = computed<SafeHtml>(() =>
    this.sanitizer.bypassSecurityTrustHtml(ICON_SET[this.name()]),
  );
}
