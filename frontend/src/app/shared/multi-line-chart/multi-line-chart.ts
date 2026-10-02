import { ChangeDetectionStrategy, Component, computed, input, signal } from '@angular/core';

/** Une courbe du graphique. */
export interface LineSeries {
  readonly key: string;
  readonly label: string;
  /** Valeur CSS, en général un jeton `var(--…)`. */
  readonly color: string;
  readonly values: readonly number[];
}

/** Une courbe prête à dessiner. */
interface DrawnSeries {
  readonly key: string;
  readonly label: string;
  readonly color: string;
  readonly path: string;
  readonly lastX: number;
  readonly lastY: number;
}

const WIDTH = 640;
const HEIGHT = 190;
const PAD_X = 6;
const PAD_TOP = 14;
const PAD_BOTTOM = 22;

/**
 * Plusieurs séries dans le temps, une couleur par série.
 *
 * Toutes les courbes partagent la même échelle verticale, bornée au
 * minimum et au maximum de l'ensemble : c'est la seule façon de comparer
 * des réseaux entre eux. Les couleurs viennent de la palette de
 * l'application, pas de celles des plateformes, et la légende reprend le
 * logo de chacune — la couleur seule ne porte jamais l'information.
 */
@Component({
  selector: 'app-multi-line-chart',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './multi-line-chart.html',
  styleUrl: './multi-line-chart.scss',
})
export class MultiLineChart {
  readonly series = input.required<readonly LineSeries[]>();
  /** Libellés de l'axe horizontal, un par point. */
  readonly labels = input.required<readonly string[]>();

  protected readonly width = WIDTH;
  protected readonly height = HEIGHT;
  protected readonly baseline = HEIGHT - PAD_BOTTOM;

  protected readonly hoverIndex = signal<number | null>(null);

  protected readonly pointCount = computed(() =>
    Math.max(0, ...this.series().map((line) => line.values.length)),
  );

  private readonly bounds = computed(() => {
    const values = this.series().flatMap((line) => [...line.values]);
    if (values.length === 0) return { min: 0, max: 1 };
    const min = Math.min(...values);
    const max = Math.max(...values);
    return { min, max: max === min ? min + 1 : max };
  });

  protected readonly scale = computed(() => this.bounds());

  private xOf(index: number): number {
    const count = this.pointCount();
    const usable = WIDTH - PAD_X * 2;
    return count > 1 ? PAD_X + (index / (count - 1)) * usable : WIDTH / 2;
  }

  private yOf(value: number): number {
    const { min, max } = this.bounds();
    const usable = HEIGHT - PAD_TOP - PAD_BOTTOM;
    return PAD_TOP + (1 - (value - min) / (max - min)) * usable;
  }

  protected readonly drawn = computed<readonly DrawnSeries[]>(() =>
    this.series().map((line) => {
      const path = line.values
        .map(
          (value, index) =>
            `${index === 0 ? 'M' : 'L'}${this.xOf(index).toFixed(1)} ${this.yOf(value).toFixed(1)}`,
        )
        .join(' ');
      const lastIndex = line.values.length - 1;
      return {
        key: line.key,
        label: line.label,
        color: line.color,
        path,
        lastX: this.xOf(lastIndex),
        lastY: this.yOf(line.values[lastIndex] ?? 0),
      };
    }),
  );

  /** Abscisse du repère vertical survolé, en unités du `viewBox`. */
  protected readonly guideX = computed(() => {
    const index = this.hoverIndex();
    return index === null ? 0 : this.xOf(index);
  });

  /** Valeurs de chaque série au point survolé. */
  protected readonly hoveredValues = computed(() => {
    const index = this.hoverIndex();
    if (index === null) return [];
    return this.series().map((line) => ({
      key: line.key,
      label: line.label,
      color: line.color,
      value: line.values[index] ?? 0,
      y: this.yOf(line.values[index] ?? 0),
      x: this.xOf(index),
    }));
  });

  protected readonly hoveredLabel = computed(() => {
    const index = this.hoverIndex();
    return index === null ? '' : (this.labels()[index] ?? '');
  });

  protected readonly hoverLeft = computed(() => {
    const index = this.hoverIndex();
    const count = this.pointCount();
    if (index === null || count <= 1) return 0;
    return (index / (count - 1)) * 100;
  });

  protected readonly hoverFlips = computed(() => this.hoverLeft() > 60);

  /**
   * Point survolé, déduit de la position du pointeur.
   *
   * Le calcul passe par la largeur rendue : le SVG est étiré, ses unités
   * internes ne correspondent pas aux pixels.
   */
  protected onMove(event: PointerEvent): void {
    const rect = (event.currentTarget as SVGElement).getBoundingClientRect();
    const count = this.pointCount();
    if (rect.width === 0 || count === 0) return;
    const ratio = (event.clientX - rect.left) / rect.width;
    const index = Math.round(ratio * (count - 1));
    this.hoverIndex.set(Math.max(0, Math.min(count - 1, index)));
  }

  protected onLeave(): void {
    this.hoverIndex.set(null);
  }
}
