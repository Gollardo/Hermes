import { LanguageSelect } from '../../i18n/language-select';
import { t, localizedSignal } from '../../i18n/i18n';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import { AuthService } from '../../core/auth.service';
import { apiErrorMessage } from '../../core/api-error';

@Component({
  selector: 'app-login-page',
  imports: [LanguageSelect, ReactiveFormsModule],
  templateUrl: './login.html',
  styleUrl: './login.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LoginPage {
  protected readonly t = t;
  private readonly auth = inject(AuthService);
  private readonly formBuilder = inject(NonNullableFormBuilder);

  protected readonly submitting = signal(false);
  protected readonly error = localizedSignal();
  protected readonly form = this.formBuilder.group({
    password: ['', [Validators.required, Validators.maxLength(1024)]],
  });

  protected submit(): void {
    this.error.set(null);
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.submitting.set(true);
    this.auth.login(this.form.getRawValue().password).subscribe({
      next: () => this.submitting.set(false),
      error: (error: unknown) => {
        this.submitting.set(false);
        this.error.set(() => apiErrorMessage(error, t('login.couldNotSignInCheckYourPassword')));
      },
    });
  }
}
