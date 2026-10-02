import { Injectable, effect, signal } from '@angular/core';
import { NAVIGATION } from '../data/navigation.data';

const RAIL_KEY = 'iagora.sidebar.rail';
const CLOSED_GROUPS_KEY = 'iagora.sidebar.closedGroups';

/**
 * État de la barre latérale : repliée en rail, et catégories fermées.
 *
 * Mémorisé dans le `localStorage` pour survivre à un rechargement. Chaque
 * accès est protégé : en navigation privée, l'API existe mais lève.
 */
@Injectable({ providedIn: 'root' })
export class SidebarState {
  readonly isRail = signal(read(RAIL_KEY) === '1');
  readonly closedGroups = signal<ReadonlySet<string>>(new Set(readList(CLOSED_GROUPS_KEY)));

  constructor() {
    effect(() => write(RAIL_KEY, this.isRail() ? '1' : '0'));
    effect(() => write(CLOSED_GROUPS_KEY, [...this.closedGroups()].join(',')));
  }

  toggleRail(): void {
    this.isRail.update((value) => !value);
  }

  isGroupOpen(key: string): boolean {
    return !this.closedGroups().has(key);
  }

  toggleGroup(key: string): void {
    this.closedGroups.update((current) => {
      const next = new Set(current);
      if (!next.delete(key)) next.add(key);
      return next;
    });
  }

  /**
   * Ouvre la catégorie contenant la route donnée.
   *
   * Sans cela, arriver sur un écran par une URL directe peut laisser sa
   * catégorie fermée, et l'entrée active invisible.
   */
  revealRoute(url: string): void {
    for (const entry of NAVIGATION) {
      if (entry.type !== 'group') continue;

      for (const child of entry.items) {
        if (child.kind === 'link') {
          if (url.startsWith(child.route)) return this.openAll(entry.key);
          continue;
        }
        // Un écran de sous-menu demande d'ouvrir les deux niveaux.
        if (child.items.some((leaf) => url.startsWith(leaf.route))) {
          return this.openAll(entry.key, child.key);
        }
      }
    }
  }

  private openAll(...keys: readonly string[]): void {
    this.closedGroups.update((current) => {
      if (!keys.some((key) => current.has(key))) return current;
      const next = new Set(current);
      for (const key of keys) next.delete(key);
      return next;
    });
  }
}

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function readList(key: string): string[] {
  const raw = read(key);
  return raw ? raw.split(',').filter(Boolean) : [];
}

function write(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    // Stockage indisponible : l'état reste valable pour la session en cours.
  }
}
