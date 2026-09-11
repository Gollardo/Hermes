import {
  ForecastDataset,
  ForecastHorizon,
  ForecastEvent,
  compareDecimal,
  subtractDecimal,
} from '../forecast/forecast-view-model';

export type ScenarioAction = 'expense' | 'income' | 'amount' | 'move';
export interface PlanChoice {
  id: string;
  version: number;
  due_on: string;
  amount: string;
  type: string;
  description: string | null;
  account_id: string;
  account_name: string;
  destination_account_id: string | null;
  destination_account_name: string | null;
  allocate_to_funds: boolean;
}
export interface ScenarioContext {
  snapshot_id: string;
  today: string;
  maximum_on: string;
  currency: string;
  accounts: { id: string; name: string; archived: boolean }[];
  plans: PlanChoice[];
  overdue_excluded_count: number;
}
export interface RiskWindow {
  from_on: string;
  through_on: string;
  recovered_on: string | null;
  minimum_balance: string;
  minimum_on: string;
  starts_at_snapshot: boolean;
}
export interface Risk {
  threshold: string;
  windows: RiskWindow[];
}
export interface Branch {
  free: ForecastDataset;
  total: ForecastDataset;
  zero_risk: Risk;
  stop_loss_risk: Risk | null;
  suggested_risk: Risk | null;
}
export interface Comparison {
  snapshot_id: string;
  currency: string;
  baseline: Branch;
  alternative: Branch;
  ending_free_delta: string;
  minimum_free_delta: string;
  ending_total_delta: string;
  suggested_boundary: {
    amount: string;
    from_on: string;
    through_on: string;
    event_ids: string[];
  } | null;
  reserve: { starting: string; baseline: string; alternative: string; delta: string };
  funds: {
    fund_id: string;
    name: string;
    starting: string;
    baseline: string;
    alternative: string;
    delta: string;
  }[];
  events: {
    occurrence_id: string;
    description: string | null;
    before_on: string | null;
    after_on: string;
    before_amount: string | null;
    after_amount: string;
    baseline_allocation: string;
    alternative_allocation: string;
    hypothetical: boolean;
    baseline_reserve: string;
    alternative_reserve: string;
    allocations: { fund_id: string; name: string; baseline: string; alternative: string }[];
  }[];
  assumptions: string[];
}
export interface ScenarioPayload {
  action: ScenarioAction;
  horizon: ForecastHorizon;
  scope_account_id: string | null;
  snapshot_id: string;
  stop_loss: string | null;
  account_id?: string;
  occurrence_id?: string;
  version?: number;
  amount?: string;
  due_on?: string;
}
export function isHypothesis(event: ForecastEvent): boolean {
  return event.origin === 'scenario';
}

/** Only SVG coordinates use Number; exact values and deltas remain decimal strings. */
export function comparisonChart(result: Comparison, stop: string | null) {
  const a = result.baseline.free,
    b = result.alternative.free;
  const values = [
    a.starting_balance,
    b.starting_balance,
    ...a.points.map((p) => p.closing_balance),
    ...b.points.map((p) => p.closing_balance),
    '0',
  ];
  if (stop !== null) values.push(stop);
  values.sort(compareDecimal);
  const low = values[0],
    high = values[values.length - 1];
  const span = Number(subtractDecimal(high, low)) || 1;
  const y = (v: string) => 170 - (Number(subtractDecimal(v, low)) / span) * 150;
  const start = Date.parse(a.from_on),
    duration = Date.parse(a.through_on) - start || 1;
  const x = (on: string) => 20 + ((Date.parse(on) - start) / duration) * 660;
  const path = (data: ForecastDataset) => {
    let line = `M 20 ${y(data.starting_balance)}`;
    for (const p of data.points) line += ` H ${x(p.on)} V ${y(p.closing_balance)}`;
    return line;
  };
  return {
    baseline: path(a),
    alternative: path(b),
    low,
    high,
    zero: y('0'),
    stop: stop === null ? null : y(stop),
  };
}
