import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import {
  PUBLICATION_STATUS_LABELS,
  PublicationStatus,
  statusModifier,
} from '../../core/models/publication';

/** Pastille de statut d'une publication. */
@Component({
  selector: 'app-status-badge',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<span class="status" [class]="modifier()">{{ label() }}</span>`,
  styles: `
    :host { display: inline-flex; }
  `,
})
export class StatusBadge {
  readonly status = input.required<PublicationStatus>();

  protected readonly label = computed(() => PUBLICATION_STATUS_LABELS[this.status()]);
  protected readonly modifier = computed(() => statusModifier(this.status()));
}
