import { ChangeDetectionStrategy, Component, effect, input, signal, untracked } from '@angular/core';
import { DecimalPipe } from '@angular/common';

const DUREE_MS = 650;

/**
 * Un nombre qui monte jusqu'à sa valeur.
 *
 * L'animation est ignorée quand le système demande moins de mouvement.
 */
@Component({
  selector: 'app-count-up',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DecimalPipe],
  template: `<span aria-hidden="true">{{ shown() | number: '1.0-0' : 'fr' }}</span
    ><span class="sr-only">{{ value() }}</span>`,
})
export class CountUp {
  readonly value = input.required<number>();
  protected readonly shown = signal(0);

  constructor() {
    effect((onCleanup) => {
      const cible = this.value();
      const depart = untracked(this.shown);
      if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches || depart === cible) {
        this.shown.set(cible);
        return;
      }
      const debut = performance.now();
      let image = 0;
      const avancer = (instant: number): void => {
        const part = Math.min(1, (instant - debut) / DUREE_MS);
        // Décélération : le chiffre se pose au lieu de s'arrêter net.
        const lisse = 1 - (1 - part) ** 3;
        this.shown.set(Math.round(depart + (cible - depart) * lisse));
        if (part < 1) image = requestAnimationFrame(avancer);
      };
      image = requestAnimationFrame(avancer);
      // Un onglet en arrière-plan suspend les images : ce délai garantit la
      // valeur juste même si l'animation ne s'est jamais jouée.
      const filet = setTimeout(() => this.shown.set(cible), DUREE_MS + 100);
      onCleanup(() => {
        cancelAnimationFrame(image);
        clearTimeout(filet);
      });
    });
  }
}
