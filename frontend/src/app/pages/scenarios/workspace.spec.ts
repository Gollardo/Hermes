import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { language } from '../../i18n/i18n';
import { WorkspacePage } from './workspace';
import { SavedWorkspace, WorkspaceContext } from './workspace-model';

const context: WorkspaceContext = {
  snapshot_id: 'a'.repeat(64),
  today: '2026-09-13',
  maximum_on: '2027-09-13',
  currency: 'RUB',
  accounts: [
    { id: 'main', name: 'Main', archived: false },
    { id: 'savings', name: 'Savings', archived: false },
  ],
  plans: [
    {
      id: 'rent',
      version: 1,
      amount: '100.0001',
      due_on: '2026-09-15',
      type: 'expense',
      description: 'Rent',
      account_id: 'main',
      account_name: 'Main',
      destination_account_id: null,
      destination_account_name: null,
      allocate_to_funds: false,
      category_id: 'living',
      rule_id: 'rule',
      origin: 'plan',
    },
  ],
  categories: [{ id: 'living', name: 'Living', type: 'expense', archived: false }],
  funds: [],
  source_policy: 'complete_read_only_schedule',
  overdue_excluded_count: 0,
  history_from: '2026-03-01',
  history_through: '2026-09-12',
  history: [],
};

describe('Oracle decision workspace', () => {
  let fixture: ComponentFixture<WorkspacePage>;
  let page: WorkspacePage;
  let http: HttpTestingController;
  beforeEach(async () => {
    language.set('ru');
    await TestBed.configureTestingModule({
      imports: [WorkspacePage],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();
    fixture = TestBed.createComponent(WorkspacePage);
    page = fixture.componentInstance;
    http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
    http.expectOne('/api/v1/scenarios/workspace-context').flush(context);
    http.expectOne('/api/v1/scenarios/saved').flush([]);
    fixture.detectChanges();
  });
  afterEach(() => {
    http.verify();
    language.set('ru');
  });
  function expense(amount = '10'): void {
    page['addDecision']();
    const decision = page['active']().decisions.at(-1)!;
    page['updateDecision'](decision.id, { account_id: 'main', amount });
    fixture.detectChanges();
  }
  function saved(): SavedWorkspace {
    return {
      id: 'saved',
      name: 'Moving',
      version: 1,
      workspace: structuredClone(page['draft']()),
      created_at: '',
      updated_at: '',
    };
  }

  it('opens complete read-only sources without guessing everyday spending or materializing plans', () => {
    http.expectNone('/api/v1/scheduling/materialize');
    expect(page['draft']().living_costs).toEqual([]);
    expect(fixture.nativeElement.textContent).toContain(
      'Незапланированные расходы пока не учитываются',
    );
  });
  it('submits multiple operation types and recurring exact amounts in one comparison', () => {
    expense('1 000,0001');
    expense('2.0001');
    const second = page['active']().decisions[1];
    page['changeAction'](second, 'transfer');
    page['updateDecision'](second.id, {
      account_id: 'main',
      destination_account_id: 'savings',
      amount: '2.0001',
      repeat: 'weekly',
      repeat_until: '2026-10-01',
    });
    page['calculate']();
    const request = http.expectOne('/api/v1/scenarios/workspaces/compare');
    expect(request.request.body.variants[0].decisions[0].amount).toBe('1000.0001');
    expect(request.request.body.variants[0].decisions[1].action).toBe('transfer');
    expect(request.request.body.variants[0].decisions[1].repeat).toBe('weekly');
    request.flush({ snapshot_id: context.snapshot_id, variants: [], baseline_estimates: [] });
  });
  it('does not submit incomplete rows and preserves input', () => {
    page['addDecision']();
    page['calculate']();
    fixture.detectChanges();
    http.expectNone('/api/v1/scenarios/workspaces/compare');
    expect(fixture.nativeElement.querySelector('[role="alert"]').textContent).toContain(
      'Проверьте',
    );
    expect(page['active']().decisions).toHaveLength(1);
  });
  it('copies decision sets independently and retains decimals across language changes', () => {
    expense('9 999,0001');
    const original = page['active']().id;
    page['addVariant'](true);
    page['updateDecision'](page['active']().decisions[0].id, { amount: '123.0001' });
    language.set('en');
    fixture.detectChanges();
    expect(page['draft']().variants.find((v) => v.id === original)!.decisions[0].amount).toBe(
      '9 999,0001',
    );
    expect(page['active']().decisions[0].amount).toBe('123.0001');
  });
  it('submits living-cost assumptions and exclusions separately from financial decisions', () => {
    page['addCost']();
    const cost = page['draft']().living_costs[0];
    page['updateCost'](cost.id, {
      account_id: 'main',
      category_id: 'living',
      mode: 'history',
      monthly_amount: undefined,
      excluded_operation_ids: ['one-off'],
    });
    page['calculate']();
    const request = http.expectOne('/api/v1/scenarios/workspaces/compare');
    expect(request.request.body.living_costs[0].mode).toBe('history');
    expect(request.request.body.living_costs[0].monthly_amount).toBeUndefined();
    expect(request.request.body.living_costs[0].excluded_operation_ids).toEqual(['one-off']);
    request.flush(
      { detail: { code: 'scenario_history_insufficient' } },
      { status: 422, statusText: 'Invalid' },
    );
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('задайте месячную оценку вручную');
    expect(page['draft']().living_costs).toHaveLength(1);
  });
  it('requires explicit source review while retaining edits after a source conflict', () => {
    page['addDecision']();
    const d = page['active']().decisions[0];
    page['changeAction'](d, 'edit');
    page['choosePlan']({ ...d, action: 'edit' }, 'rent');
    page['updateDecision'](d.id, { amount: '150.0001' });
    page['calculate']();
    http
      .expectOne('/api/v1/scenarios/workspaces/compare')
      .flush({ detail: { code: 'scenario_stale' } }, { status: 409, statusText: 'Conflict' });
    expect(page['refreshRequired']()).toBe(true);
    page['adoptSources']();
    expect(page['stale']()).toBe(true);
    expect(page['draft']().snapshot_id).not.toBe(context.snapshot_id);
    page['refresh']();
    http.expectOne('/api/v1/scenarios/workspace-context').flush({
      ...context,
      snapshot_id: 'b'.repeat(64),
      plans: [{ ...context.plans[0], version: 2, amount: '200' }],
    });
    expect(page['stale']()).toBe(true);
    expect(page['refreshRequired']()).toBe(false);
    expect(page['active']().decisions[0].version).toBe(1);
    page['adoptSources']();
    expect(page['active']().decisions[0].version).toBe(2);
    expect(page['active']().decisions[0].amount).toBe('150.0001');
    expect(page['stale']()).toBe(false);
  });
  it('preserves the draft on save conflicts and offers saving as a separate scenario', () => {
    expense('9.0001');
    const entry = saved();
    page['open'](entry);
    page['name'].set('Changed');
    page['save']();
    const update = http.expectOne('/api/v1/scenarios/saved/saved');
    expect(update.request.body.version).toBe(1);
    update.flush(
      { detail: { code: 'scenario_saved_conflict' } },
      { status: 409, statusText: 'Conflict' },
    );
    expect(page['active']().decisions[0].amount).toBe('9.0001');
    expect(page['stale']()).toBe(false);
    page['save'](true);
    const create = http.expectOne('/api/v1/scenarios/saved');
    expect(create.request.body.version).toBeNull();
    create.flush({ ...entry, id: 'copy' });
    http.expectOne('/api/v1/scenarios/saved').flush([{ ...entry, id: 'copy' }]);
    expect(page['savedId']()).toBe('copy');
  });
  it('does not replace a dirty draft until the explicit open action', () => {
    expense();
    const entry = saved();
    expense('50');
    page['requestOpen'](entry);
    expect(page['active']().decisions).toHaveLength(2);
    expect(page['pendingOpen']()).not.toBeNull();
    page['open'](entry);
    expect(page['active']().decisions).toHaveLength(1);
  });
  it('applies solver results only explicitly and recalculates the entire workspace', () => {
    expense('10');
    const d = page['active']().decisions[0];
    page['solveDecision'].set(d.id);
    page['ceiling'].set('100,0001');
    page['solve']();
    const request = http.expectOne('/api/v1/scenarios/workspaces/solve');
    expect(request.request.body.maximum_amount).toBe('100.0001');
    request.flush({
      status: 'found',
      amount: '70.0001',
      due_on: context.today,
      evaluated: 20,
      result: null,
    });
    expect(page['active']().decisions[0].amount).toBe('10');
    page['applySolution']();
    const comparison = http.expectOne('/api/v1/scenarios/workspaces/compare');
    expect(comparison.request.body.variants[0].decisions[0].amount).toBe('70.0001');
    comparison.flush({ snapshot_id: context.snapshot_id, variants: [], baseline_estimates: [] });
  });
  it('ignores results arriving after input changes or leaving the page', () => {
    expense();
    page['calculate']();
    const request = http.expectOne('/api/v1/scenarios/workspaces/compare');
    page['edit']({ stop_loss: '100' });
    request.flush({ snapshot_id: context.snapshot_id, variants: [], baseline_estimates: [] });
    expect(page['result']()).toBeNull();
    page['calculate']();
    const late = http.expectOne('/api/v1/scenarios/workspaces/compare');
    fixture.destroy();
    late.flush({ snapshot_id: context.snapshot_id, variants: [], baseline_estimates: [] });
    expect(page['result']()).toBeNull();
  });
});
