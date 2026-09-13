import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  OnDestroy,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { environment } from '../../../environments/environment';
import { apiErrorMessage } from '../../core/api-error';
import { localizedSignal, t } from '../../i18n/i18n';
import { DecimalInput, decimalPayload } from '../../shared/decimal-input';
import { DateTextPipe, formatTextDate } from '../../shared/date-text.pipe';
import { EntityCombobox } from '../../shared/entity-combobox';
import { MoneyPipe, currencySymbol, formatMoney } from '../../shared/money.pipe';
import { ForecastHorizon, compareDecimal } from '../forecast/forecast-view-model';
import { ScenariosPage } from './scenarios';
import {
  Decision,
  LivingCost,
  SavedWorkspace,
  SolveResult,
  Variant,
  Workspace,
  WorkspaceContext,
  WorkspaceResult,
} from './workspace-model';

const id = () => crypto.randomUUID();
const variant = (): Variant => ({
  id: id(),
  name: t('workbench.firstVariant'),
  decisions: [],
  expense_increase_percent: '0',
  income_delay_days: 0,
});

@Component({
  selector: 'app-workspace-page',
  imports: [
    FormsModule,
    RouterLink,
    DecimalInput,
    MoneyPipe,
    DateTextPipe,
    EntityCombobox,
    ScenariosPage,
  ],
  templateUrl: './workspace.html',
  styleUrls: ['./scenarios.css', './workspace.css'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class WorkspacePage implements OnInit, OnDestroy {
  protected readonly t = t;
  private readonly http = inject(HttpClient);
  private readonly route = inject(ActivatedRoute);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  protected readonly context = signal<WorkspaceContext | null>(null);
  protected readonly draft = signal<Workspace>({
    snapshot_id: '',
    horizon: 'month',
    scope_account_id: null,
    stop_loss: '0',
    living_costs: [],
    variants: [variant()],
  });
  protected readonly activeId = signal(this.draft().variants[0].id);
  protected readonly active = computed(
    () => this.draft().variants.find((v) => v.id === this.activeId()) ?? this.draft().variants[0],
  );
  protected readonly result = signal<WorkspaceResult | null>(null);
  protected readonly selectedResult = computed(
    () => this.result()?.variants.find((v) => v.id === this.active().id) ?? null,
  );
  protected readonly loading = signal(false);
  protected readonly refreshRequired = signal(false);
  protected readonly busy = signal(false);
  protected readonly saving = signal(false);
  protected readonly error = localizedSignal();
  protected readonly notice = localizedSignal();
  protected readonly saved = signal<SavedWorkspace[]>([]);
  protected readonly savedId = signal('');
  protected readonly savedVersion = signal<number | null>(null);
  protected readonly name = signal('');
  protected readonly dirty = signal(false);
  protected readonly pendingOpen = signal<SavedWorkspace | null>(null);
  protected readonly pendingDelete = signal('');
  protected readonly stale = computed(
    () => !!this.context() && this.context()!.snapshot_id !== this.draft().snapshot_id,
  );
  protected readonly changedSources = computed(() =>
    this.draft().variants.flatMap((v) =>
      v.decisions
        .filter((d) => d.occurrence_id)
        .map((d) => ({
          variant: v.name,
          decision: d,
          current: this.context()?.plans.find((p) => p.id === d.occurrence_id),
        }))
        .filter((item) => !item.current || item.current.version !== item.decision.version),
    ),
  );
  protected readonly currency = computed(() => currencySymbol(this.context()?.currency ?? ''));
  protected readonly accountOptions = computed(() =>
    (this.context()?.accounts ?? []).map((a) => ({
      id: a.id,
      label: a.name,
      archived: a.archived,
    })),
  );
  protected readonly activeAccounts = computed(() =>
    this.accountOptions().filter((a) => !a.archived),
  );
  protected readonly planOptions = computed(() =>
    (this.context()?.plans ?? []).map((p) => ({
      id: p.id,
      label: `${p.description || this.typeLabel(p.type)} · ${formatMoney(p.amount)} ${this.currency()}`,
      detail: `${formatTextDate(p.due_on)} · ${p.account_name}`,
    })),
  );
  protected readonly fundOptions = computed(() =>
    (this.context()?.funds ?? []).map((f) => ({ id: f.id, label: f.name })),
  );
  protected readonly historyCost = signal('');
  protected readonly historyPage = signal(0);
  protected readonly objective = signal<'maximum_amount' | 'earliest_date'>('maximum_amount');
  protected readonly solveDecision = signal('');
  protected readonly ceiling = signal('');
  protected readonly solution = signal<SolveResult | null>(null);
  protected readonly solverOptions = computed(() =>
    this.active()
      .decisions.filter(
        (d) =>
          d.enabled &&
          d.action === 'expense' &&
          !d.fund_id &&
          !this.draft().living_costs.some(
            (c) => c.account_id === d.account_id && c.category_id === d.category_id,
          ) &&
          (this.objective() !== 'earliest_date' || d.repeat === 'once'),
      )
      .map((d, i) => ({ id: d.id, label: d.description || `${t('oracle.expense')} ${i + 1}` })),
  );
  protected readonly horizons: ForecastHorizon[] = [
    'two_weeks',
    'month',
    'quarter',
    'half_year',
    'year',
  ];
  protected readonly repeatValues = ['once', 'daily', 'weekly', 'monthly', 'yearly'] as const;
  private sequence = 0;
  private alive = true;

  ngOnInit(): void {
    const params = this.route.snapshot.queryParamMap;
    const horizon = params.get('horizon') as ForecastHorizon;
    this.draft.update((d) => ({
      ...d,
      horizon: this.horizons.includes(horizon) ? horizon : 'month',
      scope_account_id: params.get('account_id'),
    }));
    this.refresh();
    this.reloadSaved();
  }
  ngOnDestroy(): void {
    this.alive = false;
    this.sequence++;
  }
  protected invalidate(): void {
    this.sequence++;
    this.result.set(null);
    this.solution.set(null);
    this.busy.set(false);
    this.error.set(null);
    this.notice.set(null);
  }
  protected edit(patch: Partial<Workspace>): void {
    this.invalidate();
    this.draft.update((d) => ({ ...d, ...patch }));
    this.dirty.set(true);
  }
  protected editVariant(patch: Partial<Variant>): void {
    this.edit({
      variants: this.draft().variants.map((v) =>
        v.id === this.active().id ? { ...v, ...patch } : v,
      ),
    });
  }
  protected selectVariant(value: string): void {
    this.activeId.set(value);
    this.solution.set(null);
    this.solveDecision.set('');
  }
  protected addVariant(copy = false): void {
    if (this.draft().variants.length >= 5) return;
    const next = copy
      ? {
          ...structuredClone(this.active()),
          id: id(),
          name: `${this.active().name} · ${t('workbench.copy')}`.slice(0, 120),
        }
      : variant();
    this.edit({ variants: [...this.draft().variants, next] });
    this.activeId.set(next.id);
  }
  protected removeVariant(): void {
    if (this.draft().variants.length <= 1) return;
    const variants = this.draft().variants.filter((v) => v.id !== this.active().id);
    this.edit({ variants });
    this.activeId.set(variants[0].id);
  }
  protected addDecision(): void {
    if (this.active().decisions.length >= 50) return;
    this.editVariant({
      decisions: [
        ...this.active().decisions,
        {
          id: id(),
          action: 'expense',
          enabled: true,
          description: '',
          amount: '',
          due_on: this.context()?.today,
          account_id: this.draft().scope_account_id ?? undefined,
          repeat: 'once',
        },
      ],
    });
  }
  protected updateDecision(key: string, patch: Partial<Decision>): void {
    this.editVariant({
      decisions: this.active().decisions.map((d) => (d.id === key ? { ...d, ...patch } : d)),
    });
  }
  protected changeAction(d: Decision, action: Decision['action']): void {
    const next: Decision = { id: d.id, action, enabled: d.enabled, description: d.description };
    if (action === 'edit' || action === 'exclude') next.apply_to = 'one';
    else
      Object.assign(next, {
        account_id: d.account_id,
        amount: d.amount ?? '',
        due_on: d.due_on ?? this.context()?.today,
        repeat: 'once',
      });
    this.editVariant({
      decisions: this.active().decisions.map((item) => (item.id === d.id ? next : item)),
    });
  }
  protected choosePlan(d: Decision, value: string): void {
    const plan = this.context()?.plans.find((p) => p.id === value);
    this.updateDecision(d.id, {
      occurrence_id: value,
      version: plan?.version,
      ...(d.action === 'edit' ? { amount: plan?.amount, due_on: plan?.due_on } : {}),
    });
  }
  protected removeDecision(key: string): void {
    this.editVariant({ decisions: this.active().decisions.filter((d) => d.id !== key) });
  }
  protected copyDecision(d: Decision): void {
    if (this.active().decisions.length < 50)
      this.editVariant({
        decisions: [...this.active().decisions, { ...structuredClone(d), id: id() }],
      });
  }
  protected categoryOptions(type: string) {
    return (this.context()?.categories ?? [])
      .filter((c) => !c.archived && c.type === type)
      .map((c) => ({ id: c.id, label: c.name }));
  }
  protected addCost(): void {
    if (this.draft().living_costs.length < 10)
      this.edit({
        living_costs: [
          ...this.draft().living_costs,
          {
            id: id(),
            account_id: this.draft().scope_account_id ?? '',
            category_id: '',
            mode: 'manual',
            monthly_amount: '',
            excluded_operation_ids: [],
          },
        ],
      });
  }
  protected updateCost(key: string, patch: Partial<LivingCost>): void {
    this.edit({
      living_costs: this.draft().living_costs.map((c) => (c.id === key ? { ...c, ...patch } : c)),
    });
  }
  protected removeCost(key: string): void {
    this.edit({ living_costs: this.draft().living_costs.filter((c) => c.id !== key) });
  }
  protected costHistory(cost: LivingCost) {
    return (this.context()?.history ?? []).filter(
      (f) => f.account_id === cost.account_id && f.category_id === cost.category_id,
    );
  }
  protected historySlice(cost: LivingCost) {
    return this.costHistory(cost).slice(this.historyPage() * 30, this.historyPage() * 30 + 30);
  }
  protected toggleExcluded(cost: LivingCost, factId: string): void {
    this.updateCost(cost.id, {
      excluded_operation_ids: cost.excluded_operation_ids.includes(factId)
        ? cost.excluded_operation_ids.filter((v) => v !== factId)
        : [...cost.excluded_operation_ids, factId],
    });
  }
  protected categoryName(value: string): string {
    return (
      this.context()?.categories.find((c) => c.id === value)?.name ??
      t('workbench.missingReference')
    );
  }
  protected accountName(value: string): string {
    return (
      this.context()?.accounts.find((a) => a.id === value)?.name ?? t('workbench.missingReference')
    );
  }
  protected fundName(value: string): string {
    return (
      this.context()?.funds.find((f) => f.id === value)?.name ?? t('workbench.missingReference')
    );
  }
  protected typeLabel(value: string): string {
    return value === 'income'
      ? t('oracle.income')
      : value === 'transfer'
        ? t('oracle.transfer')
        : value === 'edit'
          ? t('workbench.editPlan')
          : value === 'exclude'
            ? t('workbench.excludePlan')
            : t('oracle.expense');
  }
  protected repeatLabel(value: string): string {
    const keys = {
      once: 'workbench.once',
      daily: 'workbench.daily',
      weekly: 'workbench.weekly',
      monthly: 'workbench.monthly',
      yearly: 'workbench.yearly',
    } as const;
    return t(keys[value as keyof typeof keys]);
  }
  protected horizonLabel(value: ForecastHorizon): string {
    const keys = {
      two_weeks: 'forecast.2Weeks',
      month: 'forecast.month',
      quarter: 'forecast.quarter',
      half_year: 'forecast.halfYear',
      year: 'forecast.year',
    } as const;
    return t(keys[value]);
  }
  protected refresh(): void {
    this.invalidate();
    const seq = this.sequence;
    this.loading.set(true);
    this.http
      .get<WorkspaceContext>(`${environment.apiBaseUrl}/scenarios/workspace-context`)
      .subscribe({
        next: (ctx) => {
          if (!this.alive || seq !== this.sequence) return;
          this.context.set(ctx);
          this.refreshRequired.set(false);
          if (!this.draft().snapshot_id)
            this.draft.update((d) => ({ ...d, snapshot_id: ctx.snapshot_id }));
          this.loading.set(false);
        },
        error: (e) => {
          if (!this.alive || seq !== this.sequence) return;
          this.loading.set(false);
          this.fail(e);
        },
      });
  }
  protected adoptSources(): void {
    const ctx = this.context();
    if (!ctx || this.refreshRequired()) return;
    this.edit({
      snapshot_id: ctx.snapshot_id,
      variants: this.draft().variants.map((v) => ({
        ...v,
        decisions: v.decisions.map((d) => {
          const source = ctx.plans.find((p) => p.id === d.occurrence_id);
          return source ? { ...d, version: source.version } : d;
        }),
      })),
    });
  }
  private payload(): Workspace | null {
    const value = structuredClone(this.draft());
    value.stop_loss = decimalPayload(value.stop_loss || '0');
    const money = (amount: string | undefined, positive = true) =>
      !!amount &&
      /^\d{1,16}(?:\.\d{1,4})?$/.test(amount) &&
      compareDecimal(amount, '0') >= (positive ? 1 : 0);
    let bad = !money(value.stop_loss, false);
    for (const v of value.variants) {
      v.expense_increase_percent = decimalPayload(v.expense_increase_percent || '0');
      bad ||=
        !v.name.trim() ||
        !money(v.expense_increase_percent, false) ||
        compareDecimal(v.expense_increase_percent, '100') > 0 ||
        !Number.isInteger(v.income_delay_days) ||
        v.income_delay_days < 0 ||
        v.income_delay_days > 90;
      for (const d of v.decisions) {
        if (d.amount !== undefined) d.amount = decimalPayload(d.amount);
        const changed = d.action === 'edit' || d.action === 'exclude';
        bad ||= changed
          ? !d.occurrence_id || !d.version
          : !d.account_id || !money(d.amount) || !d.due_on;
        if (d.action === 'edit') bad ||= !money(d.amount) || !d.due_on;
        if (d.action === 'transfer')
          bad ||= !d.destination_account_id || d.destination_account_id === d.account_id;
        if (d.due_on)
          bad ||=
            d.due_on < (this.context()?.today ?? '') ||
            d.due_on > (this.context()?.maximum_on ?? '');
        if (d.repeat && d.repeat !== 'once')
          bad ||=
            !d.repeat_until ||
            d.repeat_until < (d.due_on ?? '') ||
            d.repeat_until > (this.context()?.maximum_on ?? '');
      }
    }
    for (const c of value.living_costs) {
      if (c.mode === 'manual') {
        c.monthly_amount = decimalPayload(c.monthly_amount ?? '');
        bad ||= !money(c.monthly_amount, false);
      } else delete c.monthly_amount;
      bad ||= !c.account_id || !c.category_id;
    }
    if (bad) {
      this.error.set(() => t('workbench.validation'));
      this.host.nativeElement
        .querySelector<HTMLElement>('input:invalid, select:invalid, .form-error')
        ?.focus();
      return null;
    }
    return value;
  }
  protected calculate(): void {
    if (this.loading() || this.busy() || this.stale()) return;
    const payload = this.payload();
    if (!payload) return;
    this.invalidate();
    this.busy.set(true);
    const seq = this.sequence;
    this.http
      .post<WorkspaceResult>(`${environment.apiBaseUrl}/scenarios/workspaces/compare`, payload)
      .subscribe({
        next: (result) => {
          if (!this.alive || seq !== this.sequence) return;
          this.result.set(result);
          this.busy.set(false);
        },
        error: (e) => {
          if (!this.alive || seq !== this.sequence) return;
          this.busy.set(false);
          this.fail(e);
        },
      });
  }
  protected solve(): void {
    const workspace = this.payload();
    if (!workspace || this.busy() || this.stale()) return;
    if (
      !this.solveDecision() ||
      (this.objective() === 'maximum_amount' &&
        (!/^\d{1,16}(?:\.\d{1,4})?$/.test(decimalPayload(this.ceiling())) ||
          compareDecimal(decimalPayload(this.ceiling()), '0') <= 0))
    ) {
      this.error.set(() => t('workbench.solverValidation'));
      return;
    }
    this.solution.set(null);
    this.busy.set(true);
    const seq = ++this.sequence;
    this.http
      .post<SolveResult>(`${environment.apiBaseUrl}/scenarios/workspaces/solve`, {
        workspace,
        variant_id: this.active().id,
        decision_id: this.solveDecision(),
        objective: this.objective(),
        ...(this.objective() === 'maximum_amount'
          ? { maximum_amount: decimalPayload(this.ceiling()) }
          : {}),
      })
      .subscribe({
        next: (value) => {
          if (!this.alive || seq !== this.sequence) return;
          this.solution.set(value);
          this.busy.set(false);
        },
        error: (e) => {
          if (!this.alive || seq !== this.sequence) return;
          this.busy.set(false);
          this.fail(e);
        },
      });
  }
  protected applySolution(): void {
    const value = this.solution();
    if (value?.status !== 'found' || !value.amount || !value.due_on) return;
    this.updateDecision(this.solveDecision(), { amount: value.amount, due_on: value.due_on });
    this.calculate();
  }
  protected reloadSaved(): void {
    this.http.get<SavedWorkspace[]>(`${environment.apiBaseUrl}/scenarios/saved`).subscribe({
      next: (values) => {
        if (this.alive) this.saved.set(values);
      },
      error: (e) => {
        if (this.alive) this.fail(e);
      },
    });
  }
  protected save(copy = false): void {
    if (this.saving()) return;
    const workspace = this.payload();
    if (!workspace || !this.name().trim()) {
      this.error.set(() => t('workbench.validation'));
      return;
    }
    this.saving.set(true);
    const savedId = copy ? '' : this.savedId();
    const body = { name: this.name(), workspace, version: savedId ? this.savedVersion() : null };
    const call = savedId
      ? this.http.put<SavedWorkspace>(`${environment.apiBaseUrl}/scenarios/saved/${savedId}`, body)
      : this.http.post<SavedWorkspace>(`${environment.apiBaseUrl}/scenarios/saved`, body);
    call.subscribe({
      next: (value) => {
        if (!this.alive) return;
        this.saving.set(false);
        this.savedId.set(value.id);
        this.savedVersion.set(value.version);
        this.dirty.set(false);
        this.notice.set(() => t('workbench.savedNotice'));
        this.reloadSaved();
      },
      error: (e) => {
        if (!this.alive) return;
        this.saving.set(false);
        this.fail(e);
      },
    });
  }
  protected requestOpen(value: SavedWorkspace): void {
    if (this.dirty()) this.pendingOpen.set(value);
    else this.open(value);
  }
  protected open(value: SavedWorkspace): void {
    this.invalidate();
    this.draft.set(structuredClone(value.workspace));
    this.activeId.set(value.workspace.variants[0].id);
    this.savedId.set(value.id);
    this.savedVersion.set(value.version);
    this.name.set(value.name);
    this.dirty.set(false);
    this.pendingOpen.set(null);
  }
  protected removeSaved(value: SavedWorkspace): void {
    this.saving.set(true);
    this.http
      .delete(`${environment.apiBaseUrl}/scenarios/saved/${value.id}`, {
        params: { version: value.version },
      })
      .subscribe({
        next: () => {
          if (!this.alive) return;
          this.saving.set(false);
          this.pendingDelete.set('');
          if (this.savedId() === value.id) {
            this.savedId.set('');
            this.savedVersion.set(null);
            this.dirty.set(true);
          }
          this.reloadSaved();
        },
        error: (e) => {
          if (!this.alive) return;
          this.saving.set(false);
          this.fail(e);
        },
      });
  }
  private fail(error: unknown): void {
    this.error.set(() => apiErrorMessage(error, t('oracle.calculateError')));
    if (
      error instanceof HttpErrorResponse &&
      error.status === 409 &&
      ['scenario_stale', 'scenario_source'].includes(error.error?.detail?.code)
    ) {
      this.refreshRequired.set(true);
      this.draft.update((d) => ({ ...d, snapshot_id: '0'.repeat(64) }));
    }
  }
}
