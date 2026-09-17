import { DOCUMENT } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import {
  afterRenderEffect,
  ElementRef,
  viewChild,
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';
import { environment } from '../../../environments/environment';
import { apiErrorMessage } from '../../core/api-error';
import { t, locale, localizedSignal } from '../../i18n/i18n';
import { DecimalInput, decimalPayload } from '../../shared/decimal-input';
import { MoneyPipe, currencySymbol } from '../../shared/money.pipe';
import { EntityCombobox } from '../../shared/entity-combobox';

interface Month {
  month: string;
  planned: string;
  actual: string;
  remaining: string;
  state: string;
}
interface Account {
  id: string;
  name: string;
  archived: boolean;
}
export interface Purchase {
  id: string;
  name: string;
  cost: string;
  inflation: string;
  purchase_month: string;
  months: number;
  target: string;
  balance: string;
  remaining: string;
  end_month: string;
  current_month: string;
  status: string;
  version: number;
  schedule: Month[];
  positions: { account_id: string; account_name: string; balance: string }[];
  history: {
    id: string;
    month: string;
    amount: string;
    action: string;
    account_id: string;
    operation_id: string | null;
  }[];
}

@Component({
  selector: 'app-depreciation-page',
  imports: [ReactiveFormsModule, MoneyPipe, DecimalInput, RouterLink, EntityCombobox],
  templateUrl: './depreciation.html',
  styleUrl: './depreciation.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DepreciationPage implements OnInit {
  protected readonly t = t;
  private readonly http = inject(HttpClient);
  private readonly builder = inject(NonNullableFormBuilder);
  private readonly destroyRef = inject(DestroyRef);
  private readonly document = inject(DOCUMENT);
  private readonly modal = viewChild<ElementRef<HTMLElement>>('modal');
  private previousModal: HTMLElement | null = null;
  private opener: HTMLElement | null = null;

  constructor() {
    afterRenderEffect(() => {
      const modal = this.modal()?.nativeElement ?? null;
      if (modal && modal !== this.previousModal) {
        (modal.querySelector<HTMLElement>('input, button') ?? modal).focus();
      }
      this.previousModal = modal;
    });
  }

  protected trapFocus(event: KeyboardEvent): void {
    if (event.key !== 'Tab') return;
    const modal = this.modal()?.nativeElement;
    if (!modal) return;
    const elements = Array.from(
      modal.querySelectorAll<HTMLElement>(
        'input:not(:disabled), button:not(:disabled), select:not(:disabled), [tabindex="0"]',
      ),
    );
    const first = elements[0];
    const last = elements.at(-1);
    if (!first || !last) {
      event.preventDefault();
      modal.focus();
      return;
    }
    if (
      event.shiftKey &&
      (this.document.activeElement === first || this.document.activeElement === modal)
    ) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && this.document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }
  private readonly url = `${environment.apiBaseUrl}/depreciation`;
  protected readonly purchases = signal<Purchase[]>([]);
  protected readonly accounts = signal<Account[]>([]);
  protected readonly options = computed(() =>
    this.accounts()
      .filter((a) => !a.archived)
      .map((a) => ({ id: a.id, label: a.name })),
  );
  protected readonly loading = signal(true);
  protected readonly saving = signal(false);
  protected readonly error = localizedSignal();
  protected readonly currency = signal('');
  protected readonly currentMonth = signal('');
  protected readonly createOpen = signal(false);
  protected readonly selected = signal<Purchase | null>(null);
  protected readonly expanded = signal<string | null>(null);
  protected readonly preview = signal<{ target: string; monthly: string } | null>(null);
  private requestId = '';
  private lastBody = '';
  protected readonly form = this.builder.group({
    name: ['', [Validators.required, Validators.maxLength(120)]],
    cost: ['', Validators.required],
    purchase_month: ['', Validators.required],
    months: [36, [Validators.required, Validators.min(1), Validators.max(600)]],
    inflation: ['', Validators.required],
  });
  protected readonly payment = this.builder.group({
    account_id: ['', Validators.required],
    source_account_id: [''],
    amount: ['', Validators.required],
    action: this.builder.control<'contribute' | 'release'>('contribute'),
  });

  ngOnInit(): void {
    this.form.valueChanges
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.preview.set(null));
    this.load();
  }
  protected load(): void {
    this.loading.set(true);
    this.error.set(null);
    forkJoin({
      purchases: this.http.get<Purchase[]>(this.url),
      accounts: this.http.get<Account[]>(`${environment.apiBaseUrl}/accounts`),
      settings: this.http.get<{ base_currency: string; application_today: string }>(
        `${environment.apiBaseUrl}/settings`,
      ),
    }).subscribe({
      next: (result) => {
        this.purchases.set(result.purchases);
        this.accounts.set(result.accounts);
        this.currency.set(currencySymbol(result.settings.base_currency));
        this.currentMonth.set(result.settings.application_today.slice(0, 7));
        const selected = this.selected();
        if (selected) {
          const refreshed = result.purchases.find((p) => p.id === selected.id);
          if (refreshed?.history.some((entry) => entry.id === this.requestId)) {
            // A lost response may already have committed: refresh resolves it, not a second payment.
            this.close();
          } else {
            this.selected.set(refreshed ?? null);
          }
        }
        this.loading.set(false);
      },
      error: (error: unknown) => {
        this.loading.set(false);
        this.fail(error);
      },
    });
  }
  protected month(value: string): string {
    const [year, month] = value.split('-').map(Number);
    return new Intl.DateTimeFormat(locale(), {
      month: 'long',
      year: 'numeric',
      timeZone: 'UTC',
    }).format(new Date(Date.UTC(year, month - 1, 1)));
  }
  protected current(purchase: Purchase): Month | undefined {
    return purchase.schedule.find((m) => m.state === 'current');
  }
  protected status(value: string): string {
    return value === 'archived'
      ? t('depreciation.archived')
      : value === 'funded'
        ? t('depreciation.funded')
        : value === 'expired'
          ? t('depreciation.expired')
          : t('depreciation.active');
  }
  protected openCreate(): void {
    this.opener = this.document.activeElement as HTMLElement | null;
    this.form.reset({
      name: '',
      cost: '',
      purchase_month: this.currentMonth(),
      months: 36,
      inflation: '',
    });
    this.preview.set(null);
    this.error.set(null);
    this.createOpen.set(true);
  }
  protected close(): void {
    if (!this.saving()) {
      this.createOpen.set(false);
      this.selected.set(null);
      this.opener?.focus();
    }
  }
  protected savePurchase(): void {
    if (this.saving()) return;
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      this.error.set(() => t('depreciation.invalid'));
      return;
    }
    const value = this.form.getRawValue();
    const body = {
      ...value,
      cost: decimalPayload(value.cost),
      inflation: decimalPayload(value.inflation),
    };
    this.saving.set(true);
    this.error.set(null);
    if (!this.preview()) {
      this.http.post<{ target: string; monthly: string }>(`${this.url}/preview`, body).subscribe({
        next: (preview) => {
          this.preview.set(preview);
          this.saving.set(false);
        },
        error: (error: unknown) => {
          this.saving.set(false);
          this.fail(error);
        },
      });
      return;
    }
    this.http.post<Purchase>(this.url, body).subscribe({
      next: () => {
        this.saving.set(false);
        this.close();
        this.load();
      },
      error: (error: unknown) => {
        this.saving.set(false);
        this.fail(error);
      },
    });
  }
  protected openPayment(purchase: Purchase, action: 'contribute' | 'release'): void {
    this.opener = this.document.activeElement as HTMLElement | null;
    this.selected.set(purchase);
    this.error.set(null);
    this.requestId = '';
    this.lastBody = '';
    this.payment.reset({
      account_id: purchase.positions[0]?.account_id ?? '',
      source_account_id: '',
      amount: action === 'contribute' ? (this.current(purchase)?.remaining ?? '') : '',
      action,
    });
  }
  protected submitPayment(): void {
    const purchase = this.selected();
    if (!purchase || this.saving()) return;
    if (this.payment.invalid) {
      this.payment.markAllAsTouched();
      this.error.set(() => t('depreciation.invalid'));
      return;
    }
    const value = this.payment.getRawValue();
    const data = {
      ...value,
      source_account_id: value.action === 'release' ? null : value.source_account_id || null,
      amount: decimalPayload(value.amount),
      version: purchase.version,
    };
    const identity = JSON.stringify(data);
    if (identity !== this.lastBody) {
      this.requestId = crypto.randomUUID();
      this.lastBody = identity;
    }
    this.saving.set(true);
    this.error.set(null);
    this.http
      .post<Purchase>(`${this.url}/${purchase.id}/contributions`, {
        ...data,
        request_id: this.requestId,
      })
      .subscribe({
        next: () => {
          this.saving.set(false);
          this.close();
          this.load();
        },
        error: (error: unknown) => {
          this.saving.set(false);
          this.fail(error);
        },
      });
  }
  protected archive(purchase: Purchase): void {
    if (this.saving()) return;
    this.saving.set(true);
    this.http
      .post<Purchase>(`${this.url}/${purchase.id}/archive`, { version: purchase.version })
      .subscribe({
        next: () => {
          this.saving.set(false);
          this.load();
        },
        error: (error: unknown) => {
          this.saving.set(false);
          this.fail(error);
        },
      });
  }
  protected accountName(id: string): string {
    return this.accounts().find((a) => a.id === id)?.name ?? id;
  }
  private fail(error: unknown): void {
    this.error.set(() => apiErrorMessage(error, t('depreciation.error')));
  }
}
