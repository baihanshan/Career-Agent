"""FastAPI application entrypoint."""

import logging


logger = logging.getLogger(__name__)

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
        allow_origins=[],
        allow_origin_regex=r"^http://(?:localhost|127\.0\.0\.1):\d+$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request, exc):
        logger.warning(
            "code=%s validation_error_count=%s",
            ValidationErrorCode.VALIDATION_ERROR.value,
            len(exc.errors()),
        )
        error = AppError(
            code=ValidationErrorCode.VALIDATION_ERROR.value,
            message="请检查输入内容：个人材料和目标岗位 JD 都不能为空，且文件类型必须受支持。",
        )
        return JSONResponse(
            status_code=422,
            content={
                "analysis_id": "analysis_validation_failed",
                "status": "failed",
                "result": None,
                "error": error.model_dump(mode="json", exclude_none=True),
            },
        )

    app.include_router(router)
    return app
app = create_app() if FastAPI is not None else None
