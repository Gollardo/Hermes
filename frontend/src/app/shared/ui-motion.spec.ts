import { TestBed } from '@angular/core/testing';
import { UiMotion } from './ui-motion';

describe('UiMotion', () => {
  let motion: UiMotion;
  let root: HTMLElement;
  let animate: ReturnType<typeof vi.fn>;
  let cancellations: ReturnType<typeof vi.fn>[];

  beforeEach(() => {
    TestBed.configureTestingModule({});
    root = document.createElement('div');
    root.innerHTML = '<section class="modal-card"></section>';
    document.body.append(root);
    cancellations = [];
    animate = vi.fn(() => {
      let reject!: (reason: Error) => void;
      const finished = new Promise<void>((_, fail) => {
        reject = fail;
      });
      const cancel = vi.fn(() => reject(new Error('cancelled')));
      cancellations.push(cancel);
      return { finished, cancel } as unknown as Animation;
    });
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({ matches: false })),
    );
    Object.defineProperty(Element.prototype, 'animate', { configurable: true, value: animate });
    motion = TestBed.inject(UiMotion);
  });

  afterEach(() => {
    TestBed.resetTestingModule();
    root.remove();
    delete (Element.prototype as unknown as { animate?: unknown }).animate;
    vi.unstubAllGlobals();
  });

  it('keeps keyboard entry and exit instantaneous', () => {
    const enter = vi.fn();
    const leave = vi.fn();
    motion.enter({ target: root, animationComplete: enter }, 'modal');
    motion.leave({ target: root, animationComplete: leave }, 'modal');
    expect(animate).not.toHaveBeenCalled();
    expect(enter).toHaveBeenCalledOnce();
    expect(leave).toHaveBeenCalledOnce();
    expect(root.hasAttribute('inert')).toBe(true);
  });

  it('finishes pointer motion immediately when the user switches to the keyboard', async () => {
    document.dispatchEvent(new Event('pointerdown'));
    const complete = vi.fn();
    motion.enter({ target: root, animationComplete: complete }, 'modal');
    expect(animate).toHaveBeenCalledTimes(2);
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    await Promise.resolve();
    expect(complete).toHaveBeenCalledOnce();
    expect(cancellations.every((cancel) => cancel.mock.calls.length === 1)).toBe(true);
    expect(document.documentElement.dataset['motionInput']).toBe('keyboard');
  });

  it('uses only opacity for reduced-motion surfaces', () => {
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({ matches: true })),
    );
    document.dispatchEvent(new Event('pointerdown'));
    motion.enter({ target: root, animationComplete: vi.fn() }, 'modal');
    for (const call of animate.mock.calls) {
      const frames = call[0] as Keyframe[];
      expect(frames.every((frame) => !('transform' in frame))).toBe(true);
    }
  });

  it('completes an interrupted entrance once and lets its exit finish independently', async () => {
    document.dispatchEvent(new Event('pointerdown'));
    const enterComplete = vi.fn();
    const leaveComplete = vi.fn();
    motion.enter({ target: root, animationComplete: enterComplete }, 'modal');
    motion.leave({ target: root, animationComplete: leaveComplete }, 'modal');
    await Promise.resolve();
    expect(enterComplete).toHaveBeenCalledOnce();
    expect(leaveComplete).not.toHaveBeenCalled();
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab' }));
    await Promise.resolve();
    expect(enterComplete).toHaveBeenCalledOnce();
    expect(leaveComplete).toHaveBeenCalledOnce();
  });

  it('makes exits inert and removes stale exits before a fast reopen', async () => {
    document.dispatchEvent(new Event('pointerdown'));
    const leaveComplete = vi.fn();
    motion.leave({ target: root, animationComplete: leaveComplete }, 'modal');
    expect(root.getAttribute('aria-hidden')).toBe('true');
    expect(root.hasAttribute('inert')).toBe(true);
    const next = document.createElement('div');
    motion.enter({ target: next, animationComplete: vi.fn() }, 'popover');
    await Promise.resolve();
    expect(leaveComplete).toHaveBeenCalledOnce();
  });
});
