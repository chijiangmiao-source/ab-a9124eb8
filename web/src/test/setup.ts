import "@testing-library/jest-dom/vitest";

// jsdom does not implement scrollIntoView / focus smooth scrolling.
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = function () {};
}
