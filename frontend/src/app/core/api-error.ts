import { HttpErrorResponse } from '@angular/common/http';
import { t } from '../i18n/i18n';

export function apiErrorMessage(error: unknown, fallback: string | (() => string)): string {
  if (!(error instanceof HttpErrorResponse)) {
    return typeof fallback === 'function' ? fallback() : fallback;
  }
  const detail: unknown = error.error?.detail;
  if (error.status === 0) return t('errors.network');
  if (Array.isArray(detail)) {
    const issue = detail[0] as { loc?: unknown; type?: unknown } | undefined;
    const fields = {
      master_password: 'login.masterPassword',
      base_currency: 'settings.baseCurrency',
      timezone: 'settings.timezone',
      category_template_language: 'setup.templateLanguage',
      amount: 'funds.amount',
      name: 'accounts.name',
      description: 'accounts.description',
      confirmation: 'settings.typeReplaceAllData',
      backup_password: 'settings.protectedBackupPassword',
      account_id: 'forecast.account',
      category_id: 'operations.category',
      occurred_on: 'operations.postingDate',
      due_on: 'operations.plannedDate',
    } as const;
    const field = Array.isArray(issue?.loc) ? issue.loc.at(-1) : undefined;
    if (typeof field !== 'string' || !(field in fields)) return t('errors.validationRequest');
    const type = issue?.type;
    return t(
      type === 'missing'
        ? 'errors.validationRequired'
        : type === 'enum' || type === 'literal_error'
          ? 'errors.validationChoice'
          : 'errors.validationInvalid',
      { field: t(fields[field as keyof typeof fields]) },
    );
  }

  if (
    typeof detail === 'object' &&
    detail !== null &&
    'code' in detail &&
    typeof detail.code === 'string'
  ) {
    const localized: Record<string, string> = {
      future_operation_requires_plan: t('errors.futureOperation'),
      invalid_default_account: t('errors.defaultAccount'),
      invalid_period: t('errors.period'),
      already_initialized: t('auth.initialSetupIsAlreadyComplete'),
      authentication_required: t('auth.yourSessionHasEndedSignInAgain'),
      base_currency_locked: t('auth.theBaseCurrencyCanNoLongerBe'),
      timezone_locked_by_schedule: t('auth.theTimezoneCannotChangeAfterRecurringRules'),
      account_has_history: t('auth.anAccountWithOperationHistoryCannotBe'),
      account_not_found: t('auth.accountNotFound'),
      archived_fund_balance: t('auth.thisChangeWouldReturnMoneyToAn'),
      category_has_active_children: t('auth.archiveTheActiveSubcategoriesFirst'),
      category_not_found: t('auth.categoryNotFound'),
      category_type_has_history: t('auth.aCategoryWithFinancialHistoryCannotChange'),
      csrf_failed: t('auth.theSecurityTokenHasExpiredRefreshThe'),
      current_password_invalid: t('auth.theCurrentMasterPasswordIsIncorrect'),
      invalid_credentials: t('auth.incorrectMasterPassword'),
      invalid_category_parent: t('auth.theParentMustBeAnActiveCategory'),
      invalid_account_reference: t('auth.theSelectedAccountIsUnavailableForA'),
      invalid_category_reference: t('auth.theSelectedCategoryIsUnavailableOrHas'),
      insufficient_balance: t('auth.insufficientAccountBalanceNegativeBalancesAreNot'),
      fund_not_found: t('auth.fundNotFoundOrArchived'),
      invalid_fund_reference: t('auth.theSelectedFundIsUnavailableForA'),
      fund_conflict: t('auth.theFundChangedInAnotherTabRefresh'),
      fund_percentage_limit: t('auth.activeFundPercentagesCannotTotalMoreThan'),
      fund_allocation_unavailable: t('auth.allocationWasNotCompletedSetAPositive'),
      dynamic_fund_targets_required: t('auth.dynamicModeRequiresATargetForEvery'),
      fund_has_balance: t('auth.aFundCanOnlyBeArchivedWhen'),
      insufficient_fund_balance: t('auth.insufficientMoneyInTheSelectedFundOn'),
      insufficient_free_balance: t('auth.insufficientFreeBalanceOnThisAccountTo'),
      login_rate_limited: t('auth.tooManyUnsuccessfulAttemptsTrySigningIn'),
      operation_conflict: t('auth.theOperationChangedInAnotherTabRefresh'),
      operation_not_found: t('auth.operationNotFound'),
      operation_linked_to_occurrence: t('auth.aConfirmedCalendarOperationCannotBeDeleted'),
      operation_linked_to_allocation: t('auth.aTransferWithFundAllocationCannotBe'),
      recurring_rule_not_found: t('auth.recurringRuleNotFound'),
      expected_occurrence_not_found: t('auth.plannedOperationNotFound'),
      forecast_account_not_found: t('auth.forecastAccountNotFound'),
      scheduling_conflict: t('auth.theScheduleChangedInAnotherTabRefresh'),
      invalid_occurrence_transition: t('auth.thisActionIsNoLongerAvailableFor'),
      confirmation_invalid: t('auth.theConfirmationPhraseDoesNotMatchNo'),
      backup_too_large: t('auth.theBackupExceedsTheSizeLimit'),
      backup_authentication_failed: t('auth.couldNotDecryptTheBackupThePassword'),
      invalid_hermes_file: t('auth.theHermesBackupStructureIsInvalid'),
      unsupported_hermes_version: t('auth.thisHermesBackupVersionIsNotSupported'),
      invalid_kdf_parameters: t('auth.theHermesBackupProtectionParametersAreInvalid'),
      invalid_backup_payload: t('auth.theDecryptedBackupDataIsDamagedOr'),
      invalid_backup: t('auth.theBackupIsDamagedIncompatibleOrViolates'),
    };
    if (localized[detail.code]) return localized[detail.code];
  }
  if (error.status === 401) return t('auth.yourSessionHasEndedSignInAgain');
  if (error.status === 403) return t('errors.forbidden');
  if (error.status === 429) return t('auth.tooManyUnsuccessfulAttemptsTrySigningIn');
  if (error.status === 422) return t('errors.validationRequest');
  return typeof fallback === 'function' ? fallback() : fallback;
}
