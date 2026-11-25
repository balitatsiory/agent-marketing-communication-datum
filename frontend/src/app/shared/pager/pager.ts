import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';

/**
 * Pagination d'une liste : ce qu'on voit, les pages voisines et les bouts, et
 * le nombre de lignes par page.
 *
 * Le composant n'a pas d'état : il affiche celui qu'on lui donne et demande les
 * changements.
 *
 * ```html
 * <app-pager [page]="page()" [pages]="pages()" [total]="total()" [size]="size()"
 *            [sizes]="[10, 25, 50]" (pageChange)="charger($event)" (sizeChange)="choisir($event)" />
 * ```
 */
@Component({
  selector: 'app-pager',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <nav class="pager" [attr.aria-label]="label()">
      <span class="cap" role="status">{{ range() }}</span>
      <div class="pages">
        <button
          class="btn btn-sm"
          type="button"
          [disabled]="page() <= 1"
          (click)="pageChange.emit(page() - 1)"
        >
          Précédent
        </button>
        @for (numero of numbers(); track $index) {
          @if (numero === null) {
            <span class="cap" aria-hidden="true">…</span>
          } @else {
            <button
              class="btn btn-sm"
              type="button"
              [class.btn-primary]="numero === page()"
              [attr.aria-current]="numero === page() ? 'page' : null"
              (click)="pageChange.emit(numero)"
            >
              {{ numero }}
            </button>
          }
        }
        <button
          class="btn btn-sm"
          type="button"
          [disabled]="page() >= pages()"
          (click)="pageChange.emit(page() + 1)"
        >
          Suivant
        </button>
      </div>
      <label class="cap per-page">
        Par page
        <select class="select" (change)="sizeChange.emit(+$any($event.target).value)">
          @for (taille of sizes(); track taille) {
            <option [value]="taille" [selected]="size() === taille">{{ taille }}</option>
          }
        </select>
      </label>
    </nav>
  `,
  styles: `
    :host {
      display: block;
    }
    .pager {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      flex-wrap: wrap;
    }
    .pages {
      display: flex;
      align-items: center;
      gap: 5px;
      flex-wrap: wrap;
    }
    .cap {
      font-size: 11.5px;
      color: var(--muted);
    }
    .per-page {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .select {
      width: auto;
      height: 34px;
      font-size: 13px;
    }
  `,
})
export class Pager {
  readonly page = input.required<number>();
  readonly pages = input.required<number>();
  readonly total = input.required<number>();
  readonly size = input.required<number>();
  readonly sizes = input.required<readonly number[]>();
  readonly label = input('Pagination');

  readonly pageChange = output<number>();
  readonly sizeChange = output<number>();

  protected readonly range = computed(() => {
    const total = this.total();
    if (total === 0) return '0';
    const debut = (this.page() - 1) * this.size() + 1;
    return `${debut}–${Math.min(total, debut + this.size() - 1)} sur ${total}`;
  });

  /** Numéros affichés ; `null` figure un saut. */
  protected readonly numbers = computed<readonly (number | null)[]>(() => {
    const total = this.pages();
    const courante = this.page();
    const gardees = [...new Set([1, courante - 1, courante, courante + 1, total])]
      .filter((n) => n >= 1 && n <= total)
      .sort((a, b) => a - b);
    return gardees.flatMap((n, i) => (i > 0 && n - gardees[i - 1] > 1 ? [null, n] : [n]));
  });
}
