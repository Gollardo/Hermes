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
  function preview(rows?: object[]) {
    const page = fixture.componentInstance;
    page.file = { filename: 'example.csv', content: 'YQ==' };
    page.account = 'account';
    page.mapping.source_date = 2;
    page.mapping.date_format = 'iso';
    page.preview();
    const req = http.expectOne('/api/v1/imports/preview');
    expect(req.request.body.occurred_on).toBeUndefined();
    req.flush({
      headers: ['Amount', 'Status'],
      sheets: ['CSV'],
      facts: [],
      plans: [],
      rows: rows ?? [
        {
          row: 2,
          raw: ['10.1234', 'pending'],
          type: 'expense',
          amount: '10.1234',
          description: 'Coffee',
          source_date: '2026-01-02',
          fact_date: '2026-01-02',
          date_error: null,
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
  it('uses each parsed source date as its editable fact date and keeps pending rows visible', () => {
    const page = preview();
    expect(page.rows().length).toBe(1);
    expect(page.rows()[0].source_date).toBe('2026-01-02');
    expect(page.rows()[0].date).toBe('2026-01-02');
    expect(fixture.nativeElement.textContent).toContain('pending');
    expect(page.selected()).toHaveLength(0);
    http.expectNone('/api/v1/imports/commit');
  });
  it('explains mapped source dates and the write-free preview in both languages', () => {
    expect(fixture.nativeElement.textContent).toContain(
      'Исходная дата из сопоставленной колонки задаёт редактируемую дату факта каждой строки.',
    );
    expect(fixture.nativeElement.textContent).toContain('Предпросмотр не меняет балансы и планы.');

    language.set('en');
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain(
      "The mapped source date seeds each row's editable fact date.",
    );
    expect(fixture.nativeElement.textContent).toContain(
      'Preview does not change balances or plans.',
    );
  });
  it('filters inclusive source dates and restores excluded row drafts on reset', () => {
    const page = preview([
      statementRow(2, '2026-01-01'),
      statementRow(3, '2026-01-02'),
      statementRow(4, '2026-01-03'),
    ]);
    expect(page.importPeriodStart).toBe('2026-01-01');
    expect(page.importPeriodEnd).toBe('2026-01-03');

    page.rows()[0].action = 'new';
    page.rows()[0].category = 'category';
    page.rows()[0].description = 'Keep this browser draft';
    page.rows()[1].action = 'new';
    page.rows()[1].category = 'category';
    page.rows()[2].action = 'new';
    page.rows()[2].category = 'category';
    page.importPeriodStart = '2026-01-02';
    page.importPeriodEnd = '2026-01-03';

    expect(page.visibleRows().map((row) => row.row)).toEqual([3, 4]);
    expect(page.excludedRowCount()).toBe(1);
    expect(page.selected().map((row) => row.row)).toEqual([3, 4]);
    page.submit();
    const request = http.expectOne('/api/v1/imports/commit');
    expect(request.request.body.decisions.map((decision: { row: number }) => decision.row)).toEqual(
      [3, 4],
    );
    request.flush(
      { detail: { code: 'insufficient_balance' } },
      { status: 409, statusText: 'Conflict' },
    );
    expect(page.importPeriodStart).toBe('2026-01-02');
    expect(page.importPeriodEnd).toBe('2026-01-03');
    expect(page.busy()).toBe(false);

    (fixture.nativeElement.querySelector('.import-period button') as HTMLButtonElement).click();
    fixture.detectChanges();
    expect(page.visibleRows().map((row) => row.row)).toEqual([2, 3, 4]);
    expect(page.rows()[0].description).toBe('Keep this browser draft');
    expect(page.selected().map((row) => row.row)).toEqual([2, 3, 4]);
  });
  it('separates import and posting periods and warns without dropping a corrected row', () => {
    const page = preview([
      statementRow(2, '2026-01-01'),
      statementRow(3, '2026-01-02'),
      statementRow(4, '2026-01-03'),
    ]);
    const corrected = page.rows()[1];
    corrected.action = 'new';
    corrected.category = 'category';
    corrected.date = '2025-12-31';
    page.rows.set([...page.rows()]);
    fixture.detectChanges();

    expect(page.selected()).toEqual([corrected]);
    expect(page.postingPeriod()).toEqual({ start: '2025-12-31', end: '2025-12-31' });
    expect(page.hasPostingOutsideImportPeriod()).toBe(true);
    expect(fixture.nativeElement.textContent).toContain('Период исходных дат для импорта');
    expect(fixture.nativeElement.textContent).toContain('Период проведения фактов');
    expect(fixture.nativeElement.textContent).toContain('выходит за период импорта');

    const [start, end] = fixture.nativeElement.querySelectorAll(
      '.import-period input[type="date"]',
    ) as NodeListOf<HTMLInputElement>;
    start.value = '2026-02-01';
    start.dispatchEvent(new Event('input'));
    end.value = '2026-02-28';
    end.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    expect(page.visibleRows()).toHaveLength(0);
    expect(page.selected()).toHaveLength(0);
    expect(fixture.nativeElement.textContent).toContain('Исключено строк: 3');
    expect(fixture.nativeElement.textContent).toContain('изменения по счетам отсутствуют');

    language.set('en');
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Source-date import period');
    expect(fixture.nativeElement.textContent).toContain('Fact-date posting period');
  });
  it('blocks legacy mappings and lets an invalid dated row be corrected or skipped', () => {
    const page = fixture.componentInstance;
    page.file = { filename: 'example.csv', content: 'YQ==' };
    page.account = 'account';
    page.preview();
    http.expectNone('/api/v1/imports/preview');
    expect(page.error()).toContain('дат');

    page.mapping.source_date = 2;
    page.mapping.date_format = 'iso';
    page.preview();
    http.expectOne('/api/v1/imports/preview').flush({
      headers: ['Amount', 'Description', 'Date'],
      sheets: ['CSV'],
      facts: [],
      plans: [],
      rows: [
        {
          row: 2,
          raw: ['10', 'Coffee', 'bad'],
          type: 'expense',
          amount: '10',
          description: 'Coffee',
          currency: 'RUB',
          error: null,
          date_error: 'Invalid source date',
          source_date: null,
          fact_date: null,
          imported_id: null,
          facts: [],
          plans: [],
        },
      ],
    });
    const row = page.rows()[0];
    row.action = 'new';
    row.category = 'category';
    page.submit();
    http.expectNone('/api/v1/imports/commit');
    row.date = '2026-01-02';
    page.changeFactDate(row);
    http.expectOne('/api/v1/imports/candidates').flush({ facts: [], plans: [] });
    page.submit();
    http.expectOne('/api/v1/imports/commit').flush({ results: [] });
  });
  it('keeps source evidence separate and copies it only on explicit request', () => {
    const page = preview();
    const row = page.rows()[0];
    expect(row.sourceDescription).toBe('Coffee');
    expect(row.description).toBe('');
    row.action = 'new';
    page.rows.set([...page.rows()]);
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Исходное описание');
    expect(fixture.nativeElement.textContent).toContain('Описание операции');
    page.copySourceDescription(row);
    expect(row.description).toBe('Coffee');
    row.description = 'Coffee with colleague';
    expect(row.sourceDescription).toBe('Coffee');
    language.set('en');
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Source description');
    expect(fixture.nativeElement.textContent).toContain('Operation description');
  });
  it('searches the selectable category hierarchy by parent or child name', () => {
    const page = preview();
    page.rows()[0].action = 'new';
    page.rows.set([...page.rows()]);
    page.categories.set([
      {
        id: 'housing',
        name: 'Жильё',
        type: 'expense',
        archived: false,
        parent_id: null,
      },
      {
        id: 'utilities',
        name: 'Коммунальные услуги с очень длинным названием',
        type: 'expense',
        archived: false,
        parent_id: 'housing',
      },
      {
        id: 'archived',
        name: 'Старая аренда',
        type: 'expense',
        archived: true,
        parent_id: 'housing',
      },
    ]);
    fixture.detectChanges();

    const combobox = fixture.nativeElement.querySelector('.row app-entity-combobox') as HTMLElement;
    expect(combobox).not.toBeNull();
    const input = combobox.querySelector('input') as HTMLInputElement;
    input.dispatchEvent(new FocusEvent('focus'));
    input.value = 'жиль';
    input.dispatchEvent(new Event('input'));
    fixture.detectChanges();

    const options = [...combobox.querySelectorAll<HTMLElement>('[role="option"]')];
    expect(options.map((option) => option.dataset['optionId'])).toEqual(['housing', 'utilities']);
    expect(options[1].textContent).toContain('Жильё → Коммунальные услуги');
    expect(options[1].classList).toContain('nested');
    options[1].click();
    expect(page.rows()[0].category).toBe('utilities');
  });
  it('searches row candidates with suggestions first and preserves the reviewed draft', () => {
    const page = preview();
    const row = page.rows()[0];
    row.action = 'plan';
    row.description = 'Reviewed note';
    row.category = '';
    row.windowDays = 3;
    row.plans = [
      {
        id: 'suggested',
        version: 1,
        type: 'expense',
        direction: 'expense',
        amount: '10.1234',
        date: '2026-01-02',
        description: 'Coffee plan with a very long descriptive label',
        category_id: 'category',
        reasons: ['amount', 'date'],
      },
      {
        id: 'manual',
        version: 1,
        type: 'expense',
        direction: 'expense',
        amount: '9.5',
        date: '2026-01-01',
        description: 'Ручной кандидат',
        category_id: 'category',
        reasons: [],
      },
    ];
    page.rows.set([...page.rows()]);
    fixture.detectChanges();

    row.plan = 'suggested';
    page.selectPlan(row);
    expect(row.date).toBe('2026-01-02');
    expect(row.category).toBe('category');
    expect(row.description).toContain('very long descriptive label');

    const combobox = fixture.nativeElement.querySelector(
      '.plan-candidate app-entity-combobox',
    ) as HTMLElement;
    const input = combobox.querySelector('input') as HTMLInputElement;
    input.dispatchEvent(new FocusEvent('focus'));
    input.value = '9,50 Food 2026-01-01 ручной';
    input.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    const options = [...combobox.querySelectorAll<HTMLElement>('[role="option"]')];
    expect(options.map((option) => option.dataset['optionId'])).toEqual(['manual']);
    expect(options[0].textContent).toContain('9,50');

    row.date = '2026-01-04';
    page.changeFactDate(row);
    const search = http.expectOne('/api/v1/imports/candidates');
    expect(search.request.body).toEqual({
      account_id: 'account',
      fact_date: '2026-01-04',
      direction: 'expense',
      amount: '10.1234',
      source_description: 'Coffee',
      window_days: 3,
    });
    search.flush({ facts: [], plans: row.plans });
    expect(row.date).toBe('2026-01-04');
    expect(row.description).toBe('Coffee plan with a very long descriptive label');
    expect(row.category).toBe('category');
  });

  it('seeds a selected plan category without preventing a reviewed override', () => {
    const page = preview();
    const row = page.rows()[0];
    row.action = 'plan';
    row.category = '';
    row.plan = 'plan';
    row.plans = [
      {
        id: 'plan',
        version: 1,
        type: 'expense',
        direction: 'expense',
        amount: '10.1234',
        date: '2026-01-02',
        description: 'Coffee plan',
        category_id: 'category',
      },
    ];

    page.selectPlan(row);
    expect(row.category).toBe('category');

    row.category = 'reviewed-category';
    page.submit();

    const request = http.expectOne('/api/v1/imports/commit');
    expect(request.request.body.decisions[0].operation.category_id).toBe('reviewed-category');
    request.flush({ results: [] });
  });

  it('localizes candidate dates while retaining ISO dates in searchable text', () => {
    const page = preview();
    const row = page.rows()[0];
    row.plans = [
      {
        id: 'candidate',
        version: 1,
        type: 'expense',
        direction: 'expense',
        amount: '10.1234',
        date: '2026-01-02',
        description: 'Coffee',
        category_id: 'category',
        reasons: [],
      },
    ];

    const ru = page.candidateOptions(row, 'plans')[0];
    expect(ru.label).toContain('2 января 2026');
    expect(ru.searchText).toContain('2026-01-02');
    language.set('en');
    const en = page.candidateOptions(row, 'plans')[0];
    expect(en.label).toContain('2 January 2026');
    expect(en.searchText).toContain('2026-01-02');
  });

  it('refreshes an existing transfer with its statement-side direction and keeps eligible choices', () => {
    const page = preview();
    const row = page.rows()[0];
    const transfer = {
      id: 'transfer',
      version: 2,
      type: 'transfer' as const,
      direction: 'expense',
      amount: '10.1234',
      date: '2026-01-02',
      description: 'Move to savings',
      category_id: null,
      reasons: ['amount'],
    };
    row.facts = [transfer];
    row.existing = transfer.id;
    row.action = 'existing';
    row.type = 'transfer';
    row.account = 'account';
    row.destination = 'savings';

    row.windowDays = 10;
    page.changeCandidateWindow(row);
    const request = http.expectOne('/api/v1/imports/candidates');
    expect(request.request.body.direction).toBe('expense');
    request.flush({ facts: [transfer], plans: [] });
    expect(row.existing).toBe('transfer');
    expect(row.type).toBe('transfer');
    expect(row.destination).toBe('savings');

    const plan = { ...transfer, id: 'transfer-plan' };
    row.statementDirection = 'income';
    row.plan = plan.id;
    row.plans = [plan];
    page.changeCandidateWindow(row);
    const incoming = http.expectOne('/api/v1/imports/candidates');
    expect(incoming.request.body.direction).toBe('income');
    incoming.flush({ facts: [transfer], plans: [plan] });
    expect(row.existing).toBe('transfer');
    expect(row.plan).toBe('transfer-plan');
  });

  it('widens candidates for only one row and drops a stale selected candidate', () => {
    const page = preview();
    const first = page.rows()[0];
    const second = { ...first, row: 3, facts: [], plans: [], windowDays: 3 };
    first.action = 'existing';
    first.existing = 'stale';
    page.rows.set([first, second]);

    first.windowDays = 10;
    page.changeCandidateWindow(first);
    const request = http.expectOne('/api/v1/imports/candidates');
    expect(request.request.body.window_days).toBe(10);
    request.flush({ facts: [], plans: [] });
    expect(first.existing).toBe('');
    expect(first.date).toBe('2026-01-02');
    expect(second.windowDays).toBe(3);
    expect(second.date).toBe('2026-01-02');
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
  it('shows and submits the effective chronological posting order', () => {
    const page = preview();
    const base = { ...page.rows()[0], action: 'new', category: 'category' };
    page.rows.set([
      { ...base, row: 2, date: '2026-01-02' },
      { ...base, row: 4, date: '2026-01-01' },
      { ...base, row: 3, date: '2026-01-01' },
    ]);
    fixture.detectChanges();

    expect(page.postingOrder().map((row) => row.row)).toEqual([3, 4, 2]);
    const summary = fixture.nativeElement.querySelector('.posting-order') as HTMLElement;
    expect(summary.textContent).toContain('3 · 1 января 2026');
    expect(summary.textContent?.indexOf('3 ·')).toBeLessThan(summary.textContent?.indexOf('4 ·'));
    expect(summary.textContent?.indexOf('4 ·')).toBeLessThan(summary.textContent?.indexOf('2 ·'));

    page.submit();
    const request = http.expectOne('/api/v1/imports/commit');
    expect(request.request.body.decisions.map((item: { row: number }) => item.row)).toEqual([
      3, 4, 2,
    ]);
    request.flush({ results: [] });
  });
  it('blocks 201 selected rows with guidance to narrow the import period', () => {
    const page = preview();
    const base = { ...page.rows()[0], action: 'new', category: 'category' };
    page.rows.set(Array.from({ length: 201 }, (_, index) => ({ ...base, row: index + 2 })));

    page.submit();

    http.expectNone('/api/v1/imports/commit');
    expect(page.error()).toContain('200');
    expect(page.error()).toContain('период');
    expect(page.selected()).toHaveLength(201);
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
  it('requires explicit merging and submits every exact source amount with one group', () => {
    const page = preview();
    const first = { ...page.rows()[0], action: 'plan', plan: 'plan', category: 'category' };
    page.plans = [
      {
        id: 'plan',
        version: 2,
        type: 'expense',
        direction: 'expense',
        amount: '10',
        date: first.date,
        description: 'Coffee',
        category_id: 'category',
      },
    ];
    first.description = 'Noisy merchant text';
    page.selectPlan(first);
    expect(first.description).toBe('Coffee');
    page.rows.set([first, { ...first, row: 3, amount: '20.5678' }]);
    fixture.detectChanges();
    expect(page.planGroups()[0].total).toBe('30.6912');
    expect(fixture.nativeElement.textContent).toContain('30,69');
    expect(fixture.nativeElement.textContent).toContain('Coffee');
    page.submit();
    http.expectNone('/api/v1/imports/commit');
    page.mergePlans['plan'] = true;
    page.submit();
    const req = http.expectOne('/api/v1/imports/commit');
    expect(req.request.body.merge_plan_rows).toEqual([[2, 3]]);
    expect(
      req.request.body.decisions.map((d: { operation: { amount: string } }) => d.operation.amount),
    ).toEqual(['10.1234', '20.5678']);
    req.flush({
      results: [
        { row: 2, operation_id: 'merged' },
        { row: 3, operation_id: 'merged' },
      ],
    });
    expect(page.selected()).toHaveLength(0);
    expect(page.rows().every((r) => r.imported_id === 'merged')).toBe(true);
  });

  it('rejects incompatible group dates and preserves its review after server failure', () => {
    const page = preview();
    const first = { ...page.rows()[0], action: 'plan', plan: 'plan', category: 'category' };
    page.rows.set([first, { ...first, row: 3, date: '2026-01-03' }]);
    page.mergePlans['plan'] = true;
    page.submit();
    http.expectNone('/api/v1/imports/commit');
    expect(page.planGroups()[0].compatible).toBe(false);
    page.rows()[1].date = first.date;
    page.submit();
    http
      .expectOne('/api/v1/imports/commit')
      .flush(
        { detail: { code: 'import_conflict', row: 3 } },
        { status: 422, statusText: 'Conflict' },
      );
    expect(page.selected()).toHaveLength(2);
    expect(page.mergePlans['plan']).toBe(true);
    expect(page.results()).toHaveLength(0);
  });

  it('keeps mapping values when format-specific controls are hidden and settings are collapsed', async () => {
    const page = fixture.componentInstance;
    page.file = { filename: 'statement.XLSX', content: 'YQ==' };
    page.profile = 'Bank';
    page.mapping.encoding = 'cp1251';
    page.mapping.delimiter = ';';
    fixture.detectChanges();
    const element: HTMLElement = fixture.nativeElement;
    expect(element.querySelector('.format-settings')?.hasAttribute('open')).toBe(false);
    expect(element.textContent).not.toContain('Кодировка CSV');
    expect(element.textContent).toContain('Лист');
    page.file = { filename: 'statement.csv', content: 'YQ==' };
    fixture.changeDetectorRef.markForCheck();
    await fixture.whenStable();
    fixture.detectChanges();
    expect(element.textContent).toContain('Кодировка CSV');
    expect(page.mapping.encoding).toBe('cp1251');
    expect(page.mapping.delimiter).toBe(';');
    http.expectNone('/api/v1/imports/inspect');
    http.expectNone('/api/v1/imports/commit');
  });
  it('keeps completed rows and source details accessible without an inactive action selector', () => {
    const page = preview();
    page.rows.set(page.rows().map((row) => ({ ...row, imported_id: 'fact' })));
    fixture.detectChanges();
    const element: HTMLElement = fixture.nativeElement;
    expect(element.querySelector('.row-action')).toBeNull();
    expect(element.querySelector('.source-details')).not.toBeNull();
    expect(element.querySelector('.row a')?.getAttribute('href')).toContain('focus=fact');
    expect(element.textContent).toContain('изменения по счетам отсутствуют');
    expect(page.selected()).toHaveLength(0);
    http.expectNone('/api/v1/imports/commit');
  });
});

function statementRow(row: number, sourceDate: string): object {
  return {
    row,
    raw: ['10.1234', sourceDate],
    type: 'expense',
    amount: '10.1234',
    description: `Coffee ${row}`,
    source_date: sourceDate,
    fact_date: sourceDate,
    date_error: null,
    currency: 'RUB',
    error: null,
    imported_id: null,
    facts: [],
    plans: [],
  };
}
