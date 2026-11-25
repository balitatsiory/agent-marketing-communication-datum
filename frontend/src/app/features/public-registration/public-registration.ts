import { ChangeDetectionStrategy, Component, OnInit, computed, inject, input, signal } from '@angular/core';

import { toApiError } from '../../core/api/api-error';
import { PublicPageDto, WebinarsApi } from '../../core/api/webinars.api';
import { BrandLogo } from '../../shared/brand-logo/brand-logo';
import { Icon } from '../../shared/icon/icon';
import { durationLabel, longSchedule } from '../webinars/webinar-format';

/**
 * Formulaire public d'inscription — `/inscription/:slug`.
 *
 * Seule page de l'application ouverte sans session : adresse e-mail, prénom,
 * nom de famille, et l'accord pour les newsletters, jamais coché d'avance.
 */
@Component({
  selector: 'app-public-registration',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [BrandLogo, Icon],
  templateUrl: './public-registration.html',
  styleUrl: './public-registration.scss',
})
export class PublicRegistration implements OnInit {
  readonly slug = input.required<string>();

  private readonly api = inject(WebinarsApi);

  protected readonly page = signal<PublicPageDto | null>(null);
  protected readonly loading = signal(true);
  protected readonly sending = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly done = signal<string | null>(null);

  protected readonly email = signal('');
  protected readonly firstName = signal('');
  protected readonly lastName = signal('');
  protected readonly consent = signal(false);
  /** Champ leurre : invisible, il ne se remplit que par un robot. */
  protected readonly website = signal('');

  protected readonly schedule = computed(() => {
    const page = this.page();
    if (!page) return '';
    const duree = page.duration_minutes ? ` · ${durationLabel(page.duration_minutes)}` : '';
    // L'heure affichée est celle du visiteur : le dire évite un rendez-vous manqué.
    const zone =
      page.starts_at && page.is_time_known
        ? ` (${Intl.DateTimeFormat().resolvedOptions().timeZone})`
        : '';
    return `${longSchedule(page)}${zone}${duree}`;
  });

  protected readonly canSend = computed(
    () =>
      /^\S+@\S+\.\S+$/.test(this.email().trim()) &&
      !!this.firstName().trim() &&
      !!this.lastName().trim() &&
      !this.sending(),
  );

  async ngOnInit(): Promise<void> {
    try {
      this.page.set(await this.api.publicPage(this.slug()));
    } catch (erreur) {
      this.error.set(toApiError(erreur).message);
    } finally {
      this.loading.set(false);
    }
  }

  protected async register(): Promise<void> {
    if (!this.canSend()) return;
    this.sending.set(true);
    this.error.set(null);
    try {
      const reponse = await this.api.registerPublic(this.slug(), {
        email: this.email().trim(),
        first_name: this.firstName().trim(),
        last_name: this.lastName().trim(),
        has_newsletter_consent: this.consent(),
        website: this.website(),
      });
      this.done.set(reponse.message);
    } catch (erreur) {
      this.error.set(toApiError(erreur).message);
    } finally {
      this.sending.set(false);
    }
  }
}
