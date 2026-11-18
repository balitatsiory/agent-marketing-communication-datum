import { ChangeDetectionStrategy, Component, ElementRef, inject, signal } from '@angular/core';
import { Router, RouterLink, RouterLinkActive } from '@angular/router';
import { NAVIGATION } from '../../core/data/navigation.data';
import { Session } from '../../core/services/session';
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
  host: {
    '(document:click)': 'auClicDocument($event)',
    '(document:keydown.escape)': 'fermerMenu()',
  },
})
export class Sidebar {
  protected readonly state = inject(SidebarState);
  protected readonly navigation = NAVIGATION;

  private readonly hote = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly router = inject(Router);
  /**
   * Session réelle : le pied de barre affiche la personne connectée.
   *
   * La ligne sous le nom portait un résumé des droits. Elle porte l'adresse,
   * parce que traduire un code de droit en libellé demande le référentiel, que
   * `GET /permissions` réserve aux administrateurs : un compte sans droit
   * d'administration verrait une ligne vide.
   */
  protected readonly session = inject(Session);

  /** Menu du compte, ouvert depuis le bouton du pied de barre. */
  protected readonly menuOuvert = signal(false);

  protected basculerMenu(): void {
    this.menuOuvert.update((ouvert) => !ouvert);
  }

  protected fermerMenu(): void {
    this.menuOuvert.set(false);
  }

  /**
   * Referme le menu dès qu'on clique ailleurs.
   *
   * L'écoute est posée sur le document, pas sur un voile transparent :
   * un clic hors du menu doit atteindre ce qu'il vise, pas être avalé
   * pour seulement refermer.
   */
  protected auClicDocument(evenement: Event): void {
    if (!this.menuOuvert()) return;
    const pied = this.hote.nativeElement.querySelector('.sb-foot');
    if (pied?.contains(evenement.target as Node)) return;
    this.fermerMenu();
  }

  /** Ferme la session, puis renvoie sur l'écran de connexion. */
  protected seDeconnecter(): void {
    this.fermerMenu();
    // signOut vide l'état local avant d'appeler l'API : on peut naviguer tout
    // de suite, sans attendre la révocation côté serveur.
    void this.session.signOut();
    void this.router.navigate(['/connexion']);
  }
}
