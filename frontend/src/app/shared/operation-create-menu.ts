import { t } from '../i18n/i18n';
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  EventEmitter,
  Input,
  Output,
  inject,
  signal,
} from '@angular/core';
import { Router } from '@angular/router';

export type CreateOperationType = 'expense' | 'income' | 'transfer' | 'balance_adjustment';

@Component({
  selector: 'app-operation-create-menu',
  templateUrl: './operation-create-menu.html',
  styleUrl: './operation-create-menu.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    '(focusout)': 'focusOut($event)',
    '(keydown.escape)': 'closeAndFocusTrigger($event)',
  },
})
export class OperationCreateMenu {
  protected readonly t = t;
  private readonly host: ElementRef<HTMLElement> = inject(ElementRef);
  private readonly router = inject(Router);

  @Input() navigate = false;
  @Output() readonly selected = new EventEmitter<CreateOperationType>();
  protected readonly open = signal(false);
  protected get items(): readonly { type: CreateOperationType; label: string; hint: string }[] {
    return [
      {
        type: 'expense',
        label: t('operation-create-menu.expense'),
        hint: t('operation-create-menu.debitAnAccount'),
      },
      {
        type: 'income',
        label: t('operation-create-menu.income'),
        hint: t('operation-create-menu.creditAnAccount'),
      },
      {
        type: 'transfer',
        label: t('operation-create-menu.transfer'),
        hint: t('operation-create-menu.betweenAccounts'),
      },
      {
        type: 'balance_adjustment',
        label: t('operation-create-menu.adjustment'),
        hint: t('operation-create-menu.correctABalance'),
      },
    ];
  }

  protected toggle(): void {
    this.open.update((value) => !value);
  }

  protected openFromKeyboard(event: KeyboardEvent, last = false): void {
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
    event.preventDefault();
    this.open.set(true);
    setTimeout(() => {
      const items = this.menuItems();
      items[last || event.key === 'ArrowUp' ? items.length - 1 : 0]?.focus();
    });
  }

  protected moveFocus(event: KeyboardEvent): void {
    const items = this.menuItems();
    const current = items.indexOf(event.currentTarget as HTMLButtonElement);
    let next: number | null = null;
    if (event.key === 'ArrowDown') next = (current + 1) % items.length;
    if (event.key === 'ArrowUp') next = (current - 1 + items.length) % items.length;
    if (event.key === 'Home') next = 0;
    if (event.key === 'End') next = items.length - 1;
    if (next === null) return;
    event.preventDefault();
    items[next]?.focus();
  }

  protected choose(type: CreateOperationType): void {
    this.open.set(false);
    if (this.navigate) {
      void this.router.navigate(['/operations'], { queryParams: { new: type } });
      return;
    }
    this.selected.emit(type);
  }

  protected focusOut(event: FocusEvent): void {
    const next = event.relatedTarget as Node | null;
    if (!next || !this.host.nativeElement.contains(next)) this.open.set(false);
  }

  protected closeAndFocusTrigger(event: Event): void {
    if (!this.open()) return;
    event.preventDefault();
    this.open.set(false);
    this.host.nativeElement.querySelector<HTMLButtonElement>('.create-menu-trigger')?.focus();
  }

  private menuItems(): HTMLButtonElement[] {
    return Array.from(
      this.host.nativeElement.querySelectorAll<HTMLButtonElement>('[role="menuitem"]'),
    );
  }
}
