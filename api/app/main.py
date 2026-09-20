"""星场身份识别审计 API。"""
import os
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .solver import Solver, build_response
from .validation import validate_payload

app = FastAPI(title="星场身份识别审计 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/identify")
async def identify(request: Request):
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(
            status_code=422,
            content={"status": "invalid",
                     "errors": [{"path": "", "message": "请求体不是合法的 JSON"}]},
        )

    data, errors = validate_payload(payload)
    if errors:
        return JSONResponse(
            status_code=422,
            content={"status": "invalid", "errors": errors},
        )

    started = time.perf_counter()
    solver = Solver(
        catalog=data["catalog"],
        obs_classes=data["obs_classes"],
        meas=data["meas"],
        threshold=data["threshold"],
        max_outliers=data["max_outliers"],
    )
    result = solver.solve()
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)

    response = build_response(
        result, data["catalog"], data["obs_classes"], data["meas"]
    )
    response["elapsed_ms"] = elapsed_ms
    response["threshold"] = data["threshold"]
    response["max_outliers"] = data["max_outliers"]
    return response


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
