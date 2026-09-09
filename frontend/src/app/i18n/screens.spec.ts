import { Type } from '@angular/core';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { AccountsPage } from '../pages/accounts/accounts';
import { CategoriesPage } from '../pages/categories/categories';
import { FundsPage } from '../pages/funds/funds';
import { ForecastPage } from '../pages/forecast/forecast';
import { HomePage } from '../pages/home/home';
import { OperationsPage } from '../pages/operations/operations';
import { ReportsPage } from '../pages/reports/reports';
import { SchedulingPage } from '../pages/scheduling/scheduling';
import { SettingsPage } from '../pages/settings/settings';
import { BackendStatusPage } from '../pages/backend-status/backend-status';
import { language, LANGUAGE_STORAGE_KEY } from './i18n';

const pages: [Type<unknown>, string][] = [
  [AccountsPage, 'Accounts'],
  [CategoriesPage, 'Categories'],
  [FundsPage, 'Funds'],
  [ForecastPage, 'Balance forecast'],
  [HomePage, 'Your money now'],
  [OperationsPage, 'Operation journal'],
  [ReportsPage, 'Income and expenses'],
  [SchedulingPage, 'Calendar'],
  [SettingsPage, 'Settings'],
  [BackendStatusPage, 'Backend availability'],
];

describe('language switching across implemented pages', () => {
  afterEach(() => {
    language.set('ru');
    localStorage.removeItem(LANGUAGE_STORAGE_KEY);
  });
  it.each(pages)(
    'updates a page and its failure state without new API calls',
    async (page, heading) => {
      localStorage.removeItem(LANGUAGE_STORAGE_KEY);
      language.set('ru');
      await TestBed.configureTestingModule({
        imports: [page],
        providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
      }).compileComponents();
      const fixture = TestBed.createComponent(page);
      const http = TestBed.inject(HttpTestingController);
      fixture.detectChanges();
      const failPending = () =>
        http
          .match(() => true)
          .forEach(
            (request) =>
              !request.cancelled &&
              request.flush(
                { detail: { code: 'unavailable' } },
                { status: 503, statusText: 'Unavailable' },
              ),
          );
      failPending();
      fixture.detectChanges();
      failPending();
      fixture.detectChanges();
      language.set('en');
      fixture.detectChanges();
      const element = fixture.nativeElement as HTMLElement;
      expect(element.textContent).toContain(heading);
      expect(element.textContent?.replace('Русский', '')).not.toMatch(/[А-Яа-яЁё]/);
      for (const control of element.querySelectorAll('[aria-label],[title],[placeholder]')) {
        for (const attribute of ['aria-label', 'title', 'placeholder'])
          expect(control.getAttribute(attribute) ?? '').not.toMatch(/[А-Яа-яЁё]/);
      }
      http.expectNone(() => true);
      language.set('ru');
      fixture.detectChanges();
      expect(element.textContent).toMatch(/[А-Яа-яЁё]/);
      http.verify();
    },
  );
});
