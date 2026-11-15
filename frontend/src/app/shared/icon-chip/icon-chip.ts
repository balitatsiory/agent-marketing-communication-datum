import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { Icon } from '../icon/icon';
import { IconName } from '../icon/icon-set';
import { SemanticRole, roleClass } from '../semantic-role';

/**
 * Icône colorée posée sur sa pastille.
 *
 * Le motif visuel repris de Phoenix : un glyphe de la couleur du
 * rôle sur un carré arrondi de sa teinte douce. Phoenix l'obtient
 * en empilant deux glyphes Font Awesome ; ici c'est un conteneur
 * et une règle CSS, sans dépendance externe.
 *
 * Le composant n'enveloppe pas une icône de plus : il réutilise
 * `<app-icon>` tel quel, et n'ajoute que la pastille. Toute icône
 * ajoutée à `ICON_SET` devient utilisable ici sans rien changer.
 *
 * @example
 * ```html
 * <app-icon-chip name="check" role="success" />
 * <app-icon-chip name="warn" role="warning" size="lg" />
 * <app-icon-chip name="megaphone" role="primary" solid />
 * ```
 */
@Component({
  selector: 'app-icon-chip',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [Icon],
  template: `
    <span class="icon-chip" [class]="classes()">
      <app-icon [name]="name()" />
    </span>
  `,
  styles: `
    :host { display: inline-flex; flex: none; }
  `,
})
export class IconChip {
  /** Nom d'un tracé de `ICON_SET`. */
  readonly name = input.required<IconName>();

  /** Ce que la pastille signifie. Décide de la paire de couleurs. */
  readonly role = input<SemanticRole>('primary');

  /** 30, 38 ou 46 px de côté. */
  readonly size = input<'sm' | 'md' | 'lg'>('md');

  /** Aplat de la couleur du rôle, glyphe en négatif. Un par écran au plus. */
  readonly solid = input(false);

  /** Pastille ronde plutôt que carrée arrondie. */
  readonly round = input(false);

  protected readonly classes = computed(() => {
    const classes = [roleClass(this.role())];
    if (this.size() !== 'md') classes.push(`icon-chip--${this.size()}`);
    if (this.solid()) classes.push('icon-chip--solid');
    if (this.round()) classes.push('icon-chip--round');
    return classes.join(' ');
  });
}
