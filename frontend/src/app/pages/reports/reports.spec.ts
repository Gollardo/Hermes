import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { ReportsPage } from './reports';

describe('ReportsPage', () => {
  let fixture: ComponentFixture<ReportsPage>;
  let http: HttpTestingController;

  beforeEach(async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-08-16T12:00:00Z'));
    await TestBed.configureTestingModule({
      imports: [ReportsPage],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();
    fixture = TestBed.createComponent(ReportsPage);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
    vi.useRealTimers();
  });

  it('shows exact category totals and operation drill-down links', () => {
    fixture.detectChanges();
    http.expectOne('/api/v1/settings').flush({ base_currency: 'RUB', timezone: 'Europe/Moscow' });
    const request = http.expectOne(
      (candidate) =>
        candidate.url === '/api/v1/reports/income-expense' &&
        candidate.params.get('type') === 'expense',
    );
    request.flush({
      type: 'expense',
      from_on: '2026-08-01',
      through_on: '2026-08-31',
      total_amount: '1200.0000',
      operation_count: 1,
      categories: [
        {
          category_id: 'category-1',
          category_name: 'Аренда',
          root_category_id: 'root-1',
          root_category_name: 'Жильё',
          amount: '1200.0000',
          share: '100.00',
          operations: [
            {
              id: 'operation-1',
              occurred_on: '2026-08-10',
              description: 'Квартира',
              amount: '1200.0000',
            },
          ],
        },
      ],
    });
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent;
    expect(text).toContain('Жильё');
    expect(text).toContain('Аренда');
    expect(text).toContain('Операций: 1');
    expect(text).toContain('1 200,00 ₽');
    expect(text).toContain('10 августа 2026');
    expect(fixture.nativeElement.querySelector('.category-chart').getAttribute('role')).toBe(
      'list',
    );
    expect(fixture.nativeElement.querySelector('.report-list details').open).toBe(false);
    expect(fixture.nativeElement.querySelector('.category-disclosure')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('.operation-link-affordance')).not.toBeNull();
    expect(
      (fixture.nativeElement.querySelector('.category-operations a') as HTMLAnchorElement).href,
    ).toContain('focus=operation-1');
  });

  it('uses the application timezone for the default month', () => {
    vi.setSystemTime(new Date('2026-08-31T22:30:00Z'));
    fixture.detectChanges();
    http
      .expectOne('/api/v1/settings')
      .flush({ base_currency: 'RUB', timezone: 'Pacific/Kiritimati' });

    const request = http.expectOne(
      '/api/v1/reports/income-expense?type=expense&from_on=2026-09-01&through_on=2026-09-30',
    );
    request.flush({
      type: 'expense',
      from_on: '2026-09-01',
      through_on: '2026-09-30',
      total_amount: '0.0000',
      operation_count: 0,
      categories: [],
    });
  });

  it('ignores an older response after the report type changes again', () => {
    fixture.detectChanges();
    http.expectOne('/api/v1/settings').flush({ base_currency: 'RUB', timezone: 'Europe/Moscow' });
    http
      .expectOne((request) => request.params.get('type') === 'expense')
      .flush({
        type: 'expense',
        from_on: '2026-08-01',
        through_on: '2026-08-31',
        total_amount: '5.0000',
        operation_count: 1,
        categories: [],
      });
    const page = fixture.componentInstance as unknown as {
      changeType: (type: 'expense' | 'income') => void;
    };
    page.changeType('income');
    const stale = http.expectOne((request) => request.params.get('type') === 'income');
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('5,00 ₽');
    expect(fixture.nativeElement.querySelector('.report-updating')).not.toBeNull();
    page.changeType('expense');
    const current = http.expectOne((request) => request.params.get('type') === 'expense');
    current.flush({
      type: 'expense',
      from_on: '2026-08-01',
      through_on: '2026-08-31',
      total_amount: '10.0000',
      operation_count: 1,
      categories: [],
    });
    stale.flush({
      type: 'income',
      from_on: '2026-08-01',
      through_on: '2026-08-31',
      total_amount: '99.0000',
      operation_count: 1,
      categories: [],
    });
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('10,00 ₽');
    expect(fixture.nativeElement.textContent).not.toContain('99,00 ₽');
  });

  it('closes displayed shares from exact amounts when API shares are already rounded', () => {
    fixture.detectChanges();
    http.expectOne('/api/v1/settings').flush({ base_currency: 'RUB', timezone: 'Europe/Moscow' });
    http
      .expectOne((request) => request.url === '/api/v1/reports/income-expense')
      .flush({
        type: 'expense',
        from_on: '2026-08-01',
        through_on: '2026-08-31',
        total_amount: '3.0000',
        operation_count: 3,
        categories: [1, 2, 3].map((index) => ({
          category_id: `category-${index}`,
          category_name: `Категория ${index}`,
          root_category_id: `category-${index}`,
          root_category_name: `Категория ${index}`,
          amount: '1.0000',
          share: '33.33',
          operations: [],
        })),
      });
    fixture.detectChanges();

    const shares = Array.from(fixture.nativeElement.querySelectorAll('.chart-value small')).map(
      (element) => (element as HTMLElement).textContent?.trim(),
    );
    expect(shares).toEqual(['33,34%', '33,33%', '33,33%']);
  });
});
