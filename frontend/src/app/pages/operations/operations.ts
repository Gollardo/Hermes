import { t, localizedSignal } from '../../i18n/i18n';
import { HttpClient, HttpParams } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { apiErrorMessage } from '../../core/api-error';
import { DateTextPipe, formatTextDate } from '../../shared/date-text.pipe';
import { currencySymbol, formatMoney, MoneyPipe } from '../../shared/money.pipe';
import { EntityCombobox, EntityOption } from '../../shared/entity-combobox';
import {
  DecimalInput,
  decimalPayload,
  moneyExpressionPayload,
  moneyExpressionValidator,
} from '../../shared/decimal-input';
import { CreateOperationType, OperationCreateMenu } from '../../shared/operation-create-menu';

type OperationType = 'income' | 'expense' | 'transfer' | 'balance_adjustment';
type CategoryType = 'income' | 'expense';

interface Account {
  id: string;
  name: string;
  balance: string;
  archived: boolean;
}

interface Category {
  id: string;
  name: string;
  type: CategoryType;
  archived: boolean;
  parent_id: string | null;
}

interface Movement {
  account_id: string;
  account_name: string;
  amount: string;
}

interface Fund {
  id: string;
  name: string;
  total_balance: string;
  archived: boolean;
}

interface FundPosition {
  fund_id: string;
  account_id: string;
  balance: string;
}

interface FundSummary {
  funds: Fund[];
  positions: FundPosition[];
}

interface OperationFundMovement {
  fund_id: string;
  fund_name: string;
  account_id: string;
  account_name: string;
  amount: string;
}

interface Operation {
  id: string;
  type: OperationType;
  occurred_on: string;
  amount: string;
  description: string | null;
  reason: string | null;
  category_id: string | null;
  category_name: string | null;
  account_id: string;
  destination_account_id: string | null;
  movements: Movement[];
  fund_id: string | null;
  fund_amount: string | null;
  fund_movements: OperationFundMovement[];
  version: number;
}

interface OperationPage {
  items: Operation[];
  page: number;
  page_size: number;
  total: number;
  total_amount: string;
}

interface ApplicationSettings {
  base_currency: string;
  timezone: string;
  default_account_id: string | null;
  application_today: string;
}

interface OneOffPlan {
  id: string;
  source_kind: 'one_off';
  scheduled_on: string;
  due_on: string;
  status: 'pending' | 'postponed' | 'confirmed' | 'cancelled';
  type: Exclude<OperationType, 'balance_adjustment'>;
  amount: string;
  description: string | null;
  account_id: string;
  account_name: string;
  destination_account_id: string | null;
  destination_account_name: string | null;
  category_id: string | null;
  category_name: string | null;
  allocate_to_funds: boolean;
  version: number;
}

interface ExpectedOccurrence extends Omit<OneOffPlan, 'source_kind'> {
  source_kind: 'recurring' | 'one_off';
  rule_id: string | null;
  actual_operation_id: string | null;
}

@Component({
  selector: 'app-operations-page',
  imports: [
    ReactiveFormsModule,
    MoneyPipe,
    DateTextPipe,
    EntityCombobox,
    DecimalInput,
    OperationCreateMenu,
    RouterLink,
  ],
  templateUrl: './operations.html',
  styleUrl: './operations.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class OperationsPage implements OnInit {
  protected readonly t = t;
  private readonly http = inject(HttpClient);
  private readonly builder = inject(NonNullableFormBuilder);
  private readonly route = inject(ActivatedRoute, { optional: true });
  private readonly router = inject(Router);

  protected readonly operations = signal<Operation[]>([]);
  protected readonly todayPlannedOperations = signal<OneOffPlan[]>([]);
  protected readonly plannedOperations = signal<OneOffPlan[]>([]);
  protected readonly focusedOperation = signal<Operation | null>(null);
  protected readonly Math = Math;
  protected readonly accounts = signal<Account[]>([]);
  protected readonly categories = signal<Category[]>([]);
  protected readonly funds = signal<Fund[]>([]);
  private readonly fundPositions = signal<FundPosition[]>([]);
  protected readonly total = signal(0);
  protected readonly totalAmount = signal('0.0000');
  protected readonly baseCurrency = signal('RUB');
  private readonly applicationToday = signal('');
  private readonly settingsReady = signal(false);
  private readonly defaultAccountId = signal<string | null>(null);
  protected readonly page = signal(1);
  protected readonly pageSize = 25;
  protected readonly loading = signal(true);
  protected readonly loadingTodayPlans = signal(false);
  protected readonly saving = signal(false);
  protected readonly confirmingPlanId = signal<string | null>(null);
  protected readonly error = localizedSignal();
  protected readonly scheduledNotice = localizedSignal();
  protected readonly editingId = signal<string | null>(null);
  protected readonly editingPlan = signal<OneOffPlan | null>(null);
  protected readonly confirmingOccurrence = signal<ExpectedOccurrence | null>(null);
  protected readonly expandedId = signal<string | null>(null);
  protected readonly formOpen = signal(false);
  protected readonly filtersOpen = signal(false);
  private defaultAccountWasApplied = false;

  protected readonly form = this.builder.group({
    type: this.builder.control<OperationType | ''>('', Validators.required),
    occurredOn: [this.today(), Validators.required],
    categoryId: [''],
    amount: ['', [Validators.required, moneyExpressionValidator]],
    accountId: ['', Validators.required],
    destinationAccountId: [''],
    description: ['', Validators.maxLength(2000)],
    reason: ['', Validators.maxLength(2000)],
    fundId: [''],
    fundAmount: ['', moneyExpressionValidator],
  });

  protected readonly filters = this.builder.group({
    occurredFrom: [''],
    occurredTo: [''],
    accountId: [''],
    type: this.builder.control<OperationType | ''>(''),
    categoryId: [''],
  });

  ngOnInit(): void {
    this.form.controls.type.valueChanges.subscribe((type) => this.handleOperationType(type));
    this.form.controls.accountId.valueChanges.subscribe((accountId) => {
      if (accountId !== this.defaultAccountId()) this.defaultAccountWasApplied = false;
    });
    const query = this.route?.snapshot.queryParamMap;
    const focusedId = query?.get('focus');
    if (focusedId) this.loadFocusedOperation(focusedId);
    const planId = query?.get('plan');
    if (planId) this.loadOneOffPlan(planId);
    const occurrenceId = query?.get('occurrence');
    if (occurrenceId) this.loadOccurrenceForConfirmation(occurrenceId);
    const queryType = query?.get('type');
    const filterType: OperationType | '' =
      queryType === 'income' ||
      queryType === 'expense' ||
      queryType === 'transfer' ||
      queryType === 'balance_adjustment'
        ? queryType
        : '';
    this.filters.patchValue({
      occurredFrom: query?.get('occurred_from') ?? '',
      occurredTo: query?.get('occurred_to') ?? '',
      categoryId: query?.get('category_id') ?? '',
      type: filterType,
    });
    if (this.filterChips().length) this.filtersOpen.set(true);
    this.loadSettings();
    this.loadDirectories();
    this.load();
    const createType = query?.get('new');
    if (isCreateOperationType(createType)) this.openCreate(createType);
  }

  protected currentOperation(): Operation | undefined {
    return this.operations().find((item) => item.id === this.editingId());
  }

  protected activeAccounts(operation?: Operation): Account[] {
    return this.accounts().filter(
      (account) =>
        !account.archived || operation?.movements.some((m) => m.account_id === account.id),
    );
  }

  protected availableCategories(): Category[] {
    const type = this.form.controls.type.value;
    if (type !== 'income' && type !== 'expense') return [];
    const current = this.currentOperation();
    return this.categories().filter(
      (category) =>
        category.type === type && (!category.archived || category.id === current?.category_id),
    );
  }

  protected availableFunds(): Fund[] {
    const currentFundId = this.currentOperation()?.fund_id;
    const accountId = this.form.controls.accountId.value;
    return this.funds().filter(
      (fund) =>
        fund.id === currentFundId ||
        (!fund.archived && this.fundAvailableOnSource(fund.id, accountId) > 0n),
    );
  }

  protected fundPositionLabel(fund: Fund): string {
    return t('operations.p0AvailableP1P2P3', {
      p0: fund.name,
      p1: formatMoney(
        formatMoneyUnits(this.fundAvailableOnSource(fund.id, this.form.controls.accountId.value)),
      ),
      p2: this.baseCurrency(),
      p3: fund.archived ? ' ' + t('funds.archived') : '',
    });
  }

  protected operationTypeLabel(type: OperationType): string {
    return {
      income: t('operation-create-menu.income'),
      expense: t('operation-create-menu.expense'),
      transfer: t('operation-create-menu.transfer'),
      balance_adjustment: t('operation-create-menu.adjustment'),
    }[type];
  }

  protected categoryLabel(category: Category): string {
    const parent = category.parent_id
      ? this.categories().find((item) => item.id === category.parent_id)
      : null;
    const label = parent ? `${parent.name} → ${category.name}` : category.name;
    return category.archived ? t('operations.p0Archived', { p0: label }) : label;
  }

  protected accountLabel(account: Account): string {
    return `${account.name} · ${formatMoney(account.balance)}${account.archived ? ' ' + t('funds.archived') : ''}`;
  }

  protected accountOptions(accounts = this.accounts()): EntityOption[] {
    return accounts.map((account) => ({
      id: account.id,
      label: account.name,
      detail: `${formatMoney(account.balance)} ${this.baseCurrency()}${account.archived ? ' ' + t('funds.archived') : ''}`,
    }));
  }

  protected destinationAccountOptions(): EntityOption[] {
    return this.accountOptions(
      this.activeAccounts(this.currentOperation()).filter(
        (account) => account.id !== this.form.controls.accountId.value,
      ),
    );
  }

  protected categoryOptions(categories = this.categories()): EntityOption[] {
    return categories.map((category) => {
      const parent = category.parent_id
        ? this.categories().find((item) => item.id === category.parent_id)
        : null;
      return {
        id: category.id,
        label: category.name,
        detail: `${category.type === 'income' ? t('operation-create-menu.income') : t('operation-create-menu.expense')}${parent ? ` · ${parent.name}` : ''}${category.archived ? ' ' + t('funds.archived') : ''}`,
      };
    });
  }

  protected transferDirection(operation: Operation): string {
    if (operation.type !== 'transfer') {
      return operation.category_name || operation.movements[0]?.account_name || '—';
    }
    const source = operation.movements.find((movement) => moneyUnits(movement.amount)! < 0n);
    const destination = operation.movements.find((movement) => moneyUnits(movement.amount)! > 0n);
    return source && destination
      ? `${source.account_name} → ${destination.account_name}`
      : t('operations.directionUnavailable');
  }

  protected operationContext(operation: Operation): string {
    if (operation.type === 'transfer') return this.transferDirection(operation);
    const account = operation.movements[0]?.account_name;
    const fund = operation.fund_movements[0]?.fund_name;
    return [operation.category_name, account, fund ? t('operations.fundP0', { p0: fund }) : null]
      .filter(Boolean)
      .join(' · ');
  }

  protected signedAmount(operation: Pick<Operation, 'type' | 'amount'>): string {
    if (operation.type === 'income') return `+${operation.amount}`;
    if (operation.type === 'expense') return `-${operation.amount}`;
    return operation.amount;
  }

  protected plannedOperationContext(plan: OneOffPlan): string {
    if (plan.type === 'transfer') {
      return `${plan.account_name} → ${plan.destination_account_name ?? '—'}`;
    }
    return plan.account_name;
  }

  protected plannedStatusLabel(plan: OneOffPlan): string {
    return plan.status === 'postponed' ? t('operations.postponedTo') : t('operations.scheduledFor');
  }

  protected isConfirmingPlan(plan: OneOffPlan): boolean {
    return this.confirmingPlanId() === plan.id;
  }

  protected applyPlanToday(plan: OneOffPlan): void {
    const today = this.applicationToday();
    if (!today || this.confirmingPlanId()) return;
    const confirmed = window.confirm(
      [
        t('operations.applyThisOneOffPlanToday'),
        t('operations.postingDateTheCurrentHermesDayAt'),
        `${this.operationTypeLabel(plan.type)}: ${formatMoney(this.signedAmount(plan))} ${this.baseCurrency()}.`,
        t('operations.accountP0', { p0: this.plannedOperationContext(plan) }),
        t('operations.theActualBalanceWillChangeAfterApplication'),
      ].join('\n'),
    );
    if (!confirmed) return;

    this.error.set(null);
    this.confirmingPlanId.set(plan.id);
    this.http
      .post<OneOffPlan>(`${environment.apiBaseUrl}/scheduling/occurrences/${plan.id}/confirm`, {
        version: plan.version,
      })
      .subscribe({
        next: () => {
          this.confirmingPlanId.set(null);
          this.scheduledNotice.set(() => t('operations.theOneOffPlanWasAppliedAnd'));
          this.load();
          this.loadDirectories();
        },
        error: (error: unknown) => {
          this.confirmingPlanId.set(null);
          this.error.set(() => apiErrorMessage(error, t('operations.couldNotApplyTheOneOffPlan')));
          this.load();
        },
      });
  }

  protected editPlan(plan: OneOffPlan): void {
    this.loadOneOffPlan(plan.id);
  }

  protected removePlan(plan: OneOffPlan): void {
    if (!window.confirm(t('operations.deleteTheOneOffPlanItWill'))) {
      return;
    }
    this.http
      .post<OneOffPlan>(`${environment.apiBaseUrl}/scheduling/occurrences/${plan.id}/cancel`, {
        version: plan.version,
      })
      .subscribe({
        next: () => {
          this.cancelEdit();
          this.load();
        },
        error: (error: unknown) =>
          this.error.set(() => apiErrorMessage(error, t('operations.couldNotDeleteTheOneOffPlan'))),
      });
  }

  protected adjustmentBaseBalance(): string | null {
    const accountId = this.form.controls.accountId.value;
    const account = this.accounts().find((item) => item.id === accountId);
    if (!account) return null;
    const existing = this.currentOperation();
    if (existing?.type !== 'balance_adjustment' || existing.account_id !== accountId) {
      return normalizeMoney(account.balance);
    }
    const oldMovement = existing.movements.find((movement) => movement.account_id === accountId);
    return subtractMoney(account.balance, oldMovement?.amount ?? '0');
  }

  protected adjustmentDelta(target = this.form.controls.amount.value): string | null {
    const base = this.adjustmentBaseBalance();
    const normalizedTarget = moneyExpressionPayload(target);
    return base === null || normalizedTarget === null
      ? null
      : subtractMoney(normalizedTarget, base);
  }

  protected canSubmit(): boolean {
    const value = this.form.getRawValue();
    const amount = moneyExpressionPayload(value.amount);
    const fundAmount = value.fundAmount ? moneyExpressionPayload(value.fundAmount) : '';
    if (amount === null || fundAmount === null) return false;
    const postingAmount =
      value.type === 'balance_adjustment' ? this.adjustmentDelta(amount) : amount;
    const expectedBalance = moneyUnits(amount);
    return (
      this.settingsReady() &&
      this.form.valid &&
      postingAmount !== null &&
      (value.type !== 'balance_adjustment' ||
        (expectedBalance !== null && expectedBalance >= 0n)) &&
      this.shapeIsValid(
        value.type,
        postingAmount,
        value.accountId,
        value.categoryId,
        value.destinationAccountId,
        value.reason,
        value.fundId,
        fundAmount,
        amount,
      ) &&
      this.fundSelectionIsValid(value.type, value.accountId, value.fundId, amount, fundAmount) &&
      !(this.usesExpectedOperationFields() && value.type === 'balance_adjustment') &&
      !(this.isOccurrenceConfirmationMode() && Boolean(value.fundId) && value.fundId !== 'allocate')
    );
  }

  protected isOccurrenceConfirmationMode(): boolean {
    return Boolean(this.confirmingOccurrence());
  }

  protected usesExpectedOperationFields(): boolean {
    return this.isPlanMode() || this.isOccurrenceConfirmationMode();
  }

  protected isPlanMode(): boolean {
    if (this.isOccurrenceConfirmationMode()) return false;
    return (
      Boolean(this.editingPlan()) ||
      (!this.editingId() && this.isFutureDate(this.form.controls.occurredOn.value))
    );
  }

  protected filterChips(): string[] {
    const value = this.filters.getRawValue();
    const chips: string[] = [];
    if (value.occurredFrom) chips.push(t('operations.fromP0', { p0: value.occurredFrom }));
    if (value.occurredTo) chips.push(t('operations.throughP0', { p0: value.occurredTo }));
    if (value.accountId) {
      chips.push(
        this.accounts().find((item) => item.id === value.accountId)?.name ?? t('forecast.account'),
      );
    }
    if (value.type) chips.push(this.operationTypeLabel(value.type));
    if (value.categoryId) {
      const category = this.categories().find((item) => item.id === value.categoryId);
      chips.push(category ? this.categoryLabel(category) : t('operations.category'));
    }
    return chips;
  }

  protected submit(): void {
    this.error.set(null);
    const value = this.form.getRawValue();
    const amount = moneyExpressionPayload(value.amount);
    const fundAmount = value.fundAmount ? moneyExpressionPayload(value.fundAmount) : '';
    const postingAmount =
      value.type === 'balance_adjustment' && amount !== null
        ? this.adjustmentDelta(amount)
        : amount;
    if (!this.canSubmit() || postingAmount === null || fundAmount === null) {
      this.form.markAllAsTouched();
      this.error.set(() => t('operations.completeTheRequiredFieldsForTheSelected'));
      return;
    }
    const body: Record<string, unknown> = {
      type: value.type,
      occurred_on: value.occurredOn,
      amount: decimalPayload(postingAmount),
      account_id: value.accountId,
      destination_account_id: value.type === 'transfer' ? value.destinationAccountId : null,
      category_id: value.type === 'income' || value.type === 'expense' ? value.categoryId : null,
      description: value.description || null,
      reason: value.type === 'balance_adjustment' ? value.reason : null,
      fund_id: value.type === 'expense' || value.type === 'transfer' ? value.fundId || null : null,
      fund_amount:
        value.type === 'transfer' && value.fundId && value.fundAmount
          ? decimalPayload(fundAmount)
          : null,
    };
    const id = this.editingId();
    const plan = this.editingPlan();
    const occurrence = this.confirmingOccurrence();
    const existing = this.operations().find((item) => item.id === id);
    if (occurrence) {
      body['allocate_to_funds'] = value.type === 'transfer' && value.fundId === 'allocate';
      delete body['occurred_on'];
      delete body['reason'];
      delete body['fund_id'];
      delete body['fund_amount'];
    } else if (this.isPlanMode()) {
      body['scheduled_on'] = value.occurredOn;
      body['allocate_to_funds'] = value.type === 'transfer' && value.fundId === 'allocate';
      body['fund_id'] = null;
      body['fund_amount'] = null;
      delete body['occurred_on'];
      delete body['reason'];
      if (plan) body['version'] = plan.version;
    } else if (existing) body['version'] = existing.version;
    this.saving.set(true);
    const request: Observable<Operation | OneOffPlan | ExpectedOccurrence> = occurrence
      ? this.http.post<ExpectedOccurrence>(
          `${environment.apiBaseUrl}/scheduling/occurrences/${occurrence.id}/confirm`,
          { version: occurrence.version, operation: body },
        )
      : this.isPlanMode()
        ? plan
          ? this.http.put<OneOffPlan>(
              `${environment.apiBaseUrl}/scheduling/one-off-plans/${plan.id}`,
              body,
            )
          : this.http.post<OneOffPlan>(`${environment.apiBaseUrl}/scheduling/one-off-plans`, body)
        : id
          ? this.http.put<Operation>(`${environment.apiBaseUrl}/operations/${id}`, body)
          : this.http.post<Operation>(`${environment.apiBaseUrl}/operations`, body);
    request.subscribe({
      next: (result) => {
        this.saving.set(false);
        if (occurrence && 'actual_operation_id' in result && result.actual_operation_id) {
          const operationId = result.actual_operation_id;
          this.scheduledNotice.set(() => t('operations.thePlannedOperationWasConfirmedAndAdded'));
          this.cancelEdit();
          this.load();
          this.loadDirectories();
          this.loadFocusedOperation(operationId);
          void this.router.navigate(['/operations'], {
            queryParams: { focus: operationId },
            replaceUrl: true,
          });
          return;
        }
        if (this.isPlanMode() && 'scheduled_on' in result) {
          this.scheduledNotice.set(() =>
            t('operations.oneOffOperationScheduledForP0', {
              p0: formatTextDate(result.scheduled_on),
            }),
          );
        }
        this.cancelEdit();
        this.load();
        this.loadDirectories();
      },
      error: (error: unknown) => {
        this.saving.set(false);
        this.error.set(() => apiErrorMessage(error, t('operations.couldNotSaveTheOperation')));
      },
    });
  }

  protected edit(operation: Operation): void {
    this.defaultAccountWasApplied = false;
    this.editingId.set(operation.id);
    this.form.setValue({
      type: operation.type,
      occurredOn: operation.occurred_on,
      categoryId: operation.category_id ?? '',
      amount:
        operation.type === 'balance_adjustment'
          ? (this.accounts().find((account) => account.id === operation.account_id)?.balance ?? '')
          : operation.amount,
      accountId: operation.account_id,
      destinationAccountId: operation.destination_account_id ?? '',
      description: operation.description ?? '',
      reason: operation.reason ?? '',
      fundId: operation.fund_id ?? '',
      fundAmount: operation.type === 'transfer' ? (operation.fund_amount ?? '') : '',
    });
    this.formOpen.set(true);
  }

  protected openCreate(type: CreateOperationType = 'expense'): void {
    this.cancelEdit();
    this.form.controls.type.setValue(type);
    this.applyDefaultAccount();
    this.formOpen.set(true);
  }

  protected cancelEdit(): void {
    this.defaultAccountWasApplied = false;
    this.editingId.set(null);
    this.editingPlan.set(null);
    this.confirmingOccurrence.set(null);
    this.form.reset({
      type: '',
      occurredOn: this.today(),
      categoryId: '',
      amount: '',
      accountId: '',
      destinationAccountId: '',
      description: '',
      reason: '',
      fundId: '',
      fundAmount: '',
    });
    this.formOpen.set(false);
  }

  protected remove(operation: Operation): void {
    if (
      !window.confirm(
        t('operations.deleteOperationP0BalancesWillBeRecalculated', {
          p0: this.operationTypeLabel(operation.type),
        }),
      )
    )
      return;
    this.http
      .delete<void>(
        `${environment.apiBaseUrl}/operations/${operation.id}?version=${operation.version}`,
      )
      .subscribe({
        next: () => {
          this.load();
          this.loadDirectories();
        },
        error: (error: unknown) =>
          this.error.set(() => apiErrorMessage(error, t('operations.couldNotDeleteTheOperation'))),
      });
  }

  protected toggleDetails(operation: Operation): void {
    this.expandedId.set(this.expandedId() === operation.id ? null : operation.id);
  }

  protected applyFilters(): void {
    this.page.set(1);
    this.load();
  }

  protected clearFilters(): void {
    this.filters.reset({
      occurredFrom: '',
      occurredTo: '',
      accountId: '',
      type: '',
      categoryId: '',
    });
    this.applyFilters();
  }

  protected previousPage(): void {
    if (this.page() > 1) {
      this.page.update((value) => value - 1);
      this.load();
    }
  }

  protected nextPage(): void {
    if (this.page() * this.pageSize < this.total()) {
      this.page.update((value) => value + 1);
      this.load();
    }
  }

  private shapeIsValid(
    type: OperationType | '',
    amount: string,
    accountId: string,
    categoryId: string,
    destinationAccountId: string,
    reason: string,
    fundId: string,
    fundAmount: string,
    physicalAmount: string,
  ): boolean {
    if (!type || !accountId) return false;
    if ((type === 'income' || type === 'expense') && !categoryId) return false;
    if (type === 'transfer' && (!destinationAccountId || destinationAccountId === accountId)) {
      return false;
    }
    if (type === 'balance_adjustment' && !reason.trim()) return false;
    if (type === 'transfer' && fundId && fundId !== 'allocate') {
      const virtualUnits = moneyUnits(fundAmount);
      const physicalUnits = moneyUnits(physicalAmount);
      if (
        virtualUnits === null ||
        physicalUnits === null ||
        virtualUnits <= 0n ||
        virtualUnits > physicalUnits
      ) {
        return false;
      }
    }
    const units = moneyUnits(amount);
    if (units === null) return false;
    return type === 'balance_adjustment' ? units !== 0n : units > 0n;
  }

  private fundSelectionIsValid(
    type: OperationType | '',
    accountId: string,
    fundId: string,
    physicalAmount: string,
    fundAmount: string,
  ): boolean {
    if (!fundId || fundId === 'allocate' || (type !== 'expense' && type !== 'transfer'))
      return true;
    const required = moneyUnits(type === 'expense' ? physicalAmount : fundAmount);
    return (
      required !== null &&
      required > 0n &&
      required <= this.fundAvailableOnSource(fundId, accountId)
    );
  }

  private fundAvailableOnSource(fundId: string, accountId: string): bigint {
    const current =
      moneyUnits(
        this.fundPositions().find(
          (position) => position.fund_id === fundId && position.account_id === accountId,
        )?.balance ?? '0',
      ) ?? 0n;
    const oldMovement = this.currentOperation()?.fund_movements.find(
      (movement) => movement.fund_id === fundId && movement.account_id === accountId,
    );
    return current - (moneyUnits(oldMovement?.amount ?? '0') ?? 0n);
  }

  private loadSettings(): void {
    this.http.get<ApplicationSettings>(`${environment.apiBaseUrl}/settings`).subscribe({
      next: (settings) => {
        this.baseCurrency.set(currencySymbol(settings.base_currency));
        this.applicationToday.set(settings.application_today);
        this.defaultAccountId.set(settings.default_account_id);
        this.settingsReady.set(true);
        this.applyDefaultAccount();
        if (this.confirmingOccurrence()) {
          this.form.controls.occurredOn.setValue(settings.application_today);
        } else if (
          !this.editingId() &&
          !this.editingPlan() &&
          this.form.controls.occurredOn.pristine
        ) {
          this.form.controls.occurredOn.setValue(settings.application_today);
          this.form.controls.occurredOn.markAsPristine();
        }
        this.loadPlannedOperations(this.filters.getRawValue());
      },
      error: (error: unknown) =>
        this.error.set(() =>
          apiErrorMessage(error, t('operations.couldNotLoadCurrencyAndTimezone')),
        ),
    });
  }

  private loadFocusedOperation(operationId: string): void {
    this.http.get<Operation>(`${environment.apiBaseUrl}/operations/${operationId}`).subscribe({
      next: (operation) => this.focusedOperation.set(operation),
      error: (error: unknown) =>
        this.error.set(() =>
          apiErrorMessage(error, t('operations.couldNotOpenTheLinkedOperation')),
        ),
    });
  }

  private loadOneOffPlan(planId: string): void {
    this.http
      .get<OneOffPlan>(`${environment.apiBaseUrl}/scheduling/occurrences/${planId}`)
      .subscribe({
        next: (plan) => {
          if (
            plan.source_kind !== 'one_off' ||
            plan.status === 'confirmed' ||
            plan.status === 'cancelled'
          ) {
            this.error.set(() => t('operations.thisPlanCannotBeEdited'));
            return;
          }
          this.defaultAccountWasApplied = false;
          this.editingPlan.set(plan);
          this.form.setValue({
            type: plan.type,
            occurredOn: plan.scheduled_on,
            categoryId: plan.category_id ?? '',
            amount: plan.amount,
            accountId: plan.account_id,
            destinationAccountId: plan.destination_account_id ?? '',
            description: plan.description ?? '',
            reason: '',
            fundId: plan.allocate_to_funds ? 'allocate' : '',
            fundAmount: '',
          });
          this.formOpen.set(true);
        },
        error: (error: unknown) =>
          this.error.set(() => apiErrorMessage(error, t('operations.couldNotOpenTheOneOffPlan'))),
      });
  }

  private loadOccurrenceForConfirmation(occurrenceId: string): void {
    this.http
      .get<ExpectedOccurrence>(`${environment.apiBaseUrl}/scheduling/occurrences/${occurrenceId}`)
      .subscribe({
        next: (occurrence) => {
          if (occurrence.status === 'confirmed' || occurrence.status === 'cancelled') {
            this.error.set(() => t('operations.thisPlannedOperationCannotBeConfirmed'));
            return;
          }
          this.defaultAccountWasApplied = false;
          this.confirmingOccurrence.set(occurrence);
          this.form.setValue({
            type: occurrence.type,
            occurredOn: this.applicationToday() || this.today(),
            categoryId: occurrence.category_id ?? '',
            amount: occurrence.amount,
            accountId: occurrence.account_id,
            destinationAccountId: occurrence.destination_account_id ?? '',
            description: occurrence.description ?? '',
            reason: '',
            fundId: occurrence.allocate_to_funds ? 'allocate' : '',
            fundAmount: '',
          });
          this.formOpen.set(true);
        },
        error: (error: unknown) =>
          this.error.set(() =>
            apiErrorMessage(error, t('operations.couldNotOpenThePlannedOperation')),
          ),
      });
  }

  private loadDirectories(): void {
    this.http.get<Account[]>(`${environment.apiBaseUrl}/accounts`).subscribe({
      next: (accounts) => {
        this.accounts.set(accounts);
        this.applyDefaultAccount();
      },
      error: (error: unknown) =>
        this.error.set(() => apiErrorMessage(error, t('accounts.couldNotLoadAccounts'))),
    });
    this.http.get<Category[]>(`${environment.apiBaseUrl}/categories`).subscribe({
      next: (categories) => this.categories.set(categories),
      error: (error: unknown) =>
        this.error.set(() => apiErrorMessage(error, t('categories.couldNotLoadCategories'))),
    });
    this.http.get<FundSummary>(`${environment.apiBaseUrl}/funds/summary`).subscribe({
      next: (summary) => {
        this.funds.set(summary.funds);
        this.fundPositions.set(summary.positions);
      },
      error: (error: unknown) =>
        this.error.set(() => apiErrorMessage(error, t('funds.couldNotLoadFunds'))),
    });
  }

  private load(): void {
    this.loading.set(true);
    const filter = this.filters.getRawValue();
    let params = new HttpParams().set('page', this.page()).set('page_size', this.pageSize);
    for (const [key, value] of Object.entries({
      occurred_from: filter.occurredFrom,
      occurred_to: filter.occurredTo,
      account_id: filter.accountId,
      type: filter.type,
      category_id: filter.categoryId,
    })) {
      if (value) params = params.set(key, value);
    }
    this.http.get<OperationPage>(`${environment.apiBaseUrl}/operations`, { params }).subscribe({
      next: (result) => {
        this.operations.set(result.items);
        this.total.set(result.total);
        this.totalAmount.set(result.total_amount);
        this.loading.set(false);
      },
      error: (error: unknown) => {
        this.loading.set(false);
        this.error.set(() => apiErrorMessage(error, t('operations.couldNotLoadTheJournal')));
      },
    });
    if (this.applicationToday()) this.loadPlannedOperations(filter);
  }

  private loadPlannedOperations(filter: {
    occurredFrom: string;
    occurredTo: string;
    accountId: string;
    type: OperationType | '';
    categoryId: string;
  }): void {
    const params = this.oneOffPlanParams(filter);
    const today = this.applicationToday();
    if (!params || !today) {
      this.todayPlannedOperations.set([]);
      this.plannedOperations.set([]);
      this.loadingTodayPlans.set(false);
      return;
    }

    this.loadOneOffPlanPage(
      params,
      (items) =>
        this.plannedOperations.set(
          this.filterOneOffPlans(items, filter).filter((plan) => plan.due_on !== today),
        ),
      () => t('operations.couldNotLoadOneOffPlans'),
    );

    if (!this.todayIsWithinPeriod(filter, today)) {
      this.todayPlannedOperations.set([]);
      this.loadingTodayPlans.set(false);
      return;
    }
    this.loadingTodayPlans.set(true);
    this.loadAllOneOffPlans(
      params.set('due_from', today).set('due_to', today),
      (items) => {
        this.todayPlannedOperations.set(this.filterOneOffPlans(items, filter));
        this.loadingTodayPlans.set(false);
      },
      () => t('operations.couldNotLoadTodaySOneOff'),
      () => this.loadingTodayPlans.set(false),
    );
  }

  private oneOffPlanParams(filter: {
    occurredFrom: string;
    occurredTo: string;
    accountId: string;
    type: OperationType | '';
    categoryId: string;
  }): HttpParams | null {
    let params = new HttpParams()
      .set('page_size', '367')
      .append('source_kind', 'one_off')
      .append('status', 'pending')
      .append('status', 'postponed');
    if (filter.occurredFrom) params = params.set('due_from', filter.occurredFrom);
    if (filter.occurredTo) params = params.set('due_to', filter.occurredTo);
    if (filter.accountId) params = params.set('account_id', filter.accountId);
    if (filter.type && filter.type !== 'balance_adjustment')
      params = params.set('type', filter.type);
    if (filter.type === 'balance_adjustment') {
      return null;
    }
    return params;
  }

  private loadAllOneOffPlans(
    params: HttpParams,
    onSuccess: (items: OneOffPlan[]) => void,
    fallbackError: () => string,
    onError?: () => void,
  ): void {
    const items: OneOffPlan[] = [];
    const loadPage = (page: number): void => {
      this.http
        .get<{ items: OneOffPlan[]; total: number }>(
          `${environment.apiBaseUrl}/scheduling/occurrences`,
          { params: params.set('page', page) },
        )
        .subscribe({
          next: (result) => {
            items.push(...result.items);
            if (items.length < result.total) {
              loadPage(page + 1);
              return;
            }
            onSuccess(items);
          },
          error: (error: unknown) => {
            onError?.();
            this.error.set(() => apiErrorMessage(error, fallbackError));
          },
        });
    };
    loadPage(1);
  }

  private loadOneOffPlanPage(
    params: HttpParams,
    onSuccess: (items: OneOffPlan[]) => void,
    fallbackError: () => string,
  ): void {
    this.http
      .get<{ items: OneOffPlan[] }>(`${environment.apiBaseUrl}/scheduling/occurrences`, {
        params: params.set('page', 1),
      })
      .subscribe({
        next: (result) => onSuccess(result.items),
        error: (error: unknown) => this.error.set(() => apiErrorMessage(error, fallbackError)),
      });
  }

  private filterOneOffPlans(items: OneOffPlan[], filter: { categoryId: string }): OneOffPlan[] {
    return filter.categoryId
      ? items.filter((plan) => plan.category_id === filter.categoryId)
      : items;
  }

  private todayIsWithinPeriod(
    filter: { occurredFrom: string; occurredTo: string },
    today: string,
  ): boolean {
    return (
      (!filter.occurredFrom || filter.occurredFrom <= today) &&
      (!filter.occurredTo || filter.occurredTo >= today)
    );
  }

  private today(): string {
    return this.applicationToday();
  }

  protected isFutureDate(value: string): boolean {
    return Boolean(value && this.applicationToday() && value > this.applicationToday());
  }

  private applyDefaultAccount(): void {
    if (this.editingId() || this.form.controls.accountId.value) return;
    const type = this.form.controls.type.value;
    if (type !== 'income' && type !== 'expense') return;
    const defaultId = this.defaultAccountId();
    if (
      defaultId &&
      this.accounts().some((account) => account.id === defaultId && !account.archived)
    ) {
      this.form.controls.accountId.setValue(defaultId, { emitEvent: false });
      this.defaultAccountWasApplied = true;
    }
  }

  private handleOperationType(type: OperationType | ''): void {
    if (type !== 'income' && type !== 'expense' && this.defaultAccountWasApplied) {
      this.form.controls.accountId.setValue('', { emitEvent: false });
      this.defaultAccountWasApplied = false;
      return;
    }
    this.applyDefaultAccount();
  }
}

function isCreateOperationType(value: string | null | undefined): value is CreateOperationType {
  return (
    value === 'expense' ||
    value === 'income' ||
    value === 'transfer' ||
    value === 'balance_adjustment'
  );
}

function moneyUnits(value: string): bigint | null {
  const match = /^(-?)(\d{1,16})(?:\.(\d{1,4}))?$/.exec(value.trim());
  if (!match) return null;
  const fraction = (match[3] ?? '').padEnd(4, '0');
  const units = BigInt(match[2]) * 10_000n + BigInt(fraction || '0');
  return match[1] === '-' ? -units : units;
}

function formatMoneyUnits(units: bigint): string {
  const sign = units < 0n ? '-' : '';
  const absolute = units < 0n ? -units : units;
  const integer = absolute / 10_000n;
  const fraction = String(absolute % 10_000n).padStart(4, '0');
  return `${sign}${integer}.${fraction}`;
}

function normalizeMoney(value: string): string | null {
  const units = moneyUnits(value);
  return units === null ? null : formatMoneyUnits(units);
}

function subtractMoney(minuend: string, subtrahend: string): string | null {
  const left = moneyUnits(minuend);
  const right = moneyUnits(subtrahend);
  return left === null || right === null ? null : formatMoneyUnits(left - right);
}
