"""FastAPI application for the star-field identification audit console."""

from __future__ import annotations

import os
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .solver import SolveValidationError, solve
from .scenarios import list_scenarios

SERVICE_NAME = os.getenv("SERVICE_NAME", "star-id-api")


app = FastAPI(
    title="星场身份审计台 API",
    description="精确整数分支限界搜索的星敏感器注入映射识别服务",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STARTED_AT = time.time()


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "uptime_seconds": round(time.time() - STARTED_AT, 3),
    }


@app.exception_handler(SolveValidationError)
async def handle_validation_error(_: Request, exc: SolveValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": "校验失败", "issues": exc.issues},
    )


@app.get("/api/scenarios")
def scenarios_endpoint() -> list[dict]:
    return list_scenarios()


@app.post("/api/solve")
async def solve_endpoint(request: Request) -> dict:
    # Accept raw JSON on purpose: every business/shape/type rule lives in
    # solver.solve(), so validation failures always carry locatable issues.
    try:
        payload = await request.json()
    except ValueError:
        return JSONResponse(
            status_code=422,
            content={
                "detail": "校验失败",
                "issues": [{"loc": [], "message": "请求体不是合法 JSON"}],
            },
        )
    started = time.perf_counter()
    result = solve(payload)
    result["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
    return result
