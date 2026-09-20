import type { Issue, Scenario, SolveRequest, SolveResult } from "./types";

export class ValidationFailed extends Error {
  issues: Issue[];
  constructor(issues: Issue[]) {
    super("校验失败");
    this.issues = issues;
  }
}

async function parseError(res: Response): Promise<never> {
  let issues: Issue[] = [];
  try {
    const data = await res.json();
    if (Array.isArray(data.issues)) issues = data.issues;
  } catch {
    /* ignore */
  }
  if (issues.length === 0) issues = [{ loc: [], message: `HTTP ${res.status}` }];
  throw new ValidationFailed(issues);
}

export async function fetchHealth(): Promise<{ status: string }> {
  const res = await fetch("/api/health");
  if (!res.ok) await parseError(res);
  return res.json();
}

export async function fetchScenarios(): Promise<Scenario[]> {
  const res = await fetch("/api/scenarios");
  if (!res.ok) await parseError(res);
  return res.json();
}

export async function solve(req: SolveRequest): Promise<SolveResult> {
  const res = await fetch("/api/solve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) await parseError(res);
  return res.json();
}
