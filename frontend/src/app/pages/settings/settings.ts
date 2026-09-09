import { LanguageSelect } from '../../i18n/language-select';
import { t, localizedSignal } from '../../i18n/i18n';
import { HttpClient } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import { environment } from '../../../environments/environment';
import { AuthService } from '../../core/auth.service';
import { apiErrorMessage } from '../../core/api-error';
import { formatTextTimestamp } from '../../shared/date-text.pipe';
import { currencySymbol } from '../../shared/money.pipe';
import { EntityCombobox, EntityOption } from '../../shared/entity-combobox';

interface ApplicationSettings {
  base_currency: string;
  timezone: string;
  default_account_id: string | null;
  fund_allocation_mode: 'manual' | 'dynamic';
  base_currency_locked: boolean;
  updated_at: string;
}

interface Account {
  id: string;
  name: string;
  archived: boolean;
}

interface BackupPreview {
  format: string;
  app_version: string;
  exported_at: string;
  base_currency: string;
  timezone: string;
  integrity_verified: boolean;
  counts: Record<string, number>;
}

interface BackupDocumentEnvelope {
  exported_at?: string;
  created_at?: string;
}

const CURRENCIES = ['RUB', 'USD', 'EUR', 'GBP', 'CNY', 'JPY', 'KZT', 'TRY', 'AED', 'CHF'];
const RESTORE_CONFIRMATION = 'ЗАМЕНИТЬ ВСЕ ДАННЫЕ';

@Component({
  selector: 'app-settings-page',
  imports: [LanguageSelect, ReactiveFormsModule, EntityCombobox],
  templateUrl: './settings.html',
  styleUrl: './settings.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SettingsPage implements OnInit {
  protected readonly t = t;
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);
  private readonly formBuilder = inject(NonNullableFormBuilder);

  protected readonly currencies = CURRENCIES;
  protected readonly timezones = supportedTimezones();
  protected readonly timezoneOptions: EntityOption[] = this.timezones.map((timezone) => ({
    id: timezone,
    label: timezone,
    searchText: timezone.replaceAll('_', ' '),
  }));
  protected readonly loading = signal(true);
  protected readonly savingSettings = signal(false);
  protected readonly savingFundMode = signal(false);
  protected readonly changingPassword = signal(false);
  protected readonly settingsError = localizedSignal();
  protected readonly accountsError = localizedSignal();
  protected readonly settingsSuccess = localizedSignal();
  protected readonly fundModeError = localizedSignal();
  protected readonly fundModeSuccess = localizedSignal();
  protected readonly currentFundMode = signal<'manual' | 'dynamic'>('manual');
  protected readonly passwordError = localizedSignal();
  protected readonly passwordSuccess = localizedSignal();
  protected readonly currencyLocked = signal(false);
  protected readonly accounts = signal<Account[]>([]);
  protected readonly backupDocument = signal<unknown | null>(null);
  protected readonly backupPreview = signal<BackupPreview | null>(null);
  protected readonly backupBusy = signal(false);
  protected readonly backupError = localizedSignal();
  protected readonly backupSuccess = localizedSignal();
  protected readonly backupRequiresPassword = signal(false);
  protected get restoreConfirmation(): string {
    return t('settings.restorePhrase');
  }
  protected readonly formatTimestamp = formatTextTimestamp;
  protected readonly currencyLabel = currencySymbol;
  private selectedBackupSequence = 0;

  protected readonly settingsForm = this.formBuilder.group({
    baseCurrency: ['RUB', [Validators.required, Validators.pattern(/^[A-Za-z]{3}$/)]],
    timezone: ['UTC', Validators.required],
    defaultAccountId: this.formBuilder.control({ value: '', disabled: true }),
  });
  protected readonly fundModeForm = this.formBuilder.group({
    mode: this.formBuilder.control<'manual' | 'dynamic'>('manual'),
  });

  protected accountOptions(): EntityOption[] {
    return this.accounts()
      .filter((account) => !account.archived)
      .map((account) => ({ id: account.id, label: account.name }));
  }

  protected readonly passwordForm = this.formBuilder.group({
    currentPassword: ['', [Validators.required, Validators.maxLength(1024)]],
    newPassword: ['', [Validators.required, Validators.minLength(12), Validators.maxLength(1024)]],
    newPasswordConfirmation: ['', Validators.required],
  });

  protected readonly restoreForm = this.formBuilder.group({
    confirmation: ['', Validators.required],
    masterPassword: ['', [Validators.required, Validators.maxLength(1024)]],
    backupPassword: ['', Validators.maxLength(1024)],
  });

  protected readonly hermesExportForm = this.formBuilder.group({
    masterPassword: ['', [Validators.required, Validators.maxLength(1024)]],
  });

  ngOnInit(): void {
    this.loadSettings();
  }

  protected saveSettings(): void {
    this.settingsError.set(null);
    this.settingsSuccess.set(null);
    if (this.settingsForm.invalid) {
      this.settingsForm.markAllAsTouched();
      return;
    }
    const value = this.settingsForm.getRawValue();
    this.savingSettings.set(true);
    this.http
      .put<ApplicationSettings>(`${environment.apiBaseUrl}/settings`, {
        base_currency: value.baseCurrency,
        timezone: value.timezone,
        default_account_id: value.defaultAccountId || null,
      })
      .subscribe({
        next: (settings) => {
          this.savingSettings.set(false);
          this.applySettings(settings);
          this.settingsSuccess.set(() => t('settings.settingsSaved'));
        },
        error: (error: unknown) => {
          this.savingSettings.set(false);
          this.settingsError.set(() => apiErrorMessage(error, t('settings.couldNotSaveSettings')));
        },
      });
  }

  protected changePassword(): void {
    this.passwordError.set(null);
    this.passwordSuccess.set(null);
    if (this.passwordForm.invalid) {
      this.passwordForm.markAllAsTouched();
      return;
    }
    const value = this.passwordForm.getRawValue();
    if (value.newPassword !== value.newPasswordConfirmation) {
      this.passwordError.set(() => t('settings.theNewPasswordsDoNotMatch'));
      return;
    }
    this.changingPassword.set(true);
    this.auth
      .changePassword({
        current_password: value.currentPassword,
        new_master_password: value.newPassword,
      })
      .subscribe({
        next: () => {
          this.changingPassword.set(false);
          this.passwordForm.reset();
          this.passwordSuccess.set(() => t('settings.masterPasswordChangedOtherSessionsHaveEnded'));
        },
        error: (error: unknown) => {
          this.changingPassword.set(false);
          this.passwordError.set(() =>
            apiErrorMessage(error, t('settings.couldNotChangeTheMasterPassword')),
          );
        },
      });
  }

  protected saveFundMode(): void {
    const mode = this.fundModeForm.controls.mode.value;
    this.fundModeError.set(null);
    this.fundModeSuccess.set(null);
    this.savingFundMode.set(true);
    this.http
      .put<ApplicationSettings>(`${environment.apiBaseUrl}/settings/fund-allocation-mode`, { mode })
      .subscribe({
        next: (settings) => {
          this.savingFundMode.set(false);
          this.applySettings(settings);
          this.fundModeSuccess.set(() =>
            mode === 'dynamic'
              ? t('settings.dynamicAllocationEnabled')
              : t('settings.currentPercentagesSavedForManualMode'),
          );
        },
        error: (error: unknown) => {
          this.savingFundMode.set(false);
          this.fundModeError.set(() =>
            apiErrorMessage(error, t('settings.couldNotChangeAllocationMode')),
          );
        },
      });
  }

  protected logoutAll(): void {
    this.auth.logoutAll().subscribe({
      error: (error: unknown) =>
        this.settingsError.set(() => apiErrorMessage(error, t('settings.couldNotEndAllSessions'))),
    });
  }

  protected exportJsonBackup(): void {
    this.backupBusy.set(true);
    this.backupError.set(null);
    this.backupSuccess.set(null);
    this.http.get<BackupDocumentEnvelope>(`${environment.apiBaseUrl}/backup/export`).subscribe({
      next: (document) => {
        this.backupBusy.set(false);
        this.downloadBackup(document, 'json');
        this.backupSuccess.set(() => t('settings.plaintextJsonBackupCreatedStoreItIn'));
      },
      error: (error: unknown) => {
        this.backupBusy.set(false);
        this.backupError.set(() => apiErrorMessage(error, t('settings.couldNotCreateTheBackup')));
      },
    });
  }

  protected exportHermesBackup(): void {
    if (this.hermesExportForm.invalid) {
      this.hermesExportForm.markAllAsTouched();
      return;
    }
    this.backupBusy.set(true);
    this.backupError.set(null);
    this.backupSuccess.set(null);
    this.http
      .post<BackupDocumentEnvelope>(`${environment.apiBaseUrl}/backup/export/hermes`, {
        master_password: this.hermesExportForm.controls.masterPassword.value,
      })
      .subscribe({
        next: (document) => {
          this.backupBusy.set(false);
          this.hermesExportForm.reset();
          this.downloadBackup(document, 'hermes');
          this.backupSuccess.set(() =>
            t('settings.protectedHermesBackupCreatedRestorationWillRequire'),
          );
        },
        error: (error: unknown) => {
          this.backupBusy.set(false);
          this.hermesExportForm.reset();
          this.backupError.set(() =>
            apiErrorMessage(error, t('settings.couldNotCreateTheProtectedBackup')),
          );
        },
      });
  }

  protected chooseBackup(event: Event): void {
    const sequence = ++this.selectedBackupSequence;
    const file = (event.target as HTMLInputElement).files?.[0];
    this.backupPreview.set(null);
    this.backupDocument.set(null);
    this.backupError.set(null);
    this.backupSuccess.set(null);
    this.backupRequiresPassword.set(false);
    this.restoreForm.reset();
    if (!file) return;
    if (file.size > 72 * 1024 * 1024) {
      this.backupError.set(() => t('settings.theFileExceedsThe72MbLimit'));
      return;
    }
    file
      .text()
      .then((text) => {
        if (sequence !== this.selectedBackupSequence) return;
        let document: unknown;
        try {
          document = JSON.parse(text);
        } catch {
          this.backupError.set(() => t('settings.theFileIsNotValidJson'));
          return;
        }
        const format = this.backupFormat(document);
        if (format === 'hermes-json-backup' && file.size > 50 * 1024 * 1024) {
          this.backupError.set(() => t('settings.thePlaintextJsonBackupExceedsThe50'));
          return;
        }
        this.backupDocument.set(document);
        this.backupRequiresPassword.set(format === 'hermes');
        if (format === 'hermes') return;
        this.previewSelectedBackup(sequence);
      })
      .catch(() => {
        if (sequence !== this.selectedBackupSequence) return;
        this.backupBusy.set(false);
        this.backupError.set(() => t('settings.couldNotReadTheSelectedFileSelect'));
      });
  }

  protected previewEncryptedBackup(): void {
    if (!this.restoreForm.controls.backupPassword.value) {
      this.restoreForm.controls.backupPassword.markAsTouched();
      this.backupError.set(() => t('settings.enterTheProtectedBackupPassword'));
      return;
    }
    this.previewSelectedBackup(this.selectedBackupSequence);
  }

  protected restoreBackup(): void {
    const backup = this.backupDocument();
    const value = this.restoreForm.getRawValue();
    if (!backup || this.restoreForm.invalid || value.confirmation !== this.restoreConfirmation) {
      this.restoreForm.markAllAsTouched();
      if (value.confirmation !== this.restoreConfirmation) {
        this.backupError.set(() => t('auth.theConfirmationPhraseDoesNotMatchNo'));
      }
      return;
    }
    this.backupBusy.set(true);
    this.backupError.set(null);
    this.http
      .post(`${environment.apiBaseUrl}/backup/restore`, {
        backup,
        confirmation: RESTORE_CONFIRMATION,
        master_password: value.masterPassword,
        backup_password: this.backupRequiresPassword() ? value.backupPassword : null,
      })
      .subscribe({
        next: () => {
          this.backupBusy.set(false);
          this.backupSuccess.set(() => t('settings.allDataRestoredReloadingTheApplication'));
          window.location.reload();
        },
        error: (error: unknown) => {
          this.backupBusy.set(false);
          this.restoreForm.controls.masterPassword.reset();
          this.backupError.set(() =>
            apiErrorMessage(error, t('settings.restorationCancelledNoDataWasChanged')),
          );
        },
      });
  }

  private previewSelectedBackup(sequence: number): void {
    const backup = this.backupDocument();
    if (!backup) return;
    this.backupBusy.set(true);
    this.backupError.set(null);
    this.http
      .post<BackupPreview>(`${environment.apiBaseUrl}/backup/preview`, {
        backup,
        backup_password: this.backupRequiresPassword()
          ? this.restoreForm.controls.backupPassword.value
          : null,
      })
      .subscribe({
        next: (preview) => {
          if (sequence !== this.selectedBackupSequence) return;
          this.backupBusy.set(false);
          this.backupPreview.set(preview);
        },
        error: (error: unknown) => {
          if (sequence !== this.selectedBackupSequence) return;
          this.backupBusy.set(false);
          this.restoreForm.controls.backupPassword.reset();
          this.backupError.set(() => apiErrorMessage(error, t('settings.backupValidationFailed')));
        },
      });
  }

  private backupFormat(document: unknown): string | null {
    if (typeof document !== 'object' || document === null || !('format' in document)) return null;
    return typeof document.format === 'string' ? document.format : null;
  }

  private downloadBackup(document: BackupDocumentEnvelope, extension: 'json' | 'hermes'): void {
    const blob = new Blob([JSON.stringify(document, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = window.document.createElement('a');
    link.href = url;
    link.download = `hermes-backup-${new Date().toISOString().slice(0, 10)}.${extension}`;
    link.click();
    URL.revokeObjectURL(url);
  }

  private loadSettings(): void {
    this.loading.set(true);
    this.http.get<ApplicationSettings>(`${environment.apiBaseUrl}/settings`).subscribe({
      next: (settings) => {
        this.loading.set(false);
        this.applySettings(settings);
      },
      error: (error: unknown) => {
        this.loading.set(false);
        this.settingsError.set(() => apiErrorMessage(error, t('settings.couldNotLoadSettings')));
      },
    });
    this.http.get<Account[]>(`${environment.apiBaseUrl}/accounts`).subscribe({
      next: (accounts) => {
        this.accounts.set(accounts);
        this.accountsError.set(null);
        this.settingsForm.controls.defaultAccountId.enable();
      },
      error: (error: unknown) => {
        this.settingsForm.controls.defaultAccountId.disable();
        this.accountsError.set(() =>
          apiErrorMessage(error, t('settings.couldNotLoadAccountsOtherSettingsRemain')),
        );
      },
    });
  }

  private applySettings(settings: ApplicationSettings): void {
    const fundMode = settings.fund_allocation_mode ?? 'manual';
    this.currencyLocked.set(settings.base_currency_locked);
    this.settingsForm.setValue({
      baseCurrency: settings.base_currency,
      timezone: settings.timezone,
      defaultAccountId: settings.default_account_id ?? '',
    });
    this.currentFundMode.set(fundMode);
    this.fundModeForm.setValue({ mode: fundMode });
    if (settings.base_currency_locked) {
      this.settingsForm.controls.baseCurrency.disable();
    }
  }
}

function detectedTimezone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
}

function supportedTimezones(): string[] {
  const intl = Intl as typeof Intl & { supportedValuesOf?: (key: 'timeZone') => string[] };
  const values = intl.supportedValuesOf?.('timeZone') ?? ['UTC', detectedTimezone()];
  return [...new Set(['UTC', detectedTimezone(), ...values])].sort();
}
