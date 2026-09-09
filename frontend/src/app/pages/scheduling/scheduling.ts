import { t, localizedSignal, locale, plural } from '../../i18n/i18n';
import { HttpClient, HttpParams } from '@angular/common/http';
import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { EMPTY, Observable, expand, forkJoin, reduce } from 'rxjs';

import { environment } from '../../../environments/environment';
import { apiErrorMessage } from '../../core/api-error';
import { DateTextPipe, formatTextDate } from '../../shared/date-text.pipe';
import { currencySymbol, formatMoney, MoneyPipe } from '../../shared/money.pipe';
import { EntityCombobox, EntityOption } from '../../shared/entity-combobox';
import {
  DecimalInput,
  moneyExpressionPayload,
  moneyExpressionValidator,
} from '../../shared/decimal-input';

type OperationType = 'income' | 'expense' | 'transfer';
type Frequency = 'daily' | 'weekly' | 'monthly' | 'yearly';
type OccurrenceStatus = 'pending' | 'confirmed' | 'postponed' | 'cancelled';

interface Account {
  id: string;
  name: string;
  archived: boolean;
}

interface Category {
  id: string;
  name: string;
  type: 'income' | 'expense';
  archived: boolean;
  parent_id: string | null;
}

interface Settings {
  base_currency: string;
}

interface RecurringRule {
  id: string;
  type: OperationType;
  frequency: Frequency;
  interval: number;
  weekdays: number[] | null;
  start_on: string;
  end_on: string | null;
  amount: string;
  description: string | null;
  account_id: string;
  account_name: string;
  destination_account_id: string | null;
  destination_account_name: string | null;
  category_id: string | null;
  category_name: string | null;
  allocate_to_funds: boolean;
  shift_future_on_postpone: boolean;
  series_shift_days: number;
  active: boolean;
  version: number;
}

interface ExpectedOccurrence {
  id: string;
  source_kind: 'recurring' | 'one_off';
  rule_id: string | null;
  scheduled_on: string;
  due_on: string;
  status: OccurrenceStatus;
  manually_modified: boolean;
  series_shift_days: number;
  preserve_from_series_shift: boolean;
  overdue: boolean;
  type: OperationType;
  amount: string;
  description: string | null;
  account_id: string;
  account_name: string;
  destination_account_id: string | null;
  destination_account_name: string | null;
  category_id: string | null;
  category_name: string | null;
  allocate_to_funds: boolean;
  actual_operation_id: string | null;
  version: number;
}

interface OccurrencePage {
  items: ExpectedOccurrence[];
  page: number;
  page_size: number;
  total: number;
}

interface Materialization {
  horizon_from: string;
  horizon_to: string;
  created: number;
  updated: number;
  cancelled: number;
}

interface PostponeResult extends ExpectedOccurrence {
  series_shift_applied: boolean;
  shift_days: number;
  shifted_occurrences: number;
  preserved_occurrences: number;
  rule_version: number;
}

interface CalendarDay {
  iso: string;
  day: number;
  inMonth: boolean;
  today: boolean;
  occurrences: ExpectedOccurrence[];
}

interface UpcomingGroup {
  dueOn: string;
  occurrences: ExpectedOccurrence[];
}

@Component({
  selector: 'app-scheduling-page',
  imports: [ReactiveFormsModule, RouterLink, MoneyPipe, DateTextPipe, EntityCombobox, DecimalInput],
  templateUrl: './scheduling.html',
  styleUrls: ['../directory.css', './scheduling.css', './scheduling-actions.css'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SchedulingPage implements OnInit {
  protected readonly t = t;
  private readonly http = inject(HttpClient);
  private readonly builder = inject(NonNullableFormBuilder);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private occurrenceRequestId = 0;

  protected readonly accounts = signal<Account[]>([]);
  protected readonly categories = signal<Category[]>([]);
  protected readonly rules = signal<RecurringRule[]>([]);
  protected readonly calendarOccurrences = signal<ExpectedOccurrence[]>([]);
  protected readonly upcoming = signal<ExpectedOccurrence[]>([]);
  protected readonly upcomingTotal = signal(0);
  protected readonly today = signal('');
  protected readonly selectedMonth = signal('');
  protected readonly baseCurrency = signal('RUB');
  protected readonly loading = signal(true);
  protected readonly saving = signal(false);
  protected readonly error = localizedSignal();
  protected readonly editingId = signal<string | null>(null);
  protected readonly ruleFormOpen = signal(false);
  protected readonly busyOccurrenceId = signal<string | null>(null);
  protected readonly postponeDates = signal<Record<string, string>>({});
  protected readonly editingConfirmationId = signal<string | null>(null);
  protected readonly selectedCalendarDay = signal<CalendarDay | null>(null);
  protected readonly actionNotice = localizedSignal();

  protected readonly filters = this.builder.group({
    accountId: [''],
    type: this.builder.control<OperationType | ''>(''),
  });

  protected readonly confirmationForm = this.builder.group({
    amount: ['', [Validators.required, moneyExpressionValidator]],
  });

  protected readonly ruleForm = this.builder.group({
    type: this.builder.control<OperationType>('expense', Validators.required),
    frequency: this.builder.control<Frequency>('monthly', Validators.required),
    interval: [1, [Validators.required, Validators.min(1), Validators.max(3)]],
    monday: [false],
    tuesday: [false],
    wednesday: [false],
    thursday: [false],
    friday: [false],
    saturday: [false],
    sunday: [false],
    startOn: ['', Validators.required],
    endOn: [''],
    amount: ['', [Validators.required, moneyExpressionValidator]],
    description: ['', Validators.maxLength(2000)],
    accountId: ['', Validators.required],
    destinationAccountId: [''],
    categoryId: [''],
    allocateToFunds: [false],
    shiftFutureOnPostpone: [false],
  });

  protected readonly monthTitle = computed(() => {
    const value = this.selectedMonth();
    if (!value) return '';
    const parsed = parseIsoDate(value);
    return new Intl.DateTimeFormat(locale(), { month: 'long', year: 'numeric' }).format(
      new Date(parsed.year, parsed.month - 1, 1),
    );
  });

  protected readonly upcomingGroups = computed<UpcomingGroup[]>(() => {
    const groups = new Map<string, ExpectedOccurrence[]>();
    for (const occurrence of this.upcoming()) {
      const items = groups.get(occurrence.due_on) ?? [];
      items.push(occurrence);
      groups.set(occurrence.due_on, items);
    }
    return Array.from(groups, ([dueOn, occurrences]) => ({ dueOn, occurrences }));
  });

  protected readonly calendarDays = computed<CalendarDay[]>(() => {
    const month = this.selectedMonth();
    if (!month) return [];
    const { start } = calendarGridRange(month);
    const selected = parseIsoDate(month);
    const byDate = new Map<string, ExpectedOccurrence[]>();
    for (const occurrence of this.calendarOccurrences()) {
      const items = byDate.get(occurrence.due_on) ?? [];
      items.push(occurrence);
      byDate.set(occurrence.due_on, items);
    }
    return Array.from({ length: 42 }, (_, index) => {
      const value = addDays(start, index);
      const parsed = parseIsoDate(value);
      return {
        iso: value,
        day: parsed.day,
        inMonth: parsed.month === selected.month,
        today: value === this.today(),
        occurrences: byDate.get(value) ?? [],
      };
    });
  });

  ngOnInit(): void {
    this.ruleForm.controls.type.valueChanges.subscribe(() => this.resetDependentFields());
    this.filters.valueChanges.subscribe(() => this.loadOccurrences());
    this.materializeAndLoad();
  }

  protected activeAccounts(): Account[] {
    const editing = this.editingRule();
    return this.accounts().filter(
      (account) =>
        !account.archived ||
        account.id === editing?.account_id ||
        account.id === editing?.destination_account_id,
    );
  }

  protected accountLabel(account: Account): string {
    return `${account.name}${account.archived ? ' ' + t('funds.archived') : ''}`;
  }

  protected availableCategories(): Category[] {
    const type = this.ruleForm.controls.type.value;
    if (type === 'transfer') return [];
    const editingCategoryId = this.editingRule()?.category_id;
    return this.categories().filter(
      (category) =>
        category.type === type && (!category.archived || category.id === editingCategoryId),
    );
  }

  protected categoryLabel(category: Category): string {
    return `${category.name}${category.archived ? ' ' + t('funds.archived') : ''}`;
  }

  protected accountOptions(accounts = this.accounts()): EntityOption[] {
    return accounts.map((account) => ({
      id: account.id,
      label: account.name,
      detail: account.archived ? t('forecast.archived') : undefined,
    }));
  }

  protected ruleAccountOptions(excludeId = ''): EntityOption[] {
    return this.activeAccounts()
      .filter((account) => account.id !== excludeId)
      .map((account) => ({
        id: account.id,
        label: account.name,
        detail: account.archived ? t('forecast.archived') : undefined,
        disabled: account.archived && this.ruleWillBeActive(),
      }));
  }

  protected ruleCategoryOptions(): EntityOption[] {
    return this.availableCategories().map((category) => {
      const parent = category.parent_id
        ? this.categories().find((item) => item.id === category.parent_id)
        : null;
      return {
        id: category.id,
        label: category.name,
        detail: `${category.type === 'income' ? t('operation-create-menu.income') : t('operation-create-menu.expense')}${parent ? ` · ${parent.name}` : ''}${category.archived ? ' ' + t('funds.archived') : ''}`,
        disabled: category.archived && this.ruleWillBeActive(),
      };
    });
  }

  protected canSaveRule(): boolean {
    if (this.ruleForm.invalid) return false;
    const value = this.ruleForm.getRawValue();
    if (!positiveDecimal(value.amount)) return false;
    if (this.hasUnavailableReference()) return false;
    if (value.endOn && value.endOn < value.startOn) return false;
    const day = Number(value.startOn.slice(8, 10));
    if (value.frequency === 'monthly' && day > 28) return false;
    if (value.frequency === 'yearly' && value.startOn.slice(5) === '02-29') return false;
    if (value.frequency === 'weekly' && !this.selectedWeekdays().length) return false;
    if (value.type === 'transfer') {
      return Boolean(value.destinationAccountId && value.destinationAccountId !== value.accountId);
    }
    return Boolean(value.categoryId);
  }

  protected submitRule(): void {
    if (!this.canSaveRule()) {
      this.ruleForm.markAllAsTouched();
      return;
    }
    this.saving.set(true);
    this.error.set(null);
    const body = this.ruleBody();
    const existing = this.rules().find((rule) => rule.id === this.editingId());
    const request = existing
      ? this.http.put<RecurringRule>(`${environment.apiBaseUrl}/scheduling/rules/${existing.id}`, {
          ...body,
          active: existing.active,
          version: existing.version,
        })
      : this.http.post<RecurringRule>(`${environment.apiBaseUrl}/scheduling/rules`, body);
    request.subscribe({
      next: () => {
        this.saving.set(false);
        this.cancelEdit();
        this.loadSchedule();
      },
      error: (error: unknown) => {
        this.saving.set(false);
        this.error.set(() => apiErrorMessage(error, t('scheduling.couldNotSaveTheRecurringRule')));
      },
    });
  }

  protected editRule(rule: RecurringRule): void {
    this.editingId.set(rule.id);
    this.ruleForm.patchValue({
      type: rule.type,
      frequency: rule.frequency,
      interval: rule.interval ?? 1,
      monday: rule.weekdays?.includes(1) ?? false,
      tuesday: rule.weekdays?.includes(2) ?? false,
      wednesday: rule.weekdays?.includes(3) ?? false,
      thursday: rule.weekdays?.includes(4) ?? false,
      friday: rule.weekdays?.includes(5) ?? false,
      saturday: rule.weekdays?.includes(6) ?? false,
      sunday: rule.weekdays?.includes(7) ?? false,
      startOn: rule.start_on,
      endOn: rule.end_on ?? '',
      amount: rule.amount,
      description: rule.description ?? '',
      accountId: rule.account_id,
      destinationAccountId: rule.destination_account_id ?? '',
      categoryId: rule.category_id ?? '',
      allocateToFunds: rule.allocate_to_funds,
      shiftFutureOnPostpone: rule.shift_future_on_postpone,
    });
    this.ruleFormOpen.set(true);
  }

  protected openRule(): void {
    this.cancelEdit();
    this.ruleFormOpen.set(true);
  }

  protected cancelEdit(): void {
    this.editingId.set(null);
    this.ruleForm.reset({
      type: 'expense',
      frequency: 'monthly',
      interval: 1,
      monday: false,
      tuesday: false,
      wednesday: false,
      thursday: false,
      friday: false,
      saturday: false,
      sunday: false,
      startOn: this.today(),
      endOn: '',
      amount: '',
      description: '',
      accountId: '',
      destinationAccountId: '',
      categoryId: '',
      allocateToFunds: false,
      shiftFutureOnPostpone: false,
    });
    this.ruleFormOpen.set(false);
  }

  protected toggleRule(rule: RecurringRule): void {
    if (
      rule.active &&
      !window.confirm(
        t('scheduling.disableRuleP0', { p0: this.ruleTitle(rule) }) +
          t('scheduling.untouchedFutureEventsWillBeCancelledConfirmed'),
      )
    )
      return;
    this.saving.set(true);
    this.http
      .put<RecurringRule>(`${environment.apiBaseUrl}/scheduling/rules/${rule.id}`, {
        type: rule.type,
        frequency: rule.frequency,
        interval: rule.interval,
        weekdays: rule.weekdays,
        start_on: rule.start_on,
        end_on: rule.end_on,
        amount: rule.amount,
        description: rule.description,
        account_id: rule.account_id,
        destination_account_id: rule.destination_account_id,
        category_id: rule.category_id,
        allocate_to_funds: rule.allocate_to_funds,
        shift_future_on_postpone: rule.shift_future_on_postpone,
        active: !rule.active,
        version: rule.version,
      })
      .subscribe({
        next: () => {
          this.saving.set(false);
          this.loadSchedule();
        },
        error: (error: unknown) => {
          this.saving.set(false);
          this.error.set(() => apiErrorMessage(error, t('scheduling.couldNotChangeTheRuleStatus')));
        },
      });
  }

  protected moveMonth(offset: number): void {
    const current = parseIsoDate(this.selectedMonth());
    const next = new Date(current.year, current.month - 1 + offset, 1);
    this.selectedMonth.set(toIsoDate(next));
    this.loadOccurrences();
  }

  protected resetMonth(): void {
    this.selectedMonth.set(`${this.today().slice(0, 7)}-01`);
    this.loadOccurrences();
  }

  protected occurrenceTitle(occurrence: ExpectedOccurrence): string {
    if (occurrence.description) return occurrence.description;
    return this.typeLabel(occurrence.type);
  }

  protected sourceLabel(occurrence: ExpectedOccurrence): string {
    return occurrence.source_kind === 'one_off'
      ? t('scheduling.oneOff')
      : t('scheduling.recurring');
  }

  protected ruleTitle(rule: RecurringRule): string {
    return rule.description || `${this.typeLabel(rule.type)} · ${formatMoney(rule.amount)}`;
  }

  protected typeLabel(type: OperationType): string {
    return {
      income: t('operation-create-menu.income'),
      expense: t('operation-create-menu.expense'),
      transfer: t('operation-create-menu.transfer'),
    }[type];
  }

  protected frequencyLabel(frequency: Frequency): string {
    return {
      daily: t('scheduling.daily'),
      weekly: t('scheduling.weekly'),
      monthly: t('scheduling.monthly'),
      yearly: t('scheduling.yearly'),
    }[frequency];
  }

  protected recurrenceLabel(rule: RecurringRule): string {
    if (rule.frequency === 'weekly') {
      const weekdayLabels = [
        t('scheduling.mon0638'),
        t('scheduling.tue0639'),
        t('scheduling.wed0640'),
        t('scheduling.thu0641'),
        t('scheduling.fri0642'),
        t('scheduling.sat0643'),
        t('scheduling.sun0644'),
      ];
      const days = (rule.weekdays ?? []).map((day) => weekdayLabels[day - 1]).join(', ');
      const interval =
        rule.interval === 1
          ? t('scheduling.everyWeek0645')
          : t('scheduling.everyP0Weeks', { p0: rule.interval });
      return `${interval}${days ? ` · ${days}` : ''}`;
    }
    if (rule.frequency === 'monthly') {
      return rule.interval === 1
        ? t('scheduling.everyMonth0647')
        : t('scheduling.everyP0Months', { p0: rule.interval });
    }
    return this.frequencyLabel(rule.frequency).toLowerCase();
  }

  protected statusLabel(status: OccurrenceStatus): string {
    return {
      pending: t('scheduling.pending'),
      confirmed: t('scheduling.confirmed'),
      postponed: t('scheduling.postponed'),
      cancelled: t('scheduling.cancelled'),
    }[status];
  }

  protected accountDirection(occurrence: ExpectedOccurrence): string {
    return occurrence.destination_account_name
      ? `${occurrence.account_name} → ${occurrence.destination_account_name}`
      : occurrence.account_name;
  }

  protected actionable(occurrence: ExpectedOccurrence): boolean {
    return occurrence.status === 'pending' || occurrence.status === 'postponed';
  }

  protected calendarDaySummary(day: CalendarDay): string | null {
    const terms = day.occurrences
      .filter((occurrence) => this.actionable(occurrence) && occurrence.type !== 'transfer')
      .map((occurrence) => `${occurrence.type === 'expense' ? '-' : '+'}${occurrence.amount}`);
    const total = terms.length ? moneyExpressionPayload(terms.join('')) : '0';
    if (total === null || /^0(?:\.0+)?$/.test(total)) return null;
    return total.startsWith('-') ? total : `+${total}`;
  }

  protected calendarDayLabel(day: CalendarDay, summary?: string): string {
    const overdueCount = this.calendarDayOverdueCount(day);
    const parts = [t('scheduling.openEventsForP0P1', { p0: day.iso, p1: day.occurrences.length })];
    if (summary)
      parts.push(t('scheduling.totalP0P1', { p0: formatMoney(summary), p1: this.baseCurrency() }));
    if (overdueCount) parts.push(t('scheduling.overdueP00655', { p0: overdueCount }));
    return parts.join(', ');
  }

  protected calendarDayOverdueCount(day: CalendarDay): number {
    return day.occurrences.filter((occurrence) => occurrence.overdue).length;
  }

  protected calendarDayFocusId(day: CalendarDay): string | null {
    const occurrenceId = this.route.snapshot.queryParamMap.get('focus');
    return occurrenceId && day.occurrences.some((occurrence) => occurrence.id === occurrenceId)
      ? `occurrence-${occurrenceId}`
      : null;
  }

  protected openOccurrenceEditor(occurrence: ExpectedOccurrence): void {
    if (occurrence.source_kind === 'one_off') {
      void this.router.navigate(['/operations'], { queryParams: { plan: occurrence.id } });
      return;
    }
    void this.router.navigate(['/operations'], { queryParams: { occurrence: occurrence.id } });
  }

  protected openCalendarDay(day: CalendarDay): void {
    this.selectedCalendarDay.set(day);
  }

  protected closeCalendarDay(): void {
    this.selectedCalendarDay.set(null);
  }

  protected postponeDate(occurrence: ExpectedOccurrence): string {
    return this.postponeDates()[occurrence.id] ?? occurrence.due_on;
  }

  protected setPostponeDate(occurrenceId: string, value: string): void {
    this.postponeDates.update((dates) => ({ ...dates, [occurrenceId]: value }));
  }

  protected confirm(occurrence: ExpectedOccurrence): void {
    const amount = this.confirmationAmount(occurrence);
    const normalized = moneyExpressionPayload(amount);
    if (normalized === null || !positiveDecimal(normalized)) return;
    this.runOccurrenceAction(
      occurrence,
      'confirm',
      { version: occurrence.version, amount: normalized },
      () => t('scheduling.couldNotConfirmThePlannedOperation'),
    );
  }

  protected confirmationAmount(occurrence: ExpectedOccurrence): string {
    return this.editingConfirmationId() === occurrence.id
      ? this.confirmationForm.controls.amount.value
      : occurrence.amount;
  }

  protected editConfirmationAmount(occurrence: ExpectedOccurrence): void {
    this.confirmationForm.controls.amount.setValue(occurrence.amount);
    this.editingConfirmationId.set(occurrence.id);
  }

  protected cancelConfirmationAmountEdit(): void {
    this.confirmationForm.reset();
    this.editingConfirmationId.set(null);
  }

  protected validConfirmationAmount(occurrence: ExpectedOccurrence): boolean {
    return positiveDecimal(this.confirmationAmount(occurrence));
  }

  protected occurrenceRule(occurrence: ExpectedOccurrence): RecurringRule | undefined {
    return this.rules().find((rule) => rule.id === occurrence.rule_id);
  }

  protected postponeConsequence(occurrence: ExpectedOccurrence): string | null {
    const rule = this.occurrenceRule(occurrence);
    const next = this.postponeDate(occurrence);
    if (!rule?.shift_future_on_postpone || !next || next === occurrence.due_on) return null;
    const days = daysBetween(occurrence.due_on, next);
    return t('scheduling.theCurrentDateAndFollowingUntouchedEvents', { p0: signedDays(days) });
  }

  protected earlyApplicationWarning(occurrence: ExpectedOccurrence): string | null {
    if (occurrence.source_kind !== 'one_off' || occurrence.due_on <= this.today()) return null;
    return t('scheduling.plannedDateP0YouAreApplyingThis', {
      p0: formatTextDate(occurrence.due_on),
    });
  }

  protected oneOffConfirmationConsequence(occurrence: ExpectedOccurrence): string | null {
    if (occurrence.source_kind !== 'one_off') return null;
    const amount = `${formatMoney(occurrence.amount)} ${this.baseCurrency()}`;
    if (occurrence.type === 'expense') {
      return t('scheduling.todayP1WillBeDebitedFromAccount', {
        p0: occurrence.account_name,
        p1: amount,
      });
    }
    if (occurrence.type === 'income') {
      return t('scheduling.todayP1WillBeCreditedToAccount', {
        p0: occurrence.account_name,
        p1: amount,
      });
    }
    return t('scheduling.todayP0WillBeTransferredFromAccount', {
      p0: amount,
      p1: occurrence.account_name,
      p2: occurrence.destination_account_name ?? '—',
    });
  }

  protected postpone(occurrence: ExpectedOccurrence): void {
    const dueOn = this.postponeDate(occurrence);
    if (!dueOn || dueOn === occurrence.due_on) return;
    const rule = this.occurrenceRule(occurrence);
    this.runOccurrenceAction(
      occurrence,
      'postpone',
      {
        version: occurrence.version,
        due_on: dueOn,
        ...(rule?.shift_future_on_postpone ? { rule_version: rule.version } : {}),
      },
      () => t('scheduling.couldNotPostponeThePlannedOperation'),
    );
  }

  protected cancel(occurrence: ExpectedOccurrence): void {
    if (
      !window.confirm(
        t('scheduling.cancelPlannedOperationP0', { p0: this.occurrenceTitle(occurrence) }),
      )
    )
      return;
    this.runOccurrenceAction(occurrence, 'cancel', { version: occurrence.version }, () =>
      t('scheduling.couldNotCancelThePlannedOperation'),
    );
  }

  private materializeAndLoad(): void {
    this.loading.set(true);
    this.http
      .post<Materialization>(`${environment.apiBaseUrl}/scheduling/materialize`, {})
      .subscribe({
        next: (materialization) => {
          this.today.set(materialization.horizon_from);
          const requestedMonth = this.route.snapshot.queryParamMap.get('month');
          this.selectedMonth.set(
            requestedMonth && /^\d{4}-(0[1-9]|1[0-2])$/.test(requestedMonth)
              ? `${requestedMonth}-01`
              : `${materialization.horizon_from.slice(0, 7)}-01`,
          );
          this.ruleForm.controls.startOn.setValue(materialization.horizon_from);
          this.loadReferenceData();
        },
        error: (error: unknown) => {
          this.loading.set(false);
          this.error.set(() => apiErrorMessage(error, t('scheduling.couldNotPrepareTheCalendar')));
        },
      });
  }

  private loadReferenceData(): void {
    forkJoin({
      accounts: this.http.get<Account[]>(`${environment.apiBaseUrl}/accounts`),
      categories: this.http.get<Category[]>(`${environment.apiBaseUrl}/categories`),
      settings: this.http.get<Settings>(`${environment.apiBaseUrl}/settings`),
      rules: this.http.get<RecurringRule[]>(`${environment.apiBaseUrl}/scheduling/rules`),
    }).subscribe({
      next: ({ accounts, categories, settings, rules }) => {
        this.accounts.set(accounts);
        this.categories.set(categories);
        this.baseCurrency.set(currencySymbol(settings.base_currency));
        this.rules.set(rules);
        this.loadOccurrences();
      },
      error: (error: unknown) => {
        this.loading.set(false);
        this.error.set(() => apiErrorMessage(error, t('scheduling.couldNotLoadCalendarData')));
      },
    });
  }

  private loadSchedule(): void {
    this.http.get<RecurringRule[]>(`${environment.apiBaseUrl}/scheduling/rules`).subscribe({
      next: (rules) => {
        this.rules.set(rules);
        this.loadOccurrences();
      },
      error: (error: unknown) => {
        this.loading.set(false);
        this.error.set(() => apiErrorMessage(error, t('scheduling.couldNotUpdateTheSchedule')));
      },
    });
  }

  private loadOccurrences(): void {
    if (!this.selectedMonth() || !this.today()) return;
    const requestId = ++this.occurrenceRequestId;
    this.loading.set(true);
    const filters = this.filters.getRawValue();
    const range = calendarGridRange(this.selectedMonth());
    let calendarParams = new HttpParams()
      .set('page_size', '367')
      .set('due_from', range.start)
      .set('due_to', range.end);
    let upcomingParams = new HttpParams()
      .set('page_size', '12')
      .set('due_to', this.today())
      .append('status', 'pending')
      .append('status', 'postponed');
    if (filters.accountId) {
      calendarParams = calendarParams.set('account_id', filters.accountId);
      upcomingParams = upcomingParams.set('account_id', filters.accountId);
    }
    if (filters.type) {
      calendarParams = calendarParams.set('type', filters.type);
      upcomingParams = upcomingParams.set('type', filters.type);
    }
    forkJoin({
      calendar: this.loadAllOccurrences(calendarParams),
      upcoming: this.http.get<OccurrencePage>(`${environment.apiBaseUrl}/scheduling/occurrences`, {
        params: upcomingParams,
      }),
    }).subscribe({
      next: ({ calendar, upcoming }) => {
        if (requestId !== this.occurrenceRequestId) return;
        this.calendarOccurrences.set(calendar);
        this.upcoming.set(upcoming.items);
        this.upcomingTotal.set(upcoming.total);
        this.loading.set(false);
        this.focusRequestedOccurrence();
      },
      error: (error: unknown) => {
        if (requestId !== this.occurrenceRequestId) return;
        this.loading.set(false);
        this.error.set(() => apiErrorMessage(error, t('scheduling.couldNotLoadPlannedOperations')));
      },
    });
  }

  private focusRequestedOccurrence(): void {
    const occurrenceId = this.route.snapshot.queryParamMap.get('focus');
    if (!occurrenceId) return;
    queueMicrotask(() => {
      const target = document.getElementById(`occurrence-${occurrenceId}`) as
        | (HTMLElement & {
            scrollIntoView?: (options?: ScrollIntoViewOptions) => void;
          })
        | null;
      target?.scrollIntoView?.({ behavior: 'smooth', block: 'center' });
      target?.focus({ preventScroll: true });
    });
  }

  private loadAllOccurrences(params: HttpParams): Observable<ExpectedOccurrence[]> {
    return this.http
      .get<OccurrencePage>(`${environment.apiBaseUrl}/scheduling/occurrences`, {
        params: params.set('page', '1'),
      })
      .pipe(
        expand((page) => {
          const loaded = page.page * page.page_size;
          if (loaded >= page.total) return EMPTY;
          return this.http.get<OccurrencePage>(`${environment.apiBaseUrl}/scheduling/occurrences`, {
            params: params.set('page', String(page.page + 1)),
          });
        }),
        reduce((items, page) => [...items, ...page.items], [] as ExpectedOccurrence[]),
      );
  }

  protected editingRule(): RecurringRule | undefined {
    return this.rules().find((rule) => rule.id === this.editingId());
  }

  protected ruleWillBeActive(): boolean {
    return this.editingRule()?.active ?? true;
  }

  protected hasUnavailableReference(): boolean {
    if (!this.ruleWillBeActive()) return false;
    const value = this.ruleForm.getRawValue();
    const account = this.accounts().find((item) => item.id === value.accountId);
    const destination = this.accounts().find((item) => item.id === value.destinationAccountId);
    const category = this.categories().find((item) => item.id === value.categoryId);
    return Boolean(
      account?.archived ||
      (value.type === 'transfer' && destination?.archived) ||
      (value.type !== 'transfer' && category?.archived),
    );
  }

  private runOccurrenceAction(
    occurrence: ExpectedOccurrence,
    action: 'confirm' | 'postpone' | 'cancel',
    body: Record<string, string | number>,
    fallback: () => string,
  ): void {
    this.busyOccurrenceId.set(occurrence.id);
    this.error.set(null);
    this.actionNotice.set(null);
    this.http
      .post<ExpectedOccurrence | PostponeResult>(
        `${environment.apiBaseUrl}/scheduling/occurrences/${occurrence.id}/${action}`,
        body,
      )
      .subscribe({
        next: (result) => {
          this.busyOccurrenceId.set(null);
          if (action === 'postpone' && 'series_shift_applied' in result) {
            this.actionNotice.set(() =>
              result.series_shift_applied
                ? t('scheduling.seriesShiftedByP0FollowingEventsUpdated', {
                    p0: signedDays(result.shift_days),
                    p1: result.shifted_occurrences,
                    p2: result.preserved_occurrences,
                  })
                : t('scheduling.onlyTheSelectedEventWasPostponed'),
            );
            this.loadSchedule();
          } else {
            this.loadOccurrences();
          }
        },
        error: (error: unknown) => {
          this.busyOccurrenceId.set(null);
          this.error.set(() => apiErrorMessage(error, fallback));
          if (this.isSchedulingConflict(error)) this.loadOccurrences();
        },
      });
  }

  private isSchedulingConflict(error: unknown): boolean {
    if (!error || typeof error !== 'object' || !('error' in error)) return false;
    const payload = error.error;
    if (!payload || typeof payload !== 'object' || !('detail' in payload)) return false;
    const detail = payload.detail;
    return Boolean(
      detail &&
      typeof detail === 'object' &&
      'code' in detail &&
      detail.code === 'scheduling_conflict',
    );
  }

  private resetDependentFields(): void {
    this.ruleForm.controls.categoryId.setValue('');
    this.ruleForm.controls.destinationAccountId.setValue('');
    if (this.ruleForm.controls.type.value !== 'transfer') {
      this.ruleForm.controls.allocateToFunds.setValue(false);
    }
  }

  protected selectedWeekdays(): number[] {
    const value = this.ruleForm.getRawValue();
    return [
      value.monday,
      value.tuesday,
      value.wednesday,
      value.thursday,
      value.friday,
      value.saturday,
      value.sunday,
    ].flatMap((selected, index) => (selected ? [index + 1] : []));
  }

  private ruleBody(): Record<string, string | number | boolean | number[] | null> {
    const value = this.ruleForm.getRawValue();
    return {
      type: value.type,
      frequency: value.frequency,
      interval: value.frequency === 'weekly' || value.frequency === 'monthly' ? value.interval : 1,
      weekdays: value.frequency === 'weekly' ? this.selectedWeekdays() : null,
      start_on: value.startOn,
      end_on: value.endOn || null,
      amount: moneyExpressionPayload(value.amount)!,
      description: value.description || null,
      account_id: value.accountId,
      destination_account_id: value.type === 'transfer' ? value.destinationAccountId || null : null,
      category_id: value.type === 'transfer' ? null : value.categoryId || null,
      allocate_to_funds: value.type === 'transfer' && value.allocateToFunds,
      shift_future_on_postpone: value.shiftFutureOnPostpone,
    };
  }
}

function parseIsoDate(value: string): { year: number; month: number; day: number } {
  const [year, month, day] = value.split('-').map(Number);
  return { year, month, day };
}

function toIsoDate(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function addDays(value: string, amount: number): string {
  const parsed = parseIsoDate(value);
  return toIsoDate(new Date(parsed.year, parsed.month - 1, parsed.day + amount));
}

function positiveDecimal(value: string): boolean {
  const normalized = moneyExpressionPayload(value);
  if (normalized === null || normalized.startsWith('-')) return false;
  const match = /^(\d{1,16})(?:\.(\d{1,4}))?$/.exec(normalized);
  if (!match) return false;
  return BigInt(match[1]) > 0n || BigInt(match[2] ?? '0') > 0n;
}

function daysBetween(from: string, to: string): number {
  const left = parseIsoDate(from);
  const right = parseIsoDate(to);
  const leftUtc = Date.UTC(left.year, left.month - 1, left.day);
  const rightUtc = Date.UTC(right.year, right.month - 1, right.day);
  return Math.round((rightUtc - leftUtc) / 86_400_000);
}

function signedDays(days: number): string {
  const absolute = Math.abs(days);
  const text = plural(absolute, {
    one: 'common.daysOne',
    few: 'common.daysFew',
    many: 'common.daysMany',
    other: 'common.daysOther',
  });
  return `${days > 0 ? '+' : days < 0 ? '-' : ''}${text}`;
}

function calendarGridRange(month: string): { start: string; end: string } {
  const parsed = parseIsoDate(month);
  const first = new Date(parsed.year, parsed.month - 1, 1);
  const mondayOffset = (first.getDay() + 6) % 7;
  const start = toIsoDate(
    new Date(first.getFullYear(), first.getMonth(), first.getDate() - mondayOffset),
  );
  return { start, end: addDays(start, 41) };
}
