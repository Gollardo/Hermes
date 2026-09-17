import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { language } from '../../i18n/i18n';
import { DepreciationPage, Purchase } from './depreciation';

const purchase: Purchase = {
  id: 'purchase-1',
  name: 'Laptop',
  cost: '200000',
  inflation: '10',
  purchase_month: '2026-08',
  months: 36,
  target: '266200',
  balance: '5000',
  remaining: '261200',
  end_month: '2029-08',
  current_month: '2026-09',
  status: 'active',
  version: 2,
  schedule: [
    {
      month: '2026-09',
      planned: '7394.4444',
      actual: '5000',
      remaining: '2394.4444',
      state: 'current',
    },
  ],
  positions: [{ account_id: 'account-1', account_name: 'Savings', balance: '5000' }],
  history: [],
};

describe('DepreciationPage', () => {
  let fixture: ComponentFixture<DepreciationPage>;
  let http: HttpTestingController;
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DepreciationPage],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();
    fixture = TestBed.createComponent(DepreciationPage);
    http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
  });
  afterEach(() => {
    language.set('ru');
    http.verify();
  });
  function loaded(purchases: Purchase[] = []) {
    http.expectOne('/api/v1/depreciation').flush(purchases);
    http
      .expectOne('/api/v1/accounts')
      .flush([{ id: 'account-1', name: 'Savings', archived: false }]);
    http
      .expectOne('/api/v1/settings')
      .flush({ base_currency: 'RUB', application_today: '2026-09-17' });
    fixture.detectChanges();
  }
  function click(text: string) {
    const button = Array.from(
      fixture.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>,
    ).find((b) => b.textContent?.trim() === text);
    expect(button).toBeDefined();
    button?.click();
    fixture.detectChanges();
  }
  function input(id: string, value: string) {
    const element = fixture.nativeElement.querySelector(`#${id}`) as HTMLInputElement;
    element.value = value;
    element.dispatchEvent(new Event('input'));
    fixture.detectChanges();
  }
  function submit() {
    fixture.nativeElement.querySelector('form').dispatchEvent(new Event('submit'));
    fixture.detectChanges();
  }

  it('previews exact comma inputs then creates without introducing a target input', () => {
    loaded();
    click('Добавить покупку');
    input('purchase-name', 'Laptop');
    input('purchase-cost', '200000,1234');
    input('purchase-inflation', '10,1250');
    submit();
    const preview = http.expectOne('/api/v1/depreciation/preview');
    expect(preview.request.body.cost).toBe('200000.1234');
    expect(preview.request.body.inflation).toBe('10.1250');
    expect(preview.request.body.purchase_month).toBe('2026-09');
    preview.flush({ target: '267108.6701', monthly: '7419.6852' });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('267 108,67');
    language.set('en');
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Estimated replacement cost');
    submit();
    const create = http.expectOne('/api/v1/depreciation');
    expect(create.request.body.target).toBeUndefined();
    create.flush(purchase);
    loaded([purchase]);
    expect(fixture.nativeElement.querySelector('[role=dialog]')).toBeNull();
  });
  it('invalidates the preview when input changes', () => {
    loaded();
    click('Добавить покупку');
    input('purchase-name', 'Laptop');
    input('purchase-cost', '200000');
    input('purchase-inflation', '10');
    submit();
    http
      .expectOne('/api/v1/depreciation/preview')
      .flush({ target: '266200', monthly: '7394.4444' });
    fixture.detectChanges();
    input('purchase-inflation', '12');
    submit();
    const request = http.expectOne('/api/v1/depreciation/preview');
    expect(request.request.body.inflation).toBe('12');
    request.flush({ target: '280985.6', monthly: '7805.1555' });
  });
  it('shows fixed monthly plan and retries a failed contribution with the same request id', () => {
    loaded([purchase]);
    expect(fixture.nativeElement.textContent).toContain('7 394,44');
    expect(fixture.nativeElement.textContent).toContain('2 394,44');
    click('Внести');
    input('payment-amount', '123,4567');
    submit();
    const request = http.expectOne('/api/v1/depreciation/purchase-1/contributions');
    expect(request.request.body.amount).toBe('123.4567');
    expect(request.request.body.account_id).toBe('account-1');
    const id: string = request.request.body.request_id;
    request.error(new ProgressEvent('error'));
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('#payment-amount').value).toContain('123');
    submit();
    const retry = http.expectOne('/api/v1/depreciation/purchase-1/contributions');
    expect(retry.request.body.request_id).toBe(id);
    retry.flush(purchase);
    loaded([purchase]);
  });
  it('keeps failed loads distinct from an empty savings list', () => {
    http.expectOne('/api/v1/depreciation').flush({}, { status: 500, statusText: 'Error' });
    http.match('/api/v1/accounts');
    http.match('/api/v1/settings');
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role=alert]')).not.toBeNull();
    expect(fixture.nativeElement.textContent).not.toContain('Добавьте покупку, её стоимость');
  });

  it('resolves an uncertain committed payment on refresh without offering a duplicate retry', () => {
    loaded([purchase]);
    click('Внести');
    input('payment-amount', '100');
    submit();
    const request = http.expectOne('/api/v1/depreciation/purchase-1/contributions');
    const id: string = request.request.body.request_id;
    request.error(new ProgressEvent('error'));
    fixture.detectChanges();
    const refresh = fixture.nativeElement.querySelector(
      '[role=dialog] button.secondary:nth-of-type(1)',
    );
    expect(refresh).toBeTruthy();
    const buttons = Array.from(
      fixture.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>,
    );
    buttons.find((b) => b.textContent?.trim() === 'Обновить данные')?.click();
    loaded([
      {
        ...purchase,
        version: 3,
        balance: '5100',
        history: [
          {
            id,
            month: '2026-09',
            amount: '100',
            action: 'contribute',
            account_id: 'account-1',
            operation_id: null,
          },
        ],
      },
    ]);
    expect(fixture.nativeElement.querySelector('[role=dialog]')).toBeNull();
  });

  it('moves keyboard focus into the dialog and traps Tab at its boundary', () => {
    loaded();
    click('Добавить покупку');
    const modal = fixture.nativeElement.querySelector('[role=dialog]') as HTMLElement;
    expect(modal.contains(document.activeElement)).toBe(true);
    const submitButton = modal.querySelector('button[type=submit]') as HTMLButtonElement;
    submitButton.focus();
    submitButton.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true }),
    );
    expect(document.activeElement).not.toBe(submitButton);
    expect(modal.contains(document.activeElement)).toBe(true);
  });
});
