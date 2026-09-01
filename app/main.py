from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
from typing import Optional

import httpx
from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .cache import TTLCache
from .config import get_settings
from .errors import ErrorCode, FxError
from .service import ConversionService
from .upstream import FrankfurterClient


def create_app(service: Optional[ConversionService] = None) -> FastAPI:
    """Build the app. A pre-built ``service`` can be injected for tests;
    otherwise one is created (with its own httpx client) for the app lifetime."""

    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # A caller-supplied service (tests) is wired eagerly below, so the
        # lifespan only owns the real httpx client and its clean shutdown.
        if service is not None:
            yield
            return

        client = httpx.AsyncClient(timeout=settings.request_timeout)
        app.state.service = ConversionService(
            FrankfurterClient(client, settings.upstream_base),
            TTLCache(),
            settings.latest_cache_ttl,
        )
        try:
            yield
        finally:
            await client.aclose()

    app = FastAPI(title="fx-tool", version="1.0", lifespan=lifespan)
    if service is not None:
        app.state.service = service

    @app.exception_handler(FxError)
    async def _handle_fx_error(_request: Request, exc: FxError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content={"error": exc.code.value, "message": exc.message},
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(p) for p in first.get("loc", []) if p != "query") or "request"
        return JSONResponse(
            status_code=422,
            content={
                "error": ErrorCode.invalid_request.value,
                "message": f"invalid or missing parameter: {field}.",
            },
        )

    @app.get("/tools/convert")
    async def convert(
        request: Request,
        amount: Decimal = Query(...),
        from_: str = Query(..., alias="from"),
        to: str = Query(...),
        date_: Optional[date] = Query(None, alias="date"),
    ) -> JSONResponse:
        service: ConversionService = request.app.state.service
        response = await service.convert(amount=amount, base=from_, target=to, on=date_)
        return JSONResponse(content=response.model_dump(by_alias=True, mode="json"))

    @app.get("/health")
    async def health() -> dict:
        return {"ok": True}

    return app


app = create_app()
