import { t } from '../i18n/i18n';
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Input,
  OnChanges,
  forwardRef,
  inject,
  signal,
} from '@angular/core';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';

export interface EntityOption {
  id: string;
  label: string;
  detail?: string;
  searchText?: string;
  disabled?: boolean;
}

@Component({
  selector: 'app-entity-combobox',
  templateUrl: './entity-combobox.html',
  styleUrl: './entity-combobox.css',
  providers: [
    { provide: NG_VALUE_ACCESSOR, useExisting: forwardRef(() => EntityCombobox), multi: true },
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { '(focusout)': 'handleFocusOut($event)' },
})
export class EntityCombobox implements ControlValueAccessor, OnChanges {
  protected readonly t = t;
  private static nextId = 0;
  private readonly host = inject(ElementRef<HTMLElement>);
  protected value = '';
  private onChange: (value: string) => void = () => undefined;
  private onTouched: () => void = () => undefined;

  @Input() options: EntityOption[] = [];
  @Input() inputId = `entity-input-${EntityCombobox.nextId++}`;
  @Input() accessibleLabel: string | null = null;
  @Input() placeholder: string | null = null;
  @Input() recentKey = 'entities';
  @Input() emptyLabel: string | null = null;
  @Input() allowEmpty = false;
  @Input() matchMode: 'prefix' | 'contains' = 'prefix';
  protected readonly query = signal('');
  protected readonly open = signal(false);
  protected readonly disabled = signal(false);
  protected readonly activeIndex = signal(-1);
  protected readonly optionsId = `entity-options-${EntityCombobox.nextId++}`;

  protected visibleOptions(): EntityOption[] {
    const query = normalize(this.query());
    if (query) {
      return this.options.filter((option) => {
        const searchText = normalize(option.searchText ?? option.label);
        return this.matchMode === 'contains'
          ? searchText.includes(query)
          : searchText.startsWith(query);
      });
    }
    const recent = this.readRecent();
    return recent
      .map((id) => this.options.find((option) => option.id === id))
      .filter((option): option is EntityOption => Boolean(option))
      .slice(0, 5);
  }

  protected emptyMessage(): string {
    return this.query().trim()
      ? (this.emptyLabel ?? t('entity-combobox.noMatchesFound'))
      : t('entity-combobox.startTypingAName');
  }

  protected activeOptionId(): string | null {
    if (!this.open()) return null;
    const option = this.visibleOptions()[this.activeIndex()];
    return option ? this.optionId(option.id) : null;
  }

  protected optionId(id: string): string {
    return `${this.optionsId}-${id}`;
  }

  protected input(event: Event): void {
    this.query.set((event.target as HTMLInputElement).value);
    this.activeIndex.set(-1);
    this.open.set(true);
    if (this.value) {
      this.value = '';
      this.onChange('');
    }
  }

  protected focus(event: FocusEvent): void {
    if (!this.disabled()) {
      this.open.set(true);
      (event.target as HTMLInputElement).select();
    }
  }

  protected select(option: EntityOption): void {
    if (this.disabled() || option.disabled) return;
    this.value = option.id;
    this.query.set(option.label);
    this.open.set(false);
    this.onChange(option.id);
    this.onTouched();
    this.saveRecent(option.id);
  }

  protected clear(): void {
    if (this.disabled()) return;
    this.value = '';
    this.query.set('');
    this.onChange('');
    this.open.set(true);
  }

  protected keydown(event: KeyboardEvent): void {
    const options = this.visibleOptions();
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      this.open.set(true);
      this.activeIndex.set(this.nextEnabledIndex(options, 1));
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      this.open.set(true);
      this.activeIndex.set(this.nextEnabledIndex(options, -1));
    } else if (
      event.key === 'Enter' &&
      this.open() &&
      this.activeIndex() >= 0 &&
      options[this.activeIndex()]
    ) {
      event.preventDefault();
      this.select(options[this.activeIndex()]);
    } else if (event.key === 'Escape') {
      this.open.set(false);
    }
  }

  protected handleFocusOut(event: FocusEvent): void {
    const next = event.relatedTarget as Node | null;
    if (!next || !this.host.nativeElement.contains(next)) {
      this.open.set(false);
      this.onTouched();
      if (!this.value) this.query.set('');
    }
  }

  writeValue(value: string | null): void {
    this.value = value ?? '';
    this.query.set(this.options.find((option) => option.id === this.value)?.label ?? '');
  }

  ngOnChanges(): void {
    if (this.value) {
      this.query.set(this.options.find((option) => option.id === this.value)?.label ?? '');
    }
  }

  registerOnChange(fn: (value: string) => void): void {
    this.onChange = fn;
  }
  registerOnTouched(fn: () => void): void {
    this.onTouched = fn;
  }
  setDisabledState(disabled: boolean): void {
    this.disabled.set(disabled);
  }

  private readRecent(): string[] {
    try {
      const value: unknown = JSON.parse(
        localStorage.getItem(`hermes-recent-${this.recentKey}`) ?? '[]',
      );
      return Array.isArray(value)
        ? value.filter((item): item is string => typeof item === 'string').slice(0, 5)
        : [];
    } catch {
      return [];
    }
  }

  private saveRecent(id: string): void {
    try {
      localStorage.setItem(
        `hermes-recent-${this.recentKey}`,
        JSON.stringify([id, ...this.readRecent().filter((item) => item !== id)].slice(0, 5)),
      );
    } catch {
      /* Storage may be unavailable in privacy mode. */
    }
  }

  private nextEnabledIndex(options: EntityOption[], direction: 1 | -1): number {
    if (!options.length) return -1;
    let index = this.activeIndex();
    if (index < 0 || index >= options.length) index = direction === 1 ? -1 : 0;
    const candidates = Array.from(
      { length: options.length },
      (_, offset) => (index + direction * (offset + 1) + options.length) % options.length,
    );
    return candidates.find((candidate) => !options[candidate].disabled) ?? -1;
  }
}

function normalize(value: string): string {
  return value
    .trim()
    .replace(/^[^\p{L}\p{N}]+/u, '')
    .toLocaleLowerCase('ru-RU');
}
