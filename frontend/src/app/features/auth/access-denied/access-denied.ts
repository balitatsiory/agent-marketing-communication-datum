import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink } from '@angular/router';

import { Topbar } from '../../../layout/topbar/topbar';
import { Icon } from '../../../shared/icon/icon';

/**
 * Écran d'accès refusé.
 *
 * N'affiche jamais le code technique du droit manquant : l'identifiant interne
 * d'une permission appartient au schéma de base et non au vocabulaire métier.
 */
@Component({
  selector: 'app-access-denied',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, Topbar, Icon],
  templateUrl: './access-denied.html',
  styleUrl: './access-denied.scss',
})
export class AccessDenied {}
