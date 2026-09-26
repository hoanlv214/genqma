import { GlobalWindow } from "happy-dom";

const window = new GlobalWindow({ url: "http://localhost:5173" });

const storageMap = new Map<string, string>();
const mockStorage = {
  getItem: (k: string) => storageMap.get(k) ?? null,
  setItem: (k: string, v: string) => storageMap.set(k, String(v)),
  removeItem: (k: string) => storageMap.delete(k),
  clear: () => storageMap.clear(),
  get length() {
    return storageMap.size;
  },
  key: (i: number) => Array.from(storageMap.keys())[i] ?? null,
};

Object.assign(globalThis, {
  window,
  document: window.document,
  navigator: window.navigator,
  location: window.location,
  HTMLElement: window.HTMLElement,
  customElements: window.customElements,
  Event: window.Event,
  CustomEvent: window.CustomEvent,
  Node: window.Node,
  localStorage: mockStorage,
  sessionStorage: mockStorage,
  CSSStyleSheet: (window as any).CSSStyleSheet || class CSSStyleSheet {},
  ResizeObserver: class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  },
  IntersectionObserver: class IntersectionObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  },
  getComputedStyle: window.getComputedStyle ? window.getComputedStyle.bind(window) : (() => ({ getPropertyValue: () => "" })),
  requestAnimationFrame: (cb: (time: number) => void) => setTimeout(() => cb(Date.now()), 0),
  cancelAnimationFrame: (id: any) => clearTimeout(id),
});
