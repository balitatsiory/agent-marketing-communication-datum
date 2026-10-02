import { Injectable, computed, signal } from '@angular/core';
import { CURRENT_USER } from '../data/users.data';
import { User } from '../models/user';

/**
 * Session de l'utilisateur — maquette d'authentification.
 *
 * Aucun jeton, aucun appel réseau : l'écran de connexion sert à valider
 * le parcours, pas à protéger quoi que ce soit. À remplacer par
 * `POST /api/v1/auth/login` et le garde de route qui va avec.
 */
@Injectable({ providedIn: 'root' })
export class Session {
  private readonly current = signal<User | null>(null);

  readonly user = this.current.asReadonly();
  readonly isSignedIn = computed(() => this.current() !== null);

  /** Ouvre la session. Toute saisie est acceptée, puisque rien n'est vérifié. */
  signIn(): void {
    this.current.set(CURRENT_USER);
  }

  signOut(): void {
    this.current.set(null);
  }
}
