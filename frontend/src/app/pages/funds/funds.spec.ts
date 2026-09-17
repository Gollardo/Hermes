import { provideRouter } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { FundsPage } from './funds';

const SUMMARY = {
  funds: [
    {
      id: 'fund-1',
      name: 'Reserve',
      description: null,
      allocation_percentage: '10.0000',
      manual_allocation_percentage: '10.0000',
      allocation_mode: 'manual',
      target_amount: '20.0000',
      total_balance: '25.0000',
      remaining_amount: '0',
      distribution_status: 'manual',
      progress_percentage: '125.00',
      archived: false,
      version: 1,
    },
  ],
  positions: [],
  accounts: [
    {
      account_id: 'account-1',
      account_name: 'Savings',
      physical_balance: '100.0000',
      reserved_balance: '25.0000',
      fund_reserved_balance: '25.0000',
      reserve_balance: '0',
      free_balance: '75.0000',
      archived: false,
    },
  ],
  active_percentage: '10.0000',
  allocation_mode: 'manual',
  total_reserved: '25.0000',
  total_fund_reserved: '25.0000',
  total_reserve: '0',
  total_free: '75.0000',
};

describe('FundsPage', () => {
  let fixture: ComponentFixture<FundsPage>;
  let http: HttpTestingController;

  beforeEach(async () => {
    localStorage.setItem('hermes-recent-accounts', JSON.stringify(['account-1']));
    await TestBed.configureTestingModule({
      imports: [FundsPage],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    fixture = TestBed.createComponent(FundsPage);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  function flushInitial(summary = SUMMARY): void {
    fixture.detectChanges();
    http.expectOne('/api/v1/settings').flush({ timezone: 'UTC', base_currency: 'RUB' });
    http.expectOne('/api/v1/funds/summary').flush(summary);
    http
      .expectOne((request) => request.url === '/api/v1/funds/history')
      .flush({ items: [], page: 1, page_size: 25, total: 0 });
    fixture.detectChanges();
  }

  it('shows exact progress above 100 percent while capping only the progress bar', () => {
    flushInitial();
    const progress = fixture.nativeElement.querySelector('.fund-progress') as HTMLElement;
    expect(progress.textContent).toContain('125,00%');
    expect((progress.querySelector('progress') as HTMLProgressElement).value).toBe(100);
    expect(fixture.nativeElement.textContent).toContain('125,00%');
  });

  it('explains dynamic percentages and removes manual percentage editing', () => {
    fixture.detectChanges();
    http.expectOne('/api/v1/settings').flush({ timezone: 'UTC', base_currency: 'RUB' });
    http.expectOne('/api/v1/funds/summary').flush({
      ...SUMMARY,
      allocation_mode: 'dynamic',
      active_percentage: '0',
      funds: [
        {
          ...SUMMARY.funds[0],
          allocation_percentage: '0',
          allocation_mode: 'dynamic',
          distribution_status: 'filled',
        },
      ],
    });
    http
      .expectOne((request) => request.url === '/api/v1/funds/history')
      .flush({ items: [], page: 1, page_size: 25, total: 0 });
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Динамически по целям');
    expect(fixture.nativeElement.textContent).toContain('Цель достигнута');
    clickButton('Изменить');
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('#fund-percentage')).toBeNull();
    expect(
      (fixture.nativeElement.querySelector('#fund-target') as HTMLInputElement).placeholder,
    ).toBe('Обязательно');
  });

  it('normalizes and submits an optional target entered with a comma', () => {
    flushInitial();
    const create = [...fixture.nativeElement.querySelectorAll('button')].find(
      (button: HTMLButtonElement) => button.textContent.trim() === 'Создать фонд',
    ) as HTMLButtonElement;
    create.click();
    fixture.detectChanges();

    const name = fixture.nativeElement.querySelector('#fund-name') as HTMLInputElement;
    name.value = 'Travel';
    name.dispatchEvent(new Event('input'));
    const target = fixture.nativeElement.querySelector('#fund-target') as HTMLInputElement;
    target.value = '1000,5';
    target.dispatchEvent(new Event('input'));
    target.dispatchEvent(new FocusEvent('blur'));
    fixture.detectChanges();
    expect(target.value).toBe('1 000,50');

    fixture.nativeElement.querySelector('.modal-card form').dispatchEvent(new Event('submit'));
    const request = http.expectOne('/api/v1/funds');
    expect(request.request.method).toBe('POST');
    expect(request.request.body.target_amount).toBe('1000.50');
    expect(request.request.body.initial_amount).toBeUndefined();
    request.flush({});
    http.expectOne('/api/v1/funds/summary').flush(SUMMARY);
    http
      .expectOne((candidate) => candidate.url === '/api/v1/funds/history')
      .flush({ items: [], page: 1, page_size: 25, total: 0 });
  });

  it('permits editing a fund definition and keeps physical coverage visible', () => {
    flushInitial();
    expect(fixture.nativeElement.textContent).toContain(
      'Физический остаток = фонды + амортизационные накопления + резерв + свободно',
    );
    expect(fixture.nativeElement.textContent).toContain('75,00');
    clickButton('Изменить');
    expect((fixture.nativeElement.querySelector('#fund-name') as HTMLInputElement).value).toBe(
      'Reserve',
    );
  });

  it('keeps a percentage preview editable and commits exact decimal strings', () => {
    flushInitial();
    clickButton('Выделить со счёта');
    setValue('#allocation-account', 'account-1');
    setValue('#allocation-amount', '10');
    clickButton('Рассчитать по процентам');
    http.expectOne('/api/v1/funds/allocation-preview').flush({
      account_id: 'account-1',
      amount: '10',
      allocations: [{ fund_id: 'fund-1', amount: '2.5000', allocation_percentage: '25.0000' }],
      allocated_amount: '2.5000',
      unallocated_amount: '7.5000',
      free_before: '75.0000',
      free_after: '72.5000',
    });
    fixture.detectChanges();
    setValue('#allocation-0', '3.1250');
    fixture.nativeElement.querySelector('.modal-card form').dispatchEvent(new Event('submit'));
    const request = http.expectOne('/api/v1/funds/allocations');
    expect(request.request.body.allocations[0].amount).toBe('3.1250');
    request.flush({});
    http.expectOne('/api/v1/funds/summary').flush({
      funds: [],
      positions: [],
      accounts: [],
      active_percentage: '0',
      allocation_mode: 'manual',
      total_reserved: '0',
      total_free: '0',
    });
    http
      .expectOne((candidate) => candidate.url === '/api/v1/funds/history')
      .flush({ items: [], page: 1, page_size: 25, total: 0 });
  });

  it('transfers an exact amount to a selected fund without using percentages', () => {
    flushInitial({
      ...SUMMARY,
      funds: [
        ...SUMMARY.funds,
        {
          ...SUMMARY.funds[0],
          id: 'fund-2',
          name: 'Travel',
          allocation_percentage: '0.0000',
          manual_allocation_percentage: '0.0000',
          total_balance: '0.0000',
          remaining_amount: '100.0000',
        },
      ],
      accounts: [
        ...SUMMARY.accounts,
        {
          ...SUMMARY.accounts[0],
          account_id: 'account-2',
          account_name: 'Main',
          physical_balance: '200.0000',
          free_balance: '200.0000',
        },
      ],
    });
    localStorage.setItem('hermes-recent-accounts', JSON.stringify(['account-1', 'account-2']));
    localStorage.setItem('hermes-recent-funds', JSON.stringify(['fund-2']));

    clickButton('Перевести в фонд');
    setValue('#specific-transfer-source', 'account-2');
    setValue('#specific-transfer-destination', 'account-1');
    setValue('#specific-transfer-fund', 'fund-2');
    setValue('#specific-transfer-amount', '12,5');
    fixture.nativeElement.querySelector('.modal-card form').dispatchEvent(new Event('submit'));

    const request = http.expectOne('/api/v1/funds/transfer-and-allocate');
    expect(request.request.body.source_account_id).toBe('account-2');
    expect(request.request.body.destination_account_id).toBe('account-1');
    expect(request.request.body.fund_id).toBe('fund-2');
    expect(request.request.body.amount).toBe('12.5');
    expect(request.request.body.occurred_on).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(request.request.body.description).toBeNull();
    request.flush({});
    http.expectOne('/api/v1/funds/summary').flush(SUMMARY);
    http
      .expectOne((candidate) => candidate.url === '/api/v1/funds/history')
      .flush({ items: [], page: 1, page_size: 25, total: 0 });
  });

  it('explains a frozen manual reserve and blocks releasing more than its balance', () => {
    fixture.detectChanges();
    http.expectOne('/api/v1/settings').flush({ timezone: 'UTC', base_currency: 'RUB' });
    http.expectOne('/api/v1/funds/summary').flush({
      ...SUMMARY,
      total_reserve: '5.0000',
      accounts: [
        {
          ...SUMMARY.accounts[0],
          fund_reserved_balance: '20.0000',
          reserve_balance: '5.0000',
        },
      ],
    });
    http
      .expectOne((request) => request.url === '/api/v1/funds/history')
      .flush({ items: [], page: 1, page_size: 25, total: 0 });
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain(
      'Резерв сохранён после динамического режима',
    );
    clickButton('Вернуть в свободные');
    setValue('#reserve-release-amount', '6');
    fixture.nativeElement.querySelector('.modal-card form').dispatchEvent(new Event('submit'));
    fixture.detectChanges();
    const submit = fixture.nativeElement.querySelector(
      '.modal-card button[type="submit"]',
    ) as HTMLButtonElement;
    expect(submit.disabled).toBe(true);
    expect(fixture.nativeElement.textContent).toContain('не больше резерва выбранного счёта');
  });

  it('blocks percentage overflow and invalidates a stale allocation preview', () => {
    flushInitial();
    clickButton('Создать фонд');
    setValue('#fund-percentage', '95');
    const fundSubmit = fixture.nativeElement.querySelector(
      '.modal-card button[type="submit"]',
    ) as HTMLButtonElement;
    expect(fundSubmit.disabled).toBe(true);
    expect(fixture.nativeElement.textContent).toContain('Доступно: 90,00%');

    clickButton('Закрыть');
    clickButton('Выделить со счёта');
    setValue('#allocation-account', 'account-1');
    setValue('#allocation-amount', '10');
    clickButton('Рассчитать по процентам');
    const staleRequest = http.expectOne('/api/v1/funds/allocation-preview');
    setValue('#allocation-amount', '11');
    staleRequest.flush({
      account_id: 'account-1',
      amount: '10',
      allocations: [{ fund_id: 'fund-1', amount: '2.5000' }],
      allocated_amount: '2.5000',
      unallocated_amount: '7.5000',
      free_before: '75.0000',
      free_after: '72.5000',
    });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).not.toContain('Распределение можно поправить');
  });

  function setValue(selector: string, value: string): void {
    const control = fixture.nativeElement.querySelector(selector) as HTMLInputElement;
    const combobox =
      control.closest('app-entity-combobox') ??
      (control.tagName === 'APP-ENTITY-COMBOBOX' ? control : null);
    if (combobox) {
      const input = combobox.querySelector('input') as HTMLInputElement;
      input.value = '';
      input.dispatchEvent(new Event('input'));
      input.dispatchEvent(new Event('focus'));
      fixture.detectChanges();
      (combobox.querySelector(`[data-option-id="${value}"]`) as HTMLButtonElement).click();
      fixture.detectChanges();
      return;
    }
    control.value = value;
    control.dispatchEvent(new Event('input'));
    control.dispatchEvent(new Event('change'));
    fixture.detectChanges();
  }

  function clickButton(label: string): void {
    const button = [...fixture.nativeElement.querySelectorAll('button')].find(
      (item: HTMLButtonElement) =>
        item.textContent.trim() === label || item.getAttribute('aria-label') === label,
    ) as HTMLButtonElement;
    button.click();
    fixture.detectChanges();
  }
});

// Release uses the same modal and exact-decimal contract as other fund actions.
describe('Fund release', () => {
  let fixture: ComponentFixture<FundsPage>;
  let http: HttpTestingController;
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FundsPage],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    fixture = TestBed.createComponent(FundsPage);
    http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
    http.expectOne('/api/v1/settings').flush({ timezone: 'UTC', base_currency: 'RUB' });
    http.expectOne('/api/v1/funds/summary').flush({
      ...SUMMARY,
      positions: [{ fund_id: 'fund-1', account_id: 'account-1', balance: '25.0000' }],
      accounts: [
        ...SUMMARY.accounts,
        {
          ...SUMMARY.accounts[0],
          account_id: 'account-2',
          account_name: 'Salary',
          free_balance: '100.0000',
        },
      ],
    });
    http.expectOne((r) => r.url === '/api/v1/funds/history').flush({ items: [], total: 0 });
    fixture.detectChanges();
    const button = [...fixture.nativeElement.querySelectorAll('button')].find((b: unknown) =>
      (b as HTMLButtonElement).textContent?.includes('Вывести из фонда'),
    ) as HTMLButtonElement;
    button.click();
    fixture.detectChanges();
  });
  afterEach(() => http.verify());

  it('posts exact comma input once and retains the same request identity after failure', () => {
    const page = fixture.componentInstance;
    page['releaseForm'].patchValue({
      accountId: 'account-1',
      destinationAccountId: 'account-2',
      amount: '12,3456',
    });
    expect(page['canReleaseFund']()).toBe(true);
    page['releaseFund']();
    page['releaseFund']();
    const request = http.expectOne('/api/v1/funds/releases');
    expect(request.request.body.amount).toBe('12.3456');
    expect(request.request.body.destination_account_id).toBe('account-2');
    const id = request.request.body.request_id;
    request.flush({}, { status: 503, statusText: 'Unavailable' });
    expect(page['releaseForm'].controls.amount.value).toBe('12,3456');
    expect(page['activeModal']()).toBe('fundRelease');
    page['releaseFund']();
    const retry = http.expectOne('/api/v1/funds/releases');
    expect(retry.request.body.request_id).toBe(id);
    retry.flush({ operation_id: 'operation-1' });
    http.expectOne('/api/v1/funds/summary').flush(SUMMARY);
    http.expectOne((r) => r.url === '/api/v1/funds/history').flush({ items: [], total: 0 });
    expect(page['activeModal']()).toBeNull();
  });

  it('supports release on the same account and blocks invalid positions and dates', () => {
    const page = fixture.componentInstance;
    page['releaseForm'].patchValue({ accountId: 'account-1', amount: '25.0001' });
    expect(page['canReleaseFund']()).toBe(false);
    page['releaseForm'].patchValue({ amount: '25', occurredOn: '2999-01-01' });
    expect(page['canReleaseFund']()).toBe(false);
    page['releaseForm'].patchValue({
      occurredOn: page['applicationToday'](),
      accountId: 'account-2',
    });
    expect(page['canReleaseFund']()).toBe(false);
    page['releaseForm'].patchValue({ accountId: 'account-1' });
    page['releaseFund']();
    const request = http.expectOne('/api/v1/funds/releases');
    expect(request.request.body.destination_account_id).toBeNull();
    request.flush({}, { status: 409, statusText: 'Conflict' });
  });
});
