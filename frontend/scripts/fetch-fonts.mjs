/**
 * Télécharge les .woff2 de Nunito Sans dans `public/fonts/`.
 *
 * Pourquoi un script plutôt que les fichiers dans le dépôt : ce sont
 * des binaires, et un dépôt de code se porte mieux sans. Pourquoi pas
 * un CDN : l'application auto-héberge déjà ses polices, pour ne faire
 * aucune requête vers un tiers.
 *
 *   node scripts/fetch-fonts.mjs      (ou : npm run fonts:nunito)
 *
 * Le script demande à l'API Google Fonts la feuille de style de la
 * variante variable, y lit les adresses des .woff2 et les enregistre
 * sous les noms attendus par `src/styles/_fonts.scss`.
 *
 * Licence : Nunito Sans est sous SIL Open Font License 1.1 — usage
 * commercial et auto-hébergement autorisés, le texte de la licence
 * doit accompagner les fichiers de police redistribués. Le script
 * enregistre donc aussi OFL.txt à côté des .woff2.
 */

import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const CSS_URL =
  'https://fonts.googleapis.com/css2?family=Nunito+Sans:wght@300..900&display=swap';

/* Sans cet en-tête, l'API renvoie du .ttf au lieu du .woff2. */
const MODERN_BROWSER =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36';

const DESTINATION = join(process.cwd(), 'public', 'fonts');

/** Correspondance entre le commentaire de sous-ensemble et le nom de fichier. */
const SUBSETS = {
  latin: 'nunito-sans-variable-latin.woff2',
  'latin-ext': 'nunito-sans-variable-latin-ext.woff2',
};

async function main() {
  console.log('Lecture de la feuille de style Google Fonts…');
  const response = await fetch(CSS_URL, { headers: { 'User-Agent': MODERN_BROWSER } });
  if (!response.ok) {
    throw new Error(`Google Fonts a répondu ${response.status}. Réseau bloqué ?`);
  }
  const css = await response.text();

  // La feuille est une suite de blocs, chacun précédé d'un commentaire
  // qui nomme son sous-ensemble (latin, latin-ext, …), puis d'une règle
  // @font-face dont le src pointe sur le .woff2 correspondant.
  const blocs = css.split('/*').slice(1);
  let écrits = 0;

  await mkdir(DESTINATION, { recursive: true });

  for (const bloc of blocs) {
    const sousEnsemble = bloc.slice(0, bloc.indexOf('*/')).trim();
    const nomFichier = SUBSETS[sousEnsemble];
    if (!nomFichier) continue;

    const url = bloc.match(/url\((https:\/\/[^)]+\.woff2)\)/)?.[1];
    if (!url) continue;

    const fichier = await fetch(url);
    if (!fichier.ok) throw new Error(`Téléchargement de ${url} : ${fichier.status}`);

    const chemin = join(DESTINATION, nomFichier);
    await writeFile(chemin, Buffer.from(await fichier.arrayBuffer()));
    console.log(`  ✓ ${nomFichier}`);
    écrits += 1;
  }

  if (écrits !== Object.keys(SUBSETS).length) {
    throw new Error(
      `${écrits} fichier(s) écrit(s) sur ${Object.keys(SUBSETS).length} attendus. ` +
        'La réponse de Google Fonts a peut-être changé de forme.',
    );
  }

  const licence = await fetch(
    'https://raw.githubusercontent.com/googlefonts/nunito/main/OFL.txt',
  ).catch(() => null);
  if (licence?.ok) {
    await writeFile(join(DESTINATION, 'nunito-sans-OFL.txt'), await licence.text());
    console.log('  ✓ nunito-sans-OFL.txt');
  } else {
    console.warn(
      '  ! Licence non récupérée. À placer à la main : OFL 1.1 depuis\n' +
        '    https://fonts.google.com/specimen/Nunito+Sans/license',
    );
  }

  console.log('\nTerminé. Relancez `ng serve` pour voir la police appliquée.');
}

main().catch((erreur) => {
  console.error('\nÉchec :', erreur.message);
  console.error(
    "\nSi le réseau est filtré, récupérez les deux .woff2 à la main depuis\n" +
      'https://fonts.google.com/specimen/Nunito+Sans et placez-les dans\n' +
      `${DESTINATION} sous les noms :\n  ` +
      Object.values(SUBSETS).join('\n  '),
  );
  process.exitCode = 1;
});
