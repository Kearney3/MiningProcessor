/// <reference types="vitest/globals" />
import "@testing-library/jest-dom/vitest";

// Initialize the production i18n instance for tests (before component imports).
import i18n from "../i18n";

beforeEach(() => {
  void i18n.changeLanguage("zh");
});

// Mock Tauri API modules
vi.mock("@tauri-apps/api/core", () => ({
  invoke: vi.fn(),
}));

vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn(() => Promise.resolve(() => {})),
  emit: vi.fn(),
}));

vi.mock("@tauri-apps/plugin-dialog", () => ({
  open: vi.fn(),
  save: vi.fn(),
  ask: vi.fn(),
  confirm: vi.fn(),
  message: vi.fn(),
}));
