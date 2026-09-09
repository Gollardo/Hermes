import { HttpErrorResponse } from '@angular/common/http';
import { apiErrorMessage } from './api-error';
import { language, localizedSignal, t } from '../i18n/i18n';

describe('localized API errors', () => {
  afterEach(() => language.set('ru'));
  it.each(['ru', 'en'] as const)('keeps safe code and status fallbacks in %s', (selected) => {
    language.set(selected);
    for (const status of [0, 401, 403, 409, 422, 429, 500, 503]) {
      const text = apiErrorMessage(
        new HttpErrorResponse({
          status,
          error: { detail: { code: 'unknown', message: 'SECRET <script>' } },
        }),
        () => t('accounts.couldNotSaveTheAccount'),
      );
      expect(text).not.toContain('SECRET');
      expect(text).not.toContain('<script>');
      expect(text.length).toBeGreaterThan(10);
      if (selected === 'en') expect(text).not.toMatch(/[А-Яа-я]/);
    }
    expect(
      apiErrorMessage(new Error('SECRET'), () => t('accounts.couldNotSaveTheAccount')),
    ).not.toContain('SECRET');
  });
  it('localizes existing structured errors after switching and keeps backup failure non-diagnostic', () => {
    const error = new HttpErrorResponse({
      status: 400,
      error: { detail: { code: 'backup_authentication_failed', message: 'wrong key' } },
    });
    const state = localizedSignal();
    state.set(() => apiErrorMessage(error, 'fallback'));
    expect(state()).toContain('Пароль неверен или файл повреждён');
    language.set('en');
    expect(state()).toContain('password is incorrect or the file is damaged');
    expect(state()).not.toContain('wrong key');
  });
  it('maps safe validation field/type metadata without exposing input or arbitrary field names', () => {
    language.set('en');
    const response = (loc: unknown, type: string) =>
      new HttpErrorResponse({
        status: 422,
        error: { detail: [{ loc, type, input: 'SECRET', msg: 'SECRET' }] },
      });
    expect(apiErrorMessage(response(['body', 'master_password'], 'missing'), 'fallback')).toBe(
      'Complete “Master password”.',
    );
    expect(
      apiErrorMessage(response(['body', 'category_template_language'], 'enum'), 'fallback'),
    ).toBe('Choose a valid value for “New category language”.');
    expect(apiErrorMessage(response(['body', 'SECRET'], 'value_error'), 'fallback')).toBe(
      'Check the completed fields and try again.',
    );
  });
});
