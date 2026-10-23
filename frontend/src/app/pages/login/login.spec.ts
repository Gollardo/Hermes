import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of } from 'rxjs';

import { AuthService } from '../../core/auth.service';
import { LoginPage } from './login';

describe('LoginPage', () => {
  let fixture: ComponentFixture<LoginPage>;
  const auth = { login: vi.fn(() => of(void 0)) };

  beforeEach(async () => {
    auth.login.mockClear();
    await TestBed.configureTestingModule({
      imports: [LoginPage],
      providers: [{ provide: AuthService, useValue: auth }],
    }).compileComponents();
    fixture = TestBed.createComponent(LoginPage);
    await fixture.whenStable();
  });

  it('reveals actionable validation and focuses the missing password', async () => {
    fixture.nativeElement.querySelector('form').dispatchEvent(new Event('submit'));
    await fixture.whenStable();
    await new Promise<void>((resolve) => queueMicrotask(resolve));
    const input = fixture.nativeElement.querySelector('#login-password') as HTMLInputElement;
    expect(input.getAttribute('aria-invalid')).toBe('true');
    expect(input.getAttribute('aria-describedby')).toContain('login-password-error');
    expect(document.activeElement).toBe(input);
    expect(auth.login).not.toHaveBeenCalled();
  });

  it('shows and hides the existing password without changing its value', async () => {
    const input = fixture.nativeElement.querySelector('#login-password') as HTMLInputElement;
    input.value = 'difficult password';
    input.dispatchEvent(new Event('input'));
    const toggle = fixture.nativeElement.querySelector('.password-toggle') as HTMLButtonElement;
    toggle.click();
    await fixture.whenStable();
    expect(input.type).toBe('text');
    expect(input.value).toBe('difficult password');
    expect(toggle.getAttribute('aria-pressed')).toBe('true');
    toggle.click();
    await fixture.whenStable();
    expect(input.type).toBe('password');
  });
});
