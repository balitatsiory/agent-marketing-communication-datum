import {
  DestroyRef,
  Directive,
  ElementRef,
  NgZone,
  afterNextRender,
  effect,
  inject,
  input,
  signal,
} from '@angular/core';
import * as echarts from 'echarts';
import type { ECharts, EChartsOption } from 'echarts';
import { IAGORA_CHART_THEME_NAME, buildIagoraChartTheme } from './chart-theme';

/** Le thème ne s'enregistre qu'une fois pour toute l'application. */
let themeRegistered = false;

/**
 * Pose un graphique ECharts sur l'élément qui porte la directive.
 *
 * L'élément doit avoir une hauteur : ECharts mesure son conteneur,
 * et un conteneur sans hauteur donne un graphique invisible.
 *
 * @example
 * ```html
 * <div class="plot" [appChart]="followerOption()"></div>
 * ```
 * ```scss
 * .plot { width: 100%; height: 220px; }
 * ```
 *
 * Ce que la directive prend en charge, et qu'il ne faut donc pas
 * refaire dans les composants :
 *
 *  - l'initialisation après le premier rendu, jamais avant — sinon
 *    le conteneur n'a pas encore sa taille ;
 *  - le redimensionnement, par `ResizeObserver` sur le conteneur
 *    lui-même et non sur la fenêtre : un graphique dans un panneau
 *    repliable suit aussi ;
 *  - la destruction de l'instance, que l'on oublie facilement et
 *    qui fuit en mémoire à chaque navigation ;
 *  - l'exécution hors de la zone Angular : ECharts installe ses
 *    propres écouteurs, et les laisser dans la zone relance la
 *    détection de changement à chaque survol de la souris.
 */
@Directive({
  selector: '[appChart]',
})
export class Chart {
  /**
   * Option ECharts complète. Remplacée entièrement à chaque
   * changement (`notMerge`), ce qui évite les restes d'une
   * configuration précédente quand des séries disparaissent.
   */
  readonly option = input.required<EChartsOption>({ alias: 'appChart' });

  /** Affiche le voile de chargement d'ECharts. */
  readonly loading = input(false);

  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly zone = inject(NgZone);

  private chart: ECharts | null = null;
  private resizeObserver: ResizeObserver | null = null;

  /** Passe à vrai une fois l'instance créée ; les effets attendent ce signal. */
  private readonly ready = signal(false);

  constructor() {
    // Ne s'exécute pas au rendu côté serveur : ECharts a besoin du DOM.
    afterNextRender(() => {
      if (!themeRegistered) {
        echarts.registerTheme(IAGORA_CHART_THEME_NAME, buildIagoraChartTheme());
        themeRegistered = true;
      }

      this.zone.runOutsideAngular(() => {
        this.chart = echarts.init(this.host.nativeElement, IAGORA_CHART_THEME_NAME, {
          renderer: 'canvas',
        });
        this.resizeObserver = new ResizeObserver(() => this.chart?.resize());
        this.resizeObserver.observe(this.host.nativeElement);
      });

      this.ready.set(true);
    });

    effect(() => {
      const option = this.option();
      if (!this.ready()) return;
      this.zone.runOutsideAngular(() => this.chart?.setOption(option, true));
    });

    effect(() => {
      const isLoading = this.loading();
      if (!this.ready()) return;
      this.zone.runOutsideAngular(() => {
        if (isLoading) this.chart?.showLoading('default', { text: 'Chargement…' });
        else this.chart?.hideLoading();
      });
    });

    inject(DestroyRef).onDestroy(() => {
      this.resizeObserver?.disconnect();
      this.chart?.dispose();
      this.chart = null;
    });
  }
}
