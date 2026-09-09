import { t, localizedSignal } from '../../i18n/i18n';
import { HttpClient, HttpParams } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { catchError, forkJoin, of, switchMap } from 'rxjs';

import { environment } from '../../../environments/environment';
import { apiErrorMessage } from '../../core/api-error';
import { DateTextPipe } from '../../shared/date-text.pipe';
import { currencySymbol, MoneyPipe } from '../../shared/money.pipe';
import { OperationCreateMenu } from '../../shared/operation-create-menu';

interface Coverage {
  physical_balance: string;
}

interface FundSummary {
  accounts: Coverage[];
  funds: { id: string; name: string; total_balance: string }[];
  total_reserved: string;
  total_free: string;
}

interface CategoryAmount {
  category_id: string;
  category_name: string;
  amount: string;
}

interface CategorySummary {
  income: CategoryAmount[];
  expense: CategoryAmount[];
}

interface AnalyticsChart {
  title: string;
  context: string;
  items: CategoryAmount[];
  operationType: 'income' | 'expense' | null;
}

interface Forecast {
  from_on: string;
  through_on: string;
  starting_balance: string;
  ending_balance: string;
  minimum_balance: string;
  minimum_on: string;
  first_negative_on: string | null;
}

interface Operation {
  id: string;
  type: 'income' | 'expense' | 'transfer' | 'balance_adjustment';
  occurred_on: string;
  amount: string;
  description: string | null;
  reason: string | null;
  category_name: string | null;
}

interface OperationPage {
  items: Operation[];
}

interface Occurrence {
  id: string;
  due_on: string;
  overdue: boolean;
  type: 'income' | 'expense' | 'transfer';
  amount: string;
  description: string | null;
}

interface OccurrencePage {
  items: Occurrence[];
  total: number;
}

interface Materialization {
  horizon_from: string;
}

interface Settings {
  base_currency: string;
}

@Component({
  selector: 'app-home-page',
  imports: [RouterLink, MoneyPipe, DateTextPipe, OperationCreateMenu],
  templateUrl: './home.html',
  styleUrl: './home.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HomePage implements OnInit {
  protected readonly t = t;
  private readonly http = inject(HttpClient);

  protected readonly summary = signal<FundSummary | null>(null);
  protected readonly forecast = signal<Forecast | null>(null);
  protected readonly recentOperations = signal<Operation[]>([]);
  protected readonly attention = signal<Occurrence[]>([]);
  protected readonly attentionTotal = signal(0);
  protected readonly categories = signal<CategorySummary>({ income: [], expense: [] });
  protected readonly analyticsFrom = signal('');
  protected readonly analyticsThrough = signal('');
  protected readonly analyticsError = localizedSignal();
  protected readonly baseCurrency = signal('RUB');
  protected readonly loading = signal(true);
  protected readonly error = localizedSignal();

  ngOnInit(): void {
    this.http
      .post<Materialization>(`${environment.apiBaseUrl}/scheduling/materialize`, {})
      .pipe(
        switchMap((materialization) => {
          const attentionParams = new HttpParams()
            .set('page_size', '6')
            .set('due_to', materialization.horizon_from)
            .append('status', 'pending')
            .append('status', 'postponed');
          const monthFrom = `${materialization.horizon_from.slice(0, 7)}-01`;
          const [year, month] = monthFrom.split('-').map(Number);
          const monthThrough = `${year}-${String(month).padStart(2, '0')}-${String(new Date(year, month, 0).getDate()).padStart(2, '0')}`;
          this.analyticsFrom.set(monthFrom);
          this.analyticsThrough.set(monthThrough);
          return forkJoin({
            summary: this.http.get<FundSummary>(`${environment.apiBaseUrl}/funds/summary`),
            forecast: this.http.get<Forecast>(`${environment.apiBaseUrl}/forecast`, {
              params: new HttpParams().set('horizon', 'month'),
            }),
            operations: this.http.get<OperationPage>(`${environment.apiBaseUrl}/operations`, {
              params: new HttpParams().set('page_size', '5'),
            }),
            attention: this.http.get<OccurrencePage>(
              `${environment.apiBaseUrl}/scheduling/occurrences`,
              { params: attentionParams },
            ),
            settings: this.http.get<Settings>(`${environment.apiBaseUrl}/settings`),
            categories: this.http
              .get<CategorySummary>(`${environment.apiBaseUrl}/operations/category-summary`, {
                params: new HttpParams().set('from_on', monthFrom).set('through_on', monthThrough),
              })
              .pipe(
                catchError((error: unknown) => {
                  this.analyticsError.set(() =>
                    apiErrorMessage(error, t('home.couldNotLoadTheCategoryBreakdown')),
                  );
                  return of({ income: [], expense: [] });
                }),
              ),
          });
        }),
      )
      .subscribe({
        next: ({ summary, forecast, operations, attention, settings, categories }) => {
          this.summary.set(summary);
          this.forecast.set(forecast);
          this.recentOperations.set(operations.items);
          this.attention.set(attention.items);
          this.attentionTotal.set(attention.total);
          this.baseCurrency.set(currencySymbol(settings.base_currency));
          this.categories.set(categories);
          this.loading.set(false);
        },
        error: (error: unknown) => {
          this.loading.set(false);
          this.error.set(() => apiErrorMessage(error, t('home.couldNotBuildTheOverview')));
        },
      });
  }

  protected physicalTotal(): string {
    const units = this.summary()?.accounts.reduce(
      (total, account) => total + (moneyUnits(account.physical_balance) ?? 0n),
      0n,
    );
    return formatUnits(units ?? 0n);
  }

  protected operationTitle(operation: Operation): string {
    return (
      operation.description ||
      operation.reason ||
      operation.category_name ||
      this.typeLabel(operation.type)
    );
  }

  protected typeLabel(type: Operation['type'] | Occurrence['type']): string {
    return {
      income: t('operation-create-menu.income'),
      expense: t('operation-create-menu.expense'),
      transfer: t('operation-create-menu.transfer'),
      balance_adjustment: t('operation-create-menu.adjustment'),
    }[type];
  }

  protected signedOperation(operation: Operation): string {
    if (operation.type === 'income') return `+${operation.amount}`;
    if (operation.type === 'expense') return `-${operation.amount}`;
    return operation.amount;
  }

  protected chartItems(items: CategoryAmount[]): CategoryAmount[] {
    const top = items.slice(0, 5);
    const rest = items
      .slice(5)
      .reduce((total, item) => total + (moneyUnits(item.amount) ?? 0n), 0n);
    return rest > 0n
      ? [
          ...top,
          { category_id: 'other', category_name: t('home.other'), amount: formatUnits(rest) },
        ]
      : top;
  }

  protected analyticsCharts(): AnalyticsChart[] {
    return [
      {
        title: t('home.expensesByCategory'),
        context: t('home.currentCalendarMonth'),
        items: this.categories().expense,
        operationType: 'expense',
      },
      {
        title: t('home.incomeByCategory'),
        context: t('home.currentCalendarMonth'),
        items: this.categories().income,
        operationType: 'income',
      },
      {
        title: t('home.moneySetAside'),
        context: t('home.currentState'),
        items: this.fundsChart(),
        operationType: null,
      },
    ];
  }

  protected donutStyle(items: CategoryAmount[]): string {
    const values = this.chartItems(items).map((item) => moneyUnits(item.amount) ?? 0n);
    const total = values.reduce((sum, value) => sum + value, 0n);
    if (!total) return 'conic-gradient(var(--line) 0 100%)';
    let offset = 0;
    return `conic-gradient(${values
      .map((value, index) => {
        const start = offset;
        offset += Number((value * 10_000n) / total) / 100;
        return `${this.chartColor(index)} ${start}% ${offset}%`;
      })
      .join(',')})`;
  }

  protected chartColor(index: number): string {
    return ['#2f7d5b', '#77a98d', '#a8cdb8', '#d6b66d', '#c98b73', '#8e9aa0'][index];
  }

  protected fundsChart(): CategoryAmount[] {
    const data = this.summary();
    return (
      data?.funds
        .filter((fund) => (moneyUnits(fund.total_balance) ?? 0n) > 0n)
        .map((fund) => ({
          category_id: fund.id,
          category_name: fund.name,
          amount: fund.total_balance,
        }))
        .sort((left, right) => {
          const difference = (moneyUnits(right.amount) ?? 0n) - (moneyUnits(left.amount) ?? 0n);
          return difference === 0n
            ? left.category_name.localeCompare(right.category_name, 'ru')
            : difference > 0n
              ? 1
              : -1;
        }) ?? []
    );
  }
}

function moneyUnits(value: string): bigint | null {
  const match = /^(-?)(\d+)(?:\.(\d{1,4}))?$/.exec(value);
  if (!match) return null;
  const units = BigInt(match[2]) * 10_000n + BigInt((match[3] ?? '').padEnd(4, '0'));
  return match[1] ? -units : units;
}

function formatUnits(units: bigint): string {
  const sign = units < 0n ? '-' : '';
  const absolute = units < 0n ? -units : units;
  return `${sign}${absolute / 10_000n}.${String(absolute % 10_000n).padStart(4, '0')}`;
}
