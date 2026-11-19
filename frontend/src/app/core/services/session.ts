import { Injectable, computed, inject, signal } from '@angular/core';

import { AuthApi, Me } from '../api/auth.api';

/**
 * Clé du jeton de renouvellement dans le stockage local.
 *
 * Le jeton d'ACCÈS, lui, ne quitte jamais la mémoire : il expire en quinze
 * minutes et n'a donc pas besoin de survivre à un rechargement de page. Le
 * jeton de renouvellement doit y survivre, sans quoi fermer l'onglet
 * déconnecterait. C'est un compromis assumé : un script injecté pourrait le
 * lire, mais il pourrait de toute façon appeler l'API au nom de l'utilisateur.
 */
const CLE_RENOUVELLEMENT = 'iagora.refresh_token';

/**
 * Session de l'utilisateur, branchée sur l'API.
 *
 * Remplace la maquette qui acceptait n'importe quelle saisie.
 */
@Injectable({ providedIn: 'root' })
export class Session {
  private readonly api = inject(AuthApi);

  private readonly jetonDacces = signal<string | null>(null);
  private readonly profil = signal<Me | null>(null);
  private restauration: Promise<void> | null = null;

  readonly user = this.profil.asReadonly();
  readonly isSignedIn = computed(() => this.profil() !== null);
  readonly permissions = computed<readonly string[]>(() => this.profil()?.permissions ?? []);

  /** Nom affichable, ou chaîne vide si personne n'est connecté. */
  readonly fullName = computed(() => {
    const me = this.profil();
    return me ? `${me.first_name} ${me.last_name}` : '';
  });

  /** Initiales pour la pastille, faute de photo. */
  readonly initials = computed(() => {
    const me = this.profil();
    if (!me) return '';
    return `${me.first_name.charAt(0)}${me.last_name.charAt(0)}`.toUpperCase();
  });

  /** Jeton d'accès courant. Lu par l'intercepteur, pas par les écrans. */
  get token(): string | null {
    return this.jetonDacces();
  }

  /** L'utilisateur détient-il ce droit ? L'absence du code vaut refus. */
  has(code: string): boolean {
    return this.permissions().includes(code);
  }

  async signIn(email: string, password: string): Promise<void> {
    const jetons = await this.api.login(email, password);
    this.jetonDacces.set(jetons.access_token);
    this.enregistrerRenouvellement(jetons.refresh_token);
    this.profil.set(await this.api.me());
  }

  /**
   * Obtient un nouveau jeton d'accès. Renvoie `null` si la session est morte.
   *
   * Appelée par l'intercepteur sur une réponse 401, et au démarrage par
   * `restore()`. Le backend fait tourner le jeton de renouvellement à chaque
   * appel : il faut donc enregistrer celui qu'il renvoie, sinon le suivant
   * serait un rejeu et invaliderait toute la lignée.
   */
  async refresh(): Promise<string | null> {
    const renouvellement = this.lireRenouvellement();
    if (!renouvellement) return null;

    try {
      const jetons = await this.api.refresh(renouvellement);
      this.jetonDacces.set(jetons.access_token);
      this.enregistrerRenouvellement(jetons.refresh_token);
      return jetons.access_token;
    } catch {
      this.oublier();
      return null;
    }
  }

  /**
   * Rétablit la session au démarrage, une seule fois.
   *
   * Le garde de route l'attend : sans cela, un rechargement de page sur un
   * écran protégé renverrait sur la connexion alors que la session est valide.
   */
  restore(): Promise<void> {
    this.restauration ??= this.restaurer();
    return this.restauration;
  }

  private async restaurer(): Promise<void> {
    if (!(await this.refresh())) return;
    try {
      this.profil.set(await this.api.me());
    } catch {
      this.oublier();
    }
  }

  async signOut(): Promise<void> {
    const renouvellement = this.lireRenouvellement();
    // L'état local est vidé d'abord : la déconnexion ne doit pas dépendre de
    // la réussite de l'appel réseau.
    this.oublier();
    if (!renouvellement) return;
    try {
      await this.api.logout(renouvellement);
    } catch {
      // La session est fermée localement de toute façon.
    }
  }

  private oublier(): void {
    this.jetonDacces.set(null);
    this.profil.set(null);
    this.enregistrerRenouvellement(null);
  }

  private lireRenouvellement(): string | null {
    try {
      return localStorage.getItem(CLE_RENOUVELLEMENT);
    } catch {
      return null;
    }
  }

  private enregistrerRenouvellement(valeur: string | null): void {
    try {
      if (valeur === null) localStorage.removeItem(CLE_RENOUVELLEMENT);
      else localStorage.setItem(CLE_RENOUVELLEMENT, valeur);
    } catch {
      // Stockage indisponible (navigation privée stricte) : la session ne
      // survivra pas au rechargement, mais elle fonctionne.
    }
  }
}
