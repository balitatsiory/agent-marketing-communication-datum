/**
 * Propose au navigateur d'enregistrer un fichier reçu de l'API.
 *
 * Un simple lien ne suffit pas : la route exige le jeton d'accès, que seul un
 * appel de l'application porte.
 */
export function downloadFile(contenu: Blob, nom: string): void {
  const adresse = URL.createObjectURL(contenu);
  const lien = document.createElement('a');
  lien.href = adresse;
  lien.download = nom;
  lien.click();
  // Libérée au tour suivant : le navigateur lit l'adresse après le clic.
  setTimeout(() => URL.revokeObjectURL(adresse), 0);
}

/** « Bilan été 2026 » → « bilan-ete-2026 », pour un nom de fichier. */
export function fileSlug(texte: string): string {
  return texte
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .slice(0, 60)
    .replace(/^-+|-+$/g, '');
}
