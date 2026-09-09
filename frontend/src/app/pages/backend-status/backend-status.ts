import { t } from '../../i18n/i18n';
import { HttpClient } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';

import { environment } from '../../../environments/environment';

type HealthState = 'checking' | 'available' | 'unavailable';

interface HealthResponse {
  status: 'ok';
}

@Component({
  selector: 'app-backend-status-page',
  templateUrl: './backend-status.html',
  styleUrl: './backend-status.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BackendStatusPage implements OnInit {
  protected readonly t = t;
  private readonly http = inject(HttpClient);

  protected readonly state = signal<HealthState>('checking');

  ngOnInit(): void {
    this.check();
  }

  protected check(): void {
    this.state.set('checking');
    this.http.get<HealthResponse>(`${environment.apiBaseUrl}/health`).subscribe({
      next: ({ status }) => this.state.set(status === 'ok' ? 'available' : 'unavailable'),
      error: () => this.state.set('unavailable'),
    });
  }
}
