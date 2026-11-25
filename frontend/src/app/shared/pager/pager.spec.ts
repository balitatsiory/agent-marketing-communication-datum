import { TestBed } from '@angular/core/testing';

import { Pager } from './pager';

describe('Pager', () => {
  it('ne montre une nouvelle taille qu’une fois appliquée par le parent', () => {
    const fixture = TestBed.createComponent(Pager);
    for (const [nom, valeur] of Object.entries({
      page: 1,
      pages: 3,
      total: 22,
      size: 10,
      sizes: [10, 25, 50],
    })) {
      fixture.componentRef.setInput(nom, valeur);
    }
    const demandes: number[] = [];
    fixture.componentInstance.sizeChange.subscribe((taille) => demandes.push(taille));
    fixture.detectChanges();
    const liste: HTMLSelectElement = fixture.nativeElement.querySelector('select');

    liste.value = '50';
    liste.dispatchEvent(new Event('change'));

    expect(demandes).toEqual([50]);
    // La demande peut échouer : la liste montre toujours la taille affichée.
    expect(liste.value).toBe('10');

    fixture.componentRef.setInput('size', 50);
    fixture.detectChanges();

    expect(liste.value).toBe('50');
  });
});
