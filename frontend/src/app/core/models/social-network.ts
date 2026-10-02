/**
 * Réseaux sociaux sur lesquels Datum Academy publie.
 *
 * Les codes reprennent ceux de la table de référence `social_networks`
 * du backend : ils servent de clé partout dans l'application.
 */
export type SocialNetworkCode = 'facebook' | 'instagram' | 'linkedin' | 'youtube' | 'tiktok';

/**
 * Couleur de série d'un réseau, pour les graphiques.
 *
 * Déclarées dans `styles/_tokens.scss` — voir le commentaire qui dit
 * pourquoi ce ne sont pas les couleurs des plateformes.
 */
export const NETWORK_SERIES_COLORS: Readonly<Record<SocialNetworkCode, string>> = {
  instagram: 'var(--series-instagram)',
  facebook: 'var(--series-facebook)',
  linkedin: 'var(--series-linkedin)',
  tiktok: 'var(--series-tiktok)',
  youtube: 'var(--series-youtube)',
};

/** Compte de réseau social raccordé à l'espace Datum Academy. */
export interface SocialNetwork {
  readonly code: SocialNetworkCode;
  /** Libellé affiché à l'utilisateur. */
  readonly label: string;
  /** Nom du compte tel qu'il apparaît sur le réseau. */
  readonly accountName: string;
  /** Nature du compte : « Page », « Compte », « Page entreprise »… */
  readonly accountKind: string;
  readonly isConnected: boolean;
  readonly followerCount: number;
  /** Nombre d'envois sur ce réseau pour la période affichée. */
  readonly deliveryCount: number;

  /* --- chiffres de l'écran Réseaux & plateformes --- */

  /** Publications parties sur ce réseau pendant la période. */
  readonly publicationCount: number;
  /** Consultations de la page ou du profil pendant la période. */
  readonly profileViewCount: number;

  /**
   * Adresse publique du profil, telle qu'on l'ouvrirait dans un
   * navigateur. `null` tant qu'elle n'a pas été renseignée : mieux vaut
   * un bouton désactivé qu'un lien mort.
   */
  readonly profileUrl: string | null;

  /**
   * Trente relevés quotidiens du nombre d'abonnés, du plus ancien au plus
   * récent. Le dernier vaut `followerCount`.
   *
   * Aucune plateforme ne rend cet historique de façon fiable au-delà de
   * quelques semaines — Instagram le limite à trente jours. Il faut donc
   * en conserver un relevé quotidien de son côté.
   */
  readonly followerHistory: readonly number[];

  /** Dernière collecte des statistiques. */
  readonly lastSyncLabel: string;
  /** Renseigné quand la connexion demande une action. */
  readonly connectionNote: string | null;
}
