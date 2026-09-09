import { language } from '../../i18n/i18n';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { ForecastPage } from './forecast';

const FORECAST = {
  balance_mode: 'free',
  scope: 'all',
  account_id: null,
  account_name: null,
  horizon: 'month',
  granularity: 'day',
  from_on: '2026-08-12',
  through_on: '2026-09-12',
  starting_balance: '100.0000',
  ending_balance: '-20.0000',
  minimum_balance: '-20.0000',
  minimum_on: '2026-08-20',
  first_negative_on: '2026-08-20',
  first_negative_balance: '-20.0000',
  expected_income: '30.0000',
  expected_expense: '150.0000',
  overdue_excluded_count: 1,
  points: [
    {
      period_from: '2026-08-12',
      on: '2026-08-12',
      opening_balance: '100.0000',
      change: '0',
      closing_balance: '100.0000',
      events: [],
    },
    {
      period_from: '2026-08-20',
      on: '2026-08-20',
      opening_balance: '100.0000',
      change: '-120.0000',
      closing_balance: '-20.0000',
      events: [
        {
          occurrence_id: 'occurrence-1',
          due_on: '2026-08-20',
          type: 'expense',
          status: 'pending',
          description: 'Аренда',
          account_name: 'Основной',
          destination_account_name: null,
          amount: '120.0000',
          effect: '-120.0000',
        },
      ],
    },
    {
      period_from: '2026-09-12',
      on: '2026-09-12',
      opening_balance: '-20.0000',
      change: '0',
      closing_balance: '-20.0000',
      events: [],
    },
  ],
};

const FUND_FORECAST = {
  allocation_mode: 'manual',
  horizon: 'month',
  granularity: 'day',
  from_on: '2026-08-12',
  through_on: '2026-09-12',
  planned_transfer_total: '0.0000',
  planned_allocation_total: '0.0000',
  unallocated_total: '0.0000',
  blocked_allocation_count: 0,
  allocation_events: [],
  series: [],
};

const POPULATED_FUND_FORECAST = {
  ...FUND_FORECAST,
  planned_transfer_total: '100.0000',
  planned_allocation_total: '80.0000',
  unallocated_total: '20.0000',
  series: [
    {
      fund_id: 'fund-1',
      fund_name: 'Резерв',
      allocation_percentage: '80.0000',
      ending_allocation_percentage: '80.0000',
      starting_balance: '20.0000',
      ending_balance: '100.0000',
      points: [
        {
          period_from: '2026-08-12',
          on: '2026-08-20',
          change: '80.0000',
          balance: '100.0000',
        },
      ],
    },
  ],
};

describe('ForecastPage', () => {
  let fixture: ComponentFixture<ForecastPage>;
  let http: HttpTestingController;

  beforeEach(async () => {
    localStorage.setItem('hermes-recent-accounts', JSON.stringify(['account-1']));
    await TestBed.configureTestingModule({
      imports: [ForecastPage],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();
    fixture = TestBed.createComponent(ForecastPage);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    language.set('ru');
    vi.unstubAllGlobals();
    http.verify();
  });

  it.each(['ru', 'en'] as const)(
    'adapts date labels to chart width without changing forecast points in %s',
    async (selected) => {
      let resize: ResizeObserverCallback | undefined;
      const disconnect = vi.fn();
      vi.stubGlobal(
        'ResizeObserver',
        class {
          constructor(callback: ResizeObserverCallback) {
            resize = callback;
          }
          observe = vi.fn();
          disconnect = disconnect;
        },
      );
      flushInitial();
      http.expectOne('/api/v1/forecast?horizon=month&balance_mode=free').flush(FORECAST);
      language.set(selected);
      fixture.detectChanges();
      await fixture.whenStable();
      const pointCount = fixture.nativeElement.querySelectorAll('.chart-point').length;
      const setWidth = (width: number) => {
        resize?.([{ contentRect: { width } } as ResizeObserverEntry], {} as ResizeObserver);
        fixture.detectChanges();
      };
      setWidth(240);
      const narrow = fixture.nativeElement.querySelectorAll('.chart-date-ticks span');
      expect(narrow.length).toBe(2);
      expect(narrow[0].classList.contains('first-tick')).toBe(true);
      expect(narrow[1].classList.contains('last-tick')).toBe(true);
      const endpoints = [narrow[0].textContent, narrow[1].textContent];
      setWidth(900);
      const wide = fixture.nativeElement.querySelectorAll('.chart-date-ticks span');
      expect(wide.length).toBeGreaterThan(narrow.length);
      expect([wide[0].textContent, wide[wide.length - 1].textContent]).toEqual(endpoints);
      expect(fixture.nativeElement.querySelectorAll('.chart-point').length).toBe(pointCount);
      fixture.destroy();
      expect(disconnect).toHaveBeenCalled();
    },
  );

  it('prioritizes safe-to-spend, cash-gap and synchronized day details', () => {
    flushInitial();
    http.expectOne('/api/v1/forecast?horizon=month&balance_mode=free').flush(FORECAST);
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent;
    expect(text).toContain('Можно потратить сейчас');
    expect(text).toContain('Сначала закройте прогнозируемый дефицит');
    expect(text).toContain('Кассовый разрыв');
    expect(text).toContain('-20,00 ₽');
    expect(text).toContain('Аренда');
    expect(text).toContain('Просроченные события не включены: 1');
    expect(fixture.nativeElement.querySelector('.forecast-chart')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('.negative-zone')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('.risk-segment')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('.zero-caption').textContent).toContain('0,00 ₽');
    expect(fixture.nativeElement.querySelector('.safe-spend-card strong').textContent.trim()).toBe(
      '0,00 ₽',
    );

    const calendarLink = fixture.nativeElement.querySelector('.event-link') as HTMLAnchorElement;
    expect(calendarLink.getAttribute('href')).toContain('month=2026-08');
    expect(calendarLink.getAttribute('href')).toContain('focus=occurrence-1');
  });

  it('renders the enlarged fund allocation diagram and exact values without a line chart', () => {
    flushInitial(POPULATED_FUND_FORECAST);
    http.expectOne('/api/v1/forecast?horizon=month&balance_mode=free').flush(FORECAST);
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('.fund-projection-donut')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('.fund-line-chart')).toBeNull();
    expect(fixture.nativeElement.textContent).toContain('Резерв · 80,00%');
    expect(fixture.nativeElement.textContent).toContain('Сейчас');
    expect(fixture.nativeElement.textContent).toContain('20,00 ₽');
    expect(fixture.nativeElement.textContent).toContain('100,00 ₽');
    expect(fixture.nativeElement.textContent).toContain('Останется свободно:');
    expect(fixture.nativeElement.textContent).toContain('20,00 ₽');
  });

  it('shows blocked dynamic replenishments even when no fund series exists', () => {
    flushInitial({
      ...FUND_FORECAST,
      allocation_mode: 'dynamic',
      planned_transfer_total: '100.0000',
      unallocated_total: '100.0000',
      blocked_allocation_count: 1,
    });
    http.expectOne('/api/v1/forecast?horizon=month&balance_mode=free').flush(FORECAST);
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain(
      'Создайте неархивный фонд с целью, чтобы увидеть перспективу распределения.',
    );
    expect(fixture.nativeElement.textContent).toContain(
      'Плановых переводов без доступных незаполненных фондов: 1',
    );
  });

  it('keeps the cash forecast visible and exposes a retry when fund projection fails', () => {
    fixture.detectChanges();
    http.expectOne('/api/v1/scheduling/materialize').flush({
      horizon_from: '2026-08-12',
      horizon_to: '2027-08-12',
      created: 0,
      updated: 0,
      cancelled: 0,
    });
    http.expectOne('/api/v1/accounts').flush([]);
    http.expectOne('/api/v1/settings').flush({ base_currency: 'RUB' });
    http
      .expectOne('/api/v1/forecast/funds?horizon=month')
      .flush({ detail: 'Unavailable' }, { status: 503, statusText: 'Service Unavailable' });
    http.expectOne('/api/v1/forecast?horizon=month&balance_mode=free').flush(FORECAST);
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('.forecast-chart')).not.toBeNull();
    expect(fixture.nativeElement.textContent).toContain('Перспектива фондов недоступна');
    (
      fixture.nativeElement.querySelector('.fund-forecast-error button') as HTMLButtonElement
    ).click();
    http.expectOne('/api/v1/forecast/funds?horizon=month').flush(FUND_FORECAST);
  });

  it('replaces stale data with loading and explains an event-free horizon', () => {
    flushInitial();
    http.expectOne('/api/v1/forecast?horizon=month&balance_mode=free').flush(noRiskForecast());
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Нет известных ожидаемых событий');
    expect(fixture.nativeElement.textContent).toContain('Кассовых разрывов не ожидается');

    const week = [...fixture.nativeElement.querySelectorAll('.period-switcher button')].find(
      (button: HTMLButtonElement) => button.textContent.trim() === '2 недели',
    ) as HTMLButtonElement;
    week.click();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Рассчитываем будущие остатки');
    expect(fixture.nativeElement.textContent).not.toContain('Прогноз на конец периода');
    http
      .expectOne('/api/v1/forecast?horizon=two_weeks&balance_mode=free')
      .flush({ ...noRiskForecast(), horizon: 'two_weeks' });
    http
      .expectOne('/api/v1/forecast/funds?horizon=two_weeks')
      .flush({ ...FUND_FORECAST, horizon: 'two_weeks' });
  });

  it('requests a selected account and horizon', () => {
    flushInitial();
    http.expectOne('/api/v1/forecast?horizon=month&balance_mode=free').flush(FORECAST);
    fixture.detectChanges();

    const account = fixture.nativeElement.querySelector('app-entity-combobox') as HTMLElement;
    (account.querySelector('input') as HTMLInputElement).dispatchEvent(new Event('focus'));
    fixture.detectChanges();
    (account.querySelector('[data-option-id="account-1"]') as HTMLButtonElement).click();
    fixture.detectChanges();
    http
      .expectOne(
        (request) =>
          request.url === '/api/v1/forecast' && request.params.get('account_id') === 'account-1',
      )
      .flush({ ...FORECAST, scope: 'account', account_id: 'account-1', account_name: 'Основной' });

    const quarter = [...fixture.nativeElement.querySelectorAll('.period-switcher button')].find(
      (button: HTMLButtonElement) => button.textContent.trim() === 'Квартал',
    ) as HTMLButtonElement;
    quarter.click();
    http
      .expectOne(
        (request) =>
          request.url === '/api/v1/forecast' &&
          request.params.get('horizon') === 'quarter' &&
          request.params.get('account_id') === 'account-1',
      )
      .flush({ ...FORECAST, horizon: 'quarter' });
    http
      .expectOne('/api/v1/forecast/funds?horizon=quarter')
      .flush({ ...FUND_FORECAST, horizon: 'quarter' });
  });

  it('defaults to free money and can include reserved money', () => {
    flushInitial();
    http.expectOne('/api/v1/forecast?horizon=month&balance_mode=free').flush(FORECAST);
    fixture.detectChanges();

    const allMoney = [...fixture.nativeElement.querySelectorAll('.balance-switcher button')].find(
      (button: HTMLButtonElement) => button.textContent.trim() === 'Все средства',
    ) as HTMLButtonElement;
    allMoney.click();

    http.expectOne('/api/v1/forecast?horizon=month&balance_mode=total').flush({
      ...FORECAST,
      balance_mode: 'total',
    });
  });

  it('shows exact tooltip data and selects a timeline event', () => {
    flushInitial();
    http.expectOne('/api/v1/forecast?horizon=month&balance_mode=free').flush(FORECAST);
    fixture.detectChanges();

    const points = fixture.nativeElement.querySelectorAll('.chart-point');
    points[1].dispatchEvent(new Event('mouseenter'));
    fixture.detectChanges();
    const tooltip = fixture.nativeElement.querySelector('.chart-tooltip');
    expect(tooltip.textContent).toContain('20 августа 2026');
    expect(tooltip.textContent).toContain('-20,00 ₽');
    expect(tooltip.textContent).toContain('Посмотреть операции →');

    const timelineEvent = fixture.nativeElement.querySelector(
      '.timeline-event',
    ) as HTMLButtonElement;
    timelineEvent.click();
    fixture.detectChanges();
    expect(timelineEvent.getAttribute('aria-pressed')).toBe('true');
    expect(fixture.nativeElement.querySelector('#day-detail-title').textContent).toContain(
      '20 августа 2026',
    );
  });

  it('includes the actual current balance in the chart scale and marker', () => {
    flushInitial();
    http.expectOne('/api/v1/forecast?horizon=month&balance_mode=free').flush({
      ...noRiskForecast(),
      starting_balance: '1000.0000',
      ending_balance: '100.0000',
      minimum_balance: '100.0000',
      expected_expense: '900.0000',
      points: [
        {
          ...FORECAST.points[0],
          opening_balance: '1000.0000',
          change: '-900.0000',
          closing_balance: '100.0000',
        },
        {
          ...FORECAST.points[0],
          period_from: '2026-09-12',
          on: '2026-09-12',
          opening_balance: '100.0000',
          closing_balance: '100.0000',
        },
      ],
    });
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('.actual-start-marker')).not.toBeNull();
    expect(
      fixture.nativeElement.querySelector('.y-axis-scale').textContent.replace(/\s/g, ' '),
    ).toContain('1 000');
  });

  it('uses an adaptive Y-axis and hides zero for a safely positive forecast', () => {
    flushInitial();
    http.expectOne('/api/v1/forecast?horizon=month&balance_mode=free').flush({
      ...noRiskForecast(),
      starting_balance: '22000.0000',
      ending_balance: '25000.0000',
      minimum_balance: '18500.0000',
      minimum_on: '2026-08-20',
      points: [
        {
          ...FORECAST.points[0],
          opening_balance: '22000.0000',
          closing_balance: '22000.0000',
        },
        {
          ...FORECAST.points[0],
          period_from: '2026-08-20',
          on: '2026-08-20',
          opening_balance: '22000.0000',
          change: '-3500.0000',
          closing_balance: '18500.0000',
        },
        {
          ...FORECAST.points[0],
          period_from: '2026-09-12',
          on: '2026-09-12',
          opening_balance: '18500.0000',
          change: '6500.0000',
          closing_balance: '25000.0000',
        },
      ],
    });
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('.zero-line')).toBeNull();
    expect(fixture.nativeElement.querySelector('.zero-caption')).toBeNull();
    expect(fixture.nativeElement.querySelector('.negative-zone')).toBeNull();
    const axisText = fixture.nativeElement
      .querySelector('.y-axis-scale')
      .textContent.replace(/\s/g, ' ');
    expect(axisText).toContain('16 000');
    expect(axisText).toContain('26 000');
  });

  it('keeps zero visible when a positive forecast approaches the deficit boundary', () => {
    flushInitial();
    http.expectOne('/api/v1/forecast?horizon=month&balance_mode=free').flush({
      ...noRiskForecast(),
      starting_balance: '1000.0000',
      ending_balance: '100.0000',
      minimum_balance: '100.0000',
      points: [
        {
          ...FORECAST.points[0],
          opening_balance: '1000.0000',
          change: '-900.0000',
          closing_balance: '100.0000',
        },
      ],
    });
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('.zero-line')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('.zero-caption').textContent).toContain('0,00 ₽');
    expect(fixture.nativeElement.querySelector('.negative-zone')).toBeNull();
  });

  it('shows an exact cash-gap marker and day detail for a monthly interval', () => {
    flushInitial();
    http.expectOne('/api/v1/forecast?horizon=month&balance_mode=free').flush({
      ...FORECAST,
      horizon: 'year',
      granularity: 'month',
      through_on: '2026-08-31',
      ending_balance: '100.0000',
      points: [
        {
          period_from: '2026-08-12',
          on: '2026-08-31',
          opening_balance: '100.0000',
          change: '0.0000',
          closing_balance: '100.0000',
          events: [
            FORECAST.points[1].events[0],
            {
              ...FORECAST.points[1].events[0],
              occurrence_id: 'occurrence-2',
              due_on: '2026-08-25',
              type: 'income',
              description: 'Возврат',
              amount: '120.0000',
              effect: '120.0000',
            },
          ],
        },
      ],
    });
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('.cash-gap-marker')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('#day-detail-title').textContent).toContain(
      '20 августа 2026',
    );
    expect(fixture.nativeElement.querySelector('.day-detail').textContent).toContain('Аренда');
    expect(fixture.nativeElement.querySelector('.day-detail').textContent).not.toContain('Возврат');
    const timelineEvents = [
      ...fixture.nativeElement.querySelectorAll('.timeline-event'),
    ] as HTMLButtonElement[];
    expect(timelineEvents[0].getAttribute('aria-pressed')).toBe('true');
    expect(timelineEvents[1].getAttribute('aria-pressed')).toBe('false');
  });

  it('uses one tab stop and arrow-key navigation for chart points', async () => {
    flushInitial();
    http.expectOne('/api/v1/forecast?horizon=month&balance_mode=free').flush(FORECAST);
    fixture.detectChanges();

    const points = [
      ...fixture.nativeElement.querySelectorAll('.chart-point'),
    ] as HTMLButtonElement[];
    expect(points.filter((point) => point.tabIndex === 0)).toHaveLength(1);
    points[1].dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight' }));
    await fixture.whenStable();
    fixture.detectChanges();

    expect(points[2].getAttribute('aria-pressed')).toBe('true');
    expect(points[2].tabIndex).toBe(0);
  });

  function flushInitial(fundForecast: object = FUND_FORECAST): void {
    fixture.detectChanges();
    http.expectOne('/api/v1/scheduling/materialize').flush({
      horizon_from: '2026-08-12',
      horizon_to: '2027-08-12',
      created: 0,
      updated: 0,
      cancelled: 0,
    });
    http
      .expectOne('/api/v1/accounts')
      .flush([{ id: 'account-1', name: 'Основной', archived: false }]);
    http.expectOne('/api/v1/settings').flush({ base_currency: 'RUB' });
    http.expectOne('/api/v1/forecast/funds?horizon=month').flush(fundForecast);
  }
});

function noRiskForecast() {
  return {
    ...FORECAST,
    ending_balance: '100.0000',
    minimum_balance: '100.0000',
    minimum_on: '2026-08-12',
    first_negative_on: null,
    first_negative_balance: null,
    expected_income: '0',
    expected_expense: '0',
    overdue_excluded_count: 0,
    points: [
      FORECAST.points[0],
      {
        ...FORECAST.points[0],
        period_from: '2026-09-12',
        on: '2026-09-12',
      },
    ],
  };
}
