import { t, localizedSignal } from '../../i18n/i18n';
import { HttpClient } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import { environment } from '../../../environments/environment';
import { apiErrorMessage } from '../../core/api-error';
import { currencySymbol, MoneyPipe } from '../../shared/money.pipe';
import { DecimalInput, decimalPayload } from '../../shared/decimal-input';

type AccountType = 'cash' | 'debit' | 'savings';

interface Account {
  id: string;
  type: AccountType;
  name: string;
  description: string | null;
  balance: string;
  archived: boolean;
}

@Component({
  selector: 'app-accounts-page',
  imports: [ReactiveFormsModule, MoneyPipe, DecimalInput],
  templateUrl: './accounts.html',
  styleUrl: './accounts.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AccountsPage implements OnInit {
  protected readonly t = t;
  private readonly http = inject(HttpClient);
  private readonly builder = inject(NonNullableFormBuilder);

  protected readonly accounts = signal<Account[]>([]);
  protected readonly loading = signal(true);
  protected readonly saving = signal(false);
  protected readonly error = localizedSignal();
  protected readonly editingId = signal<string | null>(null);
  protected readonly formOpen = signal(false);
  protected readonly baseCurrency = signal('₽');
  protected readonly form = this.builder.group({
    name: ['', [Validators.required, Validators.maxLength(120)]],
    type: this.builder.control<AccountType>('cash', Validators.required),
    description: ['', Validators.maxLength(2000)],
    initialBalance: ['0', [Validators.required, Validators.pattern(/^\d{1,16}(?:[.,]\d{1,4})?$/)]],
  });

  ngOnInit(): void {
    this.load();
    this.http.get<{ base_currency: string }>(`${environment.apiBaseUrl}/settings`).subscribe({
      next: ({ base_currency: baseCurrency }) => {
        this.baseCurrency.set(currencySymbol(baseCurrency));
      },
      error: (error: unknown) =>
        this.error.set(() => apiErrorMessage(error, t('settings.couldNotLoadSettings'))),
    });
  }

  protected submit(): void {
    this.error.set(null);
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const value = this.form.getRawValue();
    const id = this.editingId();
    const body = { type: value.type, name: value.name, description: value.description || null };
    this.saving.set(true);
    const request = id
      ? this.http.put<Account>(`${environment.apiBaseUrl}/accounts/${id}`, body)
      : this.http.post<Account>(`${environment.apiBaseUrl}/accounts`, {
          ...body,
          initial_balance: decimalPayload(value.initialBalance),
        });
    request.subscribe({
      next: () => {
        this.saving.set(false);
        this.cancelEdit();
        this.load();
      },
      error: (error: unknown) => {
        this.saving.set(false);
        this.error.set(() => apiErrorMessage(error, t('accounts.couldNotSaveTheAccount')));
      },
    });
  }

  protected edit(account: Account): void {
    this.editingId.set(account.id);
    this.form.setValue({
      name: account.name,
      type: account.type,
      description: account.description ?? '',
      initialBalance: '0',
    });
    this.form.controls.initialBalance.disable();
    this.formOpen.set(true);
  }

  protected openCreate(): void {
    this.cancelEdit();
    this.formOpen.set(true);
  }

  protected cancelEdit(): void {
    this.editingId.set(null);
    this.form.reset({ name: '', type: 'cash', description: '', initialBalance: '0' });
    this.form.controls.initialBalance.enable();
    this.formOpen.set(false);
  }

  protected accountTypeLabel(type: AccountType): string {
    return { cash: t('accounts.cash'), debit: t('accounts.debit'), savings: t('accounts.savings') }[
      type
    ];
  }

  protected toggleArchive(account: Account): void {
    const action = account.archived ? 'restore' : 'archive';
    this.http
      .post<Account>(`${environment.apiBaseUrl}/accounts/${account.id}/${action}`, {})
      .subscribe({
        next: () => this.load(),
        error: (error: unknown) =>
          this.error.set(() =>
            apiErrorMessage(error, t('accounts.couldNotChangeTheAccountStatus')),
          ),
      });
  }

  protected remove(account: Account): void {
    this.http.delete<void>(`${environment.apiBaseUrl}/accounts/${account.id}`).subscribe({
      next: () => this.load(),
      error: (error: unknown) =>
        this.error.set(() => apiErrorMessage(error, t('accounts.couldNotDeleteTheAccount'))),
    });
  }

  private load(): void {
    this.loading.set(true);
    this.http.get<Account[]>(`${environment.apiBaseUrl}/accounts`).subscribe({
      next: (accounts) => {
        this.accounts.set(accounts);
        this.loading.set(false);
      },
      error: (error: unknown) => {
        this.loading.set(false);
        this.error.set(() => apiErrorMessage(error, t('accounts.couldNotLoadAccounts')));
      },
    });
  }
}
