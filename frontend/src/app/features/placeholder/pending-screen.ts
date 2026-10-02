import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Topbar } from '../../layout/topbar/topbar';
import { Icon } from '../../shared/icon/icon';

/**
 * Écran dont la route existe mais dont la page reste à construire.
 *
 * Une page d'attente nommée vaut mieux qu'un lien mort : le parcours
 * de navigation reste vérifiable de bout en bout.
 */
@Component({
  selector: 'app-pending-screen',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, Topbar, Icon],
  template: `
    <app-topbar [trail]="trail()">
      <a class="btn" routerLink="/publications">Retour aux publications</a>
    </app-topbar>

    <div class="page">
      <div class="empty">
        <app-icon [name]="icon()" size="lg" />
        <h2>{{ title() }}</h2>
        <p>{{ note() }}</p>
        <p class="ref">Maquette {{ mockup() }}</p>
      </div>
    </div>
  `,
  styles: `
    :host { display: contents; }

    .page {
      flex: 1;
      min-height: 0;
      overflow-y: auto;
      padding: 22px 24px 28px;
      display: flex;
      flex-direction: column;
    }

    .empty app-icon { color: var(--border-2); }

    .ref {
      font-family: var(--f-mono);
      font-size: 10px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--muted);
    }
  `,
})
export class PendingScreen {
  readonly title = input.required<string>();
  readonly trail = input.required<readonly string[]>();
  readonly icon = input.required<'chat' | 'video' | 'share' | 'history' | 'bell' | 'users' | 'gear'>();
  readonly mockup = input('non maquettée');
  readonly note = input(
    'Cet écran est prévu : sa route et sa place dans la navigation sont posées, la page reste à construire.',
  );
}
