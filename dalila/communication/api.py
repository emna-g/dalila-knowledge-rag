"""Versioned HTTP boundary for the existing Dalila agent."""

import logging
import os
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from dalila.config import charger_env
from dalila.communication.schemas import (
    ApiError,
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    GeoJSONFeatureCollection,
    MapZonesResponse,
)
from dalila.communication.service import AgentFactory, ChatService, MapService, creer_agent

logger = logging.getLogger(__name__)

def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", str(uuid4()))


def create_app(
    agent_factory: AgentFactory = creer_agent,
    map_service: Optional[MapService] = None,
) -> FastAPI:
    charger_env()
    app = FastAPI(
        title="DALILA API",
        version="1.0.0",
        description="Versioned, source-aware HTTP interface for the DALILA agent.",
    )
    app.state.chat_service = ChatService(agent_factory)
    app.state.map_service = map_service or MapService()

    origins = [
        origin.strip()
        for origin in os.environ.get(
            "DALILA_CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request_id = str(uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError):
        error = ErrorResponse(
            request_id=_request_id(request),
            error=ApiError(
                code="invalid_request",
                message="La requête ne respecte pas le contrat de l'API.",
            ),
        )
        return JSONResponse(status_code=422, content=error.model_dump(mode="json"))

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        code = "not_found" if exc.status_code == 404 else "http_error"
        message = str(exc.detail) if isinstance(exc.detail, str) else "La requête HTTP n'a pas pu être traitée."
        error = ErrorResponse(
            request_id=_request_id(request),
            error=ApiError(code=code, message=message),
        )
        return JSONResponse(status_code=exc.status_code, content=error.model_dump(mode="json"))

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        request_id = _request_id(request)
        logger.exception("DALILA request failed (request_id=%s)", request_id)
        error = ErrorResponse(
            request_id=request_id,
            error=ApiError(
                code="internal_error",
                message="Une erreur interne a empêché le traitement de la requête.",
            ),
        )
        return JSONResponse(status_code=500, content=error.model_dump(mode="json"))

    @app.post("/api/v1/chat", response_model=ChatResponse)
    def chat(payload: ChatRequest, request: Request) -> ChatResponse:
        return request.app.state.chat_service.traiter(_request_id(request), payload)

    @app.get("/api/v1/map/zones", response_model=MapZonesResponse)
    def map_zones(request: Request) -> MapZonesResponse:
        return request.app.state.map_service.zones()

    @app.get(
        "/api/v1/map/zones/{zone_id}/lots",
        response_model=GeoJSONFeatureCollection,
    )
    def map_zone_lots(
        request: Request,
        zone_id: str = Path(..., min_length=1, max_length=24),
        limit: int = Query(default=500, ge=1, le=1000),
        after_lot_id: Optional[int] = Query(default=None, ge=0),
    ) -> GeoJSONFeatureCollection:
        result = request.app.state.map_service.lots(zone_id, limit, after_lot_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Zone absente des vues publiques AFI.")
        return result

    return app


app = create_app()
