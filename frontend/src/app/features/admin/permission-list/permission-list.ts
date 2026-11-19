import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  computed,
  effect,
  inject,
  signal,
  viewChild,
} from '@angular/core';

import { toApiError } from '../../../core/api/api-error';
import { UsersApi } from '../../../core/api/users.api';
import {
  ACCOUNT_STATUS_LABELS,
  Permission,
  UserView,
  toPermission,
  toUserView,
} from '../../../core/models/user';
import { Session } from '../../../core/services/session';
import { Topbar } from '../../../layout/topbar/topbar';
import { Icon } from '../../../shared/icon/icon';

const TAILLE_PAGE = 200;

interface DroitAvecDetenteurs extends Permission {
  readonly detenteurs: readonly UserView[];
}

/**
 * Référentiel des droits.
 *
 * **Avertissement.** La table `permissions` ne contient aujourd'hui que deux
 * droits, `manage_users` et `manage_permissions`. L'écran paraîtra vide, et
 * c'est normal : chaque module suivant insère les siens par migration. Ne pas
 * combler ce vide avec des droits inventés.
 *
 * **Calcul et attribution côté client.** Le backend n'expose ni
 * `GET /permissions/{code}/users` ni `PUT /permissions/{code}/users`. Les
 * détenteurs d'un droit sont obtenus en croisant `UsersApi.permissions()` et
 * `UsersApi.list({ page: 1, size: 200 }, true)`. L'attribution par sélection
 * multiple complète les droits existants de chaque compte choisi et appelle
 * `UsersApi.setPermissions(idUsers, codes)` pour chacun.
 */
@Component({
  selector: 'app-permission-list',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [Topbar, Icon],
  templateUrl: './permission-list.html',
  styleUrl: './permission-list.scss',
  host: {
    '(document:keydown.escape)': 'fermerDetenteurs()',
  },
})
export class PermissionList {
  private readonly api = inject(UsersApi);
  private readonly session = inject(Session);
  private readonly boutonFermer = viewChild<ElementRef<HTMLButtonElement>>('boutonFermer');

  protected readonly statusLabels = ACCOUNT_STATUS_LABELS;

  private readonly catalogue = signal<readonly Permission[]>([]);
  private readonly comptes = signal<readonly UserView[]>([]);

  protected readonly chargement = signal(true);
  protected readonly enCours = signal(false);
  protected readonly erreur = signal<string | null>(null);
  protected readonly erreurAction = signal<string | null>(null);
  protected readonly avis = signal<string | null>(null);

  private readonly codeOuvert = signal<string | null>(null);
  protected readonly rechercheCandidat = signal('');
  protected readonly selectionIds = signal<ReadonlySet<number>>(new Set());

  protected readonly peutAttribuerDesDroits = computed(() =>
    this.session.has('manage_permissions'),
  );

  protected readonly droits = computed<readonly DroitAvecDetenteurs[]>(() => {
    const comptes = this.comptes();
    return [...this.catalogue()]
      .sort((a, b) => a.sortOrder - b.sortOrder)
      .map((droit) => ({
        ...droit,
        detenteurs: comptes.filter((compte) => compte.permissions.includes(droit.code)),
      }));
  });

  protected readonly droitOuvert = computed<DroitAvecDetenteurs | null>(
    () => this.droits().find((droit) => droit.code === this.codeOuvert()) ?? null,
  );

  /**
   * Comptes éligibles à l'attribution du droit ouvert : non archivés et ne
   * détenant pas encore ce droit.
   */
  protected readonly candidatsEligibles = computed<readonly UserView[]>(() => {
    const droit = this.droitOuvert();
    if (!droit) return [];
    return this.comptes().filter(
      (compte) => compte.status !== 'archived' && !compte.permissions.includes(droit.code),
    );
  });

  protected readonly candidatsFiltres = computed<readonly UserView[]>(() => {
    const terme = this.rechercheCandidat().trim().toLowerCase();
    const candidats = this.candidatsEligibles();
    if (!terme) return candidats;
    return candidats.filter(
      (compte) =>
        compte.fullName.toLowerCase().includes(terme) ||
        compte.email.toLowerCase().includes(terme),
    );
  });

  protected readonly comptesSelectionnes = computed<readonly UserView[]>(() => {
    const ids = this.selectionIds();
    return this.candidatsEligibles().filter((compte) => ids.has(compte.idUsers));
  });

  protected readonly toutEstSelectionne = computed(() => {
    const filtres = this.candidatsFiltres();
    if (filtres.length === 0) return false;
    const ids = this.selectionIds();
    return filtres.every((compte) => ids.has(compte.idUsers));
  });

  constructor() {
    effect(() => {
      this.boutonFermer()?.nativeElement.focus();
    });
    void this.charger();
  }

  private async charger(): Promise<void> {
    this.chargement.set(true);
    this.erreur.set(null);
    try {
      const [droits, page] = await Promise.all([
        this.api.permissions(),
        this.api.list({ page: 1, size: TAILLE_PAGE }, true),
      ]);
      this.catalogue.set(droits.map(toPermission));
      this.comptes.set(page.items.map(toUserView));
    } catch (erreur) {
      this.erreur.set(toApiError(erreur).message);
    } finally {
      this.chargement.set(false);
    }
  }

  protected ouvrirDetenteurs(code: string): void {
    this.codeOuvert.set(code);
    this.rechercheCandidat.set('');
    this.selectionIds.set(new Set());
    this.erreurAction.set(null);
    this.avis.set(null);
  }

  protected fermerDetenteurs(): void {
    this.codeOuvert.set(null);
    this.rechercheCandidat.set('');
    this.selectionIds.set(new Set());
    this.erreurAction.set(null);
    this.avis.set(null);
  }

  protected estSelectionne(idUsers: number): boolean {
    return this.selectionIds().has(idUsers);
  }

  protected basculerSelection(idUsers: number): void {
    if (!this.peutAttribuerDesDroits() || this.enCours()) return;
    this.selectionIds.update((courant) => {
      const suivant = new Set(courant);
      if (!suivant.delete(idUsers)) suivant.add(idUsers);
      return suivant;
    });
    this.avis.set(null);
  }

  protected basculerTout(): void {
    if (!this.peutAttribuerDesDroits() || this.enCours()) return;
    const filtres = this.candidatsFiltres();
    const toutCocher = !this.toutEstSelectionne();
    this.selectionIds.update((courant) => {
      const suivant = new Set(courant);
      for (const compte of filtres) {
        if (toutCocher) suivant.add(compte.idUsers);
        else suivant.delete(compte.idUsers);
      }
      return suivant;
    });
    this.avis.set(null);
  }

  protected async attribuerSelection(): Promise<void> {
    const droit = this.droitOuvert();
    const cibles = this.comptesSelectionnes();
    if (!droit || cibles.length === 0 || !this.peutAttribuerDesDroits() || this.enCours()) return;

    this.enCours.set(true);
    this.erreurAction.set(null);
    this.avis.set(null);
    try {
      const ordreCatalogue = this.catalogue().map((d) => d.code);
      const misesAJour = await Promise.all(
        cibles.map(async (compte) => {
          const ensemble = new Set([...compte.permissions, droit.code]);
          const codes = ordreCatalogue.filter((code) => ensemble.has(code));
          const accordes = await this.api.setPermissions(compte.idUsers, codes);
          return { idUsers: compte.idUsers, permissions: accordes };
        }),
      );

      const parId = new Map(misesAJour.map((m) => [m.idUsers, m.permissions]));
      this.comptes.update((courants) =>
        courants.map((compte) => {
          const permissions = parId.get(compte.idUsers);
          return permissions ? { ...compte, permissions } : compte;
        }),
      );
      this.selectionIds.set(new Set());
      this.rechercheCandidat.set('');
      this.avis.set(
        cibles.length === 1
          ? `Droit attribué à ${cibles[0].fullName}.`
          : `Droit attribué à ${cibles.length} comptes.`,
      );
    } catch (erreur) {
      this.erreurAction.set(toApiError(erreur).message);
    } finally {
      this.enCours.set(false);
    }
  }

  protected async retirerDroit(compte: UserView): Promise<void> {
    const droit = this.droitOuvert();
    if (!droit || compte.status === 'archived' || !this.peutAttribuerDesDroits() || this.enCours()) {
      return;
    }

    this.enCours.set(true);
    this.erreurAction.set(null);
    this.avis.set(null);
    try {
      const codes = compte.permissions.filter((code) => code !== droit.code);
      const accordes = await this.api.setPermissions(compte.idUsers, codes);
      this.comptes.update((courants) =>
        courants.map((c) => (c.idUsers === compte.idUsers ? { ...c, permissions: accordes } : c)),
      );
      this.avis.set(`Droit retiré à ${compte.fullName}.`);
    } catch (erreur) {
      this.erreurAction.set(toApiError(erreur).message);
    } finally {
      this.enCours.set(false);
    }
  }

  protected recharger(): void {
    void this.charger();
  }
}
