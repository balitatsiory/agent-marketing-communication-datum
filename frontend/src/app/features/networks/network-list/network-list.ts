import { DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  computed,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { RouterLink } from '@angular/router';

import { toApiError } from '../../../core/api/api-error';
import {
  SocialAccountCreate,
  SocialAccountDto,
  SocialAccountStatusDto,
  SocialAccountsApi,
  SocialPlatformDto,
} from '../../../core/api/social-accounts.api';
import { SocialNetworkCode } from '../../../core/models/social-network';
import { Session } from '../../../core/services/session';
import { Topbar } from '../../../layout/topbar/topbar';
import { Icon } from '../../../shared/icon/icon';
import { NetworkLogo } from '../../../shared/network-logo/network-logo';

type ModeRaccordement = 'manual' | 'oauth';
type ModeCles = 'own' | 'inherited';

interface FormulaireRaccordement {
  platform_code: string;
  account_display_name: string;
  account_username: string;
  account_external_id: string;
  profile_url: string;
  credential_mode: ModeCles;
  id_social_accounts_parent: number | null;
  access_token: string;
  refresh_token: string;
  token_kind: string;
  obtained_at: string;
  access_expires_at: string;
}

const RESEAUX_CONNUS: ReadonlySet<string> = new Set([
  'facebook',
  'instagram',
  'linkedin',
  'youtube',
  'tiktok',
]);

function dateDuJourIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function formulaireInitial(plateformeParDefaut: string): FormulaireRaccordement {
  return {
    platform_code: plateformeParDefaut,
    account_display_name: '',
    account_username: '',
    account_external_id: '',
    profile_url: '',
    credential_mode: 'own',
    id_social_accounts_parent: null,
    access_token: '',
    refresh_token: '',
    token_kind: plateformeParDefaut === 'facebook' ? 'page' : 'user',
    obtained_at: dateDuJourIso(),
    access_expires_at: '',
  };
}

/**
 * Réseaux & plateformes — Liste des comptes et raccordement (module 05).
 *
 * Les états et les mesures supportées sont lus depuis l'API (`social_platforms`,
 * `social_account_statuses`) pour que l'écran distingue « pas encore relevé »
 * de « non fourni par ce réseau ».
 */
@Component({
  selector: 'app-network-list',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DecimalPipe, RouterLink, Topbar, Icon, NetworkLogo],
  templateUrl: './network-list.html',
  styleUrl: './network-list.scss',
  host: {
    '(document:keydown.escape)': 'surEchap()',
  },
})
export class NetworkList {
  private readonly api = inject(SocialAccountsApi);
  private readonly session = inject(Session);

  private readonly premierChamp = viewChild<ElementRef<HTMLElement>>('premierChampModal');

  protected readonly plateformes = signal<readonly SocialPlatformDto[]>([]);
  protected readonly statuts = signal<readonly SocialAccountStatusDto[]>([]);
  protected readonly comptes = signal<readonly SocialAccountDto[]>([]);

  protected readonly chargement = signal(true);
  protected readonly enCours = signal(false);
  protected readonly erreur = signal<string | null>(null);
  protected readonly avis = signal<string | null>(null);

  protected readonly filtreStatut = signal<string>('all');
  protected readonly filtrePlateforme = signal<string>('all');
  protected readonly recherche = signal<string>('');

  // Modale « Connecter / Reconnecter un compte »
  protected readonly modaleOuverte = signal(false);
  protected readonly modeRaccordement = signal<ModeRaccordement>('manual');
  protected readonly compteAReconnecter = signal<SocialAccountDto | null>(null);
  protected readonly formulaire = signal<FormulaireRaccordement>(formulaireInitial('facebook'));
  protected readonly erreurModale = signal<string | null>(null);

  // Modale « Débrancher un compte »
  protected readonly compteADebrancher = signal<SocialAccountDto | null>(null);
  protected readonly verificationEnCoursId = signal<number | null>(null);

  protected readonly peutGerer = computed(() => this.session.has('manage_social_accounts'));

  protected readonly plateformesParCode = computed(() => {
    const carte = new Map<string, SocialPlatformDto>();
    for (const p of this.plateformes()) carte.set(p.code, p);
    return carte;
  });

  protected readonly comptesParentsEligibles = computed(() => {
    const cible = this.compteAReconnecter();
    return this.comptes().filter(
      (c) =>
        c.credential_mode === 'own' &&
        c.status_code !== 'disconnected' &&
        (cible === null || c.id_social_accounts !== cible.id_social_accounts),
    );
  });

  protected readonly compteursStatuts = computed(() => {
    const liste = this.comptes();
    const parCode: Record<string, number> = { all: liste.length };
    for (const s of this.statuts()) {
      parCode[s.code] = liste.filter((c) => c.status_code === s.code).length;
    }
    return parCode;
  });

  protected readonly totaux = computed(() => {
    const connectes = this.comptes().filter((c) => c.status_code === 'active');
    return {
      connectes: connectes.length,
      total: this.comptes().length,
      abonnes: connectes.reduce((s, c) => s + (c.metrics.followers ?? 0), 0),
      vues30j: connectes.reduce((s, c) => s + (c.metrics.views_30d ?? 0), 0),
      publications30j: connectes.reduce((s, c) => s + c.metrics.posts_30d, 0),
    };
  });

  protected readonly resultats = computed<readonly SocialAccountDto[]>(() => {
    const statut = this.filtreStatut();
    const plateforme = this.filtrePlateforme();
    const terme = this.recherche().trim().toLowerCase();

    return this.comptes().filter((c) => {
      if (statut !== 'all' && c.status_code !== statut) return false;
      if (plateforme !== 'all' && c.platform_code !== plateforme) return false;
      if (terme) {
        const foin =
          `${c.account_display_name} ${c.account_username ?? ''} ${c.platform_label} ${c.account_external_id}`.toLowerCase();
        if (!foin.includes(terme)) return false;
      }
      return true;
    });
  });

  protected readonly formulaireValide = computed(() => {
    const f = this.formulaire();
    const reconnexion = this.compteAReconnecter() !== null;
    if (!reconnexion) {
      if (!f.platform_code.trim() || !f.account_display_name.trim() || !f.account_external_id.trim()) {
        return false;
      }
    }
    if (f.credential_mode === 'inherited') {
      return f.id_social_accounts_parent !== null;
    }
    return f.access_token.trim().length > 0;
  });

  constructor() {
    void this.recharger();
  }

  protected async recharger(): Promise<void> {
    this.chargement.set(true);
    this.erreur.set(null);
    try {
      const [plateformes, statuts, comptes] = await Promise.all([
        this.api.platforms(),
        this.api.statuses(),
        this.api.list(),
      ]);
      this.plateformes.set(plateformes);
      this.statuts.set(statuts);
      this.comptes.set(comptes);
    } catch (err) {
      this.erreur.set(toApiError(err).message);
    } finally {
      this.chargement.set(false);
    }
  }

  protected codeReseau(code: string): SocialNetworkCode {
    return (RESEAUX_CONNUS.has(code) ? code : 'facebook') as SocialNetworkCode;
  }

  protected mesureSupportee(platformCode: string, metricCode: string): boolean {
    const plat = this.plateformesParCode().get(platformCode);
    if (!plat || !plat.supports_account_metrics) return false;
    return plat.supported_metrics.some((m) => m.code === metricCode);
  }

  protected classeStatut(code: string): string {
    switch (code) {
      case 'active':
        return 'status-published';
      case 'authorization_incomplete':
        return 'status-scheduled';
      case 'to_reconnect':
        return 'status-failed';
      default:
        return 'status-draft';
    }
  }

  protected hoteDe(url: string): string {
    try {
      return new URL(url).hostname.replace(/^www\./, '');
    } catch {
      return url;
    }
  }

  protected formaterDateCourte(iso: string | null): string {
    if (!iso) return 'pas encore relevé';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' });
  }

  protected ouvrirConnexion(aReconnecter: SocialAccountDto | null = null): void {
    this.erreurModale.set(null);
    this.avis.set(null);
    this.compteAReconnecter.set(aReconnecter);
    this.modeRaccordement.set('manual');

    if (aReconnecter) {
      this.formulaire.set({
        platform_code: aReconnecter.platform_code,
        account_display_name: aReconnecter.account_display_name,
        account_username: aReconnecter.account_username ?? '',
        account_external_id: aReconnecter.account_external_id,
        profile_url: aReconnecter.profile_url ?? '',
        credential_mode: aReconnecter.credential_mode,
        id_social_accounts_parent: aReconnecter.id_social_accounts_parent,
        access_token: '',
        refresh_token: '',
        token_kind:
          aReconnecter.token_kind ??
          (aReconnecter.platform_code === 'facebook' ? 'page' : 'user'),
        obtained_at: dateDuJourIso(),
        access_expires_at: '',
      });
    } else {
      const active = this.plateformes().find((p) => p.is_enabled) ?? this.plateformes()[0];
      this.formulaire.set(formulaireInitial(active?.code ?? 'facebook'));
    }

    this.modaleOuverte.set(true);
    queueMicrotask(() => this.premierChamp()?.nativeElement.focus());
  }

  protected fermerModale(): void {
    if (this.enCours()) return;
    this.modaleOuverte.set(false);
    this.compteAReconnecter.set(null);
    this.erreurModale.set(null);
  }

  protected surEchap(): void {
    if (this.compteADebrancher() !== null) {
      this.compteADebrancher.set(null);
      return;
    }
    if (this.modaleOuverte()) {
      this.fermerModale();
    }
  }

  protected majChamp<K extends keyof FormulaireRaccordement>(
    cle: K,
    valeur: FormulaireRaccordement[K],
  ): void {
    this.erreurModale.set(null);
    this.formulaire.update((f) => {
      const suivant = { ...f, [cle]: valeur };
      if (cle === 'platform_code') {
        const code = String(valeur);
        suivant.token_kind = code === 'facebook' ? 'page' : 'user';
        // Un compte Instagram Business hérite généralement du jeton de sa page Facebook parente.
        if (code === 'instagram' && this.comptesParentsEligibles().length > 0) {
          suivant.credential_mode = 'inherited';
          suivant.id_social_accounts_parent =
            this.comptesParentsEligibles().find((p) => p.platform_code === 'facebook')
              ?.id_social_accounts ?? this.comptesParentsEligibles()[0].id_social_accounts;
        } else if (code !== 'instagram' && suivant.credential_mode === 'inherited') {
          suivant.credential_mode = 'own';
          suivant.id_social_accounts_parent = null;
        }
      }
      if (cle === 'credential_mode') {
        if (valeur === 'inherited') {
          suivant.id_social_accounts_parent =
            suivant.id_social_accounts_parent ??
            this.comptesParentsEligibles()[0]?.id_social_accounts ??
            null;
        } else {
          suivant.id_social_accounts_parent = null;
        }
      }
      return suivant;
    });
  }

  protected majParent(valeur: string): void {
    const id = Number(valeur);
    this.majChamp('id_social_accounts_parent', Number.isFinite(id) && id > 0 ? id : null);
  }

  protected async soumettreRaccordement(): Promise<void> {
    if (!this.formulaireValide() || this.enCours()) return;

    this.enCours.set(true);
    this.erreurModale.set(null);
    const f = this.formulaire();
    const reconnexion = this.compteAReconnecter();

    try {
      const obtainedIso = f.obtained_at ? `${f.obtained_at}T00:00:00Z` : null;
      const expiresIso = f.access_expires_at ? `${f.access_expires_at}T23:59:59Z` : null;

      if (reconnexion) {
        const maj = await this.api.reconnect(reconnexion.id_social_accounts, {
          access_token: f.access_token.trim(),
          refresh_token: f.refresh_token.trim() || null,
          token_kind: f.token_kind.trim() || null,
          obtained_at: obtainedIso,
          access_expires_at: expiresIso,
        });
        this.comptes.update((liste) =>
          liste.map((c) => (c.id_social_accounts === maj.id_social_accounts ? maj : c)),
        );
        this.avis.set(`Le compte « ${maj.account_display_name} » a été reconnecté.`);
      } else {
        const charge: SocialAccountCreate = {
          platform_code: f.platform_code,
          account_display_name: f.account_display_name.trim(),
          account_username: f.account_username.trim() || null,
          account_external_id: f.account_external_id.trim(),
          profile_url: f.profile_url.trim() || null,
          credential_mode: f.credential_mode,
          id_social_accounts_parent:
            f.credential_mode === 'inherited' ? f.id_social_accounts_parent : null,
          access_token: f.credential_mode === 'own' ? f.access_token.trim() : null,
          refresh_token: f.credential_mode === 'own' ? f.refresh_token.trim() || null : null,
          token_kind: f.credential_mode === 'own' ? f.token_kind.trim() || null : null,
          obtained_at: f.credential_mode === 'own' ? obtainedIso : null,
          access_expires_at: f.credential_mode === 'own' ? expiresIso : null,
        };
        const cree = await this.api.create(charge);
        this.comptes.update((liste) => [cree, ...liste]);
        this.avis.set(`Le compte « ${cree.account_display_name} » a été connecté.`);
      }

      this.modaleOuverte.set(false);
      this.compteAReconnecter.set(null);
    } catch (err) {
      this.erreurModale.set(toApiError(err).message);
    } finally {
      this.enCours.set(false);
    }
  }

  protected peutVerifier(compte: SocialAccountDto): boolean {
    return (
      this.peutGerer() &&
      compte.status_code !== 'disconnected' &&
      (compte.platform_code === 'facebook' || compte.platform_code === 'instagram')
    );
  }

  protected async verifier(compte: SocialAccountDto): Promise<void> {
    if (this.verificationEnCoursId() !== null || this.enCours()) return;
    this.verificationEnCoursId.set(compte.id_social_accounts);
    this.erreur.set(null);
    this.avis.set(null);
    try {
      const res = await this.api.verify(compte.id_social_accounts);
      this.comptes.update((liste) =>
        liste.map((c) => (c.id_social_accounts === res.account.id_social_accounts ? res.account : c)),
      );
      if (res.verified) {
        this.avis.set(res.message);
      } else {
        this.erreur.set(res.message);
      }
    } catch (err) {
      this.erreur.set(toApiError(err).message);
    } finally {
      this.verificationEnCoursId.set(null);
    }
  }

  protected demanderDebranchement(compte: SocialAccountDto): void {
    this.avis.set(null);
    this.compteADebrancher.set(compte);
  }

  protected async confirmerDebranchement(): Promise<void> {
    const cible = this.compteADebrancher();
    if (!cible || this.enCours()) return;

    this.enCours.set(true);
    this.erreur.set(null);
    try {
      const maj = await this.api.disconnect(cible.id_social_accounts);
      this.comptes.update((liste) =>
        liste.map((c) => (c.id_social_accounts === maj.id_social_accounts ? maj : c)),
      );
      this.avis.set(
        `Le compte « ${maj.account_display_name} » a été débranché : ses clés sont révoquées et son historique est conservé.`,
      );
      this.compteADebrancher.set(null);
    } catch (err) {
      this.erreur.set(toApiError(err).message);
      this.compteADebrancher.set(null);
    } finally {
      this.enCours.set(false);
    }
  }
}
