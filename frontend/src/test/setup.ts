import '@testing-library/jest-dom';

// Mock ResizeObserver for recharts
class ResizeObserverMock {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}

global.ResizeObserver = ResizeObserverMock;

// Mock scrollIntoView for TimelineSlider
Element.prototype.scrollIntoView = () => {};
