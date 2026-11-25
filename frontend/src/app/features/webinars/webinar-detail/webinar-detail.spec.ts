import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { RegistrationDto, WebinarsApi } from '../../../core/api/webinars.api';
import { Session } from '../../../core/services/session';
import { WebinarDetailDialog } from './webinar-detail';

/** Ce que le test lit et appelle : les membres sont réservés au gabarit. */
interface InscritsDeLaFiche {
  loadRegistrations(page: number): Promise<void>;
  chooseRegistrationSize(taille: number): Promise<void>;
  registrationPage(): number;
  registrationSize(): number;
  registrations(): readonly RegistrationDto[];
  error(): string | null;
}

describe('WebinarDetailDialog, onglet Inscrits', () => {
  let panne = false;

  /** 22 inscrits, découpés comme le fait l'API. */
  const registrations = async (_id: number, page: number, size: number) => {
    if (panne) throw new Error('API injoignable');
    const debut = (page - 1) * size;
    const lignes = Math.max(0, Math.min(size, 22 - debut));
    return {
      items: Array.from({ length: lignes }, (_, rang) => ({
        id_webinar_registrations: debut + rang + 1,
      })),
      total: 22,
      page,
      size,
      pages: Math.ceil(22 / size),
    };
  };

  function creer(): InscritsDeLaFiche {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        { provide: WebinarsApi, useValue: { reference: async () => null, registrations } },
        { provide: Session, useValue: { has: () => true } },
      ],
    });
    // Sans détection des changements : seules les méthodes sont mises à l'épreuve.
    const fixture = TestBed.createComponent(WebinarDetailDialog);
    fixture.componentRef.setInput('id', 1);
    return fixture.componentInstance as unknown as InscritsDeLaFiche;
  }

  beforeEach(() => (panne = false));

  it('applique la nouvelle taille quand les lignes arrivent', async () => {
    const fiche = creer();
    await fiche.loadRegistrations(3);

    await fiche.chooseRegistrationSize(50);

    expect(fiche.registrationSize()).toBe(50);
    expect(fiche.registrationPage()).toBe(1);
    expect(fiche.registrations().length).toBe(22);
  });

  it('garde la taille des lignes affichées quand la demande échoue', async () => {
    const fiche = creer();
    await fiche.loadRegistrations(3);
    panne = true;

    await fiche.chooseRegistrationSize(50);

    expect(fiche.registrationSize()).toBe(10);
    expect(fiche.registrationPage()).toBe(3);
    expect(fiche.registrations().length).toBe(2);
    expect(fiche.error()).not.toBeNull();
  });
});
