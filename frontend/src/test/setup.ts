import '@testing-library/jest-dom';
import { setupServer } from 'msw/node';
import { beforeAll, afterAll, afterEach } from 'vitest';
import { handlers } from './msw-handlers';

// ---------------------------------------------------------------------------
// MSW server — intercepts HTTP in all tests
// ---------------------------------------------------------------------------
export const server = setupServer(...handlers);

beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// ---------------------------------------------------------------------------
// Browser API mocks (required by UI libraries)
// ---------------------------------------------------------------------------

// Reports a fixed non-zero size so Recharts' ResponsiveContainer renders SVG in
// jsdom (which never lays out elements). Width/height match a typical chart pane.
const MOCK_CHART_WIDTH = 800;
const MOCK_CHART_HEIGHT = 400;

class ResizeObserverMock implements ResizeObserver {
  private readonly callback: ResizeObserverCallback;

  constructor(callback: ResizeObserverCallback) {
    this.callback = callback;
  }

  observe(target: Element): void {
    const contentRect = {
      width: MOCK_CHART_WIDTH,
      height: MOCK_CHART_HEIGHT,
      top: 0,
      left: 0,
      right: MOCK_CHART_WIDTH,
      bottom: MOCK_CHART_HEIGHT,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    } as DOMRectReadOnly;
    this.callback(
      [{ target, contentRect } as ResizeObserverEntry],
      this,
    );
  }

  unobserve(): void { /* no-op mock */ }
  disconnect(): void { /* no-op mock */ }
}

globalThis.ResizeObserver = ResizeObserverMock;

Element.prototype.scrollIntoView = () => {};

// Radix UI primitives call hasPointerCapture/releasePointerCapture which jsdom
// does not implement. Stub them so Select/Popover tests don't throw.
if (!Element.prototype.hasPointerCapture) {
  Element.prototype.hasPointerCapture = () => false;
}
if (!Element.prototype.setPointerCapture) {
  Element.prototype.setPointerCapture = () => {};
}
if (!Element.prototype.releasePointerCapture) {
  Element.prototype.releasePointerCapture = () => {};
}
