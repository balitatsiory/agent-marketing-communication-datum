import { ChangeDetectionStrategy, Component, computed, input, signal } from '@angular/core';

/** Un point de la série : un jour, ses vues et ses réactions. */
export interface TimeBar {
  readonly dayLabel: string;
  readonly views: number;
  readonly reactions: number;
}

/** Une barre prête à dessiner. */
interface DrawnBar {
  readonly x: number;
  readonly viewsY: number;
  readonly viewsHeight: number;
  readonly reactionsY: number;
  readonly reactionsHeight: number;
  readonly width: number;
  readonly groupX: number;
  readonly groupWidth: number;
}

const WIDTH = 640;
const HEIGHT = 200;
const PAD_TOP = 14;
const PAD_BOTTOM = 26;
const PAD_X = 8;

/**
 * Vues et réactions jour par jour, en barres jumelées.
 *
 * Deux échelles distinctes : les réactions valent quelques dizaines quand
 * les vues se comptent en milliers. Sur une échelle commune, la série des
 * réactions serait une ligne plate contre l'axe. La légende dit le maximum
 * de chacune, pour qu'on ne compare pas deux hauteurs qui ne se comparent
 * pas.
 */
@Component({
  selector: 'app-time-bar-chart',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './time-bar-chart.html',
  styleUrl: './time-bar-chart.scss',
})
export class TimeBarChart {
  readonly bars = input.required<readonly TimeBar[]>();

  protected readonly width = WIDTH;
  protected readonly height = HEIGHT;
  protected readonly baseline = HEIGHT - PAD_BOTTOM;

  /** Index survolé, `null` hors du graphique. */
  protected readonly hoverIndex = signal<number | null>(null);

  protected readonly maxViews = computed(() =>
    Math.max(1, ...this.bars().map((bar) => bar.views)),
  );
  protected readonly maxReactions = computed(() =>
    Math.max(1, ...this.bars().map((bar) => bar.reactions)),
  );

  protected readonly drawn = computed<readonly DrawnBar[]>(() => {
    const bars = this.bars();
    if (bars.length === 0) return [];

    const usableWidth = WIDTH - PAD_X * 2;
    const usableHeight = HEIGHT - PAD_TOP - PAD_BOTTOM;
    const groupWidth = usableWidth / bars.length;
    const barWidth = Math.min(22, (groupWidth - 10) / 2);
    const maxViews = this.maxViews();
    const maxReactions = this.maxReactions();

    return bars.map((bar, index) => {
      const groupX = PAD_X + index * groupWidth;
      const centre = groupX + groupWidth / 2;
      const viewsHeight = (bar.views / maxViews) * usableHeight;
      const reactionsHeight = (bar.reactions / maxReactions) * usableHeight;
      return {
        x: centre - barWidth - 1,
        width: barWidth,
        viewsY: HEIGHT - PAD_BOTTOM - viewsHeight,
        viewsHeight,
        reactionsY: HEIGHT - PAD_BOTTOM - reactionsHeight,
        reactionsHeight,
        groupX,
        groupWidth,
      };
    });
  });

  protected readonly hovered = computed(() => {
    const index = this.hoverIndex();
    return index === null ? null : (this.bars()[index] ?? null);
  });

  /**
   * Détermine la barre survolée à partir de la position du pointeur.
   *
   * Le calcul passe par la largeur rendue, pas par le `viewBox` : le SVG
   * est étiré, les deux ne coïncident pas.
   */
  protected onMove(event: PointerEvent): void {
    const target = event.currentTarget as SVGElement;
    const rect = target.getBoundingClientRect();
    if (rect.width === 0) return;
    const ratio = (event.clientX - rect.left) / rect.width;
    const index = Math.floor(ratio * this.bars().length);
    this.hoverIndex.set(Math.max(0, Math.min(this.bars().length - 1, index)));
  }

  protected onLeave(): void {
    this.hoverIndex.set(null);
  }

  /** Position du repère survolé, en pourcentage de la largeur. */
  protected readonly hoverLeft = computed(() => {
    const index = this.hoverIndex();
    const bars = this.bars();
    if (index === null || bars.length === 0) return 0;
    return ((index + 0.5) / bars.length) * 100;
  });

  /** Le marqueur bascule à gauche près du bord droit, sinon il déborde. */
  protected readonly hoverFlips = computed(() => this.hoverLeft() > 65);
}
