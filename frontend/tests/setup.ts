import "@testing-library/jest-dom";

// recharts' ResponsiveContainer needs a measured DOM; jsdom reports 0x0.
// Stub ResizeObserver and element sizing so charts render in tests.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
global.ResizeObserver = global.ResizeObserver || (ResizeObserverStub as unknown as typeof ResizeObserver);

Object.defineProperty(HTMLElement.prototype, "offsetWidth", {
  configurable: true,
  value: 800,
});
Object.defineProperty(HTMLElement.prototype, "offsetHeight", {
  configurable: true,
  value: 400,
});
