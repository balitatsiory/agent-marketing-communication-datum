import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
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
  formaterPoids,
  toMediaReferenceNature,
  toMediaReferenceView,
  toMediaView,
  traduireErreurMedia,
} from '../../../core/models/media-reference';
import { Session } from '../../../core/services/session';
import { Topbar } from '../../../layout/topbar/topbar';
import { Icon } from '../../../shared/icon/icon';

const TAILLE_PAGE = 200;
const LIEN_ACCEPTE = /^https:\/\/\S+$/i;
/** Attente après la dernière frappe avant de charger l'aperçu d'un lien. */
const DELAI_APERCU_MS = 500;

/** Un stockage local sert des adresses relatives : copiées, elles ne mèneraient nulle part. */
function lienAbsolu(url: string | undefined): string {
  return url ? new URL(url, document.baseURI).href : '';
}

type ModeEditeur =
  | { readonly mode: 'declarer' }
  | { readonly mode: 'modifier'; readonly reference: MediaReferenceView };

type SourceMediaReference = 'bibliotheque' | 'importer';

/**
 * Médias de référence — branchés sur `/api/v1/media-references` et
 * `/api/v1/media-reference-natures`.
 *
 * Un média de référence peut être déclaré de deux façons depuis la fenêtre
 * modale :
 * - en sélectionnant une image déjà présente dans la médiathèque ;
 * - ou en important directement un nouveau fichier : le client enchaîne alors
 *   `POST /api/v1/media` puis `POST /api/v1/media-references` sans inventer de
 *   route combinée côté serveur.
 */
@Component({
  selector: 'app-media-reference-list',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, Topbar, Icon],
  templateUrl: './media-reference-list.html',
  styleUrl: './media-reference-list.scss',
  host: {
    '(document:keydown.escape)': 'auEchap()',
    '(document:keydown.arrowleft)': 'auFlecheGauche($event)',
    '(document:keydown.arrowright)': 'auFlecheDroite($event)',
  },
})
export class MediaReferenceList {
  private readonly api = inject(MediaApi);
  private readonly session = inject(Session);
  private readonly premierChampModale =
    viewChild<ElementRef<HTMLElement>>('premierChampModale');
  private readonly boutonFermerDetail =
    viewChild<ElementRef<HTMLButtonElement>>('boutonFermerDetail');

  private readonly naturesBrutes = signal<readonly MediaReferenceNature[]>([]);
  private readonly referencesBrutes = signal<readonly MediaReferenceDto[]>([]);
  private readonly bibliotheque = signal<readonly MediaView[]>([]);

  protected readonly chargement = signal(true);
  protected readonly enCours = signal(false);
  protected readonly erreur = signal<string | null>(null);
  protected readonly avis = signal<string | null>(null);

  protected readonly recherche = signal('');
  protected readonly filtreNature = signal<string>('tous');

  /** Fenêtre modale de détail d'une référence. */
  private readonly detailId = signal<number | null>(null);

  /** Fenêtre modale de déclaration ou de modification. */
  protected readonly editeur = signal<ModeEditeur | null>(null);
  protected readonly erreurModale = signal<string | null>(null);
  protected readonly modeSource = signal<SourceMediaReference>('bibliotheque');
  protected readonly rechercheMedia = signal('');
  protected readonly idMediaChoisi = signal<number | null>(null);

  /** Import direct d'un nouveau fichier dans la modale de déclaration. */
  protected readonly fichierImporte = signal<File | null>(null);
  protected readonly apercuLocal = signal<string | null>(null);
  protected readonly progression = signal<number | null>(null);

  protected readonly codeNatureChoisi = signal<string | null>(null);
  protected readonly libelleSaisi = signal('');
  protected readonly descriptionSaisie = signal('');
  protected readonly estActifSaisi = signal(true);

  /** Lien de l'image dans la fenêtre de modification : saisi, et déjà enregistré. */
  protected readonly lienSaisi = signal('');
  private readonly lienEnregistre = signal('');
  protected readonly lienCopie = signal(false);
  protected readonly apercuLien = signal<string | null>(null);
  protected readonly apercuLienEchoue = signal(false);

  protected readonly lienModifie = computed(
    () => this.lienSaisi().trim() !== this.lienEnregistre(),
  );
  protected readonly erreurLien = computed<string | null>(() => {
    if (!this.lienModifie()) return null;
    const lien = this.lienSaisi().trim();
    if (!lien) return 'Le lien ne peut pas être vide.';
    return LIEN_ACCEPTE.test(lien) ? null : 'L’adresse doit commencer par « https:// ».';
  });
  /** Adresse que le navigateur peut ouvrir : celle enregistrée, ou une saisie acceptable. */
  protected readonly lienOuvrable = computed<string | null>(() =>
    this.erreurLien() === null ? this.lienSaisi().trim() || null : null,
  );

  protected readonly retraitId = signal<number | null>(null);

  protected readonly peutGererReferences = computed(() =>
    this.session.has('manage_media_reference'),
  );
  protected readonly peutDeposerMedia = computed(() =>
    this.session.has('manage_media'),
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

  protected readonly referenceDetail = computed<MediaReferenceView | null>(
    () => this.references().find((r) => r.idMediaReferences === this.detailId()) ?? null,
  );

  protected readonly indexDetail = computed<number>(() => {
    const id = this.detailId();
    if (id === null) return -1;
    return this.resultats().findIndex((r) => r.idMediaReferences === id);
  });

  protected readonly peutDetailPrecedent = computed(() => this.indexDetail() > 0);
  protected readonly peutDetailSuivant = computed(() => {
    const idx = this.indexDetail();
    return idx >= 0 && idx < this.resultats().length - 1;
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

  protected readonly poidsFichierImporte = computed(() => {
    const fichier = this.fichierImporte();
    return fichier ? formaterPoids(fichier.size) : '';
  });

  protected readonly formulaireValide = computed(() => {
    const mode = this.editeur();
    if (!mode) return false;
    if (mode.mode === 'declarer') {
      if (this.modeSource() === 'bibliotheque' && this.idMediaChoisi() === null) return false;
      if (this.modeSource() === 'importer' && this.fichierImporte() === null) return false;
    }
    if (mode.mode === 'modifier' && this.erreurLien() !== null) return false;
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
    effect(() => {
      this.boutonFermerDetail()?.nativeElement.focus();
    });
    effect((onCleanup) => {
      const lien = this.lienOuvrable();
      const minuterie = setTimeout(() => {
        this.apercuLien.set(lien);
        this.apercuLienEchoue.set(false);
      }, DELAI_APERCU_MS);
      onCleanup(() => clearTimeout(minuterie));
    });
    inject(DestroyRef).onDestroy(() => this.libererApercu());
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

  protected descriptionNature(code: string): string | null {
    return this.natures().find((n) => n.code === code)?.description ?? null;
  }

  // ------------------------------------------------ navigation clavier modales

  protected auEchap(): void {
    if (this.editeur()) {
      this.fermerModale();
      return;
    }
    if (this.referenceDetail()) {
      this.fermerDetail();
    }
  }

  protected auFlecheGauche(evenement: Event): void {
    if (!this.referenceDetail() || this.editeur()) return;
    evenement.preventDefault();
    this.detailPrecedent();
  }

  protected auFlecheDroite(evenement: Event): void {
    if (!this.referenceDetail() || this.editeur()) return;
    evenement.preventDefault();
    this.detailSuivant();
  }

  // ------------------------------------------------ détail d'une référence (pop-up)

  protected ouvrirDetail(reference: MediaReferenceView): void {
    this.detailId.set(reference.idMediaReferences);
  }

  protected fermerDetail(): void {
    this.detailId.set(null);
  }

  protected detailPrecedent(): void {
    const idx = this.indexDetail();
    if (idx > 0) {
      this.detailId.set(this.resultats()[idx - 1].idMediaReferences);
    }
  }

  protected detailSuivant(): void {
    const idx = this.indexDetail();
    if (idx >= 0 && idx < this.resultats().length - 1) {
      this.detailId.set(this.resultats()[idx + 1].idMediaReferences);
    }
  }

  protected ouvrirModificationDepuisDetail(reference: MediaReferenceView): void {
    this.fermerDetail();
    this.ouvrirModification(reference);
  }

  // ------------------------------------------- déclaration et modification

  protected ouvrirDeclaration(): void {
    this.libererApercu();
    this.erreurModale.set(null);
    this.avis.set(null);
    this.rechercheMedia.set('');
    this.idMediaChoisi.set(null);
    this.fichierImporte.set(null);
    this.progression.set(null);
    this.modeSource.set(this.mediasEligibles().length > 0 ? 'bibliotheque' : 'importer');
    this.codeNatureChoisi.set(this.natures()[0]?.code ?? null);
    this.libelleSaisi.set('');
    this.descriptionSaisie.set('');
    this.estActifSaisi.set(true);
    this.editeur.set({ mode: 'declarer' });
  }

  protected ouvrirModification(reference: MediaReferenceView): void {
    this.libererApercu();
    this.erreurModale.set(null);
    this.avis.set(null);
    this.idMediaChoisi.set(reference.idMedia);
    this.codeNatureChoisi.set(reference.natureCode);
    this.libelleSaisi.set(reference.label);
    this.descriptionSaisie.set(reference.description ?? '');
    this.estActifSaisi.set(reference.isActive);
    const lien = lienAbsolu(reference.media?.url);
    this.lienEnregistre.set(lien);
    this.lienSaisi.set(lien);
    this.lienCopie.set(false);
    // Posé tout de suite : l'aperçu d'une autre référence ne doit pas rester affiché.
    this.apercuLien.set(lien || null);
    this.apercuLienEchoue.set(false);
    this.editeur.set({ mode: 'modifier', reference });
  }

  protected saisirLien(lien: string): void {
    this.lienSaisi.set(lien);
    this.lienCopie.set(false);
    // Le refus affiché portait sur le lien précédent.
    this.erreurModale.set(null);
  }

  protected async copierLien(champ: HTMLInputElement): Promise<void> {
    try {
      await navigator.clipboard.writeText(this.lienSaisi().trim());
      this.lienCopie.set(true);
      this.erreurModale.set(null);
    } catch {
      champ.select();
      this.erreurModale.set('Copie impossible : le lien est sélectionné, copiez-le avec Ctrl+C.');
    }
  }

  protected fermerModale(): void {
    if (this.enCours()) return;
    this.libererApercu();
    this.fichierImporte.set(null);
    this.progression.set(null);
    this.editeur.set(null);
    this.erreurModale.set(null);
  }

  protected changerModeSource(mode: SourceMediaReference): void {
    if (this.enCours()) return;
    this.modeSource.set(mode);
    this.erreurModale.set(null);
  }

  protected choisirMedia(media: MediaView): void {
    this.idMediaChoisi.set(media.idMedia);
    if (!this.libelleSaisi().trim()) {
      this.libelleSaisi.set(media.displayName);
    }
  }

  protected auChoixFichier(evenement: Event): void {
    const champ = evenement.target as HTMLInputElement;
    const fichier = champ.files?.[0] ?? null;
    this.libererApercu();
    this.erreurModale.set(null);
    this.fichierImporte.set(fichier);

    if (fichier) {
      if (!this.libelleSaisi().trim()) {
        this.libelleSaisi.set(fichier.name);
      }
      if (fichier.type.startsWith('image/')) {
        this.apercuLocal.set(URL.createObjectURL(fichier));
      }
    }
    champ.value = '';
  }

  private libererApercu(): void {
    const url = this.apercuLocal();
    if (url) {
      URL.revokeObjectURL(url);
      this.apercuLocal.set(null);
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
        let idMedia = this.idMediaChoisi();

        if (this.modeSource() === 'importer') {
          const fichier = this.fichierImporte();
          if (!fichier) return;
          this.progression.set(0);
          const mediaDto = await this.api.upload(fichier, libelle, (pct) => {
            this.progression.set(pct);
          });
          const mediaVue = toMediaView(mediaDto);
          this.bibliotheque.update((courants) => [mediaVue, ...courants]);
          idMedia = mediaVue.idMedia;
          this.progression.set(null);
        }

        if (idMedia === null) return;
        const creee = await this.api.createReference({
          id_media: idMedia,
          nature_code: natureCode,
          label: libelle,
          description,
        });
        this.referencesBrutes.update((courantes) => [creee, ...courantes]);
        this.libererApercu();
        this.fichierImporte.set(null);
        this.editeur.set(null);
        this.avis.set(`« ${creee.label} » a été déclaré comme média de référence.`);
      } else {
        const idReference = etat.reference.idMediaReferences;
        const imageRemplacee = this.lienModifie();
        // L'image d'abord : c'est l'étape qui peut être refusée, et rien d'autre
        // n'est alors enregistré.
        if (imageRemplacee) await this.remplacerImage(idReference, this.lienSaisi().trim());
        const modifiee = await this.api.updateReference(idReference, {
          nature_code: natureCode,
          label: libelle,
          description,
          is_active: this.estActifSaisi(),
        });
        this.majReference(modifiee);
        this.editeur.set(null);
        this.avis.set(
          imageRemplacee
            ? `Référence « ${modifiee.label} » mise à jour. Sa nouvelle image est enregistrée.`
            : `Référence « ${modifiee.label} » mise à jour.`,
        );
      }
    } catch (erreur) {
      this.erreurModale.set(traduireErreurMedia(erreur));
      this.progression.set(null);
    } finally {
      this.enCours.set(false);
    }
  }

  private async remplacerImage(idReference: number, lien: string): Promise<void> {
    const remplacee = await this.api.replaceReferenceImage(idReference, lien);
    // C'est fait côté serveur : un nouvel essai ne doit pas rapatrier l'image deux fois.
    this.lienEnregistre.set(lien);
    const media = toMediaView(await this.api.get(remplacee.id_media));
    this.bibliotheque.update((courants) => [media, ...courants]);
    this.majReference(remplacee);
    const copie = lienAbsolu(media.url);
    this.lienEnregistre.set(copie);
    this.lienSaisi.set(copie);
  }

  private majReference(reference: MediaReferenceDto): void {
    this.referencesBrutes.update((courantes) =>
      courantes.map((r) =>
        r.id_media_references === reference.id_media_references ? reference : r,
      ),
    );
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
      if (this.detailId() === reference.idMediaReferences) {
        this.detailId.set(null);
      }
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
