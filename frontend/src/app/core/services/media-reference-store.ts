import { Injectable, signal } from '@angular/core';
import { MEDIA_REFERENCES, simulatedAiDescription } from '../data/media-references.data';
import { MediaReference, MediaReferenceDraft } from '../models/media-reference';

/**
 * Source unique des médias de référence.
 *
 * Les données sont fictives (`media-references.data.ts`) et les
 * modifications ne vivent que le temps de la session. Quand l'API
 * existera, seul ce service changera : la page ne lit que lui.
 */
@Injectable({ providedIn: 'root' })
export class MediaReferenceStore {
  private readonly all = signal<readonly MediaReference[]>(MEDIA_REFERENCES);
  private nextId = Math.max(0, ...MEDIA_REFERENCES.map((media) => media.id)) + 1;

  /** Tous les médias, du plus récent au plus ancien. */
  readonly everything = this.all.asReadonly();

  /**
   * Description proposée par l'IA pour un fichier déposé.
   *
   * Simulée pour l'instant : voir `simulatedAiDescription`.
   */
  proposeDescription(file: File): string {
    return simulatedAiDescription(file.name);
  }

  /** Ajoute un média importé. Enregistrer vaut relecture : la case est obligatoire. */
  add(file: File, draft: MediaReferenceDraft): MediaReference {
    const media: MediaReference = {
      id: this.nextId++,
      fileName: file.name,
      ...normalise(draft),
      descriptionStatus: 'reviewed',
      previewUrl: file.type.startsWith('image/') ? URL.createObjectURL(file) : null,
    };
    this.all.update((current) => [media, ...current]);
    return media;
  }

  /** Met à jour un média existant. Le fichier, lui, ne change pas. */
  update(id: number, draft: MediaReferenceDraft): void {
    this.all.update((current) =>
      current.map((media): MediaReference =>
        media.id === id ? { ...media, ...normalise(draft), descriptionStatus: 'reviewed' } : media,
      ),
    );
  }
}

/** Le consentement n'a de sens que si une personne est représentée. */
function normalise(draft: MediaReferenceDraft): MediaReferenceDraft {
  return {
    role: draft.role,
    description: draft.description.trim(),
    depictsPerson: draft.depictsPerson,
    consentCollected: draft.depictsPerson && draft.consentCollected,
  };
}
