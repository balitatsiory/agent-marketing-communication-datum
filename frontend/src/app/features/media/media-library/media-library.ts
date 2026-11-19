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

import { MediaApi } from '../../../core/api/media.api';
import {
  MediaView,
  formaterPoids,
  toMediaView,
  traduireErreurMedia,
} from '../../../core/models/media-reference';
import { Session } from '../../../core/services/session';
import { Topbar } from '../../../layout/topbar/topbar';
import { Icon } from '../../../shared/icon/icon';

type FiltreMedia = 'actifs' | 'archives' | 'tous';

const LIBELLES_FILTRE: Readonly<Record<FiltreMedia, string>> = {
  actifs: 'Actifs',
  archives: 'Archivés',
  tous: 'Tous',
};

const TAILLE_PAGE = 200;

/**
 * Médiathèque — F-03, branchée sur `/api/v1/media`.
 *
 * **Aucune règle de taille ni de type n'est codée ici.** Le backend reconnaît
 * le format aux octets (et non à l'extension) et compresse les images de plus
 * de 8 Mo au lieu de les refuser : bloquer un fichier côté navigateur
 * contredirait le serveur.
 */
@Component({
  selector: 'app-media-library',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [Topbar, Icon],
  templateUrl: './media-library.html',
  styleUrl: './media-library.scss',
  host: {
    '(document:keydown.escape)': 'auEchap()',
    '(document:keydown.arrowleft)': 'auFlecheGauche($event)',
    '(document:keydown.arrowright)': 'auFlecheDroite($event)',
  },
})
export class MediaLibrary {
  private readonly api = inject(MediaApi);
  private readonly session = inject(Session);
  private readonly premierChampDepot =
    viewChild<ElementRef<HTMLInputElement>>('premierChampDepot');
  private readonly boutonFermerDetail =
    viewChild<ElementRef<HTMLButtonElement>>('boutonFermerDetail');

  protected readonly filtres: readonly FiltreMedia[] = ['actifs', 'archives', 'tous'];
  protected readonly libellesFiltre = LIBELLES_FILTRE;

  private readonly medias = signal<readonly MediaView[]>([]);
  protected readonly chargement = signal(true);
  protected readonly enCours = signal(false);
  protected readonly erreur = signal<string | null>(null);
  protected readonly avis = signal<string | null>(null);

  protected readonly filtre = signal<FiltreMedia>('actifs');
  protected readonly recherche = signal('');

  /** Renommage, archivage et purge depuis la vignette ou la fenêtre de détail. */
  protected readonly renommageId = signal<number | null>(null);
  protected readonly nouveauNom = signal('');
  protected readonly archivageId = signal<number | null>(null);
  protected readonly purgeId = signal<number | null>(null);

  /** Fenêtre modale de détail d'un média. */
  private readonly detailId = signal<number | null>(null);

  /** Fenêtre modale de dépôt. */
  protected readonly depotOuvert = signal(false);
  protected readonly fichierSelectionne = signal<File | null>(null);
  protected readonly nomDepot = signal('');
  protected readonly apercuLocal = signal<string | null>(null);
  protected readonly typeApercu = signal<'image' | 'video' | 'autre'>('autre');
  protected readonly progression = signal<number | null>(null);
  protected readonly erreurDepot = signal<string | null>(null);

  protected readonly peutGererMedias = computed(() => this.session.has('manage_media'));
  protected readonly peutPurger = computed(() => this.session.has('purge_media'));

  protected readonly compteurs = computed<Readonly<Record<FiltreMedia, number>>>(() => {
    const tous = this.medias();
    return {
      actifs: tous.filter((m) => !m.isArchived).length,
      archives: tous.filter((m) => m.isArchived).length,
      tous: tous.length,
    };
  });

  protected readonly resultats = computed<readonly MediaView[]>(() => {
    const filtre = this.filtre();
    const terme = this.recherche().trim().toLowerCase();

    return this.medias().filter((media) => {
      if (filtre === 'actifs' && media.isArchived) return false;
      if (filtre === 'archives' && !media.isArchived) return false;
      if (!terme) return true;
      return media.displayName.toLowerCase().includes(terme);
    });
  });

  protected readonly mediaDetail = computed<MediaView | null>(
    () => this.medias().find((m) => m.idMedia === this.detailId()) ?? null,
  );

  protected readonly indexDetail = computed<number>(() => {
    const id = this.detailId();
    if (id === null) return -1;
    return this.resultats().findIndex((m) => m.idMedia === id);
  });

  protected readonly peutDetailPrecedent = computed(() => this.indexDetail() > 0);
  protected readonly peutDetailSuivant = computed(() => {
    const idx = this.indexDetail();
    return idx >= 0 && idx < this.resultats().length - 1;
  });

  protected readonly poidsFichierSelectionne = computed(() => {
    const fichier = this.fichierSelectionne();
    return fichier ? formaterPoids(fichier.size) : '';
  });

  constructor() {
    effect(() => {
      this.premierChampDepot()?.nativeElement.focus();
    });
    effect(() => {
      this.boutonFermerDetail()?.nativeElement.focus();
    });
    inject(DestroyRef).onDestroy(() => this.libererApercu());
    void this.charger();
  }

  private async charger(): Promise<void> {
    this.chargement.set(true);
    this.erreur.set(null);
    try {
      const page = await this.api.list({ page: 1, size: TAILLE_PAGE }, true);
      this.medias.set(page.items.map(toMediaView));
    } catch (erreur) {
      this.erreur.set(traduireErreurMedia(erreur));
    } finally {
      this.chargement.set(false);
    }
  }

  protected recharger(): void {
    void this.charger();
  }

  // ------------------------------------------------ navigation clavier modale

  protected auEchap(): void {
    if (this.mediaDetail()) {
      this.fermerDetail();
      return;
    }
    if (this.depotOuvert()) {
      this.fermerDepot();
    }
  }

  protected auFlecheGauche(evenement: Event): void {
    if (!this.mediaDetail() || this.renommageId() !== null) return;
    evenement.preventDefault();
    this.detailPrecedent();
  }

  protected auFlecheDroite(evenement: Event): void {
    if (!this.mediaDetail() || this.renommageId() !== null) return;
    evenement.preventDefault();
    this.detailSuivant();
  }

  // --------------------------------------------------- détail d'un média (pop-up)

  protected ouvrirDetail(media: MediaView): void {
    this.detailId.set(media.idMedia);
  }

  protected fermerDetail(): void {
    this.detailId.set(null);
  }

  protected detailPrecedent(): void {
    const idx = this.indexDetail();
    if (idx > 0) {
      this.detailId.set(this.resultats()[idx - 1].idMedia);
    }
  }

  protected detailSuivant(): void {
    const idx = this.indexDetail();
    if (idx >= 0 && idx < this.resultats().length - 1) {
      this.detailId.set(this.resultats()[idx + 1].idMedia);
    }
  }

  // ------------------------------------------------------------------- dépôt

  protected ouvrirDepot(): void {
    this.libererApercu();
    this.fichierSelectionne.set(null);
    this.nomDepot.set('');
    this.progression.set(null);
    this.erreurDepot.set(null);
    this.avis.set(null);
    this.depotOuvert.set(true);
  }

  protected fermerDepot(): void {
    if (this.progression() !== null) return;
    this.libererApercu();
    this.fichierSelectionne.set(null);
    this.depotOuvert.set(false);
  }

  protected auChoixFichier(evenement: Event): void {
    const champ = evenement.target as HTMLInputElement;
    const fichier = champ.files?.[0] ?? null;
    this.libererApercu();
    this.erreurDepot.set(null);
    this.fichierSelectionne.set(fichier);

    if (fichier) {
      if (!this.nomDepot().trim()) {
        this.nomDepot.set(fichier.name);
      }
      const url = URL.createObjectURL(fichier);
      this.apercuLocal.set(url);
      if (fichier.type.startsWith('image/')) {
        this.typeApercu.set('image');
      } else if (fichier.type.startsWith('video/')) {
        this.typeApercu.set('video');
      } else {
        this.typeApercu.set('autre');
      }
    }
    champ.value = '';
  }

  protected async deposer(): Promise<void> {
    const fichier = this.fichierSelectionne();
    if (!fichier || this.enCours()) return;

    this.enCours.set(true);
    this.erreurDepot.set(null);
    this.progression.set(0);
    try {
      const dto = await this.api.upload(fichier, this.nomDepot(), (pct) => {
        this.progression.set(pct);
      });
      const vue = toMediaView(dto);
      this.medias.update((courants) => [vue, ...courants]);
      this.progression.set(null);
      this.fermerDepot();
      this.avis.set(`« ${vue.displayName} » a été déposé dans la médiathèque.`);
    } catch (erreur) {
      this.erreurDepot.set(traduireErreurMedia(erreur));
      this.progression.set(null);
    } finally {
      this.enCours.set(false);
    }
  }

  private libererApercu(): void {
    const url = this.apercuLocal();
    if (url) {
      URL.revokeObjectURL(url);
      this.apercuLocal.set(null);
    }
    this.typeApercu.set('autre');
  }

  // ------------------------------------------------ gestes sur une vignette

  protected ouvrirRenommage(media: MediaView): void {
    this.archivageId.set(null);
    this.purgeId.set(null);
    this.renommageId.set(media.idMedia);
    this.nouveauNom.set(media.displayName);
  }

  protected annulerRenommage(): void {
    this.renommageId.set(null);
    this.nouveauNom.set('');
  }

  protected async enregistrerRenommage(media: MediaView): Promise<void> {
    const nom = this.nouveauNom().trim();
    if (!nom || this.enCours()) return;

    this.enCours.set(true);
    this.erreur.set(null);
    try {
      const dto = await this.api.rename(media.idMedia, nom);
      const vue = toMediaView(dto);
      this.medias.update((courants) =>
        courants.map((m) => (m.idMedia === vue.idMedia ? vue : m)),
      );
      this.annulerRenommage();
      this.avis.set(`Média renommé en « ${vue.displayName} ».`);
    } catch (erreur) {
      this.erreur.set(traduireErreurMedia(erreur));
    } finally {
      this.enCours.set(false);
    }
  }

  protected demanderArchivage(idMedia: number): void {
    this.renommageId.set(null);
    this.purgeId.set(null);
    this.archivageId.set(idMedia);
  }

  protected renoncerArchivage(): void {
    this.archivageId.set(null);
  }

  protected async archiver(media: MediaView): Promise<void> {
    if (media.isArchived || this.enCours()) return;

    this.enCours.set(true);
    this.erreur.set(null);
    try {
      await this.api.archive(media.idMedia);
      this.archivageId.set(null);
      this.medias.update((courants) =>
        courants.map((m) => (m.idMedia === media.idMedia ? { ...m, isArchived: true } : m)),
      );
      this.avis.set(`« ${media.displayName} » est archivé.`);
    } catch (erreur) {
      this.erreur.set(traduireErreurMedia(erreur));
    } finally {
      this.enCours.set(false);
    }
  }

  protected demanderPurge(idMedia: number): void {
    this.renommageId.set(null);
    this.archivageId.set(null);
    this.purgeId.set(idMedia);
  }

  protected renoncerPurge(): void {
    this.purgeId.set(null);
  }

  protected async purger(media: MediaView): Promise<void> {
    if (!media.isArchived || !this.peutPurger() || this.enCours()) return;

    this.enCours.set(true);
    this.erreur.set(null);
    try {
      await this.api.purge(media.idMedia);
      this.purgeId.set(null);
      if (this.detailId() === media.idMedia) {
        this.detailId.set(null);
      }
      this.medias.update((courants) => courants.filter((m) => m.idMedia !== media.idMedia));
      this.avis.set(`« ${media.displayName} » a été définitivement supprimé.`);
    } catch (erreur) {
      this.erreur.set(traduireErreurMedia(erreur));
    } finally {
      this.enCours.set(false);
    }
  }
}
