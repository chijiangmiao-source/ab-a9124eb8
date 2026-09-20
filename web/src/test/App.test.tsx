import { render, screen, waitFor, fireEvent, within } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import App from "../App";

const SCENARIOS = [
  {
    key: "unique",
    title: "唯一最优映射（含 1 颗伪星）",
    description: "d",
    threshold: 1,
    outlier_quota: 2,
    catalog: [
      { id: "STAR-01", magnitude: 0, vector: [2, 2, 1] },
      { id: "STAR-02", magnitude: 1, vector: [2, 1, 2] },
      { id: "STAR-03", magnitude: 1, vector: [1, 2, 2] },
      { id: "STAR-04", magnitude: 2, vector: [0, 3, 0] },
      { id: "STAR-05", magnitude: 2, vector: [0, 0, 3] },
      { id: "STAR-06", magnitude: 2, vector: [3, 0, 0] },
      { id: "STAR-07", magnitude: 2, vector: [0, -3, 0] },
      { id: "STAR-08", magnitude: 2, vector: [0, 0, -3] },
    ],
    observations: [{ magnitude: 1 }, { magnitude: 2 }, { magnitude: 0 }, { magnitude: 1 }, { magnitude: 2 }, { magnitude: 0 }],
    dot_measurements: [
      [0, 3, 8, 8, 6, 99],
      [3, 0, 6, -6, 0, -99],
      [8, 6, 0, 6, 3, 99],
      [8, -6, 6, 0, 6, -99],
      [6, 0, 3, 6, 0, 99],
      [99, -99, 99, -99, 99, 0],
    ],
  },
];

function solveResult(kind: string) {
  if (kind === "incompatible") {
    return {
      status: "incompatible",
      message: "不相容：测试原因",
      kept_count: 3,
      required_kept: 5,
      outlier_quota: 1,
      threshold: 0,
      n_observations: 6,
      n_catalog: 8,
      search_nodes: 4,
      multiple: false,
      canonical: null,
      witness: null,
    };
  }
  if (kind === "multiple") {
    return {
      status: "optimal",
      message: null,
      kept_count: 6,
      rejected_count: 0,
      required_kept: 5,
      residual_sum: 0,
      outlier_quota: 0,
      threshold: 0,
      n_observations: 6,
      n_catalog: 8,
      search_nodes: 10,
      multiple: true,
      canonical: {
        assignments: [
          { observation_index: 0, catalog_index: 1, catalog_id: "STAR-02" },
          { observation_index: 1, catalog_index: 3, catalog_id: "STAR-04" },
          { observation_index: 2, catalog_index: 0, catalog_id: "STAR-01" },
          { observation_index: 3, catalog_index: 2, catalog_id: "STAR-03" },
          { observation_index: 4, catalog_index: 4, catalog_id: "STAR-05" },
          { observation_index: 5, catalog_index: 5, catalog_id: "STAR-06" },
        ],
        rejected: [],
        sequence: ["STAR-02", "STAR-04", "STAR-01", "STAR-03", "STAR-05", "STAR-06"],
        residual_pairs: [
          { i: 0, j: 1, catalog_i: "STAR-02", catalog_j: "STAR-04", measured: 3, actual: 3, residual: 0 },
        ],
        residual_sum: 0,
        at_optimal_residual: true,
      },
      witness: {
        assignments: [
          { observation_index: 0, catalog_index: 2, catalog_id: "STAR-03" },
          { observation_index: 1, catalog_index: 3, catalog_id: "STAR-04" },
          { observation_index: 2, catalog_index: 0, catalog_id: "STAR-01" },
          { observation_index: 3, catalog_index: 1, catalog_id: "STAR-02" },
          { observation_index: 4, catalog_index: 4, catalog_id: "STAR-05" },
          { observation_index: 5, catalog_index: 5, catalog_id: "STAR-06" },
        ],
        rejected: [],
        sequence: ["STAR-03", "STAR-04", "STAR-01", "STAR-02", "STAR-05", "STAR-06"],
        residual_pairs: [],
        residual_sum: 0,
        at_optimal_residual: true,
      },
    };
  }
  // optimal unique with one reject
  return {
    status: "optimal",
    message: null,
    kept_count: 5,
    rejected_count: 1,
    required_kept: 5,
    residual_sum: 0,
    outlier_quota: 2,
    threshold: 1,
    n_observations: 6,
    n_catalog: 8,
    search_nodes: 7,
    multiple: false,
    canonical: {
      assignments: [
        { observation_index: 0, catalog_index: 1, catalog_id: "STAR-02" },
        { observation_index: 1, catalog_index: 3, catalog_id: "STAR-04" },
        { observation_index: 2, catalog_index: 0, catalog_id: "STAR-01" },
        { observation_index: 3, catalog_index: 2, catalog_id: "STAR-03" },
        { observation_index: 4, catalog_index: 4, catalog_id: "STAR-05" },
      ],
      rejected: [5],
      sequence: ["STAR-02", "STAR-04", "STAR-01", "STAR-03", "STAR-05", null],
      residual_pairs: [
        { i: 0, j: 1, catalog_i: "STAR-02", catalog_j: "STAR-04", measured: 3, actual: 3, residual: 0 },
      ],
      residual_sum: 0,
      at_optimal_residual: true,
    },
    witness: null,
  };
}

function mockFetch(kind: string) {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.endsWith("/api/health")) {
      return new Response(JSON.stringify({ status: "ok" }), { status: 200 });
    }
    if (url.endsWith("/api/scenarios")) {
      return new Response(JSON.stringify(SCENARIOS), { status: 200 });
    }
    if (url.endsWith("/api/solve")) {
      if (kind === "invalid") {
        return new Response(
          JSON.stringify({
            detail: "校验失败",
            issues: [
              { loc: ["threshold"], message: "残差阈值必须是非负整数" },
              { loc: ["catalog", 0, "vector"], message: "三维向量必须是 3 个整数" },
            ],
          }),
          { status: 422, headers: { "content-type": "application/json" } },
        );
      }
      return new Response(JSON.stringify(solveResult(kind)), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    return new Response("not found", { status: 404 });
  });
}

async function run() {
  fireEvent.click(screen.getByRole("button", { name: /运行精确识别/ }));
}

describe("App audit flows", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders unique optimal result with retained/rejected nodes", async () => {
    vi.stubGlobal("fetch", mockFetch("optimal"));
    render(<App />);
    await waitFor(() => expect(screen.getByText(/已连接/)).toBeInTheDocument());
    expect(await screen.findByRole("button", { name: /唯一最优映射/ })).toBeInTheDocument();
    await run();
    expect(await screen.findByText("✅ 识别成功")).toBeInTheDocument();
    expect(screen.getAllByText("剔除（伪星）").length).toBeGreaterThan(0);
    expect(screen.getAllByText("STAR-02").length).toBeGreaterThan(0);
    expect(screen.queryByText(/检测到多解/)).not.toBeInTheDocument();
  });

  it("shows incompatible verdict", async () => {
    vi.stubGlobal("fetch", mockFetch("incompatible"));
    render(<App />);
    await run();
    expect(await screen.findByText(/不相容（INCOMPATIBLE）/)).toBeInTheDocument();
    expect(screen.getByText(/不相容：测试原因/)).toBeInTheDocument();
  });

  it("shows multiple solutions, canonical and witness", async () => {
    vi.stubGlobal("fetch", mockFetch("multiple"));
    render(<App />);
    await run();
    expect(await screen.findByText(/检测到多解/)).toBeInTheDocument();
    expect(screen.getByText("规范映射（canonical）")).toBeInTheDocument();
    expect(screen.getByText("另一份见证（witness）")).toBeInTheDocument();
    const tables = screen.getAllByRole("table");
    expect(tables.length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("STAR-03").length).toBeGreaterThan(0);
    // dashed witness path exists in the svg
    const paths = document.querySelectorAll("path[stroke-dasharray]");
    expect(paths.length).toBeGreaterThan(0);
  });

  it("keeps draft and locates reasons on validation failure", async () => {
    vi.stubGlobal("fetch", mockFetch("invalid"));
    render(<App />);
    await waitFor(() => expect(screen.getByText(/已连接/)).toBeInTheDocument());
    // a catalog input still carries the loaded draft
    const idInput = await screen.findByDisplayValue("STAR-01");
    expect(idInput).toBeInTheDocument();
    await run();
    const banner = await screen.findByText(/校验失败：草稿已保留/);
    expect(banner).toBeInTheDocument();
    const links = screen.getAllByRole("button", { name: /threshold|vector/ });
    // first issue targets threshold field which exists
    const thresholdLink = within(banner.parentElement!).getByText("threshold");
    fireEvent.click(thresholdLink.closest("button")!);
    const thresholdField = document.getElementById("f-threshold");
    expect(thresholdField).not.toBeNull();
    expect(links.length).toBeGreaterThan(0);
  });
});
