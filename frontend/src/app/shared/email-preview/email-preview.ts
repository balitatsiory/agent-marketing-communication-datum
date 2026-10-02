import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { MailContent } from '../../core/models/newsletter';
import { BrandLogo } from '../brand-logo/brand-logo';
import { Icon } from '../icon/icon';

/**
 * Rendu d'un courriel aux couleurs de Datum Academy.
 *
 * Sert deux écrans : l'aperçu d'un modèle, et ce qui a réellement été
 * envoyé. D'où `showVariables`, qui met en évidence les `{{variables}}`
 * d'un modèle — dans un envoi, elles sont déjà remplacées.
 *
 * La mise en forme reste volontairement proche de ce qu'acceptent les
 * clients de messagerie : largeur fixe, pas de grille, pas de `flex` pour
 * la structure du message.
 */
@Component({
  selector: 'app-email-preview',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [BrandLogo, Icon],
  templateUrl: './email-preview.html',
  styleUrl: './email-preview.scss',
})
export class EmailPreview {
  readonly content = input.required<MailContent>();
  /** Affiche l'objet et le pré-en-tête au-dessus du message. */
  readonly showHeader = input(true);
  /** Souligne les `{{variables}}` non substituées. */
  readonly showVariables = input(false);

  /**
   * Découpe un paragraphe en segments, en isolant les variables.
   *
   * Permet de les marquer sans injecter de HTML : le texte vient de
   * données, et le rendu reste une interpolation Angular.
   */
  protected segments(text: string): readonly { value: string; isVariable: boolean }[] {
    if (!this.showVariables()) return [{ value: text, isVariable: false }];

    const parts: { value: string; isVariable: boolean }[] = [];
    const pattern = /\{\{\s*[\w.]+\s*\}\}/g;
    let lastIndex = 0;

    for (const match of text.matchAll(pattern)) {
      const start = match.index ?? 0;
      if (start > lastIndex) {
        parts.push({ value: text.slice(lastIndex, start), isVariable: false });
      }
      parts.push({ value: match[0], isVariable: true });
      lastIndex = start + match[0].length;
    }

    if (lastIndex < text.length) {
      parts.push({ value: text.slice(lastIndex), isVariable: false });
    }
    return parts;
  }
}
