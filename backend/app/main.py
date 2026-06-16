"""FastAPI application entrypoint."""

try:
    from fastapi import FastAPI
    from fastapi.exceptions import RequestValidationError
    from fastapi.responses import JSONResponse
    from fastapi.middleware.cors import CORSMiddleware
except ImportError:  # pragma: no cover - allows structure checks before deps install
    FastAPI = None


def create_app():
    if FastAPI is None:
        raise RuntimeError("FastAPI is not installed. Install backend dependencies first.")

    from backend.app.api.routes import router
    from backend.app.core.errors import AppError, ValidationErrorCode

    app = FastAPI(title="CareerPilot Agent")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request, exc):
        error = AppError(
            code=ValidationErrorCode.VALIDATION_ERROR.value,
            message="请检查输入内容：个人材料和目标岗位 JD 都不能为空，且文件类型必须受支持。",
            details={"errors": _serializable_validation_errors(exc.errors())},
        )
        return JSONResponse(
            status_code=422,
            content={
                "analysis_id": "analysis_validation_failed",
                "status": "failed",
                "result": None,
                "error": error.model_dump(mode="json"),
            },
        )

    app.include_router(router)
    return app


def _serializable_validation_errors(errors):
    cleaned = []
    for error in errors:
        item = dict(error)
        if "ctx" in item:
            item["ctx"] = {key: str(value) for key, value in item["ctx"].items()}
        cleaned.append(item)
    return cleaned


app = create_app() if FastAPI is not None else None
