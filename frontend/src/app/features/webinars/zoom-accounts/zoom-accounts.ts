import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { RouterLink } from '@angular/router';

import { toApiError } from '../../../core/api/api-error';
import {
  ZoomAccountCheckDto,
  ZoomAccountDto,
  ZoomAccountVerifyDto,
  ZoomAccountsApi,
} from '../../../core/api/zoom-accounts.api';
import { Session } from '../../../core/services/session';
import { Topbar } from '../../../layout/topbar/topbar';
import { Icon } from '../../../shared/icon/icon';

interface Draft {
  label: string;
  host_email: string;
  external_zoom_account_id: string;
  client_id: string;
  client_secret: string;
}

const VIDE: Draft = {
  label: '',
  host_email: '',
  external_zoom_account_id: '',
  client_id: '',
  client_secret: '',
};

/**
 * Comptes Zoom — raccordement, test de connexion et renouvellement du jeton.
 *
 * Le Client Secret ne revient jamais de l'API : il se saisit, il se remplace,
 * il ne se relit pas.
 */
@Component({
  selector: 'app-zoom-accounts',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, RouterLink, Topbar, Icon],
  templateUrl: './zoom-accounts.html',
  styleUrl: './zoom-accounts.scss',
})
export class ZoomAccounts {
  private readonly api = inject(ZoomAccountsApi);
  private readonly session = inject(Session);

  protected readonly canManage = computed(() => this.session.has('manage_zoom_accounts'));

  protected readonly accounts = signal<readonly ZoomAccountDto[]>([]);
  protected readonly checks = signal<readonly ZoomAccountCheckDto[]>([]);
  protected readonly selectedId = signal<number | null>(null);
  protected readonly loading = signal(true);
  protected readonly busy = signal<'verify' | 'refresh' | 'save' | 'secret' | 'archive' | null>(
    null,
  );
  protected readonly error = signal<string | null>(null);
  protected readonly report = signal<{ ok: boolean; message: string } | null>(null);

  protected readonly draft = signal<Draft | null>(null);
  protected readonly editingId = signal<number | null>(null);
  protected readonly isSecretOpen = signal(false);
  protected readonly newSecret = signal('');
  protected readonly isArchiving = signal(false);

  protected readonly selected = computed(
    () => this.accounts().find((c) => c.id_zoom_accounts === this.selectedId()) ?? null,
  );

  protected readonly canSave = computed(() => {
    const saisie = this.draft();
    if (!saisie || this.busy()) return false;
    const requis =
      !!saisie.label.trim() &&
      /^\S+@\S+\.\S+$/.test(saisie.host_email.trim()) &&
      !!saisie.external_zoom_account_id.trim() &&
      !!saisie.client_id.trim();
    return requis && (this.editingId() !== null || saisie.client_secret.trim().length >= 8);
  });

  constructor() {
    void this.load();
  }

  private async load(): Promise<void> {
    try {
      const comptes = await this.api.list();
      this.accounts.set(comptes);
      const courant = this.selectedId();
      const garde = comptes.some((c) => c.id_zoom_accounts === courant);
      const id = garde ? courant : (comptes[0]?.id_zoom_accounts ?? null);
      this.selectedId.set(id);
      await this.loadChecks(id);
    } catch (erreur) {
      this.error.set(toApiError(erreur).message);
    } finally {
      this.loading.set(false);
    }
  }

  private async loadChecks(id: number | null): Promise<void> {
    if (id === null) {
      this.checks.set([]);
      return;
    }
    try {
      const lignes = await this.api.checks(id);
      // Seule la réponse du compte encore ouvert est retenue.
      if (this.selectedId() === id) this.checks.set(lignes);
    } catch (erreur) {
      if (this.selectedId() === id) this.error.set(toApiError(erreur).message);
    }
  }

  protected select(id: number): void {
    if (this.selectedId() === id) return;
    this.selectedId.set(id);
    this.report.set(null);
    this.isSecretOpen.set(false);
    this.isArchiving.set(false);
    this.checks.set([]);
    void this.loadChecks(id);
  }

  protected openCreation(): void {
    this.editingId.set(null);
    this.draft.set({ ...VIDE });
    this.error.set(null);
  }

  protected openEdition(compte: ZoomAccountDto): void {
    this.editingId.set(compte.id_zoom_accounts);
    this.draft.set({
      label: compte.label,
      host_email: compte.host_email,
      external_zoom_account_id: compte.external_zoom_account_id,
      client_id: compte.client_id,
      client_secret: '',
    });
    this.error.set(null);
  }

  protected closeForm(): void {
    this.draft.set(null);
  }

  protected type(champ: keyof Draft, valeur: string): void {
    this.draft.update((saisie) => (saisie ? { ...saisie, [champ]: valeur } : saisie));
  }

  protected async save(): Promise<void> {
    const saisie = this.draft();
    if (!saisie || !this.canSave()) return;
    const id = this.editingId();
    this.busy.set('save');
    this.error.set(null);
    try {
      if (id === null) {
        const resultat = await this.api.create(saisie);
        this.selectedId.set(resultat.account.id_zoom_accounts);
        this.show(resultat);
      } else {
        const { client_secret: _, ...champs } = saisie;
        await this.api.update(id, champs);
        this.report.set({ ok: true, message: 'Compte mis à jour. Testez la connexion.' });
      }
      this.draft.set(null);
      await this.load();
    } catch (erreur) {
      this.error.set(toApiError(erreur).message);
    } finally {
      this.busy.set(null);
    }
  }

  protected test(id: number): Promise<void> {
    return this.act('verify', async () => this.show(await this.api.verify(id)));
  }

  protected refresh(id: number): Promise<void> {
    return this.act('refresh', async () => this.show(await this.api.refreshToken(id)));
  }

  protected saveSecret(id: number): Promise<void> {
    return this.act('secret', async () => {
      this.show(await this.api.replaceSecret(id, this.newSecret().trim()));
      this.newSecret.set('');
      this.isSecretOpen.set(false);
    });
  }

  protected archive(id: number): Promise<void> {
    return this.act('archive', async () => {
      await this.api.archive(id);
      this.isArchiving.set(false);
      this.selectedId.set(null);
    });
  }

  private show(resultat: ZoomAccountVerifyDto): void {
    this.report.set({ ok: resultat.verified, message: resultat.message });
  }

  private async act(
    kind: 'verify' | 'refresh' | 'secret' | 'archive',
    geste: () => Promise<void>,
  ): Promise<void> {
    if (this.busy()) return;
    this.busy.set(kind);
    this.error.set(null);
    this.report.set(null);
    try {
      await geste();
      await this.load();
    } catch (erreur) {
      this.error.set(toApiError(erreur).message);
    } finally {
      this.busy.set(null);
    }
  }
}
