export interface CatalogStar {
  id: string;
  magnitude: number;
  vector: [number, number, number];
}

export interface Observation {
  magnitude: number | string;
}

export interface SolveRequest {
  threshold: number;
  outlier_quota: number;
  catalog: CatalogStar[];
  observations: Observation[];
  dot_measurements: number[][];
}

export interface Issue {
  loc: (string | number)[];
  message: string;
}

export interface ResidualPair {
  i: number;
  j: number;
  catalog_i: string;
  catalog_j: string;
  measured: number;
  actual: number;
  residual: number;
}

export interface Mapping {
  assignments: { observation_index: number; catalog_index: number; catalog_id: string }[];
  rejected: number[];
  sequence: (string | null)[];
  residual_pairs: ResidualPair[];
  residual_sum: number;
  at_optimal_residual: boolean;
}

export interface SolveResult {
  status: "optimal" | "incompatible";
  message: string | null;
  kept_count: number;
  rejected_count?: number;
  required_kept: number;
  residual_sum?: number;
  outlier_quota: number;
  threshold: number;
  n_observations: number;
  n_catalog: number;
  search_nodes: number;
  multiple: boolean;
  canonical: Mapping | null;
  witness: Mapping | null;
  elapsed_ms?: number;
}

export interface Scenario extends SolveRequest {
  key: string;
  title: string;
  description: string;
}
