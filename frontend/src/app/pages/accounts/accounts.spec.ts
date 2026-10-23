import { language } from '../../i18n/i18n';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { AccountsPage } from './accounts';

describe('AccountsPage', () => {
  let fixture: ComponentFixture<AccountsPage>;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AccountsPage],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();
    fixture = TestBed.createComponent(AccountsPage);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    language.set('ru');
    http.verify();
  });

  it('switches an open composer without changing user text, focus or exact submitted money', () => {
    fixture.detectChanges();
    http.expectOne('/api/v1/accounts').flush([]);
    http.expectOne('/api/v1/settings').flush({ base_currency: 'RUB' });
    fixture.detectChanges();
    clickButton('Добавить счёт');
    const name = fixture.nativeElement.querySelector('#account-name') as HTMLInputElement;
    const balance = fixture.nativeElement.querySelector('#initial-balance') as HTMLInputElement;
    name.value = 'Мои наличные';
    name.dispatchEvent(new Event('input'));
    balance.value = '1000,1234';
    balance.dispatchEvent(new Event('input'));
    balance.focus();
    language.set('en');
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Opening balance');
    expect(name.value).toBe('Мои наличные');
    expect(fixture.nativeElement.querySelector('#initial-balance')).toBe(balance);
    expect(document.activeElement).toBe(balance);
    expect(balance.value).toBe('1000.1234');
    http.expectNone(() => true);
    fixture.nativeElement.querySelector('form').dispatchEvent(new Event('submit'));
    const request = http.expectOne('/api/v1/accounts');
    expect(request.request.body.name).toBe('Мои наличные');
    expect(request.request.body.initial_balance).toBe('1000.1234');
    request.flush(
      { detail: { code: 'account_not_found' } },
      { status: 404, statusText: 'Not Found' },
    );
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Account not found');
    language.set('ru');
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Счёт не найден');
    expect(name.value).toBe('Мои наличные');
  });

  it('creates an account with initial balance as a string', () => {
    fixture.detectChanges();
    http.expectOne('/api/v1/accounts').flush([]);
    http.expectOne('/api/v1/settings').flush({ base_currency: 'RUB' });
    fixture.detectChanges();
    clickButton('Добавить счёт');
    const name = fixture.nativeElement.querySelector('#account-name') as HTMLInputElement;
    name.value = 'Wallet';
    name.dispatchEvent(new Event('input'));
    const balance = fixture.nativeElement.querySelector('#initial-balance') as HTMLInputElement;
    balance.value = '10.2500';
    balance.dispatchEvent(new Event('input'));
    fixture.nativeElement.querySelector('form').dispatchEvent(new Event('submit'));
    const request = http.expectOne('/api/v1/accounts');
    expect(request.request.method).toBe('POST');
    expect(request.request.body.initial_balance).toBe('10.2500');
    request.flush({});
    http.expectOne('/api/v1/accounts').flush([]);
  });

  it('does not submit a negative initial balance', () => {
    fixture.detectChanges();
    http.expectOne('/api/v1/accounts').flush([]);
    http.expectOne('/api/v1/settings').flush({ base_currency: 'RUB' });
    fixture.detectChanges();
    clickButton('Добавить счёт');
    const name = fixture.nativeElement.querySelector('#account-name') as HTMLInputElement;
    name.value = 'Wallet';
    name.dispatchEvent(new Event('input'));
    const balance = fixture.nativeElement.querySelector('#initial-balance') as HTMLInputElement;
    balance.value = '-1';
    balance.dispatchEvent(new Event('input'));
    fixture.nativeElement.querySelector('form').dispatchEvent(new Event('submit'));
    http.expectNone('/api/v1/accounts');
  });

  it('accepts a comma and normalizes the initial balance on blur', () => {
    fixture.detectChanges();
    http.expectOne('/api/v1/accounts').flush([]);
    http.expectOne('/api/v1/settings').flush({ base_currency: 'RUB' });
    fixture.detectChanges();
    clickButton('Добавить счёт');
    const name = fixture.nativeElement.querySelector('#account-name') as HTMLInputElement;
    name.value = 'Wallet';
    name.dispatchEvent(new Event('input'));
    const balance = fixture.nativeElement.querySelector('#initial-balance') as HTMLInputElement;
    balance.value = '1000,5';
    balance.dispatchEvent(new Event('input'));
    balance.dispatchEvent(new FocusEvent('blur'));
    fixture.detectChanges();
    expect(balance.value).toBe('1 000,50');
    fixture.nativeElement.querySelector('form').dispatchEvent(new Event('submit'));
    expect(http.expectOne('/api/v1/accounts').request.body.initial_balance).toBe('1000.50');
  });

  it('shows a validation error for malformed money after blur', () => {
    fixture.detectChanges();
    http.expectOne('/api/v1/accounts').flush([]);
    http.expectOne('/api/v1/settings').flush({ base_currency: 'RUB' });
    fixture.detectChanges();
    clickButton('Добавить счёт');
    const balance = fixture.nativeElement.querySelector('#initial-balance') as HTMLInputElement;
    balance.value = '12,3,4';
    balance.dispatchEvent(new Event('input'));
    balance.dispatchEvent(new FocusEvent('blur'));
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Введите неотрицательное число');
  });

  it('requires named confirmation before deleting and prevents a repeated request', () => {
    fixture.detectChanges();
    http.expectOne('/api/v1/accounts').flush([
      {
        id: 'account-1',
        type: 'cash',
        name: 'Кошелёк',
        description: null,
        balance: '0.0000',
        archived: false,
      },
    ]);
    http.expectOne('/api/v1/settings').flush({ base_currency: 'RUB' });
    fixture.detectChanges();

    (fixture.nativeElement.querySelector('.item-more-actions summary') as HTMLElement).click();
    fixture.detectChanges();
    clickButton('Удалить');
    expect(fixture.nativeElement.querySelector('[role="alertdialog"]').textContent).toContain(
      'Кошелёк',
    );
    http.expectNone('/api/v1/accounts/account-1');

    (
      fixture.nativeElement.querySelector('[role="alertdialog"] .danger') as HTMLButtonElement
    ).click();
    fixture.detectChanges();
    const request = http.expectOne('/api/v1/accounts/account-1');
    expect(request.request.method).toBe('DELETE');
    (
      fixture.nativeElement.querySelector('[role="alertdialog"] .danger') as HTMLButtonElement
    ).click();
    http.expectNone('/api/v1/accounts/account-1');
    request.flush(null);
    http.expectOne('/api/v1/accounts').flush([]);
  });

  it('reveals linked validation and focuses the first invalid field after submit', async () => {
    fixture.detectChanges();
    http.expectOne('/api/v1/accounts').flush([]);
    http.expectOne('/api/v1/settings').flush({ base_currency: 'RUB' });
    fixture.detectChanges();
    clickButton('Добавить счёт');
    fixture.nativeElement.querySelector('form').dispatchEvent(new Event('submit'));
    fixture.detectChanges();
    await new Promise<void>((resolve) => queueMicrotask(resolve));
    const name = fixture.nativeElement.querySelector('#account-name') as HTMLInputElement;
    expect(name.getAttribute('aria-invalid')).toBe('true');
    expect(name.getAttribute('aria-describedby')).toBe('account-name-error');
    expect(document.activeElement).toBe(name);
    http.expectNone('/api/v1/accounts');
  });

  function clickButton(label: string): void {
    const button = [...fixture.nativeElement.querySelectorAll('button')].find(
      (item: HTMLButtonElement) => item.textContent.trim() === label,
    ) as HTMLButtonElement;
    button.click();
    fixture.detectChanges();
  }
});
