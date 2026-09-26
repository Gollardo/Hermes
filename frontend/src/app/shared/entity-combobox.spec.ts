import { Component, ViewChild, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { FormControl, ReactiveFormsModule } from '@angular/forms';

import { EntityCombobox, EntityOption } from './entity-combobox';

@Component({
  imports: [ReactiveFormsModule, EntityCombobox],
  template: `
    <app-entity-combobox
      [formControl]="control"
      [options]="options"
      recentKey="test-options"
      [allowEmpty]="true"
      [emptySelectionLabel]="emptySelectionLabel()"
    />
  `,
})
class ComboboxHost {
  @ViewChild(EntityCombobox) combobox!: EntityCombobox;
  readonly emptySelectionLabel = signal<string | null>(null);
  readonly control = new FormControl('', { nonNullable: true });
  readonly options: EntityOption[] = [
    { id: 'housing', label: '🏠 Жильё' },
    { id: 'salary', label: 'Зарплата' },
    { id: 'pets', label: '🐕 Домашние животные' },
    { id: 'travel', label: '✈️ Путешествия' },
    { id: 'health', label: '❤️ Здоровье' },
    { id: 'sport', label: '🏃 Спорт' },
    { id: 'credit', label: 'Зачисление' },
  ];
}

describe('EntityCombobox', () => {
  let fixture: ComponentFixture<ComboboxHost>;

  it('displays an empty scope without writing that label into the form value or search', () => {
    fixture.componentInstance.emptySelectionLabel.set('All accounts');
    fixture.changeDetectorRef.markForCheck();
    fixture.detectChanges();
    const input = fixture.nativeElement.querySelector('input') as HTMLInputElement;
    expect(input.value).toBe('All accounts');
    expect(fixture.componentInstance.control.value).toBe('');
    input.dispatchEvent(new FocusEvent('focus'));
    fixture.detectChanges();
    expect(input.value).toBe('');
    input.dispatchEvent(new FocusEvent('focusout', { bubbles: true }));
    fixture.detectChanges();
    expect(input.value).toBe('All accounts');
    expect(fixture.componentInstance.control.value).toBe('');
  });

  beforeEach(async () => {
    localStorage.clear();
    await TestBed.configureTestingModule({ imports: [ComboboxHost] }).compileComponents();
    fixture = TestBed.createComponent(ComboboxHost);
    fixture.detectChanges();
  });

  function focusInput(): HTMLInputElement {
    const input = fixture.nativeElement.querySelector('input') as HTMLInputElement;
    input.dispatchEvent(new Event('focus'));
    fixture.detectChanges();
    return input;
  }

  it('shows only the five most recent available options for an empty field', () => {
    localStorage.setItem(
      'hermes-recent-test-options',
      JSON.stringify(['sport', 'health', 'travel', 'pets', 'salary', 'housing']),
    );
    focusInput();

    const options = [...fixture.nativeElement.querySelectorAll('[role="option"]')];
    expect(options).toHaveLength(5);
    expect(options.map((option: Element) => option.getAttribute('data-option-id'))).toEqual([
      'sport',
      'health',
      'travel',
      'pets',
      'salary',
    ]);
  });

  it('does not pretend arbitrary directory entries are recent', () => {
    focusInput();
    expect(fixture.nativeElement.querySelectorAll('[role="option"]')).toHaveLength(0);
    expect(fixture.nativeElement.textContent).toContain('Начните вводить название');
  });

  it('finds an emoji-prefixed category by the beginning of its textual name', () => {
    const input = focusInput();
    input.value = 'жил';
    input.dispatchEvent(new Event('input'));
    fixture.detectChanges();

    const option = fixture.nativeElement.querySelector('[role="option"]') as HTMLButtonElement;
    expect(option.textContent).toContain('Жильё');
    option.click();
    expect(fixture.componentInstance.control.value).toBe('housing');
  });

  it('supports contains matching when a dense directory opts in', () => {
    fixture.componentInstance.combobox.matchMode = 'contains';
    const input = focusInput();
    input.value = 'животные';
    input.dispatchEvent(new Event('input'));
    fixture.detectChanges();

    const option = fixture.nativeElement.querySelector('[role="option"]') as HTMLButtonElement;
    expect(option.textContent).toContain('Домашние животные');
  });

  it('selects an option with a pointer without losing the open list', () => {
    const input = focusInput();
    input.value = 'зар';
    input.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    const option = fixture.nativeElement.querySelector('[role="option"]') as HTMLButtonElement;
    option.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }));
    option.click();
    expect(fixture.componentInstance.control.value).toBe('salary');
  });

  it('ignores malformed recent-option storage instead of breaking the form', () => {
    localStorage.setItem('hermes-recent-test-options', JSON.stringify({ id: 'housing' }));
    focusInput();
    expect(fixture.nativeElement.textContent).toContain('Начните вводить название');
  });

  it('skips disabled options during keyboard selection', () => {
    fixture.componentInstance.options[1].disabled = true;
    const input = focusInput();
    input.value = 'за';
    input.dispatchEvent(new Event('input'));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown' }));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
    fixture.detectChanges();

    expect(fixture.componentInstance.control.value).toBe('credit');
  });

  it('does not let the clear action mutate a disabled form control', () => {
    fixture.componentInstance.control.setValue('housing');
    fixture.componentInstance.control.disable();
    fixture.detectChanges();

    const clear = fixture.nativeElement.querySelector('.clear') as HTMLButtonElement;
    expect(clear.disabled).toBe(true);
    clear.click();
    expect(fixture.componentInstance.control.value).toBe('housing');
  });
});
