import { ChangeDetectionStrategy, Component, ElementRef, computed, inject, signal } from '@angular/core';
import { IsActiveMatchOptions, Router, RouterLink, RouterLinkActive } from '@angular/router';
import { NAVIGATION } from '../../core/data/navigation.data';
import { NavigationChild, NavigationEntry, NavigationLink } from '../../core/models/navigation';
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

  /**
   * « Voir les webinaires » ne s'allume que sur la liste : ses voisins
   * (`/webinaires/nouveau`, `/webinaires/comptes-zoom`) commencent par la même
   * adresse. Les paramètres, eux, n'éteignent pas l'entrée.
   */
  protected activeOptions(route: string): IsActiveMatchOptions {
    return {
      paths: route === '/webinaires' ? 'exact' : 'subset',
      queryParams: 'ignored',
      matrixParams: 'ignored',
      fragment: 'ignored',
    };
  }

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

  /**
   * Ce filtrage est un confort d'affichage, pas une sécurité : masquer une
   * entrée n'empêche pas d'appeler la route. La sécurité est au backend, qui
   * renvoie 403.
   */
  protected readonly navigation = computed<readonly NavigationEntry[]>(() => {
    const autorise = (lien: NavigationLink): boolean =>
      !lien.requiresPermission || this.session.has(lien.requiresPermission);

    const entrees: NavigationEntry[] = [];
    for (const entree of NAVIGATION) {
      if (entree.type === 'link') {
        if (autorise(entree)) entrees.push(entree);
        continue;
      }

      const enfants: NavigationChild[] = [];
      for (const enfant of entree.items) {
        if (enfant.kind === 'link') {
          if (autorise(enfant)) enfants.push(enfant);
          continue;
        }
        const feuilles = enfant.items.filter(autorise);
        if (feuilles.length > 0) {
          enfants.push({ ...enfant, items: feuilles });
        }
      }

      if (enfants.length > 0) {
        entrees.push({ ...entree, items: enfants });
      }
    }
    return entrees;
  });

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
