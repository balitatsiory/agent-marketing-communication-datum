import { ChangeDetectionStrategy, Component, computed, signal } from '@angular/core';
import { ACCOUNT_CHANGES, USERS } from '../../../core/data/users.data';
import {
  ACCOUNT_CHANGE_KIND_LABELS,
  ACCOUNT_STATUS_LABELS,
  AUTH_METHOD_LABELS,
  AccountChange,
  PERMISSION_DESCRIPTIONS,
  PERMISSION_LABELS,
  PERMISSION_ORDER,
  PermissionCode,
  User,
  permissionSummary,
} from '../../../core/models/user';
import { Topbar } from '../../../layout/topbar/topbar';
import { Icon } from '../../../shared/icon/icon';

/** Filtres de la liste de comptes. */
type AccountFilter = 'all' | 'admins' | 'invited' | 'disabled';

const FILTER_LABELS: Readonly<Record<AccountFilter, string>> = {
  all: 'Tous',
  admins: 'Administrateurs',
  invited: 'Invités',
  disabled: 'Désactivés',
};

/**
 * Habilitations et utilisateurs — F-22.
 *
 * Trois colonnes : la liste des comptes, le détail du compte ouvert, et
 * le journal de ses modifications.
 *
 * **Écart assumé par rapport à la maquette fournie.** Celle-ci montrait un
 * rôle, un bouton « Changer de rôle » et une colonne « hérité du rôle »
 * avec des exceptions. Le cahier des charges dit le contraire : « Aucun
 * rôle n'est figé dans le code : un administrateur attribue les droits »
 * (F-22). Il n'y a donc rien à hériter, et chaque droit se coche compte
 * par compte. Le reste de la maquette est repris tel quel.
 */
@Component({
  selector: 'app-user-list',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [Topbar, Icon],
  templateUrl: './user-list.html',
  styleUrl: './user-list.scss',
})
export class UserList {
  protected readonly filterLabels = FILTER_LABELS;
  protected readonly filters: readonly AccountFilter[] = ['all', 'admins', 'invited', 'disabled'];

  protected readonly permissionOrder = PERMISSION_ORDER;
  protected readonly permissionLabels = PERMISSION_LABELS;
  protected readonly permissionDescriptions = PERMISSION_DESCRIPTIONS;
  protected readonly statusLabels = ACCOUNT_STATUS_LABELS;
  protected readonly authMethodLabels = AUTH_METHOD_LABELS;
  protected readonly changeKindLabels = ACCOUNT_CHANGE_KIND_LABELS;

  private readonly all = signal<readonly User[]>(USERS);
  private readonly changes = signal<readonly AccountChange[]>(ACCOUNT_CHANGES);

  protected readonly filter = signal<AccountFilter>('all');
  protected readonly searchTerm = signal('');
  private readonly selectedId = signal(USERS[0].id);

  /**
   * Droits en cours d'édition.
   *
   * Séparés du compte enregistré : tant que « Enregistrer » n'est pas
   * actionné, rien n'est acquis, et l'écran doit pouvoir le montrer.
   */
  private readonly draft = signal<ReadonlySet<PermissionCode>>(new Set(USERS[0].permissions));

  protected readonly counts = computed(() => {
    const users = this.all();
    return {
      all: users.length,
      admins: users.filter((user) => user.permissions.includes('admin')).length,
      invited: users.filter((user) => user.status === 'invited').length,
      disabled: users.filter((user) => user.status === 'disabled').length,
    };
  });

  protected readonly results = computed<readonly User[]>(() => {
    const filter = this.filter();
    const term = this.searchTerm().trim().toLowerCase();

    return this.all().filter((user) => {
      if (filter === 'admins' && !user.permissions.includes('admin')) return false;
      if (filter === 'invited' && user.status !== 'invited') return false;
      if (filter === 'disabled' && user.status !== 'disabled') return false;
      if (!term) return true;
      return (
        user.fullName.toLowerCase().includes(term) || user.email.toLowerCase().includes(term)
      );
    });
  });

  /** Compte ouvert. Bascule sur le premier de la liste si un filtre le masque. */
  protected readonly selected = computed<User | null>(() => {
    const results = this.results();
    if (results.length === 0) return null;
    return results.find((user) => user.id === this.selectedId()) ?? results[0];
  });

  protected readonly summaryOf = permissionSummary;

  /** Journal du compte ouvert, du plus récent au plus ancien. */
  protected readonly selectedChanges = computed<readonly AccountChange[]>(() => {
    const user = this.selected();
    if (!user) return [];
    return this.changes().filter((change) => change.userId === user.id);
  });

  /** Vrai si le brouillon diffère des droits enregistrés. */
  protected readonly hasPendingChanges = computed(() => {
    const user = this.selected();
    if (!user) return false;
    const draft = this.draft();
    return (
      draft.size !== user.permissions.length ||
      user.permissions.some((code) => !draft.has(code))
    );
  });

  /** Droits ajoutés ou retirés par rapport à l'enregistré. */
  protected readonly pendingCount = computed(() => {
    const user = this.selected();
    if (!user) return 0;
    const draft = this.draft();
    const saved = new Set(user.permissions);
    return PERMISSION_ORDER.filter((code) => draft.has(code) !== saved.has(code)).length;
  });

  /**
   * Un compte sur SSO n'a pas de mot de passe à réinitialiser, et un compte
   * en attente d'invitation n'en a pas encore.
   */
  protected readonly canResetPassword = computed(() => {
    const user = this.selected();
    return user !== null && user.authMethod === 'password' && user.status !== 'invited';
  });

  protected readonly resetPasswordHint = computed(() => {
    const user = this.selected();
    if (!user) return '';
    if (user.authMethod === 'google') return 'Connexion par Google : aucun mot de passe à réinitialiser.';
    if (user.status === 'invited') return "L'invitation n'a pas encore été acceptée.";
    return 'Envoie un lien valable 2 h à l’adresse du compte.';
  });

  protected readonly notice = signal<string | null>(null);

  protected select(user: User): void {
    this.selectedId.set(user.id);
    this.draft.set(new Set(user.permissions));
    this.notice.set(null);
  }

  protected isGranted(code: PermissionCode): boolean {
    return this.draft().has(code);
  }

  /** Vrai quand ce droit a été modifié sans être encore enregistré. */
  protected isPending(code: PermissionCode): boolean {
    const user = this.selected();
    if (!user) return false;
    return this.draft().has(code) !== user.permissions.includes(code);
  }

  protected togglePermission(code: PermissionCode): void {
    this.draft.update((current) => {
      const next = new Set(current);
      if (!next.delete(code)) next.add(code);
      return next;
    });
    this.notice.set(null);
  }

  protected revert(): void {
    const user = this.selected();
    if (user) this.draft.set(new Set(user.permissions));
    this.notice.set(null);
  }

  /** Enregistrement simulé : le backend n'est pas branché. */
  protected save(): void {
    const count = this.pendingCount();
    if (count === 0) return;
    this.notice.set(
      `${count} ${count > 1 ? 'droits modifiés' : 'droit modifié'} — simulation, rien n'a été enregistré.`,
    );
  }

  protected resetPassword(): void {
    const user = this.selected();
    if (!user || !this.canResetPassword()) return;
    this.notice.set(
      `Lien de réinitialisation prêt pour ${user.email} — simulation, rien n'a été envoyé.`,
    );
  }
}
