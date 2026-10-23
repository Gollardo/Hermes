import { DOCUMENT } from '@angular/common';
import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { NavigationEnd, NavigationStart, Router } from '@angular/router';
import { Subject } from 'rxjs';

import { ChartMotion, ChartMotionNavigation } from './chart-motion';

@Component({
  imports: [ChartMotion],
  template: '<div [appChartMotion]="key"></div>',
})
class HostComponent {
  key = 'first-result';
}

describe('ChartMotion', () => {
  let fixture: ComponentFixture<HostComponent>;
  let navigationEvents: Subject<unknown>;
  let document: Document;

  beforeEach(async () => {
    navigationEvents = new Subject();
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
      callback(0);
      return 1;
    });
    vi.stubGlobal('cancelAnimationFrame', vi.fn());
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({ matches: false })),
    );
    await TestBed.configureTestingModule({
      imports: [HostComponent],
      providers: [{ provide: Router, useValue: { events: navigationEvents } }],
    }).compileComponents();
    document = TestBed.inject(DOCUMENT);
  });

  afterEach(() => {
    delete document.documentElement.dataset['motionInput'];
    TestBed.resetTestingModule();
    vi.unstubAllGlobals();
  });

  it('reveals a rendered chart only after pointer input', () => {
    document.documentElement.dataset['motionInput'] = 'pointer';
    fixture = TestBed.createComponent(HostComponent);

    fixture.detectChanges();

    expect(fixture.nativeElement.firstElementChild.classList.contains('chart-motion')).toBe(true);
    expect(fixture.nativeElement.firstElementChild.classList.contains('chart-motion-pending')).toBe(
      true,
    );
    expect(fixture.nativeElement.firstElementChild.classList.contains('chart-motion-ready')).toBe(
      true,
    );
  });

  it('keeps the rendered chart static for keyboard and reduced-motion users', () => {
    fixture = TestBed.createComponent(HostComponent);
    fixture.detectChanges();
    expect(fixture.nativeElement.firstElementChild.classList.contains('chart-motion-pending')).toBe(
      false,
    );
    expect(fixture.nativeElement.firstElementChild.classList.contains('chart-motion-ready')).toBe(
      false,
    );

    document.documentElement.dataset['motionInput'] = 'pointer';
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({ matches: true })),
    );
    fixture.componentInstance.key = 'second-result';
    fixture.detectChanges();

    expect(fixture.nativeElement.firstElementChild.classList.contains('chart-motion-ready')).toBe(
      false,
    );
  });

  it('stops an active reveal as soon as the user switches to the keyboard', () => {
    document.documentElement.dataset['motionInput'] = 'pointer';
    fixture = TestBed.createComponent(HostComponent);
    fixture.detectChanges();

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab' }));

    expect(fixture.nativeElement.firstElementChild.classList.contains('chart-motion-pending')).toBe(
      false,
    );
    expect(fixture.nativeElement.firstElementChild.classList.contains('chart-motion-ready')).toBe(
      false,
    );
  });

  it('does not replay a chart reached through browser history', () => {
    fixture = TestBed.createComponent(HostComponent);
    fixture.detectChanges();
    navigationEvents.next(new NavigationStart(1, '/forecast', 'popstate'));
    navigationEvents.next(new NavigationEnd(1, '/forecast', '/forecast'));
    document.documentElement.dataset['motionInput'] = 'pointer';
    fixture.componentInstance.key = 'history-result';

    fixture.detectChanges();

    expect(fixture.nativeElement.firstElementChild.classList.contains('chart-motion-ready')).toBe(
      false,
    );
  });

  it('clears history suppression when an explicit navigation begins', () => {
    const navigation = TestBed.inject(ChartMotionNavigation);
    navigationEvents.next(new NavigationStart(1, '/forecast', 'popstate'));
    navigationEvents.next(new NavigationEnd(1, '/forecast', '/forecast'));
    expect(navigation.isHistoryNavigation()).toBe(true);

    navigationEvents.next(new NavigationStart(2, '/forecast?period=month', 'imperative'));

    expect(navigation.isHistoryNavigation()).toBe(false);
  });
});
