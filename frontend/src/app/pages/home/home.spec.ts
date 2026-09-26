import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { HomePage } from './home';

describe('HomePage', () => {
  let fixture: ComponentFixture<HomePage>;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HomePage],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();
    fixture = TestBed.createComponent(HomePage);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  function flushOverview(options?: { analyticsFailure?: boolean }): void {
    fixture.detectChanges();
    http.expectOne('/api/v1/scheduling/materialize').flush({ horizon_from: '2026-08-14' });
    http.expectOne('/api/v1/funds/summary').flush({
      accounts: [{ physical_balance: '150.0000' }],
      funds: [
        { id: 'small', name: 'Small', total_balance: '10.0000' },
        { id: 'large', name: 'Large', total_balance: '40.0000' },
      ],
      total_reserved: '50.0000',
      total_free: '100.0000',
    });
    http
      .expectOne((request) => request.url === '/api/v1/forecast')
      .flush({
        from_on: '2026-08-14',
        through_on: '2026-09-14',
        starting_balance: '150.0000',
        ending_balance: '140.0000',
        minimum_balance: '130.0000',
        minimum_on: '2026-08-20',
        first_negative_on: null,
      });
    http.expectOne((request) => request.url === '/api/v1/operations').flush({ items: [] });
    http
      .expectOne((request) => request.url === '/api/v1/scheduling/occurrences')
      .flush({ items: [], total: 0 });
    http.expectOne('/api/v1/settings').flush({ base_currency: 'RUB' });
    const categories = http.expectOne((request) => {
      return (
        request.url === '/api/v1/operations/category-summary' &&
        request.params.get('from_on') === '2026-08-01' &&
        request.params.get('through_on') === '2026-08-31'
      );
    });
    if (options?.analyticsFailure) {
      categories.flush(
        { detail: { message: 'failure' } },
        { status: 500, statusText: 'Server Error' },
      );
    } else {
      categories.flush({
        expense: [
          { category_id: 'food', category_name: 'Food', amount: '30.0000' },
          { category_id: 'home', category_name: 'Home', amount: '20.0000' },
        ],
        income: [{ category_id: 'salary', category_name: 'Salary', amount: '100.0000' }],
      });
    }
    fixture.detectChanges();
  }

  it('renders labelled, linked charts and orders funds by reserved amount', () => {
    flushOverview();

    const cards = fixture.nativeElement.querySelectorAll(
      '.breakdown-card',
    ) as NodeListOf<HTMLElement>;
    expect(cards).toHaveLength(3);
    expect(cards[2].textContent).toContain('Текущее состояние');
    expect(cards[2].querySelector('li')?.textContent).toContain('Large');
    expect(cards[0].querySelectorAll('.breakdown-track')).toHaveLength(2);
    expect(cards[1].querySelector('.breakdown-track i')).not.toBeNull();
    const expenseLink = cards[0].querySelector('li a') as HTMLAnchorElement;
    expect(expenseLink.getAttribute('href')).toContain('/operations');
    expect(expenseLink.getAttribute('href')).toContain('category_id=food');
    expect(expenseLink.getAttribute('href')).toContain('occurred_from=2026-08-01');
    expect(fixture.nativeElement.querySelectorAll('.overview-balances article')).toHaveLength(3);
    expect(fixture.nativeElement.querySelector('.forecast-ending').textContent).toContain(
      '140,00 ₽',
    );
  });

  it('keeps the financial overview available when category analytics fail', () => {
    flushOverview({ analyticsFailure: true });

    expect(fixture.nativeElement.querySelector('.overview-balances').textContent).toContain(
      '100,00 ₽',
    );
    expect(fixture.nativeElement.querySelector('.analytics-error').textContent).toContain(
      'Не удалось загрузить распределение по категориям',
    );
    expect(fixture.nativeElement.querySelector('.global-error')).toBeNull();
  });
});
