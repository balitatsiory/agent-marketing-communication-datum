import { ChangeDetectionStrategy, Component, input } from '@angular/core';

/**
 * Monogramme Datum Academy.
 *
 * Repris du site public (https://www.datumacademy.com) : neuf barres sur
 * une grille de 118 × 110, qui dessinent un « D » ajouré. Le tracé est
 * conservé au pixel près ; seule la couleur change, puisqu'elle hérite de
 * `currentColor` au lieu du blanc d'origine.
 *
 * `variant="lockup"` ajoute le nom du produit à côté du monogramme.
 */
@Component({
  selector: 'app-brand-logo',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <span class="mark" [class.mark-plate]="variant() === 'lockup'">
      <svg viewBox="0 0 118 110" role="img" aria-label="Datum Academy">
        <g fill="currentColor">
          <rect width="42" height="10" />
          <rect x="76" width="42" height="10" />
          <rect y="20" width="118" height="10" />
          <rect y="40" width="118" height="10" />
          <rect y="60" width="118" height="10" />
          <rect y="80" width="42" height="10" />
          <rect x="76" y="80" width="42" height="10" />
          <rect y="100" width="42" height="10" />
          <rect x="76" y="100" width="42" height="10" />
        </g>
      </svg>
    </span>

    @if (variant() === 'lockup') {
      <span class="name">IAGORA</span>
    }
  `,
  styles: `
    :host {
      display: inline-flex;
      align-items: center;
      gap: 9px;
      min-width: 0;
      color: var(--accent);
    }

    .mark {
      display: grid;
      place-items: center;
      flex: none;
      width: 1.6em;
      height: 1.6em;
    }

    /* Sur fond plein, le monogramme passe en blanc et la plaque porte l'accent. */
    .mark-plate {
      width: 28px;
      height: 28px;
      border-radius: 8px;
      background: var(--accent);
      color: var(--accent-ink);
      padding: 6px 5px;
    }

    .mark svg {
      width: 100%;
      height: 100%;
      display: block;
    }

    .name {
      font-family: var(--f-display);
      font-size: 19px;
      line-height: 1;
      letter-spacing: 0.01em;
      color: var(--ink);
      white-space: nowrap;
    }
  `,
})
export class BrandLogo {
  /** `mark` : le monogramme seul. `lockup` : monogramme sur plaque + nom du produit. */
  readonly variant = input<'mark' | 'lockup'>('lockup');
}
