import { t, localizedSignal, LanguageService } from './i18n/i18n';
import {
  ChangeDetectionStrategy,
  Component,
  OnDestroy,
  OnInit,
  effect,
  inject,
  signal,
  computed,
} from '@angular/core';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

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

  private readonly viewport =
    typeof window.matchMedia === 'function' ? window.matchMedia('(max-width: 58rem)') : null;
  protected readonly narrow = signal(this.viewport?.matches ?? false);
  protected readonly mobileMenuOpen = signal(false);
  protected readonly navigationHidden = computed(() =>
    this.narrow() ? !this.mobileMenuOpen() : this.sidebarHidden(),
  );
  private readonly viewportChanged = (event: MediaQueryListEvent) => {
    this.narrow.set(event.matches);
    this.mobileMenuOpen.set(false);
  };

  constructor() {
    this.viewport?.addEventListener('change', this.viewportChanged);
    inject(Router)
      .events.pipe(takeUntilDestroyed())
      .subscribe((event) => {
        if (event instanceof NavigationEnd && this.narrow() && this.mobileMenuOpen()) {
          this.mobileMenuOpen.set(false);
          document.getElementById('main-content')?.focus();
        }
      });
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
    this.viewport?.removeEventListener('change', this.viewportChanged);
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
    if (this.narrow()) {
      this.mobileMenuOpen.update((open) => !open);
      return;
    }
    this.sidebarHidden.update((hidden) => !hidden);
    localStorage.setItem('hermes-sidebar-hidden', String(this.sidebarHidden()));
  }
}

function readSidebarPreference(): boolean {
  return (
    typeof localStorage !== 'undefined' && localStorage.getItem('hermes-sidebar-hidden') === 'true'
  );
}
