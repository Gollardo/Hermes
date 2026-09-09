import { t, localizedSignal } from '../../i18n/i18n';
import { HttpClient, HttpParams } from '@angular/common/http';
import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { environment } from '../../../environments/environment';
import { apiErrorMessage } from '../../core/api-error';
import { DateTextPipe } from '../../shared/date-text.pipe';
import {
  currencySymbol,
  formatPercentageBreakdown,
  formatPercentageBreakdownFromAmounts,
  MoneyPipe,
} from '../../shared/money.pipe';

type ReportType = 'expense' | 'income';
type PeriodMode = 'month' | 'custom';

interface ReportOperation {
  id: string;
  occurred_on: string;
  description: string | null;
  amount: string;
}

interface ReportCategory {
  category_id: string;
  category_name: string;
  root_category_id: string;
  root_category_name: string;
  amount: string;
  share: string;
  operations: ReportOperation[];
}

interface IncomeExpenseReport {
  type: ReportType;
  from_on: string;
  through_on: string;
  total_amount: string;
  operation_count: number;
  categories: ReportCategory[];
}

interface Settings {
  base_currency: string;
  timezone: string;
}

@Component({
  selector: 'app-reports-page',
  imports: [FormsModule, RouterLink, MoneyPipe, DateTextPipe],
  templateUrl: './reports.html',
  styleUrl: './reports.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ReportsPage implements OnInit {
  protected readonly t = t;
  private readonly http = inject(HttpClient);
  protected readonly periodMode = signal<PeriodMode>('month');
  protected readonly selectedMonth = signal('');
  protected readonly fromOn = signal('');
  protected readonly throughOn = signal('');
  protected readonly reportType = signal<ReportType>('expense');
  protected readonly report = signal<IncomeExpenseReport | null>(null);
  protected readonly displayedShares = computed(() => {
    const report = this.report();
    if (!report) return [];
    return (
      formatPercentageBreakdownFromAmounts(
        report.categories.map((category) => category.amount),
        report.total_amount,
      ) ?? formatPercentageBreakdown(report.categories.map((category) => category.share))
    );
  });
  protected readonly baseCurrency = signal('RUB');
  protected readonly loading = signal(true);
  protected readonly error = localizedSignal();
  private requestSequence = 0;

  ngOnInit(): void {
    this.http.get<Settings>(`${environment.apiBaseUrl}/settings`).subscribe({
      next: (settings) => {
        this.baseCurrency.set(currencySymbol(settings.base_currency));
        const month = currentMonth(settings.timezone);
        const range = monthRange(month);
        this.selectedMonth.set(month);
        this.fromOn.set(range.from);
        this.throughOn.set(range.through);
        this.load();
      },
      error: (error: unknown) => {
        this.loading.set(false);
        this.error.set(() => apiErrorMessage(error, t('reports.couldNotLoadReportSettings')));
      },
    });
  }

  protected changeMode(mode: PeriodMode): void {
    if (this.periodMode() === mode) return;
    this.periodMode.set(mode);
    if (mode === 'month') this.applyMonth(this.selectedMonth());
  }

  protected applyMonth(value: string): void {
    if (!value) return;
    this.selectedMonth.set(value);
    const range = monthRange(value);
    this.fromOn.set(range.from);
    this.throughOn.set(range.through);
    this.load();
  }

  protected changeType(type: ReportType): void {
    if (this.reportType() === type) return;
    this.reportType.set(type);
    this.load();
  }

  protected applyCustom(): void {
    if (!this.fromOn() || !this.throughOn() || this.throughOn() < this.fromOn()) {
      this.error.set(() => t('reports.theEndDateMustNotPrecedeThe'));
      return;
    }
    this.load();
  }

  protected categoryLabel(category: ReportCategory): string {
    return category.category_id === category.root_category_id
      ? category.category_name
      : `${category.root_category_name} → ${category.category_name}`;
  }

  protected typeLabel(type: ReportType = this.reportType()): string {
    return type === 'expense' ? t('categories.expenses') : t('categories.income');
  }

  private load(): void {
    if (!this.fromOn() || !this.throughOn()) return;
    const sequence = ++this.requestSequence;
    this.loading.set(true);
    this.error.set(null);
    this.report.set(null);
    const params = new HttpParams()
      .set('type', this.reportType())
      .set('from_on', this.fromOn())
      .set('through_on', this.throughOn());
    this.http
      .get<IncomeExpenseReport>(`${environment.apiBaseUrl}/reports/income-expense`, { params })
      .subscribe({
        next: (report) => {
          if (sequence !== this.requestSequence) return;
          this.report.set(report);
          this.loading.set(false);
        },
        error: (error: unknown) => {
          if (sequence !== this.requestSequence) return;
          this.loading.set(false);
          this.error.set(() => apiErrorMessage(error, t('reports.couldNotBuildTheReport')));
        },
      });
  }
}

function currentMonth(timezone: string, now = new Date()): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: timezone,
    year: 'numeric',
    month: '2-digit',
  }).formatToParts(now);
  const year = parts.find((part) => part.type === 'year')?.value;
  const month = parts.find((part) => part.type === 'month')?.value;
  if (!year || !month) throw new Error('Unable to resolve application month');
  return `${year}-${month}`;
}

function monthRange(value: string): { from: string; through: string } {
  const [year, month] = value.split('-').map(Number);
  const lastDay = new Date(year, month, 0).getDate();
  return {
    from: `${value}-01`,
    through: `${value}-${String(lastDay).padStart(2, '0')}`,
  };
}
