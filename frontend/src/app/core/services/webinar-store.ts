import { Injectable, signal } from '@angular/core';
import { WEBINARS } from '../data/webinars.data';
import { Webinar } from '../models/webinar';

/**
 * Source unique des webinaires.
 *
 * Les données de départ sont statiques ; un webinaire créé ou repris par
 * le formulaire s'y ajoute le temps de la session. À remplacer par
 * `GET/POST /api/v1/webinars` quand le backend sera branché.
 */
@Injectable({ providedIn: 'root' })
export class WebinarStore {
  private readonly all = signal<readonly Webinar[]>(WEBINARS);

  /** Tous les webinaires : à venir, brouillons et passés. */
  readonly everything = this.all.asReadonly();

  /**
   * Message laissé par le formulaire à la liste, qui l'affiche puis l'efface
   * en la quittant. Simulation : rien n'est envoyé.
   */
  readonly notice = signal<string | null>(null);

  findById(id: number): Webinar | undefined {
    return this.all().find((webinar) => webinar.id === id);
  }

  nextId(): number {
    return this.all().reduce((max, webinar) => Math.max(max, webinar.id), 0) + 1;
  }

  /** Ajoute un webinaire en tête de liste, ou remplace celui qui porte le même identifiant. */
  save(webinar: Webinar): void {
    this.all.update((list) =>
      list.some((item) => item.id === webinar.id)
        ? list.map((item) => (item.id === webinar.id ? webinar : item))
        : [webinar, ...list],
    );
  }
}
