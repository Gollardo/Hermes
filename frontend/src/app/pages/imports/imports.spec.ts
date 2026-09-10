import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { TestBed, ComponentFixture } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { ImportsPage } from './imports';
import { language } from '../../i18n/i18n';

describe('Statement import', () => {
  let fixture: ComponentFixture<ImportsPage>;
  let http: HttpTestingController;
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ImportsPage],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();
    fixture = TestBed.createComponent(ImportsPage);
    http = TestBed.inject(HttpTestingController);
    http.expectOne('/api/v1/accounts').flush([{ id: 'account', name: 'Bank', archived: false }]);
    http
      .expectOne('/api/v1/categories')
      .flush([{ id: 'category', name: 'Food', type: 'expense', archived: false }]);
    http.expectOne('/api/v1/funds').flush([]);
    http.expectOne('/api/v1/settings').flush({ base_currency: 'RUB' });
    http.expectOne('/api/v1/imports/profiles').flush([]);
    fixture.detectChanges();
  });
  afterEach(() => {
    http.verify();
    language.set('ru');
  });
  function preview() {
    const page = fixture.componentInstance;
    page.file = { filename: 'example.csv', content: 'YQ==' };
    page.account = 'account';
    page.date = '2026-01-02';
    page.preview();
    const req = http.expectOne('/api/v1/imports/preview');
    expect(req.request.body.occurred_on).toBe('2026-01-02');
    req.flush({
      headers: ['Amount', 'Status'],
      sheets: ['CSV'],
      facts: [],
      plans: [],
      rows: [
        {
          row: 2,
          raw: ['10.1234', 'pending'],
          type: 'expense',
          amount: '10.1234',
          description: 'Coffee',
          currency: 'RUB',
          error: null,
          imported_id: null,
          facts: [],
          plans: [],
        },
      ],
    });
    fixture.detectChanges();
    return page;
  }
  it('does not choose a fact date automatically and keeps pending rows visible', () => {
    expect(fixture.componentInstance.date).toBe('');
    const page = preview();
    expect(page.rows().length).toBe(1);
    expect(fixture.nativeElement.textContent).toContain('pending');
    expect(page.selected()).toHaveLength(0);
    http.expectNone('/api/v1/imports/commit');
  });
  it('preserves exact amounts, choice and draft after a failed commit', () => {
    const page = preview();
    const row = page.rows()[0];
    row.action = 'new';
    row.category = 'category';
    page.submit();
    const req = http.expectOne('/api/v1/imports/commit');
    expect(req.request.body.decisions[0].operation.amount).toBe('10.1234');
    expect(req.request.body.decisions[0].operation.occurred_on).toBe('2026-01-02');
    page.submit();
    http.expectNone('/api/v1/imports/commit');
    req.flush(
      { detail: { code: 'insufficient_balance' } },
      { status: 409, statusText: 'Conflict' },
    );
    expect(page.rows()[0].action).toBe('new');
    expect(page.results()).toHaveLength(0);
    expect(page.busy()).toBe(false);
  });
  it('switches language without altering selected data and computes exact effects', () => {
    const page = preview();
    const row = page.rows()[0];
    row.action = 'new';
    row.category = 'category';
    expect(page.effects()[0].amount).toBe('-10.1234');
    language.set('en');
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Statement import');
    expect(row.date).toBe('2026-01-02');
    expect(row.amount).toBe('10.1234');
  });
  it('marks success only after commit and excludes completed rows from subsequent submission', () => {
    const page = preview();
    page.rows()[0].action = 'new';
    page.rows()[0].category = 'category';
    page.submit();
    expect(page.results()).toHaveLength(0);
    http.expectOne('/api/v1/imports/commit').flush({ results: [{ row: 2, operation_id: 'fact' }] });
    expect(page.results()).toHaveLength(1);
    expect(page.selected()).toHaveLength(0);
  });
  it('invalidates preview after mapping changes and clears stale links when action changes', () => {
    const page = preview();
    const row = page.rows()[0];
    row.plan = 'old';
    row.existing = 'old';
    row.allocate = true;
    page.changeAction(row);
    expect(row.plan).toBe('');
    expect(row.existing).toBe('');
    expect(row.allocate).toBe(false);
    page.invalidate();
    expect(page.rows()).toHaveLength(0);
  });
});
