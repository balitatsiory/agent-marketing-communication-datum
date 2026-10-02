import { ChangeDetectionStrategy, Component, input } from '@angular/core';

/**
 * Barre du haut : fil d'Ariane à gauche, actions de l'écran à droite.
 *
 * Elle appartient à l'écran et non à la coquille, parce que ses actions
 * changent d'un écran à l'autre. Les actions arrivent par projection :
 *
 * ```html
 * <app-topbar [trail]="['Publier', 'Publications']">
 *   <button class="btn btn-primary">Créer</button>
 * </app-topbar>
 * ```
 */
@Component({
  selector: 'app-topbar',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <header class="topbar">
      <div class="crumb">
        @for (step of trail(); track step; let last = $last) {
          @if (last) {
            <b>{{ step }}</b>
          } @else {
            <span>{{ step }}</span>
            <span aria-hidden="true">/</span>
          }
        }
      </div>

      <div class="topbar-actions">
        <ng-content />
      </div>
    </header>
  `,
  styles: `
    :host { display: contents; }

    .topbar {
      height: var(--topbar-h);
      flex: none;
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
      padding: 0 24px;
    }

    .crumb {
      font-family: var(--f-mono);
      font-size: 11px;
      letter-spacing: 0.04em;
      color: var(--muted);
      display: flex;
      align-items: center;
      gap: 7px;
      min-width: 0;
    }
    .crumb b { color: var(--ink-2); font-weight: 500; }

    .topbar-actions { display: flex; align-items: center; gap: 9px; }
  `,
})
export class Topbar {
  /** Fil d'Ariane, du plus général au plus précis. Le dernier est l'écran courant. */
  readonly trail = input.required<readonly string[]>();
}
