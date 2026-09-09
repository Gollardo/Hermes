import { t, localizedSignal, LanguageService } from './i18n/i18n';
import {
  ChangeDetectionStrategy,
  Component,
  OnDestroy,
  OnInit,
  effect,
  inject,
  signal,
} from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { AuthService } from './core/auth.service';
import { apiErrorMessage } from './core/api-error';
import { IdleSessionService } from './core/idle-session.service';
import { LoginPage } from './pages/login/login';
import { SetupPage } from './pages/setup/setup';

@Component({
  selector: 'app-root',
  imports: [RouterLink, RouterLinkActive, RouterOutlet, LoginPage, SetupPage],
  templateUrl: './app.html',
  styleUrl: './app.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class App implements OnInit, OnDestroy {
  protected readonly t = t;
  private readonly languageService = inject(LanguageService);
  protected readonly auth = inject(AuthService);
  private readonly idleSession = inject(IdleSessionService);
  protected readonly actionError = localizedSignal();
  protected readonly sidebarHidden = signal(readSidebarPreference());

  constructor() {
    effect(() => {
      if (this.auth.state() === 'authenticated') {
        this.idleSession.start(
          () => this.auth.expireDueToInactivity(),
          () => this.auth.keepAlive(),
          this.auth.idleTimeoutMs() ?? undefined,
        );
      } else {
        this.idleSession.stop();
      }
    });
  }

  ngOnInit(): void {
    this.auth.initialize();
  }

  ngOnDestroy(): void {
    this.idleSession.stop();
  }

  protected logout(): void {
    this.actionError.set(null);
    this.auth.logout().subscribe({
      error: (error: unknown) =>
        this.actionError.set(() => apiErrorMessage(error, t('app.couldNotEndTheSession'))),
    });
  }

  protected toggleSidebar(): void {
    this.sidebarHidden.update((hidden) => !hidden);
    localStorage.setItem('hermes-sidebar-hidden', String(this.sidebarHidden()));
  }
}

function readSidebarPreference(): boolean {
  return (
    typeof localStorage !== 'undefined' && localStorage.getItem('hermes-sidebar-hidden') === 'true'
  );
}
