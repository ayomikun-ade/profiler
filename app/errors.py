from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.services.external import UpstreamError


def error_response(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"status": "error", "message": message},
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError):
        errors = exc.errors()
        if any((err.get("loc") or ("body",))[0] == "query" for err in errors):
            return error_response(422, "Invalid query parameters")
        first = errors[0] if errors else {}
        loc = first.get("loc", ())
        where = loc[0] if loc else "body"
        field = loc[-1] if len(loc) > 1 else None
        subject = f"{where} parameter '{field}'" if field else where
        return error_response(422, f"Invalid {subject}")

    @app.exception_handler(UpstreamError)
    async def _upstream_handler(request: Request, exc: UpstreamError):
        return error_response(502, f"{exc.api_name} returned an invalid response")

    @app.exception_handler(StarletteHTTPException)
    async def _http_handler(request: Request, exc: StarletteHTTPException):
        detail = exc.detail if isinstance(exc.detail, str) else "error"
        return error_response(exc.status_code, detail)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        return error_response(500, "Internal server error")
