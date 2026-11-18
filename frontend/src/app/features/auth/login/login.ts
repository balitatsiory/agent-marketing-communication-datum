import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { toApiError } from '../../../core/api/api-error';
import { Session } from '../../../core/services/session';
import { BrandLogo } from '../../../shared/brand-logo/brand-logo';

/**
 * Écran de connexion — maquette 2a, branchée sur `POST /auth/login`.
 *
 * Le bouton « Continuer avec Google » reste visible mais désactivé : la
 * connexion par fournisseur externe n'est pas au périmètre livré. La règle
 * d'interface du projet veut qu'on grise un élément plutôt que de le masquer,
 * pour que l'utilisateur sache qu'il existe et pourquoi il ne sert pas.
 */
@Component({
  selector: 'app-login',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, RouterLink, BrandLogo],
  templateUrl: './login.html',
  styleUrl: './login.scss',
})
export class Login {
  private readonly session = inject(Session);
  private readonly router = inject(Router);

  protected readonly email = signal('');
  protected readonly password = signal('');
  protected readonly enCours = signal(false);
  protected readonly erreur = signal<string | null>(null);

  protected async submit(): Promise<void> {
    if (this.enCours()) return;

    this.erreur.set(null);
    this.enCours.set(true);
    try {
      await this.session.signIn(this.email(), this.password());
      await this.router.navigate(['/tableau-de-bord']);
    } catch (cause) {
      this.erreur.set(toApiError(cause).message);
    } finally {
      this.enCours.set(false);
    }
  }
}
