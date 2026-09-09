import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { LanguageService, t } from './i18n';

@Component({
  selector: 'app-language-select',
  template: `<label
    >{{ t('common.interfaceLanguage') }}
    <select [value]="service.language()" (change)="service.select($any($event.target).value)">
      <option value="ru">Русский</option>
      <option value="en">English</option>
    </select>
  </label>`,
  styles: `
    :host {
      display: block;
      margin-block: 1rem;
    }
    label {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 0.75rem;
    }
    select {
      width: auto;
      max-width: 100%;
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LanguageSelect {
  protected readonly service = inject(LanguageService);
  protected readonly t = t;
}
