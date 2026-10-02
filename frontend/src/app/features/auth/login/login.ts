import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { Session } from '../../../core/services/session';
import { BrandLogo } from '../../../shared/brand-logo/brand-logo';

/**
 * Écran de connexion — maquette 2a.
 *
 * Rien n'est vérifié : la session s'ouvre sur n'importe quelle saisie.
 * Voir `Session` pour ce qu'il restera à brancher.
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

  protected readonly email = signal('sarah.lemoine@datum-academy.fr');
  protected readonly password = signal('prototype');

  protected submit(): void {
    this.session.signIn();
    void this.router.navigate(['/tableau-de-bord']);
  }
}
