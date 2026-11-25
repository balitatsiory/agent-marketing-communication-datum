import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  input,
  model,
  signal,
} from '@angular/core';

import { Icon } from '../../../shared/icon/icon';

/** Mêmes limites que l'API, vérifiées ici pour répondre sans envoyer le fichier. */
const TYPES = ['image/png', 'image/jpeg', 'image/webp'];
const OCTETS_MAX = 10 * 1024 * 1024;

/**
 * Choix du visuel d'un webinaire : cliquer ou déposer une image, la voir, la
 * remplacer ou la retirer.
 *
 * Rien n'est envoyé ici : le composant tient le fichier choisi (`file`) et la
 * demande de retrait (`removed`), que l'éditeur applique à l'enregistrement.
 */
@Component({
  selector: 'app-visual-picker',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [Icon],
  host: {
    '(dragover)': 'over($event)',
    '(dragleave)': 'leave($event)',
    '(drop)': 'drop($event)',
    '[class.is-over]': 'isOver()',
  },
  template: `
    @if (shown(); as image) {
      <div class="current">
        <img [src]="image" alt="Aperçu du visuel" referrerpolicy="no-referrer" />
        <div class="side">
          @if (file(); as choisi) {
            <b class="name">{{ choisi.name }}</b>
            <span class="cap">{{ weight() }} · importé à l’enregistrement</span>
          } @else {
            <span class="cap">Visuel actuel</span>
          }
          <div class="actions">
            <label class="btn btn-sm">
              Remplacer
              <input class="sr-only" type="file" [accept]="accept" (change)="pick($event)" />
            </label>
            <button class="btn btn-sm btn-ghost" type="button" (click)="clear()">
              {{ file() ? 'Annuler ce choix' : 'Retirer' }}
            </button>
          </div>
        </div>
      </div>
    } @else {
      <label class="drop">
        <app-icon name="image" />
        <b>Importer un visuel</b>
        <span class="cap">
          Cliquer, ou déposer une image ici — PNG, JPEG ou WebP, 10 Mo au plus.
        </span>
        <input class="sr-only" type="file" [accept]="accept" (change)="pick($event)" />
      </label>
      @if (removed()) {
        <p class="cap">
          Le visuel actuel sera retiré à l’enregistrement.
          <button class="link" type="button" (click)="removed.set(false)">Le garder</button>
        </p>
      }
    }
    @if (refusal(); as motif) {
      <p class="cap err" role="alert">{{ motif }}</p>
    }
  `,
  styles: `
    :host {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .cap {
      font-size: 11.5px;
      color: var(--muted);
    }
    .err {
      color: var(--err);
    }
    .drop {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 5px;
      text-align: center;
      border: 1px dashed var(--border-2);
      border-radius: 10px;
      padding: 22px 14px;
      font-size: 13.5px;
      cursor: pointer;
      transition:
        border-color 0.15s ease,
        background 0.15s ease;
    }
    .drop:hover,
    :host(.is-over) .drop,
    :host(.is-over) .current {
      border-color: var(--accent);
      background: var(--accent-soft);
    }
    .current {
      display: flex;
      gap: 14px;
      flex-wrap: wrap;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 10px;
    }
    img {
      width: 240px;
      max-width: 100%;
      max-height: 180px;
      object-fit: contain;
      border-radius: 8px;
      background: var(--surface-2);
    }
    .side {
      flex: 1 1 180px;
      min-width: 0;
      display: flex;
      flex-direction: column;
      justify-content: center;
      gap: 6px;
    }
    .name {
      font-size: 13px;
      overflow-wrap: anywhere;
    }
    .actions {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
    /* Le champ fichier est masqué : son libellé montre qu'il a le focus. */
    label:focus-within {
      outline: 2px solid var(--accent);
      outline-offset: 2px;
    }
  `,
})
export class VisualPicker {
  /** Visuel déjà enregistré sur la fiche. */
  readonly currentUrl = input<string | null>(null);
  readonly file = model<File | null>(null);
  readonly removed = model(false);

  protected readonly accept = TYPES.join(',');
  protected readonly isOver = signal(false);
  protected readonly refusal = signal<string | null>(null);
  private readonly preview = signal<string | null>(null);

  protected readonly shown = computed(
    () => this.preview() ?? (this.removed() ? null : this.currentUrl()),
  );

  protected readonly weight = computed(() => {
    const octets = this.file()?.size ?? 0;
    return octets < 1024 * 1024
      ? `${Math.max(1, Math.round(octets / 1024))} Ko`
      : `${(octets / (1024 * 1024)).toFixed(1).replace('.', ',')} Mo`;
  });

  constructor() {
    // L'adresse d'aperçu vit aussi longtemps que le fichier choisi.
    effect((onCleanup) => {
      const fichier = this.file();
      const adresse = fichier ? URL.createObjectURL(fichier) : null;
      this.preview.set(adresse);
      if (adresse) onCleanup(() => URL.revokeObjectURL(adresse));
    });
  }

  protected pick(evenement: Event): void {
    const champ = evenement.target as HTMLInputElement;
    this.choose(champ.files?.[0]);
    // Sinon, reprendre le même fichier après un retrait ne déclencherait rien.
    champ.value = '';
  }

  protected over(evenement: DragEvent): void {
    if (!evenement.dataTransfer?.types.includes('Files')) return;
    // Sans cela, le navigateur ouvrirait le fichier à la place de la page.
    evenement.preventDefault();
    this.isOver.set(true);
  }

  protected leave(evenement: DragEvent): void {
    const zone = evenement.currentTarget as HTMLElement;
    if (!zone.contains(evenement.relatedTarget as Node | null)) this.isOver.set(false);
  }

  protected drop(evenement: DragEvent): void {
    if (!evenement.dataTransfer?.files.length) return;
    evenement.preventDefault();
    this.isOver.set(false);
    this.choose(evenement.dataTransfer.files[0]);
  }

  protected clear(): void {
    this.refusal.set(null);
    // D'abord revenir au visuel enregistré ; le retirer demande un second geste.
    if (this.file()) this.file.set(null);
    else this.removed.set(true);
  }

  private choose(fichier: File | undefined): void {
    if (!fichier) return;
    if (!TYPES.includes(fichier.type)) {
      this.refusal.set(`« ${fichier.name} » n’est pas une image PNG, JPEG ou WebP.`);
    } else if (fichier.size > OCTETS_MAX) {
      this.refusal.set(`« ${fichier.name} » dépasse 10 Mo.`);
    } else {
      this.refusal.set(null);
      this.file.set(fichier);
      this.removed.set(false);
    }
  }
}
