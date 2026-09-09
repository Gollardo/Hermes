import { t } from '../i18n/i18n';
import {
  AfterViewInit,
  Directive,
  ElementRef,
  HostListener,
  Input,
  OnDestroy,
  inject,
  effect,
} from '@angular/core';
import { AbstractControl, NgControl, ValidationErrors } from '@angular/forms';
import { Subscription } from 'rxjs';

import { formatMoney } from './money.pipe';

const DECIMAL = /^-?\d{1,16}(?:[.,]\d{1,4})?$/;
const MAX_MONEY_EXPRESSION_LENGTH = 512;
const MONEY_TERM = /([+-]?)(\d{1,16})(?:[.,](\d{1,4}))?/gy;
const MONEY_EXPRESSION = /^[+-]?\d{1,16}(?:[.,]\d{1,4})?(?:[+-]\d{1,16}(?:[.,]\d{1,4})?)*$/;

export function decimalPayload(value: string): string {
  return value.trim().replace(/\s/g, '').replace(',', '.');
}

/** Evaluates an exact addition/subtraction expression without binary floating point. */
export function moneyExpressionPayload(value: string): string | null {
  if (value.length > MAX_MONEY_EXPRESSION_LENGTH) return null;
  const compact = value.trim().replace(/\s/g, '');
  if (!MONEY_EXPRESSION.test(compact)) return null;
  const unsigned = compact.replace(/^[+-]/, '');
  if (!/[+-]/.test(unsigned)) {
    return decimalPayload(compact.replace(/^\+/, ''));
  }
  MONEY_TERM.lastIndex = 0;
  let total = 0n;
  let match: RegExpExecArray | null;
  while ((match = MONEY_TERM.exec(compact)) !== null) {
    const fraction = (match[3] ?? '').padEnd(4, '0');
    const units = BigInt(match[2]) * 10_000n + BigInt(fraction || '0');
    total += match[1] === '-' ? -units : units;
  }
  const absolute = total < 0n ? -total : total;
  const integer = absolute / 10_000n;
  if (integer.toString().length > 16) return null;
  const exactFraction = String(absolute % 10_000n).padStart(4, '0');
  const fraction = exactFraction.replace(/0+$/, '').padEnd(2, '0');
  return `${total < 0n ? '-' : ''}${integer}.${fraction}`;
}

export function moneyExpressionValidator(control: AbstractControl): ValidationErrors | null {
  const value = control.value;
  if (typeof value !== 'string' || !value.trim()) return null;
  return moneyExpressionPayload(value) === null ? { moneyExpression: true } : null;
}

@Directive({ selector: 'input[appDecimalInput]' })
export class DecimalInput implements AfterViewInit, OnDestroy {
  @Input() appDecimalInput: '' | 'expression' = '';
  private readonly ngControl = inject(NgControl, { optional: true });
  private readonly element = inject<ElementRef<HTMLInputElement>>(ElementRef);
  private readonly subscriptions = new Subscription();
  private focused = false;
  private readonly validationText = effect(() => {
    const input = this.element.nativeElement;
    const message =
      this.appDecimalInput === 'expression'
        ? t('decimal-input.enterAnAmountOrAnExpressionUsing')
        : t('decimal-input.enterANumberForExample100000');
    if (input.validity.customError) input.setCustomValidity(message);
  });

  ngAfterViewInit(): void {
    const input = this.element.nativeElement;
    const markEditing = (): void => {
      this.focused = true;
    };
    input.addEventListener('input', markEditing, { capture: true });
    this.subscriptions.add(() =>
      input.removeEventListener('input', markEditing, { capture: true }),
    );
    this.render(this.ngControl?.control?.value);
    const values = this.ngControl?.control?.valueChanges;
    if (values) {
      this.subscriptions.add(values.subscribe((value) => this.render(value)));
    }
  }

  ngOnDestroy(): void {
    this.subscriptions.unsubscribe();
  }

  @HostListener('focus', ['$event'])
  ungroupForEditing(event: FocusEvent): void {
    this.focused = true;
    const input = event.target as HTMLInputElement;
    const controlValue = this.ngControl?.control?.value;
    const editable =
      typeof controlValue === 'string' && controlValue.trim()
        ? decimalPayload(controlValue)
        : decimalPayload(input.value);
    this.ngControl?.control?.setValue(editable);
    input.value = editable;
  }

  @HostListener('blur', ['$event'])
  normalize(event: FocusEvent): void {
    this.focused = false;
    const input = event.target as HTMLInputElement;
    const raw = input.value.trim();
    if (!raw) {
      input.setCustomValidity('');
      this.ngControl?.control?.setValue('');
      this.ngControl?.control?.markAsTouched();
      this.ngControl?.control?.updateValueAndValidity();
      return;
    }
    const compact = raw.replace(/\s/g, '');
    const normalized =
      this.appDecimalInput === 'expression' ? normalizeExpression(raw) : normalizeDecimal(compact);
    if (normalized === null) {
      input.setCustomValidity(
        this.appDecimalInput === 'expression'
          ? t('decimal-input.enterAnAmountOrAnExpressionUsing')
          : t('decimal-input.enterANumberForExample100000'),
      );
      this.ngControl?.control?.setErrors({
        ...(this.ngControl?.control?.errors ?? {}),
        decimalFormat: true,
      });
      this.ngControl?.control?.markAsTouched();
      return;
    }
    input.setCustomValidity('');
    this.ngControl?.control?.setValue(normalized);
    this.ngControl?.control?.markAsTouched();
    this.ngControl?.control?.updateValueAndValidity();
    input.value = formatMoney(normalized);
    if (!this.ngControl?.control) {
      input.dispatchEvent(new Event('input', { bubbles: true }));
      this.focused = false;
    }
  }

  private render(value: unknown): void {
    if (this.focused || typeof value !== 'string' || !value.trim()) return;
    this.element.nativeElement.value = formatMoney(value);
  }
}

function normalizeDecimal(value: string): string | null {
  if (!DECIMAL.test(value)) return null;
  const [integer, fraction = ''] = decimalPayload(value).split('.');
  const normalizedFraction = fraction.replace(/0+$/, '').padEnd(2, '0');
  return `${BigInt(integer)}.${normalizedFraction}`;
}

function normalizeExpression(value: string): string | null {
  const evaluated = moneyExpressionPayload(value);
  return evaluated === null ? null : normalizeDecimal(evaluated);
}
