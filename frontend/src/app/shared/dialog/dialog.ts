import {
  DestroyRef,
  Directive,
  ElementRef,
  afterNextRender,
  inject,
  output,
} from '@angular/core';

const FOCUSABLES = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled]):not([tabindex="-1"])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

/**
 * Comportement d'une fenêtre modale, tel que le décrit le motif « dialog » de
 * l'ARIA : le focus y entre à l'ouverture, la tabulation y reste, le reste de
 * la page devient inerte, Échap la ferme, et le focus revient d'où il venait.
 *
 * L'élément marqué `data-autofocus` reçoit le focus ; à défaut, la fenêtre.
 *
 * ```html
 * <div class="modal" appDialog (dialogClosed)="close()" role="dialog" aria-modal="true">
 * ```
 */
@Directive({
  selector: '[appDialog]',
  host: {
    tabindex: '-1',
    '(keydown)': 'onKeydown($event)',
  },
})
export class Dialog {
  /** Échap a été pressé dans la fenêtre. */
  readonly dialogClosed = output<void>();

  private readonly element = inject<ElementRef<HTMLElement>>(ElementRef).nativeElement;
  private readonly made: HTMLElement[] = [];
  private opener: Element | null = null;

  constructor() {
    // Après le rendu : une fenêtre qui en remplace une autre s'ouvre ainsi
    // une fois la précédente détruite, et son arrière-plan rendu.
    afterNextRender(() => this.open());
    inject(DestroyRef).onDestroy(() => this.close());
  }

  private open(): void {
    this.opener = document.activeElement;
    // Tout ce qui n'est pas sur le chemin de la fenêtre devient inerte. Son
    // fond, lui, est sur ce chemin : un clic dessus ferme toujours.
    let node: HTMLElement | null = this.element;
    while (node && node !== document.body) {
      for (const sibling of Array.from(node.parentElement?.children ?? [])) {
        if (sibling !== node && sibling instanceof HTMLElement && !sibling.inert) {
          sibling.inert = true;
          this.made.push(sibling);
        }
      }
      node = node.parentElement;
    }
    const wanted = this.element.querySelector<HTMLElement>('[data-autofocus]');
    (wanted ?? this.element).focus();
  }

  private close(): void {
    for (const element of this.made) element.inert = false;
    this.made.length = 0;
    if (this.opener instanceof HTMLElement && this.opener.isConnected) this.opener.focus();
  }

  protected onKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      event.stopPropagation();
      this.dialogClosed.emit();
      return;
    }
    if (event.key !== 'Tab') return;
    const items = Array.from(this.element.querySelectorAll<HTMLElement>(FOCUSABLES)).filter(
      (item) => item.getClientRects().length > 0,
    );
    if (!items.length) {
      event.preventDefault();
      return;
    }
    const first = items[0];
    const last = items[items.length - 1];
    const current = document.activeElement;
    if (event.shiftKey && (current === first || current === this.element)) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && current === last) {
      event.preventDefault();
      first.focus();
    }
  }
}
