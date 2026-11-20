"""Complément du module 05 Comptes réseaux sociaux.

Apporte quatre ajouts issus de la conception des écrans et de la vérification
des API de plateformes (2025-2026) :
- colonne `profile_url` sur `social_accounts` pour ouvrir la page depuis l'écran ;
- alignement des quatre états sur le vocabulaire validé (`active`,
  `authorization_incomplete`, `to_reconnect`, `disconnected`) ;
- passage de TikTok à `supports_account_metrics = true` (Display API v2
  `user.info.stats` expose `follower_count`) ;
- amorçage de `social_platform_statistic_types` avec les noms d'API vérifiés
  de Facebook, Instagram, LinkedIn et TikTok.

Revision : 0004
Revision precedente : 0003
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "social_accounts",
        sa.Column(
            "profile_url",
            sa.String(512),
            nullable=True,
            comment="Adresse publique de la page ou du profil.",
        ),
    )

    op.execute(
        """
        UPDATE social_account_statuses SET code = 'active', label = 'Actif', sort_order = 10
        WHERE code = 'connected';
        UPDATE social_account_statuses SET code = 'to_reconnect', label = 'À reconnecter', sort_order = 30
        WHERE code = 'needs_reconnect';
        UPDATE social_account_statuses SET label = 'Débranché', sort_order = 40
        WHERE code = 'disconnected';

        INSERT INTO social_account_statuses (code, label, sort_order)
        VALUES ('authorization_incomplete', 'Autorisation incomplète', 20)
        ON CONFLICT (code) DO NOTHING;

        UPDATE social_account_error_causes
        SET id_social_account_statuses_target = (
            SELECT id_social_account_statuses
            FROM social_account_statuses
            WHERE code = 'authorization_incomplete'
        )
        WHERE code = 'permission_missing';
        """
    )

    op.execute(
        """
        UPDATE social_platforms
        SET is_enabled = true, supports_account_metrics = true
        WHERE code IN ('facebook', 'instagram', 'linkedin', 'tiktok');

        UPDATE social_platforms
        SET supports_event_polling = true
        WHERE code IN ('facebook', 'instagram', 'linkedin');
        """
    )

    op.execute(
        """
        INSERT INTO social_platform_statistic_types
            (id_social_platforms, id_social_account_statistic_types, platform_metric_name)
        SELECT p.id_social_platforms, t.id_social_account_statistic_types, v.nom_api
        FROM (VALUES
            ('facebook',  'followers',    'page_follows'),
            ('facebook',  'reach',        'page_total_media_view_unique'),
            ('facebook',  'views',        'page_media_view'),
            ('facebook',  'interactions', 'page_post_engagements'),

            ('instagram', 'followers',    'follower_count'),
            ('instagram', 'reach',        'reach'),
            ('instagram', 'views',        'views'),
            ('instagram', 'interactions', 'total_interactions'),

            ('linkedin',  'followers',    'networkSizes.firstDegreeSize'),
            ('linkedin',  'reach',        'uniqueImpressionsCount'),
            ('linkedin',  'views',        'impressionCount'),
            ('linkedin',  'interactions', 'likeCount+commentCount+shareCount+clickCount'),

            ('tiktok',    'followers',    'follower_count')
        ) AS v(plateforme, mesure, nom_api)
        JOIN social_platforms p ON p.code = v.plateforme
        JOIN social_account_statistic_types t ON t.code = v.mesure
        ON CONFLICT (id_social_platforms, id_social_account_statistic_types)
        DO UPDATE SET platform_metric_name = EXCLUDED.platform_metric_name;
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM social_platform_statistic_types")
    op.execute("UPDATE social_platforms SET supports_account_metrics = false WHERE code = 'tiktok'")
    op.execute(
        """
        UPDATE social_account_error_causes
        SET id_social_account_statuses_target = (
            SELECT id_social_account_statuses
            FROM social_account_statuses
            WHERE code = 'to_reconnect'
        )
        WHERE code = 'permission_missing';

        DELETE FROM social_account_statuses WHERE code = 'authorization_incomplete';
        UPDATE social_account_statuses SET code = 'connected', label = 'Connecte', sort_order = 10
        WHERE code = 'active';
        UPDATE social_account_statuses SET code = 'needs_reconnect', label = 'A reconnecter', sort_order = 20
        WHERE code = 'to_reconnect';
        UPDATE social_account_statuses SET label = 'Deconnecte', sort_order = 30
        WHERE code = 'disconnected';
        """
    )
    op.drop_column("social_accounts", "profile_url")
