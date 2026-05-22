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

class ResizeObserverMock implements ResizeObserver {
  observe(): void { /* no-op mock */ }
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
