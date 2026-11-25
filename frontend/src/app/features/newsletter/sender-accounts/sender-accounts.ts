import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { RouterLink } from '@angular/router';

import { toApiError } from '../../../core/api/api-error';
import {
  EmailAccountCheckDto,
  EmailAccountDto,
  EmailAccountSecurity,
  EmailAccountsApi,
} from '../../../core/api/email-accounts.api';
import { Session } from '../../../core/services/session';
import { Topbar } from '../../../layout/topbar/topbar';
import { Icon } from '../../../shared/icon/icon';

/** Ce que le formulaire tient entre l'ouverture et l'enregistrement. */
interface Brouillon {
  label: string;
  host: string;
  port: number;
  security: EmailAccountSecurity;
  username: string;
  password: string;
  from_email: string;
  from_name: string;
  reply_to_email: string;
  timeout_seconds: number;
}

/** Réglages IONOS, préremplis : c'est le cas courant. */
const IONOS: Omit<Brouillon, 'label' | 'username' | 'password' | 'from_email'> = {
  host: 'smtp.ionos.fr',
  port: 465,
  security: 'ssl_tls',
  from_name: '',
  reply_to_email: '',
  timeout_seconds: 20,
};

function brouillonVide(): Brouillon {
  return { ...IONOS, label: '', username: '', password: '', from_email: '' };
}

/**
 * Comptes d'envoi SMTP.
 *
 * L'écran sert une question simple : est-ce que les courriels peuvent partir,
 * et depuis quelle adresse ? D'où la place donnée à la dernière vérification,
 * et le bouton qui la refait — un mot de passe de boîte change sans prévenir,
 * et c'est toujours au premier envoi qu'on s'en aperçoit.
 *
 * Le mot de passe ne revient jamais de l'API : il se saisit, il se remplace,
 * il ne se relit pas.
 */
@Component({
  selector: 'app-sender-accounts',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, RouterLink, Topbar, Icon],
  templateUrl: './sender-accounts.html',
  styleUrl: './sender-accounts.scss',
})
export class SenderAccounts {
  private readonly api = inject(EmailAccountsApi);
  private readonly session = inject(Session);

  protected readonly trail: readonly string[] = ['Événements', 'Newsletter', "Comptes d'envoi"];

  protected readonly accounts = signal<readonly EmailAccountDto[]>([]);
  protected readonly checks = signal<readonly EmailAccountCheckDto[]>([]);
  protected readonly selected = signal<number | null>(null);

  protected readonly loading = signal(true);
  /** Vrai pendant un échange avec le serveur SMTP : les boutons s'éteignent. */
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  /** Dernier compte rendu d'un test, affiché tel que le serveur l'a motivé. */
  protected readonly report = signal<{ ok: boolean; message: string } | null>(null);

  /** Formulaire de création ou de modification. `null` quand il est fermé. */
  protected readonly draft = signal<Brouillon | null>(null);
  protected readonly editing = signal<number | null>(null);

  /** Saisie du mot de passe de remplacement. */
  protected readonly passwordFor = signal<number | null>(null);
  protected readonly newPassword = signal('');

  /** Saisie du destinataire d'un message de test. */
  protected readonly testFor = signal<number | null>(null);
  protected readonly testRecipient = signal('');

  protected readonly canManage = computed(() => this.session.has('manage_email_accounts'));

  protected readonly active = computed(
    () => this.accounts().find((compte) => compte.is_default) ?? null,
  );

  protected readonly selectedAccount = computed(() => {
    const id = this.selected();
    return id === null ? null : (this.accounts().find((c) => c.id_email_accounts === id) ?? null);
  });

  constructor() {
    void this.recharger();
  }

  // -------------------------------------------------------------------------
  // Lecture
  // -------------------------------------------------------------------------

  private async recharger(): Promise<void> {
    this.loading.set(true);
    this.error.set(null);
    try {
      const comptes = await this.api.list();
      this.accounts.set(comptes);
      // Le compte ouvert reste ouvert ; à défaut, on ouvre l'expéditeur actif.
      const courant = this.selected();
      const existe = comptes.some((c) => c.id_email_accounts === courant);
      const id = existe ? courant : (comptes.find((c) => c.is_default)?.id_email_accounts ?? null);
      this.selected.set(id);
      await this.chargerHistorique(id);
    } catch (erreur) {
      this.error.set(toApiError(erreur).message);
    } finally {
      this.loading.set(false);
    }
  }

  private async chargerHistorique(id: number | null): Promise<void> {
    if (id === null) {
      this.checks.set([]);
      return;
    }
    try {
      const lignes = await this.api.checks(id);
      // Deux chargements peuvent se croiser : passer d'un compte à l'autre
      // laisse la première requête en vol, et si elle répond en dernier elle
      // afficherait l'historique de A sous le nom de B. Seule la réponse du
      // compte encore ouvert est retenue.
      if (this.selected() === id) this.checks.set(lignes);
    } catch (erreur) {
      if (this.selected() === id) this.error.set(toApiError(erreur).message);
    }
  }

  protected async select(id: number): Promise<void> {
    if (this.selected() === id) return;
    this.selected.set(id);
    this.report.set(null);
    // Vidé tout de suite : mieux vaut un volet vide qu'un historique qui
    // appartient encore au compte précédent.
    this.checks.set([]);
    await this.chargerHistorique(id);
  }

  // -------------------------------------------------------------------------
  // Formulaire du compte
  // -------------------------------------------------------------------------

  protected ouvrirCreation(): void {
    if (this.busy()) return;
    this.editing.set(null);
    this.draft.set(brouillonVide());
  }

  protected ouvrirModification(compte: EmailAccountDto): void {
    this.editing.set(compte.id_email_accounts);
    this.draft.set({
      label: compte.label,
      host: compte.host,
      port: compte.port,
      security: compte.security,
      username: compte.username,
      // Le mot de passe n'est pas modifiable ici : il a sa propre fenêtre,
      // parce qu'il crée une ligne d'historique et non une modification.
      password: '',
      from_email: compte.from_email,
      from_name: compte.from_name ?? '',
      reply_to_email: compte.reply_to_email ?? '',
      timeout_seconds: compte.timeout_seconds,
    });
  }

  /**
   * Fermer pendant un enregistrement est refusé.
   *
   * Sans cela, fermer puis rouvrir un brouillon pendant l'appel ferait
   * disparaître la SECONDE saisie au retour de la première : la fermeture
   * qui suit l'enregistrement ne sait pas quelle fenêtre elle referme.
   */
  protected fermerFormulaire(): void {
    if (this.busy()) return;
    this.draft.set(null);
    this.editing.set(null);
  }

  protected majBrouillon(champ: keyof Brouillon, valeur: string): void {
    this.draft.update((brouillon) => {
      if (brouillon === null) return brouillon;
      if (champ === 'port' || champ === 'timeout_seconds') {
        return { ...brouillon, [champ]: Number(valeur) || 0 };
      }
      return { ...brouillon, [champ]: valeur };
    });
  }

  /**
   * Aligne le port sur le mode choisi.
   *
   * 465 et 587 ne sont pas interchangeables : garder l'un avec l'autre est la
   * faute la plus fréquente sur ce réglage, et elle ne se voit qu'au test.
   */
  protected changerMode(valeur: string): void {
    const mode = valeur as EmailAccountSecurity;
    this.draft.update((brouillon) =>
      brouillon === null
        ? brouillon
        : { ...brouillon, security: mode, port: mode === 'ssl_tls' ? 465 : 587 },
    );
  }

  protected readonly formulaireValide = computed(() => {
    const brouillon = this.draft();
    if (brouillon === null) return false;
    const communs =
      brouillon.label.trim().length > 0 &&
      brouillon.host.trim().length > 0 &&
      brouillon.username.trim().length > 0 &&
      brouillon.from_email.trim().length > 0 &&
      brouillon.port > 0;
    // À la création, le mot de passe est obligatoire ; à la modification, il
    // n'est pas touché.
    return this.editing() === null ? communs && brouillon.password.length >= 6 : communs;
  });

  protected async enregistrer(): Promise<void> {
    const brouillon = this.draft();
    if (brouillon === null || !this.formulaireValide()) return;

    this.busy.set(true);
    this.error.set(null);
    this.report.set(null);
    try {
      const id = this.editing();
      if (id === null) {
        const resultat = await this.api.create({
          label: brouillon.label.trim(),
          host: brouillon.host.trim(),
          port: brouillon.port,
          security: brouillon.security,
          username: brouillon.username.trim(),
          password: brouillon.password,
          from_email: brouillon.from_email.trim(),
          from_name: brouillon.from_name.trim() || null,
          reply_to_email: brouillon.reply_to_email.trim() || null,
          timeout_seconds: brouillon.timeout_seconds,
          verify_immediately: true,
        });
        this.report.set({ ok: resultat.verified, message: resultat.message });
        this.selected.set(resultat.account.id_email_accounts);
      } else {
        await this.api.update(id, {
          label: brouillon.label.trim(),
          host: brouillon.host.trim(),
          port: brouillon.port,
          security: brouillon.security,
          username: brouillon.username.trim(),
          from_email: brouillon.from_email.trim(),
          from_name: brouillon.from_name.trim() || null,
          reply_to_email: brouillon.reply_to_email.trim() || null,
          timeout_seconds: brouillon.timeout_seconds,
        });
      }
      this.draft.set(null);
      this.editing.set(null);
      await this.recharger();
    } catch (erreur) {
      this.error.set(toApiError(erreur).message);
    } finally {
      this.busy.set(false);
    }
  }

  // -------------------------------------------------------------------------
  // Mot de passe
  // -------------------------------------------------------------------------

  protected ouvrirMotDePasse(compte: EmailAccountDto): void {
    this.passwordFor.set(compte.id_email_accounts);
    this.newPassword.set('');
  }

  protected fermerMotDePasse(): void {
    if (this.busy()) return;
    this.passwordFor.set(null);
    this.newPassword.set('');
  }

  protected async enregistrerMotDePasse(): Promise<void> {
    const id = this.passwordFor();
    if (id === null || this.newPassword().length < 6) return;

    this.busy.set(true);
    this.error.set(null);
    try {
      const resultat = await this.api.setPassword(id, this.newPassword());
      this.report.set({ ok: resultat.verified, message: resultat.message });
      this.passwordFor.set(null);
      this.newPassword.set('');
      await this.recharger();
    } catch (erreur) {
      this.error.set(toApiError(erreur).message);
    } finally {
      this.busy.set(false);
    }
  }

  // -------------------------------------------------------------------------
  // Échanges avec le serveur
  // -------------------------------------------------------------------------

  protected async tester(compte: EmailAccountDto): Promise<void> {
    this.busy.set(true);
    this.error.set(null);
    this.report.set(null);
    try {
      const resultat = await this.api.verify(compte.id_email_accounts);
      this.report.set({ ok: resultat.verified, message: resultat.message });
      this.selected.set(compte.id_email_accounts);
      await this.recharger();
    } catch (erreur) {
      this.error.set(toApiError(erreur).message);
    } finally {
      this.busy.set(false);
    }
  }

  protected ouvrirMessageDeTest(compte: EmailAccountDto): void {
    this.testFor.set(compte.id_email_accounts);
    this.testRecipient.set('');
  }

  protected fermerMessageDeTest(): void {
    if (this.busy()) return;
    this.testFor.set(null);
    this.testRecipient.set('');
  }

  protected async envoyerMessageDeTest(): Promise<void> {
    const id = this.testFor();
    const destinataire = this.testRecipient().trim();
    if (id === null || !destinataire.includes('@')) return;

    this.busy.set(true);
    this.error.set(null);
    this.report.set(null);
    try {
      const resultat = await this.api.sendTestMessage(id, destinataire);
      this.report.set({ ok: resultat.verified, message: resultat.message });
      this.testFor.set(null);
      this.testRecipient.set('');
      this.selected.set(id);
      await this.recharger();
    } catch (erreur) {
      this.error.set(toApiError(erreur).message);
    } finally {
      this.busy.set(false);
    }
  }

  protected async definirParDefaut(compte: EmailAccountDto): Promise<void> {
    this.busy.set(true);
    this.error.set(null);
    try {
      await this.api.setDefault(compte.id_email_accounts);
      await this.recharger();
    } catch (erreur) {
      this.error.set(toApiError(erreur).message);
    } finally {
      this.busy.set(false);
    }
  }

  protected async archiver(compte: EmailAccountDto): Promise<void> {
    this.busy.set(true);
    this.error.set(null);
    try {
      await this.api.archive(compte.id_email_accounts);
      if (this.selected() === compte.id_email_accounts) this.selected.set(null);
      await this.recharger();
    } catch (erreur) {
      this.error.set(toApiError(erreur).message);
    } finally {
      this.busy.set(false);
    }
  }

  // -------------------------------------------------------------------------
  // Affichage
  // -------------------------------------------------------------------------

  protected modeLisible(compte: EmailAccountDto): string {
    return compte.security === 'ssl_tls' ? 'SSL/TLS' : 'STARTTLS';
  }

  /** Classe de pastille du design system, selon la dernière vérification. */
  protected etatModifier(compte: EmailAccountDto): string {
    if (compte.last_verify_ok === true) return 'status-published';
    if (compte.last_verify_ok === false) return 'status-failed';
    return 'status-draft';
  }

  protected etatLisible(compte: EmailAccountDto): string {
    if (compte.last_verify_ok === true) return 'Vérifié';
    if (compte.last_verify_ok === false) return 'En échec';
    return 'Non vérifié';
  }

  protected natureLisible(verification: EmailAccountCheckDto): string {
    return verification.kind === 'connection' ? 'Connexion' : 'Message de test';
  }
}
