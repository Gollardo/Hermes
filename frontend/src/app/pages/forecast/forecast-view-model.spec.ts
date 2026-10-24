import {
  ForecastBalanceMode,
  ForecastDataset,
  ForecastPoint,
  addDecimal,
  buildForecastViewModel,
  forecastDetailForDate,
  subtractDecimal,
} from './forecast-view-model';

const DATES = ['2026-08-15', '2026-08-16', '2026-08-17', '2026-08-18'];

describe('buildForecastViewModel', () => {
  it('derives minimum, end, safe-to-spend and flows for a positive forecast', () => {
    const viewModel = buildForecastViewModel(
      dataset(['20000', '18000', '12000', '25000'], {
        expectedIncome: '13000',
        expectedExpense: '8000',
      }),
    );

    expect(viewModel.metrics.currentBalance).toBe('20000');
    expect(viewModel.metrics.minimumBalance).toBe('12000');
    expect(viewModel.metrics.minimumBalanceDate).toBe('2026-08-17');
    expect(viewModel.metrics.forecastEndBalance).toBe('25000');
    expect(viewModel.metrics.safeToSpend).toBe('12000');
    expect(viewModel.metrics.hasCashGap).toBe(false);
    expect(viewModel.metrics.firstNegativeBalance).toBeNull();
    expect(viewModel.metrics.firstNegativeBalanceDate).toBeNull();
    expect(viewModel.metrics.totalPlannedIncome).toBe('13000');
    expect(viewModel.metrics.totalPlannedExpense).toBe('8000');
    expect(viewModel.metrics.netPlannedFlow).toBe('5000');
  });

  it('returns zero safe-to-spend and the first cash gap for a negative forecast', () => {
    const viewModel = buildForecastViewModel(
      dataset(['20000', '8000', '-2000', '15000'], {
        expectedIncome: '17000',
        expectedExpense: '22000',
      }),
    );

    expect(viewModel.metrics.minimumBalance).toBe('-2000');
    expect(viewModel.metrics.minimumBalanceDate).toBe('2026-08-17');
    expect(viewModel.metrics.safeToSpend).toBe('0');
    expect(viewModel.metrics.hasCashGap).toBe(true);
    expect(viewModel.metrics.firstNegativeBalance).toBe('-2000');
    expect(viewModel.metrics.firstNegativeBalanceDate).toBe('2026-08-17');
  });

  it('subtracts the exact minimum balance buffer and hides its breach behind a cash gap', () => {
    const buffered = dataset(['50000', '42000']);
    buffered.minimum_balance_buffer = '30000.0000';
    buffered.buffer_breach_on = null;
    expect(buildForecastViewModel(buffered).metrics.safeToSpend).toBe('12000.0000');

    const cashGap = dataset(['50000', '-10']);
    cashGap.minimum_balance_buffer = '30000.0000';
    cashGap.buffer_breach_on = null;
    expect(buildForecastViewModel(cashGap).metrics.bufferBreachDate).toBeNull();
  });

  it('keeps the first date across several consecutive negative days', () => {
    const viewModel = buildForecastViewModel(dataset(['1000', '-100', '-500', '-200']));

    expect(viewModel.metrics.minimumBalance).toBe('-500');
    expect(viewModel.metrics.minimumBalanceDate).toBe('2026-08-17');
    expect(viewModel.metrics.firstNegativeBalance).toBe('-100');
    expect(viewModel.metrics.firstNegativeBalanceDate).toBe('2026-08-16');
  });

  it('treats zero as a minimum without reporting a cash gap', () => {
    const viewModel = buildForecastViewModel(dataset(['1000', '0', '500']));

    expect(viewModel.metrics.minimumBalance).toBe('0');
    expect(viewModel.metrics.safeToSpend).toBe('0');
    expect(viewModel.metrics.hasCashGap).toBe(false);
  });

  it('uses exact backend risk metrics for monthly aggregated points', () => {
    const value = dataset(['20000', '15000'], { mode: 'total' });
    value.granularity = 'month';
    value.horizon = 'year';
    value.minimum_balance = '-2500.5000';
    value.minimum_on = '2026-08-20';
    value.first_negative_on = '2026-08-20';
    value.first_negative_balance = '-350.2500';

    const viewModel = buildForecastViewModel(value);

    expect(viewModel.metrics.minimumBalance).toBe('-2500.5000');
    expect(viewModel.metrics.minimumBalanceDate).toBe('2026-08-20');
    expect(viewModel.metrics.firstNegativeBalance).toBe('-350.2500');
    expect(viewModel.metrics.firstNegativeBalanceDate).toBe('2026-08-20');
  });

  it('keeps free and total modes tied to their own forecast snapshot', () => {
    const free = buildForecastViewModel(dataset(['7000', '5000'], { mode: 'free' }));
    const total = buildForecastViewModel(dataset(['10000', '8000'], { mode: 'total' }));

    expect(free.dataset.balance_mode).toBe('free');
    expect(free.metrics.safeToSpend).toBe('5000');
    expect(total.dataset.balance_mode).toBe('total');
    expect(total.metrics.safeToSpend).toBe('8000');
  });

  it('reconciles single-account transfers with the total net flow', () => {
    const value = dataset(['10000', '7500']);
    value.scope = 'account';
    value.points[1].events = [
      {
        occurrence_id: 'transfer-1',
        due_on: DATES[1],
        type: 'transfer',
        status: 'pending',
        description: 'В накопления',
        account_name: 'Основной',
        destination_account_name: 'Накопительный',
        amount: '2500.0000',
        effect: '-2500.0000',
      },
    ];

    const viewModel = buildForecastViewModel(value);

    expect(viewModel.metrics.totalPlannedIncome).toBe('0');
    expect(viewModel.metrics.totalPlannedExpense).toBe('0');
    expect(viewModel.metrics.netPlannedTransferFlow).toBe('-2500.0000');
    expect(viewModel.metrics.netPlannedFlow).toBe('-2500');
  });

  it('reconstructs exact day details inside a monthly interval', () => {
    const value = dataset(['8000']);
    value.granularity = 'month';
    value.horizon = 'year';
    value.points[0] = {
      period_from: '2026-08-15',
      on: '2026-08-31',
      opening_balance: '20000.0000',
      change: '-12000.0000',
      closing_balance: '8000.0000',
      events: [
        {
          occurrence_id: 'expense-1',
          due_on: '2026-08-20',
          type: 'expense',
          status: 'pending',
          description: 'Кредит',
          account_name: 'Основной',
          destination_account_name: null,
          amount: '22000.0000',
          effect: '-22000.0000',
        },
        {
          occurrence_id: 'income-1',
          due_on: '2026-08-25',
          type: 'income',
          status: 'pending',
          description: 'Возврат',
          account_name: 'Основной',
          destination_account_name: null,
          amount: '10000.0000',
          effect: '10000.0000',
        },
      ],
    };

    const detail = forecastDetailForDate(value, '2026-08-20');

    expect(detail?.opening_balance).toBe('20000.0000');
    expect(detail?.change).toBe('-22000.0000');
    expect(detail?.closing_balance).toBe('-2000.0000');
    expect(detail?.events.map((event) => event.occurrence_id)).toEqual(['expense-1']);
  });

  it('keeps decimal arithmetic exact beyond the safe Number range', () => {
    expect(addDecimal('9007199254740993.1250', '0.8750')).toBe('9007199254740994.0000');
    expect(subtractDecimal('9007199254740994.0000', '0.8750')).toBe('9007199254740993.1250');
  });
});

function dataset(
  balances: string[],
  options: {
    expectedIncome?: string;
    expectedExpense?: string;
    mode?: ForecastBalanceMode;
  } = {},
): ForecastDataset {
  const points = balances.map<ForecastPoint>((balance, index) => ({
    period_from: DATES[index],
    on: DATES[index],
    opening_balance: index === 0 ? balance : balances[index - 1],
    change: index === 0 ? '0' : difference(balance, balances[index - 1]),
    closing_balance: balance,
    events: [],
  }));
  return {
    balance_mode: options.mode ?? 'free',
    scope: 'all',
    account_id: null,
    account_name: null,
    horizon: 'month',
    granularity: 'day',
    from_on: DATES[0],
    through_on: DATES[balances.length - 1],
    starting_balance: balances[0],
    ending_balance: balances.at(-1)!,
    minimum_balance: '0',
    minimum_on: DATES[0],
    first_negative_on: null,
    first_negative_balance: null,
    expected_income: options.expectedIncome ?? '0',
    expected_expense: options.expectedExpense ?? '0',
    overdue_excluded_count: 0,
    points,
  };
}

function difference(left: string, right: string): string {
  return (Number(left) - Number(right)).toString();
}
