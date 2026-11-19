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
  permissionSummary,
  toPermission,
  toUserView,
} from '../../../core/models/user';
import { Session } from '../../../core/services/session';
import { Topbar } from '../../../layout/topbar/topbar';
import { Icon } from '../../../shared/icon/icon';

/** Filtres de la liste de comptes, calqués sur les trois états réels. */
type AccountFilter = 'tous' | 'actifs' | 'suspendus' | 'archives';

const FILTER_LABELS: Readonly<Record<AccountFilter, string>> = {
  tous: 'Tous',
  actifs: 'Actifs',
  suspendus: 'Suspendus',
  archives: 'Archivés',
};

/**
 * Une seule page suffit : l'équipe de DATUM Academy compte quelques dizaines
 * de personnes. Le jour où ce n'est plus vrai, l'API pagine déjà — seul cet
 * écran est à reprendre.
 */
const TAILLE_PAGE = 200;

/** Longueur minimale imposée par le backend (`MotDePasse`, `min_length=10`). */
const MOT_DE_PASSE_MIN = 10;

interface BrouillonDeCompte {
  email: string;
  first_name: string;
  last_name: string;
  password: string;
}

type ChampCreation = keyof BrouillonDeCompte;

const COMPTE_VIDE: BrouillonDeCompte = { email: '', first_name: '', last_name: '', password: '' };
const FORMAT_EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/**
 * Habilitations et utilisateurs — F-22, branché sur l'API.
 *
 * **Écart assumé par rapport à la maquette fournie.** Celle-ci montrait un
 * rôle, un bouton « Changer de rôle » et une colonne « hérité du rôle » avec
 * des exceptions. Le cahier des charges dit le contraire : « Aucun rôle n'est
 * figé dans le code : un administrateur attribue les droits » (F-22). Il n'y a
 * donc rien à hériter, et chaque droit se coche compte par compte.
 *
 * **Trois écarts supplémentaires, par rapport à la version sur jeu d'essai.**
 * La connexion déléguée Google, le double facteur et le statut « invitation
 * envoyée » ont disparu : aucun des trois n'existe dans l'API ni dans le
 * cahier des charges. La réinitialisation par courriel est remplacée par la
 * définition directe d'un mot de passe, seule opération que l'API expose. Le
 * journal des modifications attend le module 14 « Activité » : la table
 * `user_permissions` conserve déjà l'historique, mais aucune route ne le lit
 * encore.
 *
 * **Le catalogue des droits n'est pas écrit ici** : il est lu par
 * `GET /api/v1/permissions`, parce que la table `permissions` est alimentée
 * module par module. Cet écran affiche donc les droits existants, quels
 * qu'ils soient, sans connaître leur liste.
 */
@Component({
  selector: 'app-user-list',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [Topbar, Icon],
  templateUrl: './user-list.html',
  styleUrl: './user-list.scss',
  host: {
    '(document:keydown.escape)': 'fermerCreation()',
  },
})
export class UserList {
  private readonly api = inject(UsersApi);
  private readonly session = inject(Session);
  private readonly premierChampCreation =
    viewChild<ElementRef<HTMLInputElement>>('premierChampCreation');

  protected readonly filterLabels = FILTER_LABELS;
  protected readonly filters: readonly AccountFilter[] = [
    'tous',
    'actifs',
    'suspendus',
    'archives',
  ];
  protected readonly statusLabels = ACCOUNT_STATUS_LABELS;
  protected readonly motDePasseMin = MOT_DE_PASSE_MIN;

  private readonly comptes = signal<readonly UserView[]>([]);
  protected readonly catalogue = signal<readonly Permission[]>([]);

  protected readonly chargement = signal(true);
  protected readonly enCours = signal(false);
  protected readonly erreur = signal<string | null>(null);
  protected readonly avis = signal<string | null>(null);

  protected readonly filtre = signal<AccountFilter>('tous');
  protected readonly recherche = signal('');
  private readonly selectionId = signal<number | null>(null);

  /**
   * Droits en cours d'édition.
   *
   * Séparés des droits enregistrés : tant que « Enregistrer » n'est pas
   * actionné, rien n'est acquis, et l'écran doit pouvoir le montrer.
   */
  private readonly brouillon = signal<ReadonlySet<string>>(new Set());

  /** Panneaux ouverts à la demande, pour ne pas charger l'écran. */
  protected readonly creationOuverte = signal(false);
  protected readonly nouveauCompte = signal<BrouillonDeCompte>({ ...COMPTE_VIDE });
  private readonly champsTouches = signal<ReadonlySet<ChampCreation>>(new Set());
  protected readonly motDePasseOuvert = signal(false);
  protected readonly nouveauMotDePasse = signal('');
  protected readonly archivageDemande = signal(false);

  /**
   * Droits de la personne connectée.
   *
   * `manage_permissions` est distinct de `manage_users` : attribuer un droit
   * est la seule action permettant une élévation de privilèges, et elle se
   * concède séparément. L'écran grise les interrupteurs en conséquence.
   */
  protected readonly peutGererLesComptes = computed(() => this.session.has('manage_users'));
  protected readonly peutAttribuerDesDroits = computed(() =>
    this.session.has('manage_permissions'),
  );

  constructor() {
    effect(() => {
      if (!this.creationOuverte()) {
        this.champsTouches.set(new Set());
      }
      this.premierChampCreation()?.nativeElement.focus();
    });
    void this.charger();
  }

  // ----------------------------------------------------------------- lecture

  protected readonly compteurs = computed<Readonly<Record<AccountFilter, number>>>(() => {
    const tous = this.comptes();
    return {
      tous: tous.length,
      actifs: tous.filter((compte) => compte.status === 'active').length,
      suspendus: tous.filter((compte) => compte.status === 'suspended').length,
      archives: tous.filter((compte) => compte.status === 'archived').length,
    };
  });

  protected readonly resultats = computed<readonly UserView[]>(() => {
    const filtre = this.filtre();
    const terme = this.recherche().trim().toLowerCase();

    return this.comptes().filter((compte) => {
      if (filtre === 'actifs' && compte.status !== 'active') return false;
      if (filtre === 'suspendus' && compte.status !== 'suspended') return false;
      if (filtre === 'archives' && compte.status !== 'archived') return false;
      if (!terme) return true;
      return (
        compte.fullName.toLowerCase().includes(terme) ||
        compte.email.toLowerCase().includes(terme)
      );
    });
  });

  /**
   * Compte ouvert dans le panneau de détail.
   *
   * Volontairement indépendant des filtres : filtrer la liste ne doit pas
   * refermer le détail en cours, et surtout pas lui substituer un autre compte
   * alors que le brouillon de droits, lui, n'aurait pas suivi.
   */
  protected readonly selection = computed<UserView | null>(
    () => this.comptes().find((compte) => compte.idUsers === this.selectionId()) ?? null,
  );

  /** Résumé des droits affiché sous le nom, dans la liste. */
  protected resume(compte: UserView): string {
    return permissionSummary(compte, this.catalogue());
  }

  /** Nombre de droits cochés ou décochés sans être encore enregistrés. */
  protected readonly modifie = computed(() => {
    const compte = this.selection();
    if (!compte) return 0;

    const brouillon = this.brouillon();
    const enregistres = new Set(compte.permissions);
    const codes = new Set([
      ...this.catalogue().map((droit) => droit.code),
      ...compte.permissions,
    ]);
    return [...codes].filter((code) => brouillon.has(code) !== enregistres.has(code)).length;
  });

  protected readonly aDesModifications = computed(() => this.modifie() > 0);

  protected readonly motDePasseValide = computed(
    () => this.nouveauMotDePasse().length >= MOT_DE_PASSE_MIN,
  );

  protected readonly erreurMotDePasse = computed<string | null>(() => {
    const mdp = this.nouveauMotDePasse();
    if (mdp.length === 0 || mdp.length >= MOT_DE_PASSE_MIN) return null;
    return `Mot de passe trop court (${mdp.length} / ${MOT_DE_PASSE_MIN} caractères minimum).`;
  });

  protected readonly nouveauCompteValide = computed(() => {
    const brouillon = this.nouveauCompte();
    return (
      brouillon.email.includes('@') &&
      brouillon.first_name.trim().length > 0 &&
      brouillon.last_name.trim().length > 0 &&
      brouillon.password.length >= MOT_DE_PASSE_MIN
    );
  });

  protected readonly erreursCreation = computed<
    Readonly<Record<ChampCreation, string | null>>
  >(() => {
    const b = this.nouveauCompte();
    const touches = this.champsTouches();

    const prenom =
      touches.has('first_name') || b.first_name.length > 0
        ? b.first_name.trim().length === 0
          ? 'Le prénom est obligatoire.'
          : null
        : null;

    const nom =
      touches.has('last_name') || b.last_name.length > 0
        ? b.last_name.trim().length === 0
          ? 'Le nom est obligatoire.'
          : null
        : null;

    let email: string | null = null;
    const emailSaisi = b.email.trim();
    if (emailSaisi.length > 0) {
      if (!FORMAT_EMAIL.test(emailSaisi)) {
        email = 'Adresse électronique invalide (exemple : nom@domaine.org).';
      } else if (
        this.comptes().some((c) => c.email.toLowerCase() === emailSaisi.toLowerCase())
      ) {
        email = 'Cette adresse électronique est déjà utilisée.';
      }
    } else if (touches.has('email')) {
      email = "L'adresse électronique est obligatoire.";
    }

    let password: string | null = null;
    if (b.password.length > 0 && b.password.length < MOT_DE_PASSE_MIN) {
      password = `Mot de passe trop court (${b.password.length} / ${MOT_DE_PASSE_MIN} caractères minimum).`;
    } else if (touches.has('password') && b.password.length === 0) {
      password = 'Le mot de passe initial est obligatoire.';
    }

    return {
      first_name: prenom,
      last_name: nom,
      email,
      password,
    };
  });

  protected marquerTouche(champ: ChampCreation): void {
    this.champsTouches.update((courant) => {
      if (courant.has(champ)) return courant;
      const suivant = new Set(courant);
      suivant.add(champ);
      return suivant;
    });
  }

  // ------------------------------------------------------------- chargement

  private async charger(): Promise<void> {
    this.chargement.set(true);
    this.erreur.set(null);
    try {
      // Les comptes archivés sont demandés dès le départ : le filtre
      // « Archivés » doit pouvoir les montrer sans second appel.
      const [page, droits] = await Promise.all([
        this.api.list({ page: 1, size: TAILLE_PAGE }, true),
        this.api.permissions(),
      ]);
      this.catalogue.set(droits.map(toPermission));
      this.poser(page.items.map(toUserView));
    } catch (erreur) {
      this.erreur.set(toApiError(erreur).message);
    } finally {
      this.chargement.set(false);
    }
  }

  private poser(vues: readonly UserView[]): void {
    this.comptes.set(vues);
    const retenu = vues.find((vue) => vue.idUsers === this.selectionId()) ?? vues[0] ?? null;
    this.selectionId.set(retenu?.idUsers ?? null);
    this.brouillon.set(new Set(retenu?.permissions ?? []));
  }

  private remplacer(vue: UserView): void {
    this.comptes.update((courant) =>
      courant.map((compte) => (compte.idUsers === vue.idUsers ? vue : compte)),
    );
  }

  /**
   * Enchaîne une action sur l'API en tenant l'écran informé.
   *
   * Un seul geste à la fois : deux enregistrements concurrents sur le même
   * compte laisseraient l'écran afficher l'état du plus lent.
   */
  private async agir(action: () => Promise<void>): Promise<void> {
    if (this.enCours()) return;
    this.enCours.set(true);
    this.erreur.set(null);
    try {
      await action();
    } catch (erreur) {
      this.erreur.set(toApiError(erreur).message);
    } finally {
      this.enCours.set(false);
    }
  }

  // ---------------------------------------------------------------- gestes

  protected selectionner(compte: UserView): void {
    this.selectionId.set(compte.idUsers);
    this.brouillon.set(new Set(compte.permissions));
    this.reinitialiserLesPanneaux();
  }

  private reinitialiserLesPanneaux(): void {
    this.avis.set(null);
    this.erreur.set(null);
    this.motDePasseOuvert.set(false);
    this.nouveauMotDePasse.set('');
    this.archivageDemande.set(false);
  }

  protected accorde(code: string): boolean {
    return this.brouillon().has(code);
  }

  /** Vrai quand ce droit a été modifié sans être encore enregistré. */
  protected enAttente(code: string): boolean {
    const compte = this.selection();
    if (!compte) return false;
    return this.brouillon().has(code) !== compte.permissions.includes(code);
  }

  protected basculer(code: string): void {
    if (!this.peutAttribuerDesDroits()) return;
    this.brouillon.update((courant) => {
      const suivant = new Set(courant);
      if (!suivant.delete(code)) suivant.add(code);
      return suivant;
    });
    this.avis.set(null);
  }

  protected annuler(): void {
    const compte = this.selection();
    if (compte) this.brouillon.set(new Set(compte.permissions));
    this.avis.set(null);
  }

  protected async enregistrer(): Promise<void> {
    const compte = this.selection();
    if (!compte || this.modifie() === 0) return;

    // L'ordre du catalogue est repris : l'API accepte n'importe quel ordre,
    // mais une requête reproductible se relit plus facilement dans les journaux.
    const brouillon = this.brouillon();
    const codes = this.catalogue()
      .map((droit) => droit.code)
      .filter((code) => brouillon.has(code));

    await this.agir(async () => {
      const accordes = await this.api.setPermissions(compte.idUsers, codes);
      this.remplacer({ ...compte, permissions: accordes });
      this.brouillon.set(new Set(accordes));
      this.avis.set(
        accordes.length === 0
          ? 'Tous les droits ont été retirés. Les attributions restent archivées.'
          : `Droits enregistrés : ${accordes.length} au total.`,
      );
    });
  }

  protected async basculerActivation(): Promise<void> {
    const compte = this.selection();
    if (!compte || compte.status === 'archived') return;
    const activer = compte.status !== 'active';

    await this.agir(async () => {
      const dto = await this.api.update(compte.idUsers, { is_active: activer });
      this.remplacer(toUserView(dto));
      this.avis.set(
        activer
          ? 'Compte réactivé.'
          : "Compte suspendu. Son jeton d'accès reste valide au plus un quart d'heure, puis tout lui est refusé.",
      );
    });
  }

  protected demanderArchivage(): void {
    this.avis.set(null);
    this.archivageDemande.set(true);
  }

  protected renoncerArchivage(): void {
    this.archivageDemande.set(false);
  }

  protected async archiver(): Promise<void> {
    const compte = this.selection();
    if (!compte || compte.status === 'archived') return;

    await this.agir(async () => {
      await this.api.archive(compte.idUsers);
      this.archivageDemande.set(false);
      // La route renvoie 204 : l'état archivé est reconstruit localement
      // plutôt que relu, pour ne pas enchaîner un second appel.
      this.remplacer({ ...compte, status: 'archived' });
      this.avis.set(
        `${compte.fullName} est archivé. Le compte reste l'auteur de ses publications passées, et ses sessions ont été révoquées.`,
      );
    });
  }

  protected async definirMotDePasse(): Promise<void> {
    const compte = this.selection();
    if (!compte || !this.motDePasseValide()) return;

    await this.agir(async () => {
      await this.api.setPassword(compte.idUsers, this.nouveauMotDePasse());
      this.motDePasseOuvert.set(false);
      this.nouveauMotDePasse.set('');
      this.avis.set(
        `Mot de passe remplacé pour ${compte.email}. Aucun courriel n'est envoyé : il faut le lui transmettre.`,
      );
    });
  }

  protected majNouveauCompte(champ: keyof BrouillonDeCompte, valeur: string): void {
    this.nouveauCompte.update((courant) => ({ ...courant, [champ]: valeur }));
  }

  protected ouvrirCreation(): void {
    this.nouveauCompte.set({ ...COMPTE_VIDE });
    this.erreur.set(null);
    this.avis.set(null);
    this.creationOuverte.set(true);
  }

  protected fermerCreation(): void {
    this.creationOuverte.set(false);
  }

  protected async creer(): Promise<void> {
    if (!this.nouveauCompteValide()) return;
    const brouillon = this.nouveauCompte();

    await this.agir(async () => {
      const dto = await this.api.create({
        email: brouillon.email.trim(),
        password: brouillon.password,
        first_name: brouillon.first_name.trim(),
        last_name: brouillon.last_name.trim(),
      });
      const vue = toUserView(dto);
      this.creationOuverte.set(false);
      this.nouveauCompte.set({ ...COMPTE_VIDE });
      this.selectionId.set(vue.idUsers);
      // La liste est relue plutôt que complétée sur place : son ordre est
      // celui du backend (nom, puis prénom), et le reproduire ici serait une
      // règle de tri en double, donc une divergence en puissance.
      await this.charger();
      this.avis.set(
        `${vue.fullName} est créé, sans aucun droit. Cocher ci-dessous ce qu'il peut faire.`,
      );
    });
  }

  protected recharger(): void {
    void this.charger();
  }
}
