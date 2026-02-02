import '@testing-library/jest-dom';

// Mock ResizeObserver for recharts - empty implementations are intentional (test mocks)
class ResizeObserverMock implements ResizeObserver {
  observe(): void { /* no-op mock */ }
  unobserve(): void { /* no-op mock */ }
  disconnect(): void { /* no-op mock */ }
}

globalThis.ResizeObserver = ResizeObserverMock;

// Mock scrollIntoView for TimelineSlider
Element.prototype.scrollIntoView = () => {};
