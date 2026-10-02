/**
 * Jeu d'icônes — tracés seuls, sur une grille de 24.
 *
 * Reprises telles quelles du prototype HTML. Chaque valeur est le
 * contenu d'un `<svg viewBox="0 0 24 24">` : pas de couleur, pas de
 * remplissage, la mise en forme vient de la classe `.ico` qui hérite
 * de `currentColor`.
 */
export const ICON_SET = {
  megaphone:
    '<path d="M4 10v4a1 1 0 0 0 1 1h2l1.2 4.2a1 1 0 0 0 1 .8h.6a1 1 0 0 0 1-1.2L10 15h1l7 3.5a1 1 0 0 0 1.5-.9V6.4A1 1 0 0 0 18 5.5L11 9H5a1 1 0 0 0-1 1Z"/>',
  pencil: '<path d="M4 20h4L19 9a2.1 2.1 0 0 0-3-3L5 17v3Z"/><path d="M14.5 7.5 16.5 9.5"/>',
  sparkle:
    '<path d="M12 3.5 13.6 9 19 10.6 13.6 12.2 12 17.7 10.4 12.2 5 10.6 10.4 9 12 3.5Z"/><path d="M18 16.5l.7 2.1 2.1.7-2.1.7-.7 2.1-.7-2.1-2.1-.7 2.1-.7.7-2.1Z"/>',
  files:
    '<rect x="7" y="3.5" width="12" height="14" rx="2"/><path d="M15.5 20.5H6.8A1.8 1.8 0 0 1 5 18.7V7"/><path d="M10 8h6M10 11.5h6M10 15h3.5"/>',
  clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7v5.2l3.2 2"/>',
  calendar:
    '<rect x="3.5" y="5" width="17" height="15.5" rx="2.2"/><path d="M3.5 10h17M8 3.5v3M16 3.5v3"/><path d="M7.5 14h2.2M12 14h2.2M7.5 17.2h2.2M12 17.2h2.2"/>',
  chat:
    '<path d="M20.5 12.4c0 4-3.8 7.2-8.5 7.2a10 10 0 0 1-2.6-.34L4.5 21l1.3-3.6A6.9 6.9 0 0 1 3.5 12.4c0-4 3.8-7.2 8.5-7.2s8.5 3.2 8.5 7.2Z"/>',
  cap:
    '<path d="M2.8 9.4 12 5.2l9.2 4.2-9.2 4.2-9.2-4.2Z"/><path d="M6.5 11.2v4.4c0 1.5 2.5 2.8 5.5 2.8s5.5-1.3 5.5-2.8v-4.4"/><path d="M21.2 9.4v5.2"/>',
  video: '<rect x="2.8" y="6" width="12.6" height="12" rx="2.4"/><path d="M15.4 11 21.2 8v8l-5.8-3v-2Z"/>',
  chart: '<path d="M4 20h16"/><path d="M6.5 20V13M11 20V7.5M15.5 20v-4.6M20 20V10.5"/>',
  share:
    '<circle cx="17.5" cy="6" r="2.6"/><circle cx="6.5" cy="12" r="2.6"/><circle cx="17.5" cy="18" r="2.6"/><path d="M15.2 7.3 8.8 10.7M8.8 13.3l6.4 3.4"/>',
  history: '<path d="M3.8 12a8.2 8.2 0 1 0 2.6-6"/><path d="M3.4 3.6v4h4"/><path d="M12 7.6V12l3 1.8"/>',
  bell:
    '<path d="M6.2 10.3a5.8 5.8 0 0 1 11.6 0c0 3.4.9 5 1.7 5.9.4.4.1 1.1-.5 1.1H5c-.6 0-.9-.7-.5-1.1.8-.9 1.7-2.5 1.7-5.9Z"/><path d="M10 20.2a2.3 2.3 0 0 0 4 0"/>',
  sliders:
    '<path d="M4 7.5h10M18.5 7.5h1.5M4 16.5h3M11.5 16.5h8.5"/><circle cx="16" cy="7.5" r="2.2"/><circle cx="9" cy="16.5" r="2.2"/>',
  users:
    '<circle cx="9.4" cy="8.4" r="3.4"/><path d="M3.5 19.5c0-3.1 2.6-5.2 5.9-5.2s5.9 2.1 5.9 5.2"/><path d="M16.6 5.4a3.2 3.2 0 0 1 0 6.1M17.6 14.6c2.1.5 3.4 2 3.4 4.2"/>',
  gear:
    '<circle cx="12" cy="12" r="2.9"/><path d="M12 3.5v2.1M12 18.4v2.1M20.5 12h-2.1M5.6 12H3.5M18 6l-1.5 1.5M7.5 16.5 6 18M18 18l-1.5-1.5M7.5 7.5 6 6"/>',
  search: '<circle cx="11" cy="11" r="6.4"/><path d="M15.8 15.8 20.5 20.5"/>',
  chevron: '<path d="M6.5 9.5 12 15l5.5-5.5"/>',
  panelLeft: '<rect x="3.5" y="4.5" width="17" height="15" rx="2.2"/><path d="M10 4.5v15"/>',
  plus: '<path d="M12 5.5v13M5.5 12h13"/>',
  close: '<path d="M6.5 6.5 17.5 17.5M17.5 6.5 6.5 17.5"/>',
  filter: '<path d="M4 6h16l-6.2 7.2v5.3l-3.6 1.8v-7.1L4 6Z"/>',
  download: '<path d="M12 4v10.5M7.8 10.6 12 14.8l4.2-4.2"/><path d="M4.5 18.5h15"/>',
  external:
    '<path d="M14 5h5v5"/><path d="M19 5l-7.5 7.5"/><path d="M18 14.5v4a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 4 18.5v-11A1.5 1.5 0 0 1 5.5 6h4"/>',
  arrowRight: '<path d="M5 12h13M13 7l5 5-5 5"/>',
  check: '<path d="M5 12.5 10 17.5 19 6.5"/>',
  dots:
    '<circle cx="5.5" cy="12" r="1.4" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="1.4" fill="currentColor" stroke="none"/><circle cx="18.5" cy="12" r="1.4" fill="currentColor" stroke="none"/>',
  image:
    '<rect x="3.5" y="5" width="17" height="14" rx="2.2"/><circle cx="8.8" cy="10" r="1.6"/><path d="M4 16.5 9.5 12l4 3.4 3-2.4 4 3.5"/>',
  send: '<path d="M20.5 3.5 3.5 10.2l6.8 2.8 2.8 6.8 7.4-16.3Z"/><path d="M10.3 13 20.5 3.5"/>',
  grid:
    '<rect x="4" y="4" width="7" height="7" rx="1.6"/><rect x="13" y="4" width="7" height="7" rx="1.6"/><rect x="4" y="13" width="7" height="7" rx="1.6"/><rect x="13" y="13" width="7" height="7" rx="1.6"/>',
  columns:
    '<rect x="3.5" y="4.5" width="5" height="15" rx="1.6"/><rect x="9.5" y="4.5" width="5" height="15" rx="1.6"/><rect x="15.5" y="4.5" width="5" height="15" rx="1.6"/>',
  warn: '<path d="M12 4.5 21 19.5H3L12 4.5Z"/><path d="M12 10v4M12 16.6v.1"/>',
} as const;

/** Nom d'une icône du jeu — vérifié à la compilation. */
export type IconName = keyof typeof ICON_SET;
