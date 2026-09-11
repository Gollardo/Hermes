import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import {
  ElementRef,
  ChangeDetectionStrategy,
  Component,
  OnInit,
  OnDestroy,
  computed,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { environment } from '../../../environments/environment';
import { apiErrorMessage } from '../../core/api-error';
import { t, localizedSignal } from '../../i18n/i18n';
import { DecimalInput, decimalPayload } from '../../shared/decimal-input';
import { DateTextPipe, formatTextDate } from '../../shared/date-text.pipe';
import { EntityCombobox } from '../../shared/entity-combobox';
import { MoneyPipe, currencySymbol, formatMoney } from '../../shared/money.pipe';
import {
  ForecastHorizon,
  compareDecimal,
  forecastDetailForDate,
} from '../forecast/forecast-view-model';
import {
  Comparison,
  ScenarioAction,
  ScenarioContext,
  ScenarioPayload,
  comparisonChart,
  isHypothesis,
} from './scenario-model';

@Component({
  selector: 'app-scenarios-page',
  imports: [FormsModule, RouterLink, DecimalInput, MoneyPipe, DateTextPipe, EntityCombobox],
  templateUrl: './scenarios.html',
  styleUrl: './scenarios.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ScenariosPage implements OnInit, OnDestroy {
  protected readonly t = t;
  protected readonly isHypothesis = isHypothesis;
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly http = inject(HttpClient);
  private readonly route = inject(ActivatedRoute);
  protected readonly context = signal<ScenarioContext | null>(null);
  protected readonly result = signal<Comparison | null>(null);
  protected readonly loading = signal(false);
  protected readonly calculating = signal(false);
  protected readonly stale = signal(false);
  protected readonly error = localizedSignal();
  protected readonly action = signal<ScenarioAction>('expense');
  protected readonly horizon = signal<ForecastHorizon>('month');
  protected readonly scope = signal('');
  protected readonly account = signal('');
  protected readonly occurrence = signal('');
  protected readonly amount = signal('');
  protected readonly dueOn = signal('');
  protected readonly stopLoss = signal('');
  protected readonly selectedDate = signal('');
  protected readonly showSuggestion = signal(true);
  private sequence = 0;
  protected readonly currency = computed(() =>
    currencySymbol(this.result()?.currency ?? this.context()?.currency ?? ''),
  );
  protected readonly isNew = computed(
    () => this.action() === 'expense' || this.action() === 'income',
  );
  protected readonly accountOptions = computed(() =>
    (this.context()?.accounts ?? []).map((a) => ({
      id: a.id,
      label: a.name,
      detail: a.archived ? t('forecast.archived') : undefined,
    })),
  );
  protected readonly activeOptions = computed(() =>
    this.accountOptions().filter(
      (a) => !this.context()?.accounts.find((item) => item.id === a.id)?.archived,
    ),
  );
  protected readonly plans = computed(() =>
    (this.context()?.plans ?? []).filter(
      (p) =>
        !this.scope() || p.account_id === this.scope() || p.destination_account_id === this.scope(),
    ),
  );
  protected readonly planOptions = computed(() =>
    this.plans().map((p) => ({
      id: p.id,
      label: `${p.description || this.typeLabel(p.type)} · ${formatMoney(p.amount)} ${this.currency()}`,
      detail: `${formatTextDate(p.due_on)} · ${p.account_name}${p.destination_account_name ? ' → ' + p.destination_account_name : ''}`,
    })),
  );
  protected readonly selectedPlan = computed(() =>
    this.plans().find((p) => p.id === this.occurrence()),
  );
  protected readonly chart = computed(() => {
    const result = this.result();
    return result
      ? comparisonChart(result, result.alternative.stop_loss_risk?.threshold ?? null)
      : null;
  });
  protected readonly details = computed(() => {
    const result = this.result();
    return result
      ? {
          before: forecastDetailForDate(result.baseline.free, this.selectedDate()),
          after: forecastDetailForDate(result.alternative.free, this.selectedDate()),
        }
      : null;
  });
  protected readonly horizons = computed(() => [
    { value: 'two_weeks', label: t('forecast.2Weeks') },
    { value: 'month', label: t('forecast.month') },
    { value: 'quarter', label: t('forecast.quarter') },
    { value: 'half_year', label: t('forecast.halfYear') },
    { value: 'year', label: t('forecast.year') },
  ]);

  ngOnInit(): void {
    const params = this.route.snapshot.queryParamMap;
    const horizon = params.get('horizon');
    if (this.horizons().some((item) => item.value === horizon))
      this.horizon.set(horizon as ForecastHorizon);
    this.scope.set(params.get('account_id') ?? '');
    this.account.set(this.scope());
    this.refresh();
  }
  ngOnDestroy(): void {
    this.sequence++;
  }
  protected invalidate(): void {
    this.sequence++;
    this.result.set(null);
    this.calculating.set(false);
    this.error.set(null);
  }
  protected changeAction(value: ScenarioAction): void {
    this.action.set(value);
    this.invalidate();
  }
  protected choosePlan(id: string): void {
    this.occurrence.set(id);
    const plan = this.selectedPlan();
    if (plan) {
      this.amount.set(plan.amount);
      this.dueOn.set(plan.due_on);
    }
    this.invalidate();
  }
  protected refresh(): void {
    this.invalidate();
    const sequence = this.sequence;
    this.loading.set(true);
    this.http.get<ScenarioContext>(`${environment.apiBaseUrl}/scenarios/context`).subscribe({
      next: (context) => {
        if (sequence !== this.sequence) return;
        this.context.set(context);
        this.stale.set(false);
        this.loading.set(false);
        // Do not overwrite the user's hypothesis when refreshing changed sources.
        if (!this.dueOn()) this.dueOn.set(context.today);
      },
      error: (error: unknown) => {
        if (sequence !== this.sequence) return;
        this.loading.set(false);
        this.error.set(() => apiErrorMessage(error, t('oracle.loadError')));
      },
    });
  }
  protected calculate(): void {
    const context = this.context();
    if (!context || this.calculating() || this.loading() || this.stale()) return;
    this.invalidate();
    const amount = decimalPayload(this.amount()),
      stop = decimalPayload(this.stopLoss());
    const valid = (v: string) => /^\d{1,16}(?:\.\d{1,4})?$/.test(v);
    if (
      (this.action() !== 'move' && (!valid(amount) || compareDecimal(amount, '0') <= 0)) ||
      (stop && !valid(stop)) ||
      (this.isNew() && !this.account()) ||
      (!this.isNew() && !this.selectedPlan()) ||
      (this.action() !== 'amount' &&
        (!this.dueOn() || this.dueOn() < context.today || this.dueOn() > context.maximum_on))
    ) {
      this.error.set(() => t('oracle.validation'));
      const selector =
        this.isNew() && !this.account()
          ? '#oracle-account'
          : !this.isNew() && !this.selectedPlan()
            ? '#oracle-plan'
            : this.action() !== 'move' && (!valid(amount) || compareDecimal(amount, '0') <= 0)
              ? '[name="amount"]'
              : stop && !valid(stop)
                ? '[name="stopLoss"]'
                : '[name="date"]';
      this.host.nativeElement.querySelector<HTMLElement>(selector)?.focus();
      return;
    }
    const payload: ScenarioPayload = {
      action: this.action(),
      horizon: this.horizon(),
      scope_account_id: this.scope() || null,
      snapshot_id: context.snapshot_id,
      stop_loss: stop || null,
    };
    if (this.isNew()) payload.account_id = this.account();
    else {
      payload.occurrence_id = this.selectedPlan()!.id;
      payload.version = this.selectedPlan()!.version;
    }
    if (this.action() !== 'move') payload.amount = amount;
    if (this.action() !== 'amount') payload.due_on = this.dueOn();
    const sequence = this.sequence;
    this.calculating.set(true);
    this.http.post<Comparison>(`${environment.apiBaseUrl}/scenarios/compare`, payload).subscribe({
      next: (result) => {
        if (sequence !== this.sequence) return;
        this.result.set(result);
        this.selectedDate.set(result.alternative.free.minimum_on);
        this.calculating.set(false);
      },
      error: (error: unknown) => {
        if (sequence !== this.sequence) return;
        this.calculating.set(false);
        this.stale.set(error instanceof HttpErrorResponse && error.status === 409);
        this.error.set(() => apiErrorMessage(error, t('oracle.calculateError')));
      },
    });
  }
  protected inspectDate(on: string): void {
    this.selectedDate.set(on);
    const section = this.host.nativeElement.querySelector<HTMLElement>('.comparison-chart');
    section?.focus();
    section?.scrollIntoView?.({ block: 'start' });
  }
  protected discard(): void {
    this.invalidate();
    this.amount.set('');
    this.stopLoss.set('');
    this.occurrence.set('');
    this.dueOn.set(this.context()?.today ?? '');
    this.action.set('expense');
  }
  protected typeLabel(type: string): string {
    return type === 'income'
      ? t('oracle.income')
      : type === 'expense'
        ? t('oracle.expense')
        : t('oracle.transfer');
  }
  protected assumption(code: string): string {
    const keys = {
      materialized_plans_only: 'oracle.materialized',
      overdue_excluded: 'oracle.overdue',
      daily_closing: 'oracle.daily',
      free_money_expense: 'oracle.freeOnly',
      global_fund_sequence: 'oracle.globalFunds',
      not_a_posting_guarantee: 'oracle.notGuarantee',
      change_outside_horizon: 'oracle.outside',
      insufficient_boundary_evidence: 'oracle.noSuggestion',
    } as const;
    return code in keys ? t(keys[code as keyof typeof keys]) : t('oracle.unknownAssumption');
  }
}
