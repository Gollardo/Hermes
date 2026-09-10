import { HttpClient } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { environment } from '../../../environments/environment';
import { t, localizedSignal, TranslationKey } from '../../i18n/i18n';
import { DecimalInput, decimalPayload } from '../../shared/decimal-input';
import { MoneyPipe, currencySymbol } from '../../shared/money.pipe';
import { apiErrorMessage } from '../../core/api-error';

type Kind = 'income' | 'expense' | 'transfer';
interface Entity {
  id: string;
  name: string;
  archived: boolean;
  type?: string;
}
interface Candidate {
  id: string;
  version: number;
  type: Kind;
  direction: string;
  amount: string;
  date: string;
  description: string;
  category_id: string | null;
  account_id?: string;
  destination_account_id?: string | null;
  allocate_to_funds?: boolean;
  reasons?: string[];
}
interface Row {
  row: number;
  raw: string[];
  error: string | null;
  imported_id: string | null;
  imported_deleted: boolean;
  type: Kind;
  amount: string;
  description: string;
  currency: string;
  facts: Candidate[];
  plans: Candidate[];
  action: string;
  category: string;
  account: string;
  destination: string;
  date: string;
  plan: string;
  existing: string;
  allocate: boolean;
  fund: string;
  fundAmount: string;
}
interface Mapping {
  sheet: string;
  header_row: number;
  encoding: string;
  delimiter: string;
  amount: number;
  description: number;
  direction: number | null;
  debit: number | null;
  credit: number | null;
  currency: number | null;
  decimal_separator: string;
  expense_values: string;
  income_values: string;
}
interface Preview {
  rows: Row[];
  headers: string[];
  sheets: string[];
  facts: Candidate[];
  plans: Candidate[];
}
@Component({
  selector: 'app-imports-page',
  imports: [FormsModule, RouterLink, MoneyPipe, DecimalInput],
  templateUrl: './imports.html',
  styleUrl: './imports.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ImportsPage {
  readonly t = t;
  readonly currencySymbol = currencySymbol;
  readonly baseCurrency = signal('');
  private readonly http = inject(HttpClient);
  readonly busy = signal(false);
  readonly error = localizedSignal();
  readonly notice = localizedSignal();
  readonly funds = signal<Entity[]>([]);
  readonly accounts = signal<Entity[]>([]);
  readonly categories = signal<Entity[]>([]);
  readonly rows = signal<Row[]>([]);
  readonly headers = signal<string[]>([]);
  readonly sheets = signal<string[]>([]);
  readonly profiles = signal<{ name: string; mapping: Mapping }[]>([]);
  readonly results = signal<{ row: number; operation_id: string }[]>([]);
  facts: Candidate[] = [];
  plans: Candidate[] = [];
  file: { filename: string; content: string } | null = null;
  account = '';
  date = '';
  window = 3;
  profileName = '';
  profile = '';
  mapping: Mapping = {
    sheet: '',
    header_row: 1,
    encoding: 'utf-8-sig',
    delimiter: '',
    amount: 7,
    description: 6,
    direction: 12,
    debit: null,
    credit: null,
    currency: 8,
    decimal_separator: '.',
    expense_values: '',
    income_values: '',
  };
  readonly columns = ['amount', 'description', 'direction', 'debit', 'credit', 'currency'] as const;
  constructor() {
    this.http.get<Entity[]>(this.url('/accounts')).subscribe({
      next: (v) => this.accounts.set(v.filter((x) => !x.archived)),
      error: (e) => this.fail(e),
    });
    this.http.get<Entity[]>(this.url('/categories')).subscribe({
      next: (v) => this.categories.set(v.filter((x) => !x.archived)),
      error: (e) => this.fail(e),
    });
    this.http.get<Entity[]>(this.url('/funds')).subscribe({
      next: (v) => this.funds.set(v.filter((x) => !x.archived)),
      error: (e) => this.fail(e),
    });
    this.http.get<{ base_currency: string }>(this.url('/settings')).subscribe({
      next: (v) => this.baseCurrency.set(v.base_currency),
      error: (e) => this.fail(e),
    });
    this.loadProfiles();
  }
  columnLabel(column: string): string {
    return t(('imports.' + column) as TranslationKey);
  }
  private url(path: string): string {
    return environment.apiBaseUrl + path;
  }
  private fail(error: unknown): void {
    this.busy.set(false);
    this.error.set(() => apiErrorMessage(error, t('imports.error')));
  }
  invalidate(): void {
    this.rows.set([]);
    this.results.set([]);
  }
  loadProfiles(): void {
    this.http.get<{ name: string; mapping: Mapping }[]>(this.url('/imports/profiles')).subscribe({
      next: (v) => {
        this.profiles.set(v);
        if (!this.file && !this.profile && v.length) {
          this.mapping = { ...v[0].mapping };
        }
      },
      error: (e) => this.fail(e),
    });
  }
  useProfile(): void {
    const p = this.profiles().find((p) => p.name === this.profile);
    if (p) {
      this.mapping = { ...p.mapping };
      this.inspect();
    }
  }
  saveProfile(): void {
    if (!this.profileName.trim()) return;
    this.http
      .put(this.url('/imports/profiles'), { name: this.profileName, mapping: this.mapping })
      .subscribe({
        next: () => {
          this.notice.set(() => t('imports.saved'));
          this.loadProfiles();
        },
        error: (e) => this.fail(e),
      });
  }
  async upload(event: Event): Promise<void> {
    const file = (event.target as HTMLInputElement).files?.[0];
    if (!file) return;
    this.invalidate();
    this.file = null;
    this.error.set(null);
    if (file.size > 5_000_000) {
      this.error.set(() => t('imports.limit'));
      return;
    }
    const bytes = new Uint8Array(await file.arrayBuffer());
    let binary = '';
    for (const byte of bytes) binary += String.fromCharCode(byte);
    this.file = { filename: file.name, content: btoa(binary) };
    this.mapping.sheet = '';
    this.inspect();
  }
  inspect(): void {
    this.invalidate();
    if (!this.file) return;
    this.busy.set(true);
    this.http
      .post<{ sheets: string[]; rows: string[][] }>(this.url('/imports/inspect'), {
        ...this.file,
        mapping: this.mapping,
      })
      .subscribe({
        next: (v) => {
          this.sheets.set(v.sheets);
          this.headers.set(v.rows[this.mapping.header_row - 1] ?? []);
          this.busy.set(false);
        },
        error: (e) => this.fail(e),
      });
  }
  preview(): void {
    if (!this.file || !this.account || !this.date) {
      this.error.set(() => t('imports.missing'));
      return;
    }
    this.busy.set(true);
    this.error.set(null);
    this.results.set([]);
    this.http
      .post<Preview>(this.url('/imports/preview'), {
        ...this.file,
        mapping: this.mapping,
        account_id: this.account,
        occurred_on: this.date,
        window_days: this.window,
      })
      .subscribe({
        next: (v) => {
          this.facts = v.facts;
          this.plans = v.plans;
          this.rows.set(
            v.rows.map((r) => ({
              ...r,
              action: 'skip',
              category: this.suggestCategory(r),
              fund: '',
              fundAmount: '',
              account: this.account,
              destination: '',
              date: this.date,
              plan: '',
              existing: '',
              allocate: false,
            })),
          );
          this.busy.set(false);
        },
        error: (e) => this.fail(e),
      });
  }
  changeAction(row: Row): void {
    row.plan = '';
    row.existing = '';
    row.allocate = false;
  }
  selectPlan(row: Row): void {
    const plan = this.plans.find((p) => p.id === row.plan);
    if (!plan) return;
    row.type = plan.type;
    row.category = plan.category_id ?? '';
    row.account = plan.account_id ?? this.account;
    row.destination = plan.destination_account_id ?? '';
    row.allocate = plan.allocate_to_funds ?? false;
  }
  selectExisting(row: Row): void {
    const fact = this.facts.find((p) => p.id === row.existing);
    if (!fact) return;
    // Fetch the complete public journal fact, including both transfer accounts.
    this.busy.set(true);
    this.http
      .get<{
        type: Kind;
        occurred_on: string;
        account_id: string;
        destination_account_id: string | null;
        category_id: string | null;
        description: string | null;
        fund_id: string | null;
        fund_amount: string | null;
      }>(this.url('/operations/' + fact.id))
      .subscribe({
        next: (o) => {
          row.type = o.type;
          row.date = o.occurred_on;
          row.account = o.account_id;
          row.destination = o.destination_account_id ?? '';
          row.category = o.category_id ?? '';
          row.description = o.description ?? '';
          row.allocate = false;
          row.fund = o.fund_id ?? '';
          row.fundAmount = o.fund_amount ?? '';
          this.busy.set(false);
        },
        error: (e) => this.fail(e),
      });
  }
  suggestCategory(row: Row): string {
    const candidates = [...row.facts, ...row.plans];
    const ids = [
      ...new Set(
        candidates
          .map((c) => c.category_id)
          .filter((id) => this.categories().some((c) => c.id === id && c.type === row.type)),
      ),
    ];
    return ids.length === 1 ? (ids[0] ?? '') : '';
  }
  effects(): { name: string; amount: string }[] {
    const totals = new Map<string, bigint>();
    const add = (id: string, amount: bigint) => totals.set(id, (totals.get(id) ?? 0n) + amount);
    for (const row of this.selected()) {
      if (row.existing || !row.amount) continue;
      const [whole, fraction = ''] = row.amount.split('.');
      const units = BigInt(whole) * 10000n + BigInt(fraction.padEnd(4, '0'));
      add(row.account, row.type === 'income' ? units : -units);
      if (row.type === 'transfer') add(row.destination, units);
    }
    return [...totals].map(([id, units]) => {
      const absolute = units < 0n ? -units : units;
      return {
        name: this.accounts().find((a) => a.id === id)?.name ?? id,
        amount:
          (units < 0n ? '-' : '') +
          absolute / 10000n +
          '.' +
          (absolute % 10000n).toString().padStart(4, '0'),
      };
    });
  }
  selected(): Row[] {
    return this.rows().filter((r) => r.action !== 'skip' && !r.imported_id);
  }
  candidates(row: Row, kind: 'plans' | 'facts'): Candidate[] {
    return [
      ...row[kind],
      ...(kind === 'plans' ? this.plans : this.facts).filter(
        (p) => !row[kind].some((x) => x.id === p.id),
      ),
    ];
  }
  reason(candidate: Candidate): string {
    return (candidate.reasons ?? [])
      .map((r) =>
        r === 'amount'
          ? t('imports.reasonAmount')
          : r === 'date'
            ? t('imports.reasonDate')
            : t('imports.reasonDescription'),
      )
      .join(', ');
  }
  submit(): void {
    const selected = this.selected();
    if (this.busy() || !this.file || !selected.length) return;
    if (
      selected.length > 200 ||
      selected.some(
        (r) =>
          r.error ||
          !r.date ||
          !r.account ||
          (r.type !== 'transfer' && !r.category) ||
          (r.type === 'transfer' && !r.destination) ||
          (r.action === 'plan' && !r.plan) ||
          (r.action === 'existing' && !r.existing),
      )
    ) {
      this.error.set(() => t('imports.missing'));
      return;
    }
    this.busy.set(true);
    this.error.set(null);
    const decisions = selected.map((r) => ({
      row: r.row,
      statement_account_id: r.type === 'transfer' ? this.account : r.account,
      action: r.action,
      operation: {
        type: r.type,
        occurred_on: r.date,
        amount: r.amount,
        description: r.description,
        account_id: r.account,
        destination_account_id: r.type === 'transfer' ? r.destination : null,
        category_id: r.type === 'transfer' ? null : r.category,
        fund_id: r.type !== 'income' && r.fund ? r.fund : null,
        fund_amount: r.type === 'transfer' && r.fund ? decimalPayload(r.fundAmount) : null,
      },
      occurrence_id: r.action === 'plan' ? r.plan : null,
      occurrence_version:
        r.action === 'plan' ? this.plans.find((p) => p.id === r.plan)?.version : null,
      existing_id: r.existing || null,
      existing_version: r.existing ? this.facts.find((p) => p.id === r.existing)?.version : null,
      allocate_to_funds: r.allocate,
    }));
    this.http
      .post<{ results: { row: number; operation_id: string }[] }>(this.url('/imports/commit'), {
        ...this.file,
        mapping: this.mapping,
        decisions,
      })
      .subscribe({
        next: (v) => {
          this.results.set(v.results);
          for (const result of v.results) {
            const row = this.rows().find((r) => r.row === result.row);
            if (row) row.imported_id = result.operation_id;
          }
          this.busy.set(false);
        },
        error: (e) => this.fail(e),
      });
  }
}
