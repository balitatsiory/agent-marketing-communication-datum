import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  computed,
  effect,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { RouterLink } from '@angular/router';

import { MediaApi, MediaReferenceDto } from '../../../core/api/media.api';
import {
  MediaReferenceNature,
  MediaReferenceView,
  MediaView,
  toMediaReferenceNature,
  toMediaReferenceView,
  toMediaView,
  traduireErreurMedia,
} from '../../../core/models/media-reference';
import { Session } from '../../../core/services/session';
import { Topbar } from '../../../layout/topbar/topbar';
import { Icon } from '../../../shared/icon/icon';

const TAILLE_PAGE = 200;

type ModeEditeur =
  | { readonly mode: 'declarer' }
  | { readonly mode: 'modifier'; readonly reference: MediaReferenceView };

/**
 * Médias de référence — branchés sur `/api/v1/media-references` et
 * `/api/v1/media-reference-natures`.
 *
 * Un média de référence ne naît jamais automatiquement au dépôt : un fichier
 * est d'abord déposé dans la médiathèque (`/medias`), puis explicitement
 * déclaré ici avec sa nature (`GET /media-reference-natures`), son libellé et
 * sa description facultative.
 */
@Component({
  selector: 'app-media-reference-list',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, Topbar, Icon],
  templateUrl: './media-reference-list.html',
  styleUrl: './media-reference-list.scss',
  host: {
    '(document:keydown.escape)': 'fermerModale()',
  },
})
export class MediaReferenceList {
  private readonly api = inject(MediaApi);
  private readonly session = inject(Session);
  private readonly premierChampModale =
    viewChild<ElementRef<HTMLElement>>('premierChampModale');

  private readonly naturesBrutes = signal<readonly MediaReferenceNature[]>([]);
  private readonly referencesBrutes = signal<readonly MediaReferenceDto[]>([]);
  private readonly bibliotheque = signal<readonly MediaView[]>([]);

  protected readonly chargement = signal(true);
  protected readonly enCours = signal(false);
  protected readonly erreur = signal<string | null>(null);
  protected readonly avis = signal<string | null>(null);

  protected readonly recherche = signal('');
  protected readonly filtreNature = signal<string>('tous');

  /** Fenêtre modale de déclaration ou de modification. */
  protected readonly editeur = signal<ModeEditeur | null>(null);
  protected readonly erreurModale = signal<string | null>(null);
  protected readonly rechercheMedia = signal('');
  protected readonly idMediaChoisi = signal<number | null>(null);
  protected readonly codeNatureChoisi = signal<string | null>(null);
  protected readonly libelleSaisi = signal('');
  protected readonly descriptionSaisie = signal('');
  protected readonly estActifSaisi = signal(true);

  protected readonly retraitId = signal<number | null>(null);

  protected readonly peutGererReferences = computed(() =>
    this.session.has('manage_media_reference'),
  );

  protected readonly natures = computed<readonly MediaReferenceNature[]>(() =>
    [...this.naturesBrutes()].sort((a, b) => a.sortOrder - b.sortOrder),
  );

  protected readonly references = computed<readonly MediaReferenceView[]>(() => {
    const mediasParId = new Map(this.bibliotheque().map((m) => [m.idMedia, m]));
    const naturesParCode = new Map(this.natures().map((n) => [n.code, n]));

    return this.referencesBrutes()
      .filter((dto) => dto.deleted_at === null)
      .map((dto) => toMediaReferenceView(dto, mediasParId, naturesParCode));
  });

  protected readonly optionsFiltreNature = computed(() => {
    const toutes = this.references();
    return [
      { code: 'tous', label: 'Toutes', count: toutes.length },
      ...this.natures().map((nature) => ({
        code: nature.code,
        label: nature.label,
        count: toutes.filter((r) => r.natureCode === nature.code).length,
      })),
    ];
  });

  protected readonly resultats = computed<readonly MediaReferenceView[]>(() => {
    const nature = this.filtreNature();
    const terme = this.recherche().trim().toLowerCase();

    return this.references().filter((ref) => {
      if (nature !== 'tous' && ref.natureCode !== nature) return false;
      if (!terme) return true;
      return (
        ref.label.toLowerCase().includes(terme) ||
        (ref.description?.toLowerCase().includes(terme) ?? false) ||
        ref.natureLabel.toLowerCase().includes(terme) ||
        (ref.media?.displayName.toLowerCase().includes(terme) ?? false)
      );
    });
  });

  /**
   * Médias de la bibliothèque pouvant être déclarés comme référence : images
   * non archivées qui ne font pas déjà l'objet d'une référence active.
   */
  protected readonly mediasEligibles = computed<readonly MediaView[]>(() => {
    const dejaReferences = new Set(this.references().map((r) => r.idMedia));
    return this.bibliotheque().filter(
      (media) => !media.isArchived && media.isImage && !dejaReferences.has(media.idMedia),
    );
  });

  protected readonly mediasCandidatsFiltres = computed<readonly MediaView[]>(() => {
    const terme = this.rechercheMedia().trim().toLowerCase();
    const eligibles = this.mediasEligibles();
    if (!terme) return eligibles;
    return eligibles.filter((m) => m.displayName.toLowerCase().includes(terme));
  });

  protected readonly formulaireValide = computed(() => {
    const mode = this.editeur();
    if (!mode) return false;
    if (mode.mode === 'declarer' && this.idMediaChoisi() === null) return false;
    return (
      this.codeNatureChoisi() !== null &&
      this.libelleSaisi().trim().length > 0 &&
      this.libelleSaisi().trim().length <= 120
    );
  });

  constructor() {
    effect(() => {
      this.premierChampModale()?.nativeElement.focus();
    });
    void this.charger();
  }

  private async charger(): Promise<void> {
    this.chargement.set(true);
    this.erreur.set(null);
    try {
      const [naturesDto, refsPage, mediasPage] = await Promise.all([
        this.api.natures(),
        this.api.listReferences({ page: 1, size: TAILLE_PAGE }, false),
        this.api.list({ page: 1, size: TAILLE_PAGE }, true),
      ]);
      this.naturesBrutes.set(naturesDto.map(toMediaReferenceNature));
      this.referencesBrutes.set(refsPage.items);
      this.bibliotheque.set(mediasPage.items.map(toMediaView));
    } catch (erreur) {
      this.erreur.set(traduireErreurMedia(erreur));
    } finally {
      this.chargement.set(false);
    }
  }

  protected recharger(): void {
    void this.charger();
  }

  // ------------------------------------------- déclaration et modification

  protected ouvrirDeclaration(): void {
    this.erreurModale.set(null);
    this.avis.set(null);
    this.rechercheMedia.set('');
    this.idMediaChoisi.set(null);
    this.codeNatureChoisi.set(this.natures()[0]?.code ?? null);
    this.libelleSaisi.set('');
    this.descriptionSaisie.set('');
    this.estActifSaisi.set(true);
    this.editeur.set({ mode: 'declarer' });
  }

  protected ouvrirModification(reference: MediaReferenceView): void {
    this.erreurModale.set(null);
    this.avis.set(null);
    this.idMediaChoisi.set(reference.idMedia);
    this.codeNatureChoisi.set(reference.natureCode);
    this.libelleSaisi.set(reference.label);
    this.descriptionSaisie.set(reference.description ?? '');
    this.estActifSaisi.set(reference.isActive);
    this.editeur.set({ mode: 'modifier', reference });
  }

  protected fermerModale(): void {
    if (this.enCours()) return;
    this.editeur.set(null);
    this.erreurModale.set(null);
  }

  protected choisirMedia(media: MediaView): void {
    this.idMediaChoisi.set(media.idMedia);
    if (!this.libelleSaisi().trim()) {
      this.libelleSaisi.set(media.displayName);
    }
  }

  protected async enregistrer(): Promise<void> {
    const etat = this.editeur();
    const natureCode = this.codeNatureChoisi();
    if (!etat || !natureCode || !this.formulaireValide() || this.enCours()) return;

    this.enCours.set(true);
    this.erreurModale.set(null);
    try {
      const libelle = this.libelleSaisi().trim();
      const description = this.descriptionSaisie().trim() || null;

      if (etat.mode === 'declarer') {
        const idMedia = this.idMediaChoisi();
        if (idMedia === null) return;
        const creee = await this.api.createReference({
          id_media: idMedia,
          nature_code: natureCode,
          label: libelle,
          description,
        });
        this.referencesBrutes.update((courantes) => [creee, ...courantes]);
        this.editeur.set(null);
        this.avis.set(`« ${creee.label} » a été déclaré comme média de référence.`);
      } else {
        const modifiee = await this.api.updateReference(etat.reference.idMediaReferences, {
          nature_code: natureCode,
          label: libelle,
          description,
          is_active: this.estActifSaisi(),
        });
        this.referencesBrutes.update((courantes) =>
          courantes.map((r) =>
            r.id_media_references === modifiee.id_media_references ? modifiee : r,
          ),
        );
        this.editeur.set(null);
        this.avis.set(`Référence « ${modifiee.label} » mise à jour.`);
      }
    } catch (erreur) {
      this.erreurModale.set(traduireErreurMedia(erreur));
    } finally {
      this.enCours.set(false);
    }
  }

  // ------------------------------------------------ retrait de la référence

  protected demanderRetrait(idMediaReferences: number): void {
    this.retraitId.set(idMediaReferences);
  }

  protected renoncerRetrait(): void {
    this.retraitId.set(null);
  }

  protected async retirerReference(reference: MediaReferenceView): Promise<void> {
    if (this.enCours()) return;

    this.enCours.set(true);
    this.erreur.set(null);
    try {
      await this.api.archiveReference(reference.idMediaReferences);
      this.retraitId.set(null);
      this.referencesBrutes.update((courantes) =>
        courantes.filter((r) => r.id_media_references !== reference.idMediaReferences),
      );
      this.avis.set(
        `La qualité de référence a été retirée pour « ${reference.label} ». Le fichier reste dans la médiathèque.`,
      );
    } catch (erreur) {
      this.erreur.set(traduireErreurMedia(erreur));
    } finally {
      this.enCours.set(false);
    }
  }
}
