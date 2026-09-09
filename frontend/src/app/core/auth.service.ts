import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, tap } from 'rxjs';

import { environment } from '../../environments/environment';
import { AccessStateService } from './access-state.service';

export type AccessState =
  'checking' | 'uninitialized' | 'unauthenticated' | 'authenticated' | 'unavailable';

export interface SetupPayload {
  master_password: string;
  base_currency: string;
  timezone: string;
  create_default_categories?: boolean;
  category_template_language?: 'ru' | 'en';
  onboarding_expense_groups?: string[];
}

export interface RestoreSetupPayload {
  master_password: string;
  backup: unknown;
  backup_password?: string | null;
}

interface SetupStatusResponse {
  initialized: boolean;
}

interface SessionResponse {
  authenticated: true;
  expires_at: string;
  idle_timeout_seconds: number;
}

export interface PasswordChangePayload {
  current_password: string;
  new_master_password: string;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly access = inject(AccessStateService);

  readonly state = this.access.state.asReadonly();
  readonly expiresAt = this.access.expiresAt.asReadonly();
  readonly idleTimeoutMs = this.access.idleTimeoutMs.asReadonly();

  initialize(): void {
    this.access.checking();
    this.http.get<SetupStatusResponse>(`${environment.apiBaseUrl}/setup/status`).subscribe({
      next: ({ initialized }) => {
        if (!initialized) {
          this.access.uninitialized();
          return;
        }
        this.restoreSession();
      },
      error: () => this.access.unavailable(),
    });
  }

  setup(payload: SetupPayload): Observable<SessionResponse> {
    return this.http
      .post<SessionResponse>(`${environment.apiBaseUrl}/setup`, payload)
      .pipe(tap((session) => this.acceptSession(session)));
  }

  restoreSetup(payload: RestoreSetupPayload): Observable<SessionResponse> {
    return this.http
      .post<SessionResponse>(`${environment.apiBaseUrl}/setup/restore`, payload)
      .pipe(tap((session) => this.acceptSession(session)));
  }

  login(masterPassword: string): Observable<SessionResponse> {
    return this.http
      .post<SessionResponse>(`${environment.apiBaseUrl}/auth/login`, {
        master_password: masterPassword,
      })
      .pipe(tap((session) => this.acceptSession(session)));
  }

  logout(): Observable<void> {
    return this.http
      .post<void>(`${environment.apiBaseUrl}/auth/logout`, {})
      .pipe(tap(() => this.clearSession()));
  }

  logoutAll(): Observable<void> {
    return this.http
      .post<void>(`${environment.apiBaseUrl}/auth/logout-all`, {})
      .pipe(tap(() => this.clearSession()));
  }

  keepAlive(): void {
    this.http.post<void>(`${environment.apiBaseUrl}/auth/activity`, {}).subscribe({
      error: () => undefined,
    });
  }

  expireDueToInactivity(): void {
    this.clearSession();
    this.http.post<void>(`${environment.apiBaseUrl}/auth/logout`, {}).subscribe({
      error: () => undefined,
    });
  }

  changePassword(payload: PasswordChangePayload): Observable<void> {
    return this.http.post<void>(`${environment.apiBaseUrl}/auth/password`, payload);
  }

  private restoreSession(): void {
    this.http.get<SessionResponse>(`${environment.apiBaseUrl}/auth/session`).subscribe({
      next: (session) => {
        this.acceptSession(session);
        this.keepAlive();
      },
      error: (error: HttpErrorResponse) => {
        if (error.status === 401) {
          this.access.unauthenticated();
        } else {
          this.access.unavailable();
        }
      },
    });
  }

  private acceptSession(session: SessionResponse): void {
    this.access.authenticated(session.expires_at, session.idle_timeout_seconds);
  }

  private clearSession(): void {
    this.access.unauthenticated();
  }
}
