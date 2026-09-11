import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { language } from '../../i18n/i18n';
import { ScenariosPage } from './scenarios';
import { Comparison, ScenarioContext, comparisonChart } from './scenario-model';

const context: ScenarioContext = {
  snapshot_id: 'a'.repeat(64),
  today: '2026-09-11',
  maximum_on: '2027-09-11',
  currency: 'RUB',
  accounts: [{ id: 'main', name: 'Main', archived: false }],
  overdue_excluded_count: 0,
  plans: [
    {
      id: 'plan',
      version: 3,
      amount: '100.0001',
      due_on: '2026-09-15',
      type: 'expense',
      description: 'Rent',
      account_id: 'main',
      account_name: 'Main',
      destination_account_id: null,
      destination_account_name: null,
      allocate_to_funds: false,
    },
  ],
};
function response(): Comparison {
  const data = {
    balance_mode: 'free' as const,
    scope: 'all' as const,
    account_id: null,
    account_name: null,
    horizon: 'month' as const,
    granularity: 'day' as const,
    from_on: context.today,
    through_on: '2026-10-11',
    starting_balance: '1000.0001',
    ending_balance: '1000.0001',
    minimum_balance: '1000.0001',
    minimum_on: context.today,
    first_negative_on: null,
    first_negative_balance: null,
    expected_income: '0',
    expected_expense: '0',
    overdue_excluded_count: 0,
    points: [
      {
        period_from: context.today,
        on: context.today,
        opening_balance: '1000.0001',
        change: '0',
        closing_balance: '1000.0001',
        events: [],
      },
    ],
  };
  const branch = {
    free: data,
    total: data,
    zero_risk: { threshold: '0', windows: [] },
    stop_loss_risk: null,
    suggested_risk: null,
  };
  return {
    snapshot_id: context.snapshot_id,
    currency: 'RUB',
    baseline: branch,
    alternative: {
      ...branch,
      free: {
        ...data,
        ending_balance: '-0.0001',
        minimum_balance: '-0.0001',
        points: [
          {
            ...data.points[0],
            change: '-1000.0002',
            closing_balance: '-0.0001',
            events: [
              {
                occurrence_id: 'synthetic',
                origin: 'scenario',
                due_on: context.today,
                type: 'expense',
                status: 'pending',
                description: null,
                account_name: 'Main',
                destination_account_name: null,
                amount: '1000.0002',
                effect: '-1000.0002',
              },
            ],
          },
        ],
      },
    },
    ending_free_delta: '-1000.0002',
    minimum_free_delta: '-1000.0002',
    ending_total_delta: '-1000.0002',
    suggested_boundary: null,
    reserve: { starting: '0', baseline: '0', alternative: '0', delta: '0' },
    funds: [],
    events: [],
    assumptions: ['materialized_plans_only'],
  };
}

describe('Oracle scenario flow', () => {
  let fixture: ComponentFixture<ScenariosPage>;
  let http: HttpTestingController;
  beforeEach(async () => {
    language.set('ru');
    await TestBed.configureTestingModule({
      imports: [ScenariosPage],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();
    fixture = TestBed.createComponent(ScenariosPage);
    http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
    http.expectOne('/api/v1/scenarios/context').flush(context);
    fixture.detectChanges();
    await fixture.whenStable();
  });
  afterEach(() => {
    http.verify();
    language.set('ru');
  });
  async function input(name: string, value: string) {
    const field = fixture.nativeElement.querySelector(`[name="${name}"]`) as HTMLInputElement;
    field.value = value;
    field.dispatchEvent(new Event(field.tagName === 'SELECT' ? 'change' : 'input'));
    fixture.detectChanges();
    await fixture.whenStable();
  }
  async function account() {
    const field = fixture.nativeElement.querySelector('#oracle-account') as HTMLInputElement;
    field.dispatchEvent(new Event('focus'));
    field.value = field.id === 'oracle-plan' ? 'Rent' : 'Main';
    field.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    const option = Array.from(
      fixture.nativeElement.querySelectorAll('[role="option"]') as NodeListOf<HTMLElement>,
    ).find((node) => node.textContent?.includes('Main'))!;
    option.click();
    fixture.detectChanges();
    await fixture.whenStable();
  }
  function submit() {
    fixture.nativeElement
      .querySelector('form')
      .dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    fixture.detectChanges();
  }
  async function ready() {
    await account();
    await input('amount', '1 000,0002');
  }

  it('reads sources without materializing or creating a plan', () => {
    http.expectNone('/api/v1/scheduling/materialize');
    expect(fixture.nativeElement.textContent).toContain('Oracle не достраивает календарь');
    expect(fixture.nativeElement.querySelector('[name="date"]').value).toBe(context.today);
  });
  it('submits exact strings and renders before/after with a synthetic source label', async () => {
    await ready();
    submit();
    const request = http.expectOne('/api/v1/scenarios/compare');
    expect(request.request.body.amount).toBe('1000.0002');
    expect(request.request.body.snapshot_id).toBe(context.snapshot_id);
    expect(request.request.body.account_id).toBe('main');
    request.flush(response());
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('1 000,00 ₽');
    expect(fixture.nativeElement.textContent).toContain('С гипотезой');
    expect(fixture.nativeElement.querySelector('svg[role="img"]')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('.comparison-chart a')).toBeNull();
  });
  it('validates a missing account without sending a request', async () => {
    await input('amount', '10');
    submit();
    http.expectNone('/api/v1/scenarios/compare');
    expect(fixture.nativeElement.querySelector('[role="alert"]').textContent).toContain(
      'Проверьте',
    );
  });
  it('preserves inputs across source conflicts and requires an explicit retry', async () => {
    await ready();
    submit();
    http
      .expectOne('/api/v1/scenarios/compare')
      .flush({ detail: { code: 'scenario_stale' } }, { status: 409, statusText: 'Conflict' });
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[type="submit"]').disabled).toBe(true);
    expect(fixture.nativeElement.textContent).toContain('Исходные данные изменились');
    fixture.nativeElement.querySelector('.source-actions button').click();
    fixture.detectChanges();
    http.expectOne('/api/v1/scenarios/context').flush({ ...context, snapshot_id: 'b'.repeat(64) });
    fixture.detectChanges();
    submit();
    const request = http.expectOne('/api/v1/scenarios/compare');
    expect(request.request.body.snapshot_id).toBe('b'.repeat(64));
    expect(request.request.body.amount).toBe('1000.0002');
    request.flush(response());
  });
  it('discards a pending result and ignores its late response', async () => {
    await ready();
    submit();
    const request = http.expectOne('/api/v1/scenarios/compare');
    fixture.nativeElement.querySelector('.actions .secondary').click();
    fixture.detectChanges();
    request.flush(response());
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.answer')).toBeNull();
    await fixture.whenStable();
    expect(fixture.nativeElement.querySelector('[name="amount"]').value).toBe('');
    http.expectNone('/api/v1/scenarios/save');
  });
  it('clears results after changing controls and retains exact input across RU/EN', async () => {
    await ready();
    submit();
    http.expectOne('/api/v1/scenarios/compare').flush(response());
    fixture.detectChanges();
    language.set('en');
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('With hypothesis');
    expect(fixture.nativeElement.querySelector('[name="amount"]').value).toContain('000');
    await input('amount', '10.0001');
    expect(fixture.nativeElement.querySelector('.answer')).toBeNull();
    submit();
    const request = http.expectOne('/api/v1/scenarios/compare');
    expect(request.request.body.amount).toBe('10.0001');
    request.flush(response());
  });
  it('sends the selected occurrence version and only the changed date', async () => {
    await input('action', 'move');
    const field = fixture.nativeElement.querySelector('#oracle-plan') as HTMLInputElement;
    field.dispatchEvent(new Event('focus'));
    field.value = field.id === 'oracle-plan' ? 'Rent' : 'Main';
    field.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    (fixture.nativeElement.querySelector('[role="option"]') as HTMLElement).click();
    fixture.detectChanges();
    await fixture.whenStable();
    await input('date', '2026-10-10');
    submit();
    const request = http.expectOne('/api/v1/scenarios/compare');
    expect(request.request.body.occurrence_id).toBe('plan');
    expect(request.request.body.version).toBe(3);
    expect(request.request.body.due_on).toBe('2026-10-10');
    expect(request.request.body.amount).toBeUndefined();
    expect(request.request.body.account_id).toBeUndefined();
    request.flush(response());
  });
  it('preserves user inputs on a network error', async () => {
    await ready();
    submit();
    http.expectOne('/api/v1/scenarios/compare').error(new ProgressEvent('error'));
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[name="amount"]').value).not.toBe('');
    expect(fixture.nativeElement.querySelector('[type="submit"]').disabled).toBe(false);
  });
});

describe('Oracle comparison chart', () => {
  it('uses finite coordinates while preserving the exact financial values', () => {
    const result = response();
    result.baseline.free.starting_balance = '9999999999999999.9999';
    const original = JSON.stringify(result);
    const chart = comparisonChart(result, '100');
    expect(chart.baseline).not.toMatch(/NaN|Infinity/);
    expect(chart.alternative).not.toMatch(/NaN|Infinity/);
    expect(JSON.stringify(result)).toBe(original);
    expect(chart.high).toBe('9999999999999999.9999');
  });
});
