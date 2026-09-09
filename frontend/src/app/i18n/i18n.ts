import { DOCUMENT } from '@angular/common';
import { computed, effect, inject, Injectable, signal } from '@angular/core';

import { ru } from './ru';
import { en } from './en';

export type Language = 'ru' | 'en';
export type TranslationKey = keyof typeof ru;
export type Parameters = Readonly<Record<string, string | number | null | undefined>>;
export type MessageFactory = () => string;
export const LANGUAGE_STORAGE_KEY = 'hermes-language';
export const language = signal<Language>('ru');
export const locale = (): string => (language() === 'en' ? 'en-GB' : 'ru-RU');

export function t(key: TranslationKey, parameters: Parameters = {}): string {
  const catalog: Partial<Record<TranslationKey, string>> = language() === 'en' ? en : ru;
  const text = catalog[key] ?? ru[key] ?? ru['common.translationUnavailable'];
  return text.replace(/\{(\w+)\}/g, (_, name: string) => String(parameters[name] ?? '—'));
}

/** Keep the message recipe so existing errors and notices react to language changes. */
export function localizedSignal() {
  const recipe = signal<MessageFactory | null>(null);
  const value = computed(() => recipe()?.() ?? null);
  return Object.assign(value, { set: (message: MessageFactory | null) => recipe.set(message) });
}

export function plural(
  count: number,
  forms: {
    one: TranslationKey;
    few?: TranslationKey;
    many?: TranslationKey;
    other: TranslationKey;
  },
): string {
  const category = new Intl.PluralRules(locale()).select(count);
  const key =
    category === 'one'
      ? forms.one
      : category === 'few'
        ? forms.few
        : category === 'many'
          ? forms.many
          : forms.other;
  return t(key ?? forms.other, { count });
}

@Injectable({ providedIn: 'root' })
export class LanguageService {
  private readonly document = inject(DOCUMENT);
  readonly language = language.asReadonly();

  constructor() {
    let saved: string | null = null;
    try {
      saved = this.document.defaultView?.localStorage.getItem(LANGUAGE_STORAGE_KEY) ?? null;
    } catch {
      /* Browser storage is optional. */
    }
    language.set(saved === 'en' ? 'en' : 'ru');
    effect(() => {
      this.document.documentElement.lang = language();
      this.document.title = t('common.documentTitle');
    });
  }

  select(value: string): void {
    const selected = value === 'en' ? 'en' : 'ru';
    language.set(selected);
    try {
      this.document.defaultView?.localStorage.setItem(LANGUAGE_STORAGE_KEY, selected);
    } catch {
      /* Keep this session's choice in memory. */
    }
  }
}
