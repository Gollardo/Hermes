import { Component, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ModalFocus } from './modal-focus';

@Component({
  imports: [ModalFocus],
  template: `
    <button id="open" (click)="open.set(true)">Open</button>
    @if (open()) {
      <section appModalFocus role="dialog" tabindex="-1" (modalEscape)="open.set(false)">
        <button id="first" data-modal-initial-focus>First</button
        ><button id="last" (click)="open.set(false)">Last</button>
      </section>
    }
  `,
})
class HostComponent {
  readonly open = signal(false);
}

describe('ModalFocus', () => {
  let fixture: ComponentFixture<HostComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [HostComponent] }).compileComponents();
    fixture = TestBed.createComponent(HostComponent);
    await fixture.whenStable();
  });

  it('focuses and contains the dialog, closes with Escape, and restores focus', async () => {
    const opener = fixture.nativeElement.querySelector('#open') as HTMLButtonElement;
    opener.focus();
    opener.click();
    await fixture.whenStable();
    await new Promise<void>((resolve) => queueMicrotask(resolve));
    const first = fixture.nativeElement.querySelector('#first') as HTMLButtonElement;
    const last = fixture.nativeElement.querySelector('#last') as HTMLButtonElement;
    expect(document.activeElement).toBe(first);

    first.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true }),
    );
    expect(document.activeElement).toBe(last);
    last.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true }));
    expect(document.activeElement).toBe(first);

    first.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    await fixture.whenStable();
    await new Promise<void>((resolve) => queueMicrotask(resolve));
    expect(fixture.nativeElement.querySelector('[role="dialog"]')).toBeNull();
    expect(document.activeElement).toBe(opener);
  });
});
