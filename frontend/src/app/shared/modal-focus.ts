import { DOCUMENT } from '@angular/common';
import {
  AfterViewInit,
  Directive,
  ElementRef,
  EventEmitter,
  HostListener,
  OnDestroy,
  Output,
  inject,
} from '@angular/core';

const FOCUSABLE = [
  'button:not([disabled])',
  'a[href]',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

@Directive({
  selector: '[appModalFocus]',
  standalone: true,
})
export class ModalFocus implements AfterViewInit, OnDestroy {
  @Output() readonly modalEscape = new EventEmitter<void>();

  private readonly element = inject<ElementRef<HTMLElement>>(ElementRef).nativeElement;
  private readonly document = inject(DOCUMENT);
  private readonly opener = this.document.activeElement as HTMLElement | null;
  private readonly containFocus = (event: FocusEvent): void => {
    if (event.target instanceof Node && !this.element.contains(event.target)) {
      this.focusInitial();
    }
  };

  ngAfterViewInit(): void {
    this.document.addEventListener('focusin', this.containFocus);
    queueMicrotask(() => this.focusInitial());
  }

  ngOnDestroy(): void {
    this.document.removeEventListener('focusin', this.containFocus);
    if (this.opener?.isConnected) queueMicrotask(() => this.opener?.focus());
  }

  @HostListener('keydown', ['$event'])
  protected handleKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      event.preventDefault();
      event.stopPropagation();
      this.modalEscape.emit();
      return;
    }
    if (event.key !== 'Tab') return;
    const controls = this.focusableControls();
    if (!controls.length) {
      event.preventDefault();
      this.element.focus();
      return;
    }
    const first = controls[0];
    const last = controls.at(-1)!;
    if (event.shiftKey && this.document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && this.document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  private focusInitial(): void {
    const preferred = this.element.querySelector<HTMLElement>('[data-modal-initial-focus]');
    (preferred ?? this.element).focus();
  }

  private focusableControls(): HTMLElement[] {
    return Array.from(this.element.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
      (item) => !item.hidden && item.getAttribute('aria-hidden') !== 'true',
    );
  }
}
