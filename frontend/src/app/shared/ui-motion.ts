import { DOCUMENT } from '@angular/common';
import { AnimationCallbackEvent, DestroyRef, Injectable, inject } from '@angular/core';

type Surface = 'modal' | 'popover';
interface RunningMotion {
  animations: Animation[];
  leaving: boolean;
  finish: () => void;
}

/** Presentation only: Angular retains exiting surfaces until completion. */
@Injectable({ providedIn: 'root' })
export class UiMotion {
  private readonly document = inject(DOCUMENT);
  private readonly running = new Map<Element, RunningMotion>();
  private pointer = false;

  constructor() {
    const pointer = () => {
      this.pointer = true;
      this.document.documentElement.dataset['motionInput'] = 'pointer';
    };
    const keyboard = () => {
      this.pointer = false;
      this.document.documentElement.dataset['motionInput'] = 'keyboard';
      for (const motion of [...this.running.values()]) motion.finish();
    };
    this.document.addEventListener('pointerdown', pointer, true);
    this.document.addEventListener('keydown', keyboard, true);
    inject(DestroyRef).onDestroy(() => {
      this.document.removeEventListener('pointerdown', pointer, true);
      this.document.removeEventListener('keydown', keyboard, true);
      for (const motion of [...this.running.values()]) motion.finish();
      delete this.document.documentElement.dataset['motionInput'];
    });
  }

  enter(event: AnimationCallbackEvent, surface: Surface): void {
    // A fast reopen must never leave a second, stale overlay in front of the new one.
    for (const motion of [...this.running.values()]) {
      if (motion.leaving) motion.finish();
    }
    this.run(event, surface, false);
  }

  leave(event: AnimationCallbackEvent, surface: Surface): void {
    event.target.setAttribute('inert', '');
    event.target.setAttribute('aria-hidden', 'true');
    this.run(event, surface, true);
  }

  private run(event: AnimationCallbackEvent, surface: Surface, leaving: boolean): void {
    const root = event.target;
    const view = this.document.defaultView;
    if (!this.pointer || !view || typeof root.animate !== 'function') {
      this.running.get(root)?.finish();
      event.animationComplete();
      return;
    }
    const reduce = view.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
    const card = surface === 'modal' ? root.querySelector('.modal-card') : root;
    const targets = card && card !== root ? [root, card] : [root];
    // Read the actual in-flight state before cancelling an interrupted entrance.
    const starts = targets.map((target) => {
      const style = view.getComputedStyle(target);
      return { opacity: style.opacity, transform: style.transform };
    });
    this.running.get(root)?.finish();
    const tokens = view.getComputedStyle(this.document.documentElement);
    const duration =
      Number.parseFloat(
        tokens.getPropertyValue(surface === 'modal' ? '--motion-modal' : '--motion-popover'),
      ) || (surface === 'modal' ? 240 : 180);
    const easing = tokens.getPropertyValue('--ease-out').trim() || 'cubic-bezier(0.23, 1, 0.32, 1)';
    const animations = targets.map((target, index) => {
      const scaled = target === card && !reduce;
      const closed: Keyframe = {
        opacity: 0,
        ...(scaled ? { transform: surface === 'modal' ? 'scale(0.96)' : 'scale(0.97)' } : {}),
      };
      const opened: Keyframe = { opacity: 1, ...(scaled ? { transform: 'none' } : {}) };
      return target.animate(
        leaving
          ? [scaled ? starts[index] : { opacity: starts[index].opacity }, closed]
          : [closed, opened],
        {
          duration,
          easing,
          fill: 'both',
        },
      );
    });
    let completed = false;
    const finish = () => {
      if (completed) return;
      completed = true;
      animations.forEach((animation) => animation.cancel());
      this.running.delete(root);
      event.animationComplete();
    };
    this.running.set(root, { animations, leaving, finish });
    void Promise.all(animations.map((animation) => animation.finished.catch(() => undefined))).then(
      finish,
    );
  }
}
