import { language, LANGUAGE_STORAGE_KEY } from '../../i18n/i18n';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of } from 'rxjs';

import { AuthService } from '../../core/auth.service';
import { SettingsPage } from './settings';

describe('SettingsPage', () => {
  let fixture: ComponentFixture<SettingsPage>;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SettingsPage],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        {
          provide: AuthService,
          useValue: {
            changePassword: vi.fn(() => of(undefined)),
            logoutAll: vi.fn(() => of(undefined)),
          },
        },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(SettingsPage);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    language.set('ru');
    localStorage.removeItem(LANGUAGE_STORAGE_KEY);
    http.verify();
  });

  it('loads and updates application settings', () => {
    fixture.detectChanges();
    http.expectOne('/api/v1/settings').flush({
      base_currency: 'RUB',
      timezone: 'Europe/Moscow',
      default_account_id: null,
      base_currency_locked: false,
      updated_at: '2026-08-02T00:00:00Z',
    });
    http
      .expectOne('/api/v1/accounts')
      .flush([{ id: 'account-1', name: 'Основной', archived: false }]);
    fixture.detectChanges();

    const currency = fixture.nativeElement.querySelector('#settings-currency') as HTMLInputElement;
    currency.value = 'EUR';
    currency.dispatchEvent(new Event('input'));
    const defaultAccount = fixture.nativeElement.querySelector(
      '#settings-default-account',
    ) as HTMLInputElement;
    defaultAccount.value = 'Осн';
    defaultAccount.dispatchEvent(new Event('input'));
    defaultAccount.dispatchEvent(new Event('focus'));
    fixture.detectChanges();
    (
      fixture.nativeElement.querySelector('[data-option-id="account-1"]') as HTMLButtonElement
    ).click();
    fixture.nativeElement.querySelector('form').dispatchEvent(new Event('submit'));

    const request = http.expectOne('/api/v1/settings');
    expect(request.request.method).toBe('PUT');
    expect(request.request.body.base_currency).toBe('EUR');
    expect(request.request.body.default_account_id).toBe('account-1');
    request.flush({
      base_currency: 'EUR',
      timezone: 'Europe/Moscow',
      default_account_id: 'account-1',
      base_currency_locked: false,
      updated_at: '2026-08-02T00:01:00Z',
    });
  });

  it('switches from dynamic allocation to manual by fixing the current percentages', () => {
    fixture.detectChanges();
    http.expectOne('/api/v1/settings').flush({
      base_currency: 'RUB',
      timezone: 'Europe/Moscow',
      default_account_id: null,
      fund_allocation_mode: 'dynamic',
      base_currency_locked: true,
      updated_at: '2026-08-17T00:00:00Z',
    });
    http.expectOne('/api/v1/accounts').flush([]);
    fixture.detectChanges();

    const manual = fixture.nativeElement.querySelector(
      'input[type="radio"][value="manual"]',
    ) as HTMLInputElement;
    manual.click();
    fixture.detectChanges();
    const button = [...fixture.nativeElement.querySelectorAll('.fund-policy-panel button')].find(
      (item: HTMLButtonElement) => item.textContent.includes('Зафиксировать'),
    ) as HTMLButtonElement;
    button.click();

    const request = http.expectOne('/api/v1/settings/fund-allocation-mode');
    expect(request.request.method).toBe('PUT');
    expect(request.request.body).toEqual({ mode: 'manual' });
    request.flush({
      base_currency: 'RUB',
      timezone: 'Europe/Moscow',
      default_account_id: null,
      fund_allocation_mode: 'manual',
      base_currency_locked: true,
      updated_at: '2026-08-17T00:01:00Z',
    });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Текущие проценты зафиксированы');
  });

  it('keeps security and backup settings available when accounts cannot load', () => {
    fixture.detectChanges();
    http.expectOne('/api/v1/settings').flush({
      base_currency: 'RUB',
      timezone: 'Europe/Moscow',
      default_account_id: null,
      base_currency_locked: false,
      updated_at: '2026-08-02T00:00:00Z',
    });
    http
      .expectOne('/api/v1/accounts')
      .flush({ detail: 'Unavailable' }, { status: 503, statusText: 'Service Unavailable' });
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('#settings-currency')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('#current-password')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('#backup-file')).not.toBeNull();
    expect(
      (fixture.nativeElement.querySelector('#settings-default-account') as HTMLInputElement)
        .disabled,
    ).toBe(true);
    expect(fixture.nativeElement.textContent).toContain('Остальные настройки доступны');
  });

  it('validates a selected backup and shows the replacement summary', async () => {
    fixture.detectChanges();
    http.expectOne('/api/v1/settings').flush({
      base_currency: 'RUB',
      timezone: 'Europe/Moscow',
      default_account_id: null,
      base_currency_locked: true,
      updated_at: '2026-08-12T00:00:00Z',
    });
    http.expectOne('/api/v1/accounts').flush([]);
    fixture.detectChanges();

    const input = fixture.nativeElement.querySelector('#backup-file') as HTMLInputElement;
    const file = new File(['{"format":"hermes-json-backup"}'], 'backup.json', {
      type: 'application/json',
    });
    Object.defineProperty(input, 'files', { value: [file] });
    input.dispatchEvent(new Event('change'));
    await file.text();
    fixture.detectChanges();

    const request = http.expectOne('/api/v1/backup/preview');
    expect(request.request.method).toBe('POST');
    request.flush({
      app_version: '0.3.0',
      exported_at: '2026-08-12T00:00:00Z',
      base_currency: 'RUB',
      timezone: 'Europe/Moscow',
      default_account_id: null,
      integrity_verified: true,
      counts: {
        accounts: 1,
        categories: 1,
        operations: 2,
        account_movements: 2,
        funds: 1,
        fund_events: 1,
        fund_movements: 1,
        fund_reserve_movements: 0,
        recurring_rules: 1,
        expected_occurrences: 3,
      },
    });
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Целостность подтверждена');
    expect(fixture.nativeElement.textContent).toContain('12 августа 2026');
    expect(fixture.nativeElement.textContent).toContain('Операции: 2');
    expect(fixture.nativeElement.textContent).toContain('ЗАМЕНИТЬ ВСЕ ДАННЫЕ');
  });

  it('does not submit restore until the exact confirmation matches', () => {
    fixture.detectChanges();
    http.expectOne('/api/v1/settings').flush({
      base_currency: 'RUB',
      timezone: 'Europe/Moscow',
      default_account_id: null,
      base_currency_locked: true,
      updated_at: '2026-08-12T00:00:00Z',
    });
    http.expectOne('/api/v1/accounts').flush([]);
    const page = fixture.componentInstance as unknown as {
      backupDocument: { set: (value: unknown) => void };
      restoreForm: {
        setValue: (value: {
          confirmation: string;
          masterPassword: string;
          backupPassword: string;
        }) => void;
      };
      restoreBackup: () => void;
    };
    page.backupDocument.set({ format: 'hermes-json-backup' });
    page.restoreForm.setValue({
      confirmation: 'не совпадает',
      masterPassword: 'secret',
      backupPassword: '',
    });
    page.restoreBackup();
    fixture.detectChanges();
    http.expectNone('/api/v1/backup/restore');
    expect(fixture.nativeElement.textContent).toContain('Фраза подтверждения не совпадает');
  });

  it.each(['ru', 'en'] as const)(
    'submits through the rendered restore button in %s and rechecks after switching language',
    async (selected) => {
      fixture.detectChanges();
      http
        .expectOne('/api/v1/settings')
        .flush({ base_currency: 'RUB', timezone: 'UTC', base_currency_locked: true });
      http.expectOne('/api/v1/accounts').flush([]);
      fixture.detectChanges();
      const backup = { format: 'hermes-json-backup', schema_version: 1 };
      const file = new File([JSON.stringify(backup)], 'backup.json', { type: 'application/json' });
      const input = fixture.nativeElement.querySelector('#backup-file') as HTMLInputElement;
      Object.defineProperty(input, 'files', { value: [file] });
      input.dispatchEvent(new Event('change'));
      await file.text();
      http.expectOne('/api/v1/backup/preview').flush({
        app_version: '1.0.0',
        exported_at: '2026-09-09T00:00:00Z',
        base_currency: 'RUB',
        timezone: 'UTC',
        integrity_verified: true,
        counts: {
          accounts: 2,
          categories: 1,
          operations: 2,
          account_movements: 2,
          funds: 1,
          fund_events: 1,
          fund_movements: 1,
          fund_reserve_movements: 0,
          recurring_rules: 1,
          expected_occurrences: 3,
        },
      });
      fixture.detectChanges();
      const setLanguage = (value: string) => {
        const select = fixture.nativeElement.querySelector(
          'app-language-select select',
        ) as HTMLSelectElement;
        select.value = value;
        select.dispatchEvent(new Event('change'));
        fixture.detectChanges();
      };
      const fill = (selector: string, value: string) => {
        const field = fixture.nativeElement.querySelector(selector) as HTMLInputElement;
        field.value = value;
        field.dispatchEvent(new Event('input'));
        fixture.detectChanges();
      };
      const button = fixture.nativeElement.querySelector(
        '.restore-form button[type="submit"]',
      ) as HTMLButtonElement;
      const phrase = selected === 'ru' ? 'ЗАМЕНИТЬ ВСЕ ДАННЫЕ' : 'REPLACE ALL DATA';
      setLanguage(selected);
      fill('#restore-confirmation', phrase);
      expect(button.disabled).toBe(true);
      fill('#restore-password', 'correct-master-password');
      expect(button.disabled).toBe(false);
      setLanguage(selected === 'ru' ? 'en' : 'ru');
      expect(
        (fixture.nativeElement.querySelector('#restore-confirmation') as HTMLInputElement).value,
      ).toBe(phrase);
      expect(button.disabled).toBe(true);
      button.click();
      http.expectNone('/api/v1/backup/restore');
      fill('#restore-confirmation', selected === 'ru' ? 'REPLACE ALL DATA' : 'ЗАМЕНИТЬ ВСЕ ДАННЫЕ');
      expect(button.disabled).toBe(false);
      setLanguage(selected);
      fill('#restore-confirmation', phrase);
      button.click();
      fixture.detectChanges();
      expect(button.disabled).toBe(true);
      const request = http.expectOne('/api/v1/backup/restore');
      expect(request.request.body).toEqual({
        backup,
        confirmation: 'ЗАМЕНИТЬ ВСЕ ДАННЫЕ',
        master_password: 'correct-master-password',
        backup_password: null,
      });
      request.flush(
        { detail: { code: 'invalid_backup' } },
        { status: 422, statusText: 'Unprocessable Content' },
      );
      fixture.detectChanges();
      expect(
        (fixture.nativeElement.querySelector('#restore-password') as HTMLInputElement).value,
      ).toBe('');
      expect(button.disabled).toBe(true);
    },
  );

  it('asks for a Hermes password before preview and keeps password roles separate', async () => {
    fixture.detectChanges();
    http.expectOne('/api/v1/settings').flush({
      base_currency: 'RUB',
      timezone: 'Europe/Moscow',
      default_account_id: null,
      base_currency_locked: true,
      updated_at: '2026-08-20T00:00:00Z',
    });
    http.expectOne('/api/v1/accounts').flush([]);
    fixture.detectChanges();

    const backup = { format: 'hermes', version: 1 };
    const file = {
      name: 'protected.hermes',
      size: 128,
      text: () => Promise.resolve(JSON.stringify(backup)),
    };
    const input = fixture.nativeElement.querySelector('#backup-file') as HTMLInputElement;
    Object.defineProperty(input, 'files', { value: [file] });
    input.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    fixture.detectChanges();

    http.expectNone('/api/v1/backup/preview');
    const password = fixture.nativeElement.querySelector(
      '#backup-password-preview',
    ) as HTMLInputElement;
    password.value = 'backup-file-password';
    password.dispatchEvent(new Event('input'));
    fixture.nativeElement
      .querySelector('#backup-password-preview')
      .closest('form')
      .dispatchEvent(new Event('submit'));

    const request = http.expectOne('/api/v1/backup/preview');
    expect(request.request.body).toEqual({
      backup,
      backup_password: 'backup-file-password',
    });
  });
});
