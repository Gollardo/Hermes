import { ChangeDetectionStrategy, Component, inject, input, output } from '@angular/core';
import { RouterLink } from '@angular/router';
import { t } from '../../i18n/i18n';
import { DateTextPipe } from '../../shared/date-text.pipe';
import { ModalFocus } from '../../shared/modal-focus';
import { MoneyPipe } from '../../shared/money.pipe';
import { UiMotion } from '../../shared/ui-motion';

export type ScheduledOperationType = 'income' | 'expense' | 'transfer';
export type ScheduledOccurrenceStatus = 'pending' | 'confirmed' | 'postponed' | 'cancelled';
export interface ScheduledOccurrence {
  id: string;
  source_kind: 'recurring' | 'one_off';
  rule_id: string | null;
  scheduled_on: string;
  due_on: string;
  status: ScheduledOccurrenceStatus;
  manually_modified: boolean;
  series_shift_days: number;
  overdue: boolean;
  type: ScheduledOperationType;
  amount: string;
  description: string | null;
  preserve_from_series_shift: boolean;
  account_id: string;
  account_name: string;
  destination_account_id: string | null;
  destination_account_name: string | null;
  category_id: string | null;
  category_name: string | null;
  allocate_to_funds: boolean;
  actual_operation_id: string | null;
  version: number;
}
export interface ScheduledCalendarDay {
  iso: string;
  occurrences: ScheduledOccurrence[];
}

@Component({
  selector: 'app-calendar-day-dialog',
  imports: [RouterLink, DateTextPipe, MoneyPipe, ModalFocus],
  templateUrl: './calendar-day-dialog.html',
  styleUrl: './calendar-day-dialog.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CalendarDayDialog {
  protected readonly t = t;
  protected readonly motion = inject(UiMotion);
  readonly day = input.required<ScheduledCalendarDay>();
  readonly baseCurrency = input.required<string>();
  readonly closed = output<void>();
  readonly occurrenceSelected = output<ScheduledOccurrence>();

  protected occurrenceTitle(item: ScheduledOccurrence): string {
    return item.description?.trim() || this.typeLabel(item.type);
  }
  protected typeLabel(type: ScheduledOperationType): string {
    return {
      income: t('operation-create-menu.income'),
      expense: t('operation-create-menu.expense'),
      transfer: t('operation-create-menu.transfer'),
    }[type];
  }
  protected statusLabel(status: ScheduledOccurrenceStatus): string {
    return {
      pending: t('scheduling.pending'),
      confirmed: t('scheduling.confirmed'),
      postponed: t('scheduling.postponed'),
      cancelled: t('scheduling.cancelled'),
    }[status];
  }
}
