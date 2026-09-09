import { DOCUMENT } from '@angular/common';
import { TestBed } from '@angular/core/testing';
import { en } from './en';
import { ru } from './ru';
import {
  LanguageService,
  LANGUAGE_STORAGE_KEY,
  language,
  localizedSignal,
  plural,
  t,
  TranslationKey,
} from './i18n';
import { formatMoney, formatPercentageBreakdown } from '../shared/money.pipe';
import { decimalPayload, moneyExpressionPayload } from '../shared/decimal-input';
import { formatTextDate, formatTextTimestamp } from '../shared/date-text.pipe';

describe('multilingual contract', () => {
  afterEach(() => {
    language.set('ru');
    localStorage.removeItem(LANGUAGE_STORAGE_KEY);
    vi.restoreAllMocks();
  });

  it('has complete catalogs with matching parameters and no untranslated English entries', () => {
    expect(Object.keys(en).sort()).toEqual(Object.keys(ru).sort());
    for (const key of Object.keys(ru) as TranslationKey[]) {
      expect(en[key].trim(), key).not.toBe('');
      expect(en[key], key).not.toMatch(/[А-Яа-яЁё]/);
      const parameters = (value: string) => [...new Set(value.match(/\{\w+\}/g) ?? [])].sort();
      expect(parameters(en[key]), key).toEqual(parameters(ru[key]));
    }
  });

  it('defaults to Russian, persists explicit selection and updates accessible document metadata', () => {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, 'unsupported');
    const service = TestBed.inject(LanguageService);
    TestBed.tick();
    expect(service.language()).toBe('ru');
    service.select('en');
    TestBed.tick();
    expect(document.documentElement.lang).toBe('en');
    expect(document.title).toBe('Hermes — personal finance');
    expect(localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe('en');
    TestBed.resetTestingModule();
    expect(TestBed.inject(LanguageService).language()).toBe('en');
  });

  it('keeps switching when browser storage is unavailable', () => {
    const unavailableStorage = {
      getItem: () => {
        throw Error('blocked');
      },
      setItem: () => {
        throw Error('blocked');
      },
    };
    TestBed.configureTestingModule({
      providers: [
        {
          provide: DOCUMENT,
          useValue: {
            defaultView: { localStorage: unavailableStorage },
            documentElement: { lang: '' },
            title: '',
          },
        },
      ],
    });
    const service = TestBed.inject(LanguageService);
    service.select('en');
    expect(t('forecast.account')).toBe('Account');
    expect(() => TestBed.tick()).not.toThrow();
  });

  it('uses a readable Russian fallback and does not recursively interpret user parameters', () => {
    language.set('en');
    const original = en['forecast.account'];
    delete (en as Partial<typeof en>)['forecast.account'];
    try {
      expect(t('forecast.account')).toBe('Счёт');
    } finally {
      en['forecast.account'] = original;
    }
    expect(t('missing.key' as TranslationKey)).toBe('Сообщение недоступно.');
    expect(t('funds.archiveFundP0ThisIsOnlyPossible', { p0: '<script>{p1}</script>' })).toContain(
      '<script>{p1}</script>',
    );
  });

  it('re-renders existing notices with their original parameters after switching', () => {
    const notice = localizedSignal();
    notice.set(() =>
      t('operations.oneOffOperationScheduledForP0', { p0: formatTextDate('2026-09-09') }),
    );
    expect(notice()).toContain('9 сентября 2026');
    language.set('en');
    expect(notice()).toBe('One-off operation scheduled for 9 September 2026.');
    notice.set(null);
    expect(notice()).toBeNull();
  });

  it.each([0, 1, 2, 5, 11, 21])('uses platform plural rules for %s operations', (count) => {
    const forms = {
      one: 'common.operationsOne',
      few: 'common.operationsFew',
      many: 'common.operationsMany',
      other: 'common.operationsOther',
    } as const;
    language.set('ru');
    expect(plural(count, forms)).toBe(
      `${count} ${count === 1 || count === 21 ? 'операция' : count === 2 ? 'операции' : 'операций'}`,
    );
    language.set('en');
    expect(plural(count, forms)).toBe(`${count} ${count === 1 ? 'operation' : 'operations'}`);
  });

  it.each(['ru', 'en'] as const)('preserves exact financial contracts in %s', (selected) => {
    language.set(selected);
    expect(formatMoney('9999999999999999.9950')).toBe('10 000 000 000 000 000,00');
    expect(formatMoney('-1.0050')).toBe('-1,01');
    expect(formatPercentageBreakdown(['33.3333', '33.3333', '33.3334'])).toEqual([
      '33,33',
      '33,33',
      '33,34',
    ]);
    expect(decimalPayload('100 000,1234')).toBe('100000.1234');
    expect(moneyExpressionPayload('1000,1234 + 2.0001')).toBe('1002.1235');
    expect(formatTextDate('2024-02-29')).toBe(
      selected === 'ru' ? '29 февраля 2024' : '29 February 2024',
    );
    expect(formatTextDate('2026-01-01')).toBe(
      selected === 'ru' ? '1 января 2026' : '1 January 2026',
    );
    expect(formatTextTimestamp('2026-09-09T12:34:00Z')).toMatch(
      selected === 'ru' ? /^9 сентября 2026, \d{2}:\d{2}$/ : /^9 September 2026, \d{2}:\d{2}$/,
    );
  });
});
