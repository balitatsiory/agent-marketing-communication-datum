import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { NavigationEnd, Router, RouterOutlet } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { filter } from 'rxjs';
import { SidebarState } from '../../core/services/sidebar-state';
import { Sidebar } from '../sidebar/sidebar';

/**
 * Coquille applicative : barre latérale fixe, écran courant à droite.
 *
 * Chaque écran apporte sa propre barre du haut, d'où l'absence de
 * `<app-topbar>` ici.
 */
@Component({
  selector: 'app-shell',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterOutlet, Sidebar],
  template: `
    <div class="app">
      <app-sidebar />
      <div class="main">
        <router-outlet />
      </div>
    </div>
  `,
  styles: `
    .app { display: flex; height: 100vh; overflow: hidden; }

    .main {
      flex: 1;
      min-width: 0;
      display: flex;
      flex-direction: column;
      background: var(--ground);
    }
  `,
})
export class AppShell {
  private readonly router = inject(Router);
  private readonly sidebar = inject(SidebarState);

  constructor() {
    // Arriver par une URL directe ne doit pas laisser l'entrée active
    // cachée dans une catégorie fermée.
    this.router.events
      .pipe(
        filter((event): event is NavigationEnd => event instanceof NavigationEnd),
        takeUntilDestroyed(),
      )
      .subscribe((event) => this.sidebar.revealRoute(event.urlAfterRedirects));

    this.sidebar.revealRoute(this.router.url);
  }
}
