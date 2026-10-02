import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { SocialNetworkCode } from '../../core/models/social-network';

/** Cartouche arrondi commun à la plupart des logos de réseaux. */
function framed(inner: string): string {
  return (
    '<rect x="2" y="2" width="20" height="20" rx="5.5" fill="none" stroke="currentColor" stroke-width="1.5"/>' +
    inner
  );
}

/**
 * Logos des réseaux, redessinés en monochrome.
 *
 * Les couleurs officielles des plateformes jureraient avec la charte
 * Datum et se disputeraient l'attention avec l'accent : tout hérite de
 * `currentColor`.
 */
const NETWORK_LOGOS: Readonly<Record<SocialNetworkCode, string>> = {
  facebook: framed(
    '<path d="M14.6 8.2h-1.3c-.5 0-.8.3-.8.9v1.6h2.1l-.3 2.2h-1.8v5.3h-2.2v-5.3H8.8v-2.2h1.5V8.8c0-1.7 1-2.7 2.7-2.7h1.6v2.1Z" fill="currentColor" stroke="none"/>',
  ),
  instagram:
    '<rect x="2" y="2" width="20" height="20" rx="5.5" fill="none" stroke="currentColor" stroke-width="1.5"/><circle cx="12" cy="12" r="3.6" fill="none" stroke="currentColor" stroke-width="1.5"/><circle cx="17.1" cy="6.9" r="1.05" fill="currentColor" stroke="none"/>',
  linkedin: framed(
    '<rect x="6.2" y="10" width="2.2" height="7.8" fill="currentColor" stroke="none"/><circle cx="7.3" cy="7.1" r="1.3" fill="currentColor" stroke="none"/><path d="M10.6 17.8V10h2.1v1.1c.5-.8 1.3-1.3 2.4-1.3 1.8 0 2.8 1.1 2.8 3.2v4.8h-2.2v-4.3c0-1.1-.4-1.8-1.3-1.8s-1.5.7-1.5 1.8v4.3h-2.3Z" fill="currentColor" stroke="none"/>',
  ),
  youtube: framed('<path d="M9.8 8.4 16.6 12l-6.8 3.6V8.4Z" fill="currentColor" stroke="none"/>'),
  tiktok: framed(
    '<path d="M13.4 6.1h1.9c.2 1.5 1.1 2.5 2.6 2.7v1.9c-1-.05-1.9-.35-2.6-.9v4c0 2.2-1.6 3.7-3.6 3.7a3.6 3.6 0 0 1 0-7.2c.2 0 .4 0 .6.05v2a1.7 1.7 0 1 0 1.1 1.6V6.1Z" fill="currentColor" stroke="none"/>',
  ),
};

/** Libellés affichés — les codes, eux, restent en anglais. */
export const NETWORK_LABELS: Readonly<Record<SocialNetworkCode, string>> = {
  facebook: 'Facebook',
  instagram: 'Instagram',
  linkedin: 'LinkedIn',
  youtube: 'YouTube',
  tiktok: 'TikTok',
};

/** Exemple : `<app-network-logo network="linkedin" size="lg" />` */
@Component({
  selector: 'app-network-logo',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <svg
      class="logo-net"
      [class.logo-net-lg]="size() === 'lg'"
      viewBox="0 0 24 24"
      role="img"
      [attr.aria-label]="label()"
      [innerHTML]="paths()"
    ></svg>
  `,
  styles: `
    :host { display: inline-flex; flex: none; }
  `,
})
export class NetworkLogo {
  private readonly sanitizer = inject(DomSanitizer);

  readonly network = input.required<SocialNetworkCode>();
  readonly size = input<'md' | 'lg'>('md');

  protected readonly label = computed(() => NETWORK_LABELS[this.network()]);
  protected readonly paths = computed<SafeHtml>(() =>
    this.sanitizer.bypassSecurityTrustHtml(NETWORK_LOGOS[this.network()]),
  );
}
