import { DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  input,
  signal,
} from '@angular/core';
import { RouterLink } from '@angular/router';

import { toApiError } from '../../../core/api/api-error';
import {
  SocialAccountDto,
  SocialAccountStatisticsDto,
  SocialAccountSyncDto,
  SocialAccountTokenDto,
  SocialAccountsApi,
  SocialPostDto,
  SocialStatisticTypeDto,
  StatisticPointDto,
} from '../../../core/api/social-accounts.api';
import { SocialNetworkCode } from '../../../core/models/social-network';
import { Session } from '../../../core/services/session';
import { Topbar } from '../../../layout/topbar/topbar';
import { Icon } from '../../../shared/icon/icon';
import { NetworkLogo } from '../../../shared/network-logo/network-logo';

type OngletFiche = 'stats' | 'tokens' | 'syncs' | 'posts';

interface PointGraphique {
  readonly x: number;
  readonly y: number;
  readonly valeur: number;
  readonly etiquetteDate: string;
}

interface GraduationY {
  readonly y: number;
  readonly valeur: number;
}

const RESEAUX_CONNUS: ReadonlySet<string> = new Set([
  'facebook',
  'instagram',
  'linkedin',
  'youtube',
  'tiktok',
]);

/**
 * Fiche détaillée d'un compte réseau social (/reseaux/:id).
 *
 * Quatre onglets fidèles au modèle du module 05 :
 * - Statistiques (séries quotidiennes, nature stock / flux)
 * - Autorisations & jetons (historique des délivrances ou héritage parent)
 * - Journal des passages (`social_account_syncs`)
 * - Publications parues (`social_posts`, archivage déclaré)
 */
@Component({
  selector: 'app-network-detail',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DecimalPipe, RouterLink, Topbar, Icon, NetworkLogo],
  templateUrl: './network-detail.html',
  styleUrl: './network-detail.scss',
})
export class NetworkDetail {
  private readonly api = inject(SocialAccountsApi);
  private readonly session = inject(Session);

  /** Paramètre de route `:id` injecté par `withComponentInputBinding()`. */
  readonly id = input.required<string>();

  protected readonly compte = signal<SocialAccountDto | null>(null);
  protected readonly stats = signal<SocialAccountStatisticsDto | null>(null);
  protected readonly jetons = signal<readonly SocialAccountTokenDto[]>([]);
  protected readonly passages = signal<readonly SocialAccountSyncDto[]>([]);
  protected readonly posts = signal<readonly SocialPostDto[]>([]);

  protected readonly onglet = signal<OngletFiche>('stats');
  protected readonly periode = signal<7 | 30 | 90>(30);
  protected readonly mesureActive = signal<string>('followers');
  protected readonly filtrePassage = signal<string>('all');

  protected readonly chargement = signal(true);
  protected readonly actionEnCours = signal<string | null>(null);
  protected readonly erreur = signal<string | null>(null);
  protected readonly avis = signal<string | null>(null);

  protected readonly peutGerer = computed(() => this.session.has('manage_social_accounts'));

  protected readonly estMeta = computed(() => {
    const c = this.compte();
    return c !== null && (c.platform_code === 'facebook' || c.platform_code === 'instagram');
  });

  protected readonly typesMesures = computed<readonly SocialStatisticTypeDto[]>(
    () => this.stats()?.metric_types ?? [],
  );

  protected readonly typeMesureActif = computed<SocialStatisticTypeDto | null>(() => {
    const liste = this.typesMesures();
    return liste.find((m) => m.code === this.mesureActive()) ?? liste[0] ?? null;
  });

  protected readonly serieActive = computed<readonly StatisticPointDto[]>(() => {
    const s = this.stats();
    const type = this.typeMesureActif();
    if (!s || !type) return [];
    return s.series[type.code] ?? [];
  });

  /** Géométrie SVG du graphique d'évolution (largeur 720 × hauteur 200). */
  protected readonly graphique = computed(() => {
    const points = this.serieActive();
    if (points.length === 0) return null;

    const largeur = 720;
    const hauteur = 200;
    const padG = 54;
    const padD = 18;
    const padH = 18;
    const padB = 28;

    const valeurs = points.map((p) => p.value);
    const min = Math.min(...valeurs);
    const max = Math.max(...valeurs);
    const ecart = max - min || 1;
    const utileX = largeur - padG - padD;
    const utileY = hauteur - padH - padB;

    const pts: PointGraphique[] = points.map((p, idx) => {
      const ratioX = points.length === 1 ? 0.5 : idx / (points.length - 1);
      const x = padG + ratioX * utileX;
      const y = padH + (1 - (p.value - min) / ecart) * utileY;
      return {
        x,
        y,
        valeur: p.value,
        etiquetteDate: this.formaterDateCourte(p.metric_date),
      };
    });

    const ligne = pts.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
    const baseY = hauteur - padB;
    const aire = `${pts[0].x.toFixed(1)},${baseY} ${ligne} ${pts[pts.length - 1].x.toFixed(1)},${baseY}`;

    const graduations: GraduationY[] = [0, 0.5, 1].map((t) => ({
      y: padH + t * utileY,
      valeur: Math.round(max - t * ecart),
    }));

    return { largeur, hauteur, padG, padD, baseY, pts, ligne, aire, graduations };
  });

  protected readonly jetonActif = computed<SocialAccountTokenDto | null>(
    () => this.jetons().find((t) => t.is_active) ?? null,
  );

  protected readonly passagesFiltres = computed(() => {
    const f = this.filtrePassage();
    if (f === 'all') return this.passages();
    return this.passages().filter((p) => p.sync_kind === f);
  });

  protected readonly filAriane = computed(() => {
    const c = this.compte();
    return ['Mesurer', 'Réseaux & plateformes', c ? c.account_display_name : 'Fiche compte'];
  });

  constructor() {
    effect(() => {
      const brut = this.id();
      const idNum = Number(brut);
      if (Number.isFinite(idNum) && idNum > 0) {
        void this.chargerTout(idNum);
      } else {
        this.chargement.set(false);
        this.erreur.set("Identifiant de compte invalide.");
      }
    });
  }

  protected async chargerTout(idCompte: number): Promise<void> {
    this.chargement.set(true);
    this.erreur.set(null);
    this.avis.set(null);
    try {
      const [compte, stats, jetons, passages, posts] = await Promise.all([
        this.api.get(idCompte),
        this.api.statistics(idCompte, this.periode()),
        this.api.tokens(idCompte),
        this.api.syncs(idCompte),
        this.api.posts(idCompte),
      ]);
      this.compte.set(compte);
      this.stats.set(stats);
      this.jetons.set(jetons);
      this.passages.set(passages);
      this.posts.set(posts);
    } catch (err) {
      this.erreur.set(toApiError(err).message);
    } finally {
      this.chargement.set(false);
    }
  }

  protected async changerPeriode(jours: 7 | 30 | 90): Promise<void> {
    const c = this.compte();
    if (!c || this.periode() === jours) return;
    this.periode.set(jours);
    try {
      const stats = await this.api.statistics(c.id_social_accounts, jours);
      this.stats.set(stats);
    } catch (err) {
      this.erreur.set(toApiError(err).message);
    }
  }

  protected async actualiserStatistiques(): Promise<void> {
    const c = this.compte();
    if (!c || this.actionEnCours() !== null) return;
    this.actionEnCours.set('stats');
    this.erreur.set(null);
    this.avis.set(null);
    try {
      const res = await this.api.syncStatistics(c.id_social_accounts);
      this.compte.set(res.account);
      const [stats, passages] = await Promise.all([
        this.api.statistics(c.id_social_accounts, this.periode()),
        this.api.syncs(c.id_social_accounts),
      ]);
      this.stats.set(stats);
      this.passages.set(passages);
      if (res.ok) {
        this.avis.set(res.message);
      } else {
        this.erreur.set(res.message);
      }
    } catch (err) {
      this.erreur.set(toApiError(err).message);
    } finally {
      this.actionEnCours.set(null);
    }
  }

  protected async verifierCompte(): Promise<void> {
    const c = this.compte();
    if (!c || this.actionEnCours() !== null) return;
    this.actionEnCours.set('verify');
    this.erreur.set(null);
    this.avis.set(null);
    try {
      const res = await this.api.verify(c.id_social_accounts);
      this.compte.set(res.account);
      const [jetons, passages] = await Promise.all([
        this.api.tokens(c.id_social_accounts),
        this.api.syncs(c.id_social_accounts),
      ]);
      this.jetons.set(jetons);
      this.passages.set(passages);
      if (res.verified) {
        this.avis.set(res.message);
      } else {
        this.erreur.set(res.message);
      }
    } catch (err) {
      this.erreur.set(toApiError(err).message);
    } finally {
      this.actionEnCours.set(null);
    }
  }

  protected async importerPosts(): Promise<void> {
    const c = this.compte();
    if (!c || this.actionEnCours() !== null) return;
    this.actionEnCours.set('posts');
    this.erreur.set(null);
    this.avis.set(null);
    try {
      const res = await this.api.syncPosts(c.id_social_accounts);
      this.posts.set(res.posts);
      if (res.ok) {
        this.avis.set(res.message);
      } else {
        this.erreur.set(res.message);
      }
    } catch (err) {
      this.erreur.set(toApiError(err).message);
    } finally {
      this.actionEnCours.set(null);
    }
  }

  protected async declarerPostArchive(post: SocialPostDto): Promise<void> {
    const c = this.compte();
    if (!c || this.actionEnCours() !== null) return;
    this.actionEnCours.set(`archive-${post.id_social_posts}`);
    this.erreur.set(null);
    try {
      const maj = await this.api.archivePost(c.id_social_accounts, post.id_social_posts);
      this.posts.update((liste) =>
        liste.map((p) => (p.id_social_posts === maj.id_social_posts ? maj : p)),
      );
      this.avis.set('Publication déclarée archivée sur le réseau.');
    } catch (err) {
      this.erreur.set(toApiError(err).message);
    } finally {
      this.actionEnCours.set(null);
    }
  }

  protected valeurCarteMesure(type: SocialStatisticTypeDto): number | null {
    const pts = this.stats()?.series[type.code] ?? [];
    if (pts.length === 0) return null;
    if (type.is_summable) {
      return pts.reduce((acc, p) => acc + p.value, 0);
    }
    return pts[pts.length - 1].value;
  }

  protected codeReseau(code: string): SocialNetworkCode {
    return (RESEAUX_CONNUS.has(code) ? code : 'facebook') as SocialNetworkCode;
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

  protected libelleSortePassage(kind: string): string {
    switch (kind) {
      case 'statistics':
        return 'Statistiques';
      case 'events':
        return 'Événements';
      case 'token_check':
        return 'Vérification jeton';
      default:
        return kind;
    }
  }

  protected libelleIssue(outcome: string | null): string {
    if (!outcome) return 'En cours';
    switch (outcome) {
      case 'succeeded':
        return 'Réussi';
      case 'empty':
        return 'Rien de nouveau';
      case 'failed':
        return 'Échoué';
      default:
        return outcome;
    }
  }

  protected classeIssue(outcome: string | null): string {
    if (!outcome) return 'status-review';
    switch (outcome) {
      case 'succeeded':
        return 'status-published';
      case 'failed':
        return 'status-failed';
      default:
        return 'status-draft';
    }
  }

  protected formaterDateCourte(iso: string | null): string {
    if (!iso) return '—';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' });
  }

  protected formaterDateHeure(iso: string | null): string {
    if (!iso) return '—';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString('fr-FR', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }
}
