import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { NAVIGATION } from '../../core/data/navigation.data';
import { CURRENT_USER } from '../../core/data/users.data';
import { permissionSummary } from '../../core/models/user';
import { SidebarState } from '../../core/services/sidebar-state';
import { BrandLogo } from '../../shared/brand-logo/brand-logo';
import { Icon } from '../../shared/icon/icon';

/** Barre latérale — variante 5b : catégories repliables, repli en rail. */
@Component({
  selector: 'app-sidebar',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, RouterLinkActive, BrandLogo, Icon],
  templateUrl: './sidebar.html',
  styleUrl: './sidebar.scss',
})
export class Sidebar {
  protected readonly state = inject(SidebarState);
  protected readonly navigation = NAVIGATION;
  protected readonly user = CURRENT_USER;
  /** Pas de rôle dans IAGORA (F-22) : on résume les droits accordés. */
  protected readonly userSummary = permissionSummary(CURRENT_USER);
}
