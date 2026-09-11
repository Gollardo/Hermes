export type ForecastHorizon = 'two_weeks' | 'month' | 'quarter' | 'half_year' | 'year';
export type ForecastBalanceMode = 'free' | 'total';
export type ForecastOperationType = 'income' | 'expense' | 'transfer';

export interface ForecastEvent {
  origin?: 'plan' | 'scenario';
  occurrence_id: string;
  due_on: string;
  type: ForecastOperationType;
  status: 'pending' | 'postponed';
  description: string | null;
  account_name: string;
  destination_account_name: string | null;
  amount: string;
  effect: string;
}

export interface ForecastPoint {
  period_from: string;
  on: string;
  opening_balance: string;
  change: string;
  closing_balance: string;
  events: ForecastEvent[];
}

export interface ForecastDataset {
  balance_mode: ForecastBalanceMode;
  scope: 'all' | 'account';
  account_id: string | null;
  account_name: string | null;
  horizon: ForecastHorizon;
  granularity: 'day' | 'month';
  from_on: string;
  through_on: string;
  starting_balance: string;
  ending_balance: string;
  minimum_balance: string;
  minimum_on: string;
  first_negative_on: string | null;
  first_negative_balance: string | null;
  expected_income: string;
  expected_expense: string;
  overdue_excluded_count: number;
  points: ForecastPoint[];
}

export interface ForecastMetrics {
  currentBalance: string;
  forecastEndBalance: string;
  minimumBalance: string;
  minimumBalanceDate: string;
  firstNegativeBalance: string | null;
  firstNegativeBalanceDate: string | null;
  totalPlannedIncome: string;
  totalPlannedExpense: string;
  netPlannedTransferFlow: string;
  netPlannedFlow: string;
  safeToSpend: string;
  hasCashGap: boolean;
}

export interface ForecastTimelineEvent extends ForecastEvent {
  pointIndex: number;
}

export interface ForecastViewModel {
  dataset: ForecastDataset;
  metrics: ForecastMetrics;
  timelineEvents: ForecastTimelineEvent[];
  largestExpense: ForecastTimelineEvent | null;
  minimumPointIndex: number;
  firstNegativePointIndex: number;
}

/**
 * Builds every forecast presentation from the same API snapshot. Daily responses
 * derive point metrics directly; yearly responses keep the backend's daily risk
 * precision because their visible points are intentionally grouped by month.
 */
export function buildForecastViewModel(dataset: ForecastDataset): ForecastViewModel {
  const dailyMetrics = dataset.granularity === 'day' ? deriveDailySeriesMetrics(dataset) : null;
  const forecastEndBalance = dataset.points.at(-1)?.closing_balance ?? dataset.ending_balance;
  const minimumBalance = dailyMetrics?.minimumBalance ?? dataset.minimum_balance;
  const minimumBalanceDate = dailyMetrics?.minimumBalanceDate ?? dataset.minimum_on;
  const firstNegativeBalance = dailyMetrics?.firstNegativeBalance ?? dataset.first_negative_balance;
  const firstNegativeBalanceDate =
    dailyMetrics?.firstNegativeBalanceDate ?? dataset.first_negative_on;
  const timelineEvents = dataset.points
    .flatMap((point, pointIndex) =>
      point.events.map((event) => ({ ...event, pointIndex }) satisfies ForecastTimelineEvent),
    )
    .sort(
      (left, right) =>
        left.due_on.localeCompare(right.due_on) ||
        left.occurrence_id.localeCompare(right.occurrence_id),
    );
  const largestExpense =
    timelineEvents
      .filter((event) => event.type === 'expense' && compareDecimal(event.effect, '0') < 0)
      .reduce<ForecastTimelineEvent | null>(
        (largest, event) =>
          largest === null ||
          compareDecimal(absoluteDecimal(event.effect), absoluteDecimal(largest.effect)) > 0
            ? event
            : largest,
        null,
      ) ?? null;
  const netPlannedTransferFlow = timelineEvents
    .filter((event) => event.type === 'transfer')
    .reduce((total, event) => addDecimal(total, event.effect), '0');

  return {
    dataset,
    metrics: {
      currentBalance: dataset.starting_balance,
      forecastEndBalance,
      minimumBalance,
      minimumBalanceDate,
      firstNegativeBalance,
      firstNegativeBalanceDate,
      totalPlannedIncome: dataset.expected_income,
      totalPlannedExpense: dataset.expected_expense,
      netPlannedTransferFlow,
      netPlannedFlow: subtractDecimal(forecastEndBalance, dataset.starting_balance),
      safeToSpend: compareDecimal(minimumBalance, '0') > 0 ? minimumBalance : '0',
      hasCashGap: firstNegativeBalanceDate !== null,
    },
    timelineEvents,
    largestExpense,
    minimumPointIndex: forecastPointIndexForDate(dataset, minimumBalanceDate),
    firstNegativePointIndex: firstNegativeBalanceDate
      ? forecastPointIndexForDate(dataset, firstNegativeBalanceDate)
      : -1,
  };
}

/** Reconstructs one exact day from an aggregated interval using API event effects. */
export function forecastDetailForDate(dataset: ForecastDataset, on: string): ForecastPoint | null {
  const point = dataset.points.find(
    (candidate) =>
      candidate.period_from.localeCompare(on) <= 0 && candidate.on.localeCompare(on) >= 0,
  );
  if (!point) return null;
  if (point.period_from === point.on) return point;

  const openingBalance = point.events
    .filter((event) => event.due_on.localeCompare(on) < 0)
    .reduce((balance, event) => addDecimal(balance, event.effect), point.opening_balance);
  const events = point.events.filter((event) => event.due_on === on);
  const change = events.reduce((total, event) => addDecimal(total, event.effect), '0');

  return {
    period_from: on,
    on,
    opening_balance: openingBalance,
    change,
    closing_balance: addDecimal(openingBalance, change),
    events,
  };
}

export function forecastPointIndexForDate(dataset: ForecastDataset, on: string): number {
  const index = dataset.points.findIndex(
    (point) => point.period_from.localeCompare(on) <= 0 && point.on.localeCompare(on) >= 0,
  );
  return index >= 0 ? index : 0;
}

export function compareDecimal(left: string, right: string): number {
  const [leftUnits, rightUnits] = align(parseDecimal(left), parseDecimal(right));
  return leftUnits < rightUnits ? -1 : leftUnits > rightUnits ? 1 : 0;
}

export function subtractDecimal(left: string, right: string): string {
  const leftValue = parseDecimal(left);
  const rightValue = parseDecimal(right);
  const [leftUnits, rightUnits, scale] = align(leftValue, rightValue);
  return decimalString(leftUnits - rightUnits, scale);
}

export function addDecimal(left: string, right: string): string {
  const leftValue = parseDecimal(left);
  const rightValue = parseDecimal(right);
  const [leftUnits, rightUnits, scale] = align(leftValue, rightValue);
  return decimalString(leftUnits + rightUnits, scale);
}

export function absoluteDecimal(value: string): string {
  const parsed = parseDecimal(value);
  return decimalString(parsed.units < 0n ? -parsed.units : parsed.units, parsed.scale);
}

function deriveDailySeriesMetrics(
  dataset: ForecastDataset,
): Pick<
  ForecastMetrics,
  'minimumBalance' | 'minimumBalanceDate' | 'firstNegativeBalance' | 'firstNegativeBalanceDate'
> {
  let minimumBalance = dataset.starting_balance;
  let minimumBalanceDate = dataset.from_on;
  let firstNegativeBalance: string | null =
    compareDecimal(dataset.starting_balance, '0') < 0 ? dataset.starting_balance : null;
  let firstNegativeBalanceDate: string | null = firstNegativeBalance ? dataset.from_on : null;

  for (const point of dataset.points) {
    if (compareDecimal(point.closing_balance, minimumBalance) < 0) {
      minimumBalance = point.closing_balance;
      minimumBalanceDate = point.on;
    }
    if (firstNegativeBalanceDate === null && compareDecimal(point.closing_balance, '0') < 0) {
      firstNegativeBalance = point.closing_balance;
      firstNegativeBalanceDate = point.on;
    }
  }

  return {
    minimumBalance,
    minimumBalanceDate,
    firstNegativeBalance,
    firstNegativeBalanceDate,
  };
}

interface ParsedDecimal {
  units: bigint;
  scale: number;
}

function parseDecimal(value: string): ParsedDecimal {
  const match = /^([+-]?)(\d+)(?:\.(\d+))?$/.exec(value.trim());
  if (!match) throw new Error(`Invalid decimal value: ${value}`);
  const fraction = match[3] ?? '';
  const units = BigInt(`${match[1] === '-' ? '-' : ''}${match[2]}${fraction}`);
  return { units, scale: fraction.length };
}

function align(
  left: ParsedDecimal,
  right: ParsedDecimal,
): [leftUnits: bigint, rightUnits: bigint, scale: number] {
  const scale = Math.max(left.scale, right.scale);
  return [
    left.units * 10n ** BigInt(scale - left.scale),
    right.units * 10n ** BigInt(scale - right.scale),
    scale,
  ];
}

function decimalString(units: bigint, scale: number): string {
  if (scale === 0) return units.toString();
  const negative = units < 0n;
  const digits = (negative ? -units : units).toString().padStart(scale + 1, '0');
  const integer = digits.slice(0, -scale);
  const fraction = digits.slice(-scale);
  return `${negative ? '-' : ''}${integer}.${fraction}`;
}
