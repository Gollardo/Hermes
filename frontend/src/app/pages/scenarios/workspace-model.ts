import type { ForecastHorizon } from '../forecast/forecast-view-model';
import type { Comparison, ScenarioContext, RiskWindow } from './scenario-model';

export interface Decision {
  id: string;
  action: 'expense' | 'income' | 'transfer' | 'edit' | 'exclude';
  enabled: boolean;
  description: string;
  account_id?: string;
  destination_account_id?: string;
  category_id?: string;
  fund_id?: string;
  allocate_to_funds?: boolean;
  amount?: string;
  due_on?: string;
  repeat?: 'once' | 'daily' | 'weekly' | 'monthly' | 'yearly';
  repeat_until?: string;
  occurrence_id?: string;
  version?: number;
  apply_to?: 'one' | 'following';
}
export interface LivingCost {
  id: string;
  account_id: string;
  category_id: string;
  mode: 'manual' | 'history';
  monthly_amount?: string;
  excluded_operation_ids: string[];
}
export interface Variant {
  id: string;
  name: string;
  decisions: Decision[];
  expense_increase_percent: string;
  income_delay_days: number;
}
export interface Workspace {
  snapshot_id: string;
  horizon: ForecastHorizon;
  scope_account_id: string | null;
  stop_loss: string;
  living_costs: LivingCost[];
  variants: Variant[];
}
export interface WorkspaceContext extends Omit<ScenarioContext, 'source_policy'> {
  source_policy: string;
  plans: (ScenarioContext['plans'][number] & {
    category_id: string | null;
    rule_id: string | null;
    origin: 'plan' | 'virtual';
  })[];
  categories: { id: string; name: string; type: 'income' | 'expense'; archived: boolean }[];
  funds: { id: string; name: string }[];
  history_from: string;
  history_through: string;
  history: {
    id: string;
    account_id: string;
    category_id: string;
    on: string;
    amount: string;
    description: string | null;
  }[];
}
export interface EstimateEvidence {
  id: string;
  account_id: string;
  category_id: string;
  mode: 'manual' | 'history';
  monthly_amount: string;
  history: { month: string; actual: string; predicted: string | null }[];
  operation_ids: string[];
  mean_absolute_error: string | null;
  coverage_verified: boolean;
  projected_residual: string;
  planned_offset: string;
}
export interface VariantResult {
  id: string;
  name: string;
  comparison: Comparison;
  accounts: {
    account_id: string;
    name: string;
    minimum_free: string;
    minimum_total: string;
    windows: RiskWindow[];
  }[];
  funding_issues: {
    event_id: string;
    account_id: string;
    fund_id: string;
    on: string;
    shortfall: string;
  }[];
  estimates: EstimateEvidence[];
  feasible: boolean;
  required_buffer: string;
}
export interface WorkspaceResult {
  snapshot_id: string;
  variants: VariantResult[];
  baseline_estimates: EstimateEvidence[];
}
export interface SavedWorkspace {
  id: string;
  name: string;
  version: number;
  workspace: Workspace;
  created_at: string;
  updated_at: string;
}
export interface SolveResult {
  status: 'found' | 'no_solution';
  amount: string | null;
  due_on: string | null;
  evaluated: number;
  result: VariantResult | null;
}
