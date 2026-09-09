import { t, localizedSignal, locale, plural } from '../../i18n/i18n';
import { HttpClient, HttpParams } from '@angular/common/http';
import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  effect,
  ElementRef,
  viewChild,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';

import { environment } from '../../../environments/environment';
import { apiErrorMessage } from '../../core/api-error';
import { DateTextPipe, formatTextDate } from '../../shared/date-text.pipe';
import { EntityCombobox, EntityOption } from '../../shared/entity-combobox';
import {
  currencySymbol,
  formatMoney,
  formatPercentageBreakdown,
  MoneyPipe,
} from '../../shared/money.pipe';
import {
  ForecastBalanceMode,
  ForecastDataset,
  ForecastEvent,
  ForecastHorizon,
  ForecastPoint,
  ForecastTimelineEvent,
  ForecastViewModel,
  buildForecastViewModel,
  compareDecimal,
  forecastDetailForDate,
} from './forecast-view-model';

const PLOT_LEFT = 11;
const PLOT_RIGHT = 97;
const PLOT_TOP = 12;
const PLOT_BOTTOM = 78;
const TOOLTIP_BELOW_THRESHOLD = 27;
const TIMELINE_EVENT_LIMIT = 9;
const Y_AXIS_PADDING_RATIO = 0.12;
const ZERO_PROXIMITY_RATIO = 0.15;

interface HorizonOption {
  value: ForecastHorizon;
  label: string;
}

interface Account {
  id: string;
  name: string;
  archived: boolean;
}

interface Settings {
  base_currency: string;
}

interface PlotCoordinate {
  x: number;
  y: number;
  numericBalance: number;
}

interface PlotPoint extends ForecastPoint, PlotCoordinate {
  ariaLabel: string;
}

interface PlotScale {
  low: number;
  high: number;
  step: number;
  showZero: boolean;
}

interface AxisTick {
  y: number;
  label: string;
}

interface DateTick {
  x: number;
  label: string;
}

interface FundForecastPoint {
  period_from: string;
  on: string;
  change: string;
  balance: string;
}

interface FundForecastSeries {
  fund_id: string;
  fund_name: string;
  allocation_percentage: string;
  ending_allocation_percentage: string;
  starting_balance: string;
  ending_balance: string;
  points: FundForecastPoint[];
}

interface FundForecast {
  allocation_mode: 'manual' | 'dynamic';
  horizon: ForecastHorizon;
  granularity: 'day' | 'month';
  from_on: string;
  through_on: string;
  planned_transfer_total: string;
  planned_allocation_total: string;
  unallocated_total: string;
  starting_reserve: string;
  ending_reserve: string;
  blocked_allocation_count: number;
  allocation_events: {
    occurrence_id: string;
    due_on: string;
    incoming_amount: string;
    allocated_amount: string;
    reserve_amount: string;
    executable: boolean;
    allocations: {
      fund_id: string;
      allocation_percentage: string;
      amount: string;
    }[];
  }[];
  series: FundForecastSeries[];
}

interface PlotSegment {
  key: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  risk: boolean;
}

interface ForecastRiskMarker extends PlotCoordinate {
  on: string;
  balance: string;
  pointIndex: number;
}

@Component({
  selector: 'app-forecast-page',
  imports: [FormsModule, RouterLink, MoneyPipe, DateTextPipe, EntityCombobox],
  templateUrl: './forecast.html',
  styleUrls: [
    './forecast.css',
    './forecast-chart.css',
    './forecast-details.css',
    './forecast-funds.css',
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ForecastPage implements OnInit {
  protected readonly t = t;
  private readonly http = inject(HttpClient);
  private readonly chartCanvas = viewChild<ElementRef<HTMLElement>>('chartCanvas');
  private readonly chartWidth = signal(0);

  constructor() {
    effect((onCleanup) => {
      const canvas = this.chartCanvas()?.nativeElement;
      if (!canvas || typeof ResizeObserver === 'undefined') return;
      const observer = new ResizeObserver(([entry]) => {
        this.chartWidth.set(entry.contentRect.width);
      });
      observer.observe(canvas);
      onCleanup(() => observer.disconnect());
    });
  }

  private requestId = 0;
  private fundRequestId = 0;

  protected readonly accounts = signal<Account[]>([]);
  protected get horizons(): readonly HorizonOption[] {
    return [
      { value: 'two_weeks', label: t('forecast.2Weeks') },
      { value: 'month', label: t('forecast.month') },
      { value: 'quarter', label: t('forecast.quarter') },
      { value: 'half_year', label: t('forecast.halfYear') },
      { value: 'year', label: t('forecast.year') },
    ];
  }
  protected readonly timelineEventLimit = TIMELINE_EVENT_LIMIT;
  protected readonly baseCurrency = signal('RUB');
  protected readonly forecast = signal<ForecastDataset | null>(null);
  protected readonly fundForecast = signal<FundForecast | null>(null);
  protected readonly displayedStartingPercentages = computed(() =>
    formatPercentageBreakdown(
      this.fundForecast()?.series.map((series) => series.allocation_percentage) ?? [],
    ),
  );
  protected readonly displayedEndingPercentages = computed(() =>
    formatPercentageBreakdown(
      this.fundForecast()?.series.map((series) => series.ending_allocation_percentage) ?? [],
    ),
  );
  protected readonly fundError = localizedSignal();
  protected readonly accountOptions = computed<EntityOption[]>(() =>
    this.accounts().map((account) => ({
      id: account.id,
      label: account.name,
      detail: account.archived ? t('forecast.archived') : undefined,
    })),
  );
  protected readonly selectedAccountId = signal('');
  protected readonly selectedHorizon = signal<ForecastHorizon>('month');
  protected readonly balanceMode = signal<ForecastBalanceMode>('free');
  protected readonly selectedPointIndex = signal(0);
  protected readonly selectedDate = signal<string | null>(null);
  protected readonly hoveredPointIndex = signal<number | null>(null);
  protected readonly timelineExpanded = signal(false);
  protected readonly loading = signal(true);
  protected readonly error = localizedSignal();

  protected readonly viewModel = computed<ForecastViewModel | null>(() => {
    const value = this.forecast();
    return value ? buildForecastViewModel(value) : null;
  });

  protected readonly selectedPoint = computed(() => {
    const viewModel = this.viewModel();
    if (!viewModel) return null;
    const selectedDate = this.selectedDate();
    if (selectedDate) {
      return forecastDetailForDate(viewModel.dataset, selectedDate);
    }
    return (
      viewModel.dataset.points[this.selectedPointIndex()] ?? viewModel.dataset.points[0] ?? null
    );
  });

  protected readonly selectedTimelineDate = computed(() => {
    const selectedDate = this.selectedDate();
    if (selectedDate) return selectedDate;
    const viewModel = this.viewModel();
    if (!viewModel || viewModel.dataset.granularity !== 'day') return null;
    return viewModel.dataset.points[this.selectedPointIndex()]?.on ?? null;
  });

  protected readonly hasFutureEvents = computed(
    () => this.viewModel()?.timelineEvents.length !== 0,
  );

  protected readonly visibleTimelineEvents = computed(() => {
    const events = this.viewModel()?.timelineEvents ?? [];
    return this.timelineExpanded() ? events : events.slice(0, TIMELINE_EVENT_LIMIT);
  });

  protected readonly chartScale = computed<PlotScale>(() => {
    const value = this.forecast();
    const values = (value?.points ?? []).map((point) => Number(point.closing_balance));
    if (value) {
      values.push(Number(value.starting_balance), Number(value.minimum_balance));
      if (value.first_negative_balance !== null) {
        values.push(Number(value.first_negative_balance));
      }
    }
    const minimum = Math.min(...values);
    const maximum = Math.max(...values);
    const magnitude = Math.max(Math.abs(minimum), Math.abs(maximum), 1);
    const showZero = minimum <= 0 || maximum < 0 || minimum <= magnitude * ZERO_PROXIMITY_RATIO;
    if (showZero) values.push(0);
    const domainMinimum = Math.min(...values);
    const domainMaximum = Math.max(...values);
    const range = domainMaximum - domainMinimum;
    const padding = Math.max(range * Y_AXIS_PADDING_RATIO, magnitude * 0.02);
    const step = niceStep(
      (range === 0 ? Math.max(Math.abs(domainMaximum), 1) : range + padding * 2) / 5,
    );
    let low = Math.floor((domainMinimum - padding) / step) * step;
    let high = Math.ceil((domainMaximum + padding) / step) * step;
    if (low === high) high = low + step;
    if (showZero && low > 0) low = 0;
    if (showZero && high < 0) high = 0;
    return { low, high, step, showZero };
  });

  protected readonly plot = computed<PlotPoint[]>(() => {
    const value = this.forecast();
    if (!value?.points.length) return [];
    const scale = this.chartScale();
    const currency = this.baseCurrency();
    return value.points.map((point) => {
      const numericBalance = Number(point.closing_balance);
      const eventText = point.events.length
        ? t('forecast.operationsP0PressToShowDetails', { p0: point.events.length })
        : t('forecast.noOperations');
      return {
        ...point,
        numericBalance,
        ariaLabel: t('forecast.p0BalanceP1P2ChangeP3P4', {
          p0: formatPointPeriod(point, value.granularity),
          p1: formatMoney(point.closing_balance),
          p2: currency,
          p3: formatMoney(signedDecimal(point.change)),
          p4: eventText,
        }),
        x: plotXForDate(point.on, value),
        y: plotY(numericBalance, scale),
      };
    });
  });

  protected readonly zeroY = computed(() => plotY(0, this.chartScale()));
  protected readonly showZeroBoundary = computed(() => this.chartScale().showZero);
  protected readonly showNegativeZone = computed(
    () => this.showZeroBoundary() && Number(this.forecast()?.minimum_balance ?? 0) < 0,
  );

  protected readonly startingPlotPoint = computed<PlotCoordinate | null>(() => {
    const value = this.forecast();
    if (!value) return null;
    const numericBalance = Number(value.starting_balance);
    return {
      x: PLOT_LEFT,
      y: plotY(numericBalance, this.chartScale()),
      numericBalance,
    };
  });

  protected readonly linePlot = computed<PlotCoordinate[]>(() => {
    const startingPoint = this.startingPlotPoint();
    return startingPoint ? [startingPoint, ...this.plot()] : this.plot();
  });

  protected readonly areaPoints = computed(() => {
    const points = this.linePlot();
    if (!points.length) return '';
    const baseline = PLOT_BOTTOM;
    return [
      `${points[0].x},${baseline}`,
      ...points.map((point) => `${point.x},${point.y}`),
      `${points.at(-1)!.x},${baseline}`,
    ].join(' ');
  });

  protected readonly plotSegments = computed<PlotSegment[]>(() => {
    const points = this.linePlot();
    const zeroY = this.zeroY();
    return points.slice(1).flatMap((point, index) => {
      const previous = points[index];
      const prefix = `${index}`;
      const previousIsRisk = previous.numericBalance < 0;
      const pointIsRisk = point.numericBalance < 0;
      if (previousIsRisk === pointIsRisk) {
        return [segment(prefix, previous, point, pointIsRisk)];
      }
      const crossingRatio =
        (0 - previous.numericBalance) / (point.numericBalance - previous.numericBalance);
      const crossingX = previous.x + (point.x - previous.x) * crossingRatio;
      return [
        {
          key: `${prefix}-a`,
          x1: previous.x,
          y1: previous.y,
          x2: crossingX,
          y2: zeroY,
          risk: previousIsRisk,
        },
        {
          key: `${prefix}-b`,
          x1: crossingX,
          y1: zeroY,
          x2: point.x,
          y2: point.y,
          risk: pointIsRisk,
        },
      ];
    });
  });

  protected readonly hoveredPoint = computed(() => {
    const index = this.hoveredPointIndex();
    return index === null ? null : (this.plot()[index] ?? null);
  });

  protected readonly cashGapMarker = computed<ForecastRiskMarker | null>(() => {
    const viewModel = this.viewModel();
    if (
      !viewModel ||
      viewModel.dataset.granularity !== 'month' ||
      viewModel.metrics.firstNegativeBalanceDate === null ||
      viewModel.metrics.firstNegativeBalance === null
    ) {
      return null;
    }
    if (
      viewModel.metrics.firstNegativeBalanceDate === viewModel.dataset.from_on &&
      compareDecimal(viewModel.metrics.firstNegativeBalance, viewModel.dataset.starting_balance) ===
        0
    ) {
      return null;
    }
    const numericBalance = Number(viewModel.metrics.firstNegativeBalance);
    return {
      on: viewModel.metrics.firstNegativeBalanceDate,
      balance: viewModel.metrics.firstNegativeBalance,
      pointIndex: viewModel.firstNegativePointIndex,
      x: plotXForDate(viewModel.metrics.firstNegativeBalanceDate, viewModel.dataset),
      y: plotY(numericBalance, this.chartScale()),
      numericBalance,
    };
  });

  protected readonly yTicks = computed<AxisTick[]>(() => {
    const scale = this.chartScale();
    const ticks: AxisTick[] = [];
    for (let value = scale.low; value <= scale.high + scale.step / 2; value += scale.step) {
      ticks.push({ y: plotY(value, scale), label: formatAxisMoney(value) });
    }
    return ticks.reverse();
  });

  protected readonly dateTicks = computed<DateTick[]>(() => {
    const points = this.plot();
    if (!points.length) return [];
    // Reserve enough space for RU/EN month labels, including edge-aligned dates.
    const capacity = Math.max(
      2,
      Math.floor((this.chartWidth() * (PLOT_RIGHT - PLOT_LEFT)) / 100 / 80),
    );
    const count = Math.min(
      this.forecast()?.horizon === 'two_weeks' ? 5 : 7,
      capacity,
      points.length,
    );
    return uniqueIndexes(count, points.length).map((index) => ({
      x: points[index].x,
      label: compactDate(points[index].on, this.forecast()?.granularity === 'month'),
    }));
  });

  ngOnInit(): void {
    forkJoin({
      materialization: this.http.post<unknown>(
        `${environment.apiBaseUrl}/scheduling/materialize`,
        {},
      ),
      accounts: this.http.get<Account[]>(`${environment.apiBaseUrl}/accounts`),
      settings: this.http.get<Settings>(`${environment.apiBaseUrl}/settings`),
    }).subscribe({
      next: ({ accounts, settings }) => {
        this.accounts.set(accounts);
        this.baseCurrency.set(currencySymbol(settings.base_currency));
        this.loadForecast();
        this.loadFundForecast();
      },
      error: (error: unknown) => {
        this.loading.set(false);
        this.error.set(() => apiErrorMessage(error, t('forecast.couldNotPrepareTheForecast')));
      },
    });
  }

  protected changeAccount(value: string): void {
    this.selectedAccountId.set(value);
    this.loadForecast();
  }

  protected changeHorizon(value: ForecastHorizon): void {
    this.selectedHorizon.set(value);
    this.loadForecast();
    this.loadFundForecast();
  }

  protected changeBalanceMode(mode: ForecastBalanceMode): void {
    this.balanceMode.set(mode);
    this.loadForecast();
  }

  protected selectPoint(index: number): void {
    this.selectedPointIndex.set(index);
    this.selectedDate.set(null);
  }

  protected selectTimelineEvent(event: ForecastTimelineEvent): void {
    this.selectedPointIndex.set(event.pointIndex);
    this.selectedDate.set(event.due_on);
  }

  protected selectRiskPoint(index: number, on: string | null): void {
    if (index < 0 || on === null) return;
    this.selectedPointIndex.set(index);
    this.selectedDate.set(on);
  }

  protected movePointFocus(event: KeyboardEvent, index: number): void {
    const lastIndex = this.plot().length - 1;
    const nextIndex =
      event.key === 'Home'
        ? 0
        : event.key === 'End'
          ? lastIndex
          : event.key === 'ArrowLeft'
            ? Math.max(0, index - 1)
            : event.key === 'ArrowRight'
              ? Math.min(lastIndex, index + 1)
              : null;
    if (nextIndex === null || nextIndex === index) return;
    event.preventDefault();
    this.selectPoint(nextIndex);
    const canvas = (event.currentTarget as HTMLElement).parentElement;
    queueMicrotask(() =>
      canvas?.querySelectorAll<HTMLButtonElement>('.chart-point')[nextIndex]?.focus(),
    );
  }

  protected showPoint(index: number): void {
    this.hoveredPointIndex.set(index);
  }

  protected hidePoint(index: number): void {
    if (this.hoveredPointIndex() === index) this.hoveredPointIndex.set(null);
  }

  protected toggleTimeline(): void {
    this.timelineExpanded.update((expanded) => !expanded);
  }

  protected periodLabel(point: ForecastPoint): string {
    return formatPointPeriod(point, this.forecast()?.granularity ?? 'day');
  }

  protected detailContextLabel(point: ForecastPoint): string {
    return this.forecast()?.granularity === 'month' && point.period_from !== point.on
      ? t('forecast.selectedIntervalDetails')
      : t('forecast.selectedDayDetails');
  }

  protected balanceModeLabel(mode: ForecastBalanceMode): string {
    return mode === 'free' ? t('forecast.freeBalance') : t('forecast.totalBalance');
  }

  protected chartTitle(mode: ForecastBalanceMode): string {
    return mode === 'free' ? t('forecast.freeBalanceForecast') : t('forecast.totalBalanceForecast');
  }

  protected granularityLabel(value: ForecastDataset): string {
    return value.granularity === 'month' ? t('forecast.monthClose') : t('forecast.dayClose');
  }

  protected tooltipBelow(point: PlotPoint): boolean {
    return point.y < TOOLTIP_BELOW_THRESHOLD;
  }

  protected typeLabel(type: ForecastEvent['type']): string {
    return {
      income: t('operation-create-menu.income'),
      expense: t('operation-create-menu.expense'),
      transfer: t('operation-create-menu.transfer'),
    }[type];
  }

  protected eventTitle(event: ForecastEvent): string {
    return event.description?.trim() || this.typeLabel(event.type);
  }

  protected eventDirection(event: ForecastEvent): string {
    return event.destination_account_name
      ? `${event.account_name} → ${event.destination_account_name}`
      : event.account_name;
  }

  protected calendarQuery(event: ForecastEvent): { month: string; focus: string } {
    return { month: event.due_on.slice(0, 7), focus: event.occurrence_id };
  }

  protected signed(value: string): string {
    return signedDecimal(value);
  }

  protected operationsWord(count: number): string {
    return plural(count, {
      one: 'common.operationsOne',
      few: 'common.operationsFew',
      many: 'common.operationsMany',
      other: 'common.operationsOther',
    });
  }

  protected isNegative(value: string): boolean {
    return compareDecimal(value, '0') < 0;
  }

  protected isPositive(value: string): boolean {
    return compareDecimal(value, '0') > 0;
  }

  protected chartAriaLabel(viewModel: ForecastViewModel): string {
    const risk = viewModel.metrics.hasCashGap
      ? t('forecast.firstCashShortfallOnP0', {
          p0: formatTextDate(viewModel.metrics.firstNegativeBalanceDate),
        })
      : t('forecast.noCashShortfallsExpected');
    return t('forecast.p0FromP1ThroughP2P3', {
      p0: this.chartTitle(viewModel.dataset.balance_mode),
      p1: formatTextDate(viewModel.dataset.from_on),
      p2: formatTextDate(viewModel.dataset.through_on),
      p3: risk,
    });
  }

  protected fundDonutStyle(): string {
    const series = this.fundForecast()?.series ?? [];
    const total = series.reduce((sum, item) => sum + Number(item.ending_balance), 0);
    if (total <= 0) return 'var(--surface-soft)';
    let cursor = 0;
    return `conic-gradient(${series
      .map((item, index) => {
        const start = cursor;
        cursor += (Number(item.ending_balance) / total) * 100;
        return `${fundColor(index)} ${start}% ${cursor}%`;
      })
      .join(', ')})`;
  }

  protected fundColor(index: number): string {
    return fundColor(index);
  }

  protected isZero(value: string): boolean {
    return compareDecimal(value, '0') === 0;
  }

  protected retryFundForecast(): void {
    this.loadFundForecast();
  }

  private loadForecast(): void {
    const requestId = ++this.requestId;
    this.loading.set(true);
    this.error.set(null);
    this.forecast.set(null);
    this.selectedPointIndex.set(0);
    this.selectedDate.set(null);
    this.hoveredPointIndex.set(null);
    this.timelineExpanded.set(false);
    let params = new HttpParams().set('horizon', this.selectedHorizon());
    params = params.set('balance_mode', this.balanceMode());
    if (this.selectedAccountId()) params = params.set('account_id', this.selectedAccountId());
    this.http.get<ForecastDataset>(`${environment.apiBaseUrl}/forecast`, { params }).subscribe({
      next: (value) => {
        if (requestId !== this.requestId) return;
        const viewModel = buildForecastViewModel(value);
        this.forecast.set(value);
        const initialIndex =
          viewModel.firstNegativePointIndex >= 0
            ? viewModel.firstNegativePointIndex
            : value.points.findIndex((point) => point.events.length);
        this.selectedPointIndex.set(initialIndex >= 0 ? initialIndex : 0);
        this.selectedDate.set(
          viewModel.metrics.firstNegativeBalanceDate ?? viewModel.timelineEvents[0]?.due_on ?? null,
        );
        this.loading.set(false);
      },
      error: (error: unknown) => {
        if (requestId !== this.requestId) return;
        this.loading.set(false);
        this.error.set(() => apiErrorMessage(error, t('forecast.couldNotCalculateTheForecast')));
      },
    });
  }

  private loadFundForecast(): void {
    const requestId = ++this.fundRequestId;
    this.fundForecast.set(null);
    this.fundError.set(null);
    const params = new HttpParams().set('horizon', this.selectedHorizon());
    this.http.get<FundForecast>(`${environment.apiBaseUrl}/forecast/funds`, { params }).subscribe({
      next: (forecast) => {
        if (requestId === this.fundRequestId) this.fundForecast.set(forecast);
      },
      error: (error: unknown) => {
        if (requestId !== this.fundRequestId) return;
        // This additional read model must not hide an otherwise valid cash forecast.
        this.fundError.set(() =>
          apiErrorMessage(error, t('forecast.couldNotCalculateTheFundOutlook')),
        );
      },
    });
  }
}

const FUND_COLORS = ['#086b4c', '#52a36f', '#d28a0c', '#526b82', '#a64872', '#6d4bb8'];

function fundColor(index: number): string {
  return FUND_COLORS[index % FUND_COLORS.length];
}

function segment(
  key: string,
  from: PlotCoordinate,
  to: PlotCoordinate,
  risk: boolean,
): PlotSegment {
  return { key, x1: from.x, y1: from.y, x2: to.x, y2: to.y, risk };
}

function isoDayNumber(value: string): number {
  const [year, month, day] = value.split('-').map(Number);
  return Date.UTC(year, month - 1, day) / 86_400_000;
}

function plotY(value: number, scale: PlotScale): number {
  return (
    PLOT_TOP + ((scale.high - value) / (scale.high - scale.low || 1)) * (PLOT_BOTTOM - PLOT_TOP)
  );
}

function plotXForDate(on: string, dataset: ForecastDataset): number {
  const from = isoDayNumber(dataset.from_on);
  const through = isoDayNumber(dataset.through_on);
  return PLOT_LEFT + ((isoDayNumber(on) - from) / (through - from || 1)) * (PLOT_RIGHT - PLOT_LEFT);
}

function formatPointPeriod(
  point: ForecastPoint,
  granularity: ForecastDataset['granularity'],
): string {
  return granularity === 'month' && point.period_from !== point.on
    ? `${formatTextDate(point.period_from)} — ${formatTextDate(point.on)}`
    : formatTextDate(point.on);
}

function signedDecimal(value: string): string {
  return compareDecimal(value, '0') > 0 ? `+${value}` : value;
}

function niceStep(rawStep: number): number {
  const exponent = Math.floor(Math.log10(rawStep || 1));
  const fraction = rawStep / 10 ** exponent;
  const niceFraction = fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 5 ? 5 : 10;
  return niceFraction * 10 ** exponent;
}

function formatAxisMoney(value: number): string {
  const normalized = Math.abs(value) < 0.005 ? 0 : value;
  return new Intl.NumberFormat('ru-RU', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
    .format(normalized)
    .replace(/\u00a0/g, ' ');
}

function compactDate(value: string, monthOnly = false): string {
  const [year, month, day] = value.split('-').map(Number);
  return new Intl.DateTimeFormat(
    locale(),
    monthOnly
      ? { month: 'short', year: 'numeric', timeZone: 'UTC' }
      : { day: 'numeric', month: 'short', timeZone: 'UTC' },
  )
    .format(new Date(Date.UTC(year, month - 1, day)))
    .replace('.', '');
}

function uniqueIndexes(count: number, total: number): number[] {
  return [
    ...new Set(
      Array.from({ length: count }, (_, index) =>
        Math.round((index * (total - 1)) / Math.max(count - 1, 1)),
      ),
    ),
  ];
}
