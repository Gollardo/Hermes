import { DOCUMENT } from '@angular/common';
import {
  AfterViewInit,
  DestroyRef,
  Directive,
  ElementRef,
  Injectable,
  Input,
  OnChanges,
  OnDestroy,
  SimpleChanges,
  inject,
} from '@angular/core';
import { NavigationEnd, NavigationStart, Router } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

/** Remembers whether the last completed navigation came from browser history. */
@Injectable({ providedIn: 'root' })
export class ChartMotionNavigation {
  private historyNavigation = false;
  private pendingHistoryNavigation = false;

  constructor() {
    inject(Router)
      .events.pipe(takeUntilDestroyed())
      .subscribe((event) => {
        if (event instanceof NavigationStart) {
          this.pendingHistoryNavigation = event.navigationTrigger === 'popstate';
          if (!this.pendingHistoryNavigation) this.historyNavigation = false;
        }
        if (event instanceof NavigationEnd) {
          this.historyNavigation = this.pendingHistoryNavigation;
        }
      });
  }

  isHistoryNavigation(): boolean {
    return this.historyNavigation;
  }
}

/** Adds a short, interruptible visual reveal to a confirmed chart result. */
@Directive({
  selector: '[appChartMotion]',
  host: { class: 'chart-motion' },
})
export class ChartMotion implements AfterViewInit, OnChanges, OnDestroy {
  @Input() appChartMotion: string | null = null;

  private readonly document = inject(DOCUMENT);
  private readonly element = inject(ElementRef<HTMLElement>);
  private readonly navigation = inject(ChartMotionNavigation);
  private viewReady = false;
  private frame: number | null = null;
  private readonly stopForKeyboard = () => {
    this.cancel();
    this.element.nativeElement.classList.remove('chart-motion-pending', 'chart-motion-ready');
  };

  constructor() {
    this.document.addEventListener('keydown', this.stopForKeyboard, true);
    inject(DestroyRef).onDestroy(() =>
      this.document.removeEventListener('keydown', this.stopForKeyboard, true),
    );
  }

  ngAfterViewInit(): void {
    this.viewReady = true;
    this.replay();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['appChartMotion'] && this.viewReady) this.replay();
  }

  ngOnDestroy(): void {
    this.cancel();
  }

  private replay(): void {
    this.cancel();
    const chart = this.element.nativeElement;
    chart.classList.remove('chart-motion-pending', 'chart-motion-ready');
    if (!this.canAnimate()) return;
    chart.classList.add('chart-motion-pending');

    const schedule = globalThis.requestAnimationFrame?.bind(globalThis);
    if (!schedule) {
      chart.classList.add('chart-motion-ready');
      return;
    }
    this.frame = schedule(() => {
      this.frame = schedule(() => {
        this.frame = null;
        chart.classList.add('chart-motion-ready');
      });
    });
  }

  private canAnimate(): boolean {
    const view = this.document.defaultView;
    return Boolean(
      this.appChartMotion &&
      this.document.documentElement.dataset['motionInput'] === 'pointer' &&
      !this.navigation.isHistoryNavigation() &&
      !view?.matchMedia?.('(prefers-reduced-motion: reduce)').matches,
    );
  }

  private cancel(): void {
    if (this.frame === null) return;
    globalThis.cancelAnimationFrame?.(this.frame);
    this.frame = null;
  }
}
