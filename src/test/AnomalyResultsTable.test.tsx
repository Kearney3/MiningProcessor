import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AnomalyResultsTable } from "../components/AnomalyResultsTable";

describe("AnomalyResultsTable", () => {
  it("renders anomaly details in a scrollable table", () => {
    render(
      <AnomalyResultsTable
        records={[
          {
            数据类型: "油耗信息",
            行号: 28,
            日期: "2026-08-11",
            班次: "Day",
            设备名称: "GTL LT4000M5 LIGHTTOWER",
            设备编号: "LP0028",
            异常列: "油品消耗",
            异常值: 50001,
            检测方法: "threshold",
            说明: "超过最大阈值 50000",
          },
        ]}
      />,
    );

    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByText("异常值明细")).toBeInTheDocument();
    expect(screen.getByText("GTL LT4000M5 LIGHTTOWER")).toBeInTheDocument();
    expect(screen.getByText("50001")).toHaveClass("text-red-600");
  });

  it("does not render an empty results section", () => {
    render(<AnomalyResultsTable records={[]} />);

    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});
