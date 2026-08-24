import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { FileScanPanel } from "../components/FileScanPanel";
import type { ScanResult } from "../lib/types";

describe("FileScanPanel", () => {
  it("keeps the selected status icon within the file row", () => {
    const path = "/tmp/Fuel report.xlsx";
    const result: ScanResult = {
      matched: { fuel: [path] },
      missing: [],
      files: [{
        path,
        name: "Fuel report.xlsx",
        relative_path: "Fuel report.xlsx",
        types: ["fuel"],
        recognized: true,
        selected: true,
      }],
    };

    const { container } = render(
      <FileScanPanel
        result={result}
        selectedPaths={new Set([path])}
        onToggle={vi.fn()}
        onToggleAll={vi.fn()}
        typeLabel={(type) => type}
      />,
    );

    const checkIcon = [...container.querySelectorAll("svg")]
      .find((icon) => icon.classList.contains("text-emerald-600"));
    expect(checkIcon).toBeInTheDocument();
    expect(checkIcon).toHaveClass("h-3.5", "w-3.5");
  });

  it("filters by type and paginates the scan results", () => {
    const files = Array.from({ length: 9 }, (_, index) => {
      const path = `/tmp/report-${index + 1}.xlsx`;
      return {
        path,
        name: `report-${index + 1}.xlsx`,
        relative_path: `report-${index + 1}.xlsx`,
        types: [index === 8 ? "production" : "fuel"],
        recognized: true,
        selected: true,
      };
    });
    const result: ScanResult = {
      matched: {
        fuel: files.slice(0, 8).map((file) => file.path),
        production: [files[8].path],
      },
      missing: [],
      files,
    };

    const { container } = render(
      <FileScanPanel
        result={result}
        selectedPaths={new Set(files.map((file) => file.path))}
        onToggle={vi.fn()}
        onToggleAll={vi.fn()}
        typeLabel={(type) => type}
      />,
    );

    expect(screen.getByText("report-1.xlsx")).toBeInTheDocument();
    expect(screen.queryByText("report-9.xlsx")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "下一页" }));
    expect(screen.getByText("report-9.xlsx")).toBeInTheDocument();
    expect(container.querySelectorAll('[aria-hidden="true"].h-14')).toHaveLength(7);

    fireEvent.click(screen.getByRole("tab", { name: /production/ }));
    expect(screen.getByText("report-9.xlsx")).toBeInTheDocument();
    expect(screen.queryByText("report-1.xlsx")).not.toBeInTheDocument();
  });
});
