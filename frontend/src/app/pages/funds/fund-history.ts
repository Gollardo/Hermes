import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
import { RouterLink } from '@angular/router';

import { t } from '../../i18n/i18n';
import { DateTextPipe } from '../../shared/date-text.pipe';
import { MoneyPipe } from '../../shared/money.pipe';

export interface FundMovement {
  fund_id: string;
  fund_name: string;
  account_id: string;
  account_name: string;
  amount: string;
}

export interface FundEvent {
  caused_by_operation_id?: string | null;
  id: string;
  type:
    | 'allocation'
    | 'redistribution'
    | 'fund_transfer'
    | 'reserve_distribution'
    | 'reserve_release'
    | 'fund_release'
    | 'expense'
    | 'transfer';
  occurred_on: string;
  description: string | null;
  movements: FundMovement[];
  reserve_movements: {
    account_id: string;
    account_name: string;
    amount: string;
  }[];
}

@Component({
  selector: 'app-fund-history',
  imports: [RouterLink, DateTextPipe, MoneyPipe],
  templateUrl: './fund-history.html',
  styleUrl: './fund-history.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FundHistory {
  protected readonly t = t;
  readonly events = input.required<FundEvent[]>();
  readonly page = input.required<number>();
  readonly pageSize = input.required<number>();
  readonly total = input.required<number>();
  readonly baseCurrency = input.required<string>();
  readonly previousPage = output<void>();
  readonly nextPage = output<void>();
  protected readonly Math = Math;

  protected eventLabel(event: FundEvent): string {
    return {
      allocation: t('funds.allocation'),
      redistribution: t('funds.reallocation'),
      fund_transfer: t('funds.transferBetweenFunds0368'),
      reserve_distribution: t('funds.automaticContributionFromReserve'),
      reserve_release: t('funds.reserveRelease'),
      fund_release: t('funds.releaseTitle'),
      expense: t('funds.fundExpense'),
      transfer: t('funds.transferWithFund'),
    }[event.type];
  }
}
