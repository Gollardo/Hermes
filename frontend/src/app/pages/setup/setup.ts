import { LanguageSelect } from '../../i18n/language-select';
import { t, localizedSignal, language, Language } from '../../i18n/i18n';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import { AuthService } from '../../core/auth.service';
import { apiErrorMessage } from '../../core/api-error';

const CURRENCIES = ['RUB', 'USD', 'EUR', 'GBP', 'CNY', 'JPY', 'KZT', 'TRY', 'AED', 'CHF'];
type SetupMode = 'fresh' | 'restore';

interface OnboardingQuestion {
  key: string;
  title: string;
  question: string;
}

function questions(): OnboardingQuestion[] {
  return [
    {
      key: 'housing',
      title: t('setup.housing'),
      question: t('setup.wouldYouLikeToTrackHousingCosts'),
    },
    {
      key: 'car',
      title: t('setup.car'),
      question: t('setup.doYouOwnACarWhoseExpenses'),
    },
    {
      key: 'transport',
      title: t('setup.transport'),
      question: t('setup.doYouUsePublicTransportTaxisCar'),
    },
    {
      key: 'children',
      title: t('setup.children'),
      question: t('setup.doYouHaveChildrenWhoseExpensesYou'),
    },
    {
      key: 'family',
      title: t('setup.familyAndLovedOnes'),
      question: t('setup.wouldYouLikeToTrackFamilySpending'),
    },
    {
      key: 'pets',
      title: t('setup.pets'),
      question: t('setup.doYouHavePets'),
    },
    {
      key: 'health',
      title: t('setup.health'),
      question: t('setup.wouldYouLikeToTrackDoctorsMedicines'),
    },
    {
      key: 'sport',
      title: t('setup.sportsAndActivity'),
      question: t('setup.doYouPlaySportsOrRegularlySpend'),
    },
    {
      key: 'education',
      title: t('setup.educationAndDevelopment'),
      question: t('setup.doYouSpendMoneyOnEducationCourses'),
    },
    {
      key: 'work',
      title: t('setup.workAndCareer'),
      question: t('setup.doYouHavePersonalExpensesRelatedTo'),
    },
    {
      key: 'business',
      title: t('setup.businessAndSelfEmployment'),
      question: t('setup.doYouRunABusinessWorkFor'),
    },
    {
      key: 'travel',
      title: t('setup.travel'),
      question: t('setup.wouldYouLikeToTrackTripsHolidays'),
    },
    {
      key: 'entertainment',
      title: t('setup.leisureAndEntertainment'),
      question: t('setup.wouldYouLikeToTrackCafS'),
    },
    {
      key: 'shopping',
      title: t('setup.shoppingAndPersonalItems'),
      question: t('setup.wouldYouLikeToTrackClothingElectronics'),
    },
  ];
}

@Component({
  selector: 'app-setup-page',
  imports: [LanguageSelect, ReactiveFormsModule],
  templateUrl: './setup.html',
  styleUrl: './setup.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SetupPage {
  protected readonly t = t;
  private readonly auth = inject(AuthService);
  private readonly formBuilder = inject(NonNullableFormBuilder);

  protected readonly templateLanguage = signal<Language>(language());
  protected readonly currencies = CURRENCIES;
  protected readonly timezones = supportedTimezones();
  protected get questions() {
    return questions();
  }
  protected readonly step = signal(1);
  protected readonly mode = signal<SetupMode | null>(null);
  protected readonly selectedGroups = signal(new Set<string>());
  protected readonly backupName = signal<string | null>(null);
  protected readonly backupRequiresPassword = signal(false);
  protected readonly readingBackup = signal(false);
  protected readonly submitting = signal(false);
  protected readonly error = localizedSignal();
  private backupDocument: unknown | null = null;
  private backupSequence = 0;

  protected readonly form = this.formBuilder.group({
    password: ['', [Validators.required, Validators.minLength(12), Validators.maxLength(1024)]],
    passwordConfirmation: ['', Validators.required],
    baseCurrency: ['RUB', [Validators.required, Validators.pattern(/^[A-Za-z]{3}$/)]],
    timezone: [detectedTimezone(), Validators.required],
    backupPassword: ['', Validators.maxLength(1024)],
  });

  protected startFresh(): void {
    this.backupSequence += 1;
    this.mode.set('fresh');
    this.templateLanguage.set(language());
    this.backupDocument = null;
    this.backupName.set(null);
    this.backupRequiresPassword.set(false);
    this.readingBackup.set(false);
    this.error.set(null);
    this.step.set(2);
  }

  protected chooseBackup(event: Event): void {
    const sequence = ++this.backupSequence;
    const file = (event.target as HTMLInputElement).files?.[0];
    this.backupDocument = null;
    this.backupName.set(null);
    this.backupRequiresPassword.set(false);
    this.mode.set(null);
    this.readingBackup.set(false);
    this.error.set(null);
    if (!file) return;
    if (file.size > 72 * 1024 * 1024) {
      this.error.set(() => t('settings.theFileExceedsThe72MbLimit'));
      return;
    }
    this.readingBackup.set(true);
    file
      .text()
      .then((text) => {
        if (sequence !== this.backupSequence) return;
        try {
          this.backupDocument = JSON.parse(text);
          const format = this.backupFormat(this.backupDocument);
          if (format === 'hermes-json-backup' && file.size > 50 * 1024 * 1024) {
            this.backupDocument = null;
            this.error.set(() => t('settings.thePlaintextJsonBackupExceedsThe50'));
            return;
          }
          this.backupRequiresPassword.set(format === 'hermes');
          this.backupName.set(file.name);
          this.mode.set('restore');
          this.step.set(2);
        } catch {
          this.error.set(() => t('settings.theFileIsNotValidJson'));
        } finally {
          this.readingBackup.set(false);
        }
      })
      .catch(() => {
        if (sequence !== this.backupSequence) return;
        this.readingBackup.set(false);
        this.error.set(() => t('setup.couldNotReadTheSelectedFile'));
      });
  }

  protected back(): void {
    this.error.set(null);
    if (this.step() === 3) {
      this.step.set(2);
      return;
    }
    this.backupSequence += 1;
    this.mode.set(null);
    this.backupDocument = null;
    this.backupName.set(null);
    this.backupRequiresPassword.set(false);
    this.readingBackup.set(false);
    this.step.set(1);
  }

  protected continueToCategories(): void {
    if (!this.credentialsValid()) return;
    if (this.mode() === 'restore') {
      this.submit();
      return;
    }
    this.step.set(3);
  }

  protected toggleGroup(key: string, checked: boolean): void {
    const next = new Set(this.selectedGroups());
    if (checked) next.add(key);
    else next.delete(key);
    this.selectedGroups.set(next);
  }

  protected submit(): void {
    if (!this.credentialsValid() || this.submitting()) return;
    const value = this.form.getRawValue();
    this.submitting.set(true);
    this.error.set(null);

    if (this.mode() === 'restore' && this.backupDocument) {
      this.auth
        .restoreSetup({
          master_password: value.password,
          backup: this.backupDocument,
          backup_password: this.backupRequiresPassword() ? value.backupPassword : null,
        })
        .subscribe({
          next: () => this.submitting.set(false),
          error: (error: unknown) => {
            this.submitting.set(false);
            this.error.set(() =>
              apiErrorMessage(error, t('setup.backupValidationFailedChooseAnotherFile')),
            );
          },
        });
      return;
    }

    this.auth
      .setup({
        master_password: value.password,
        base_currency: value.baseCurrency,
        timezone: value.timezone,
        create_default_categories: this.mode() === 'fresh',
        category_template_language: this.templateLanguage(),
        onboarding_expense_groups: this.mode() === 'fresh' ? [...this.selectedGroups()] : [],
      })
      .subscribe({
        next: () => {
          this.submitting.set(false);
        },
        error: (error: unknown) => {
          this.submitting.set(false);
          this.error.set(() => apiErrorMessage(error, t('setup.couldNotCompleteInitialSetup')));
        },
      });
  }

  private credentialsValid(): boolean {
    const value = this.form.getRawValue();
    if (
      this.form.invalid ||
      value.password !== value.passwordConfirmation ||
      (this.mode() === 'restore' && this.backupRequiresPassword() && !value.backupPassword)
    ) {
      this.form.markAllAsTouched();
      if (this.form.valid && value.password !== value.passwordConfirmation) {
        this.error.set(() => t('setup.thePasswordsDoNotMatch'));
      }
      return false;
    }
    return true;
  }

  private backupFormat(document: unknown): string | null {
    if (typeof document !== 'object' || document === null || !('format' in document)) return null;
    return typeof document.format === 'string' ? document.format : null;
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
