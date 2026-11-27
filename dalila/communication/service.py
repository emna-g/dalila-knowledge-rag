"""Application adapter between HTTP DTOs and the existing DALILA agent."""

from typing import Any, Callable, Dict, List, Optional, Protocol

from dalila.communication.schemas import (
    ApiError,
    ChatRequest,
    ChatResponse,
    GeoJSONFeatureCollection,
    MapZonesResponse,
    SourceReference,
)


class AgentPort(Protocol):
    def repondre(
        self,
        message: str,
        historique: List[Dict[str, str]],
        lang: Optional[str],
        contexte: Optional[str],
    ) -> Dict[str, Any]:
        ...


AgentFactory = Callable[[], AgentPort]


def creer_agent() -> AgentPort:
    from dalila.harnais.agent import Agent

    return Agent()


def _source_reference(value: Dict[str, Any], passage: bool = False) -> SourceReference:
    source_id = value.get("source_id")
    if passage:
        source_id = value.get("id") or source_id
    return SourceReference(
        source_id=str(source_id) if source_id is not None else None,
        title=value.get("titre") or value.get("title") or value.get("name"),
        source=value.get("source"),
        url=value.get("url") or value.get("lien") or value.get("source_url"),
        date=value.get("date_source") or value.get("date") or value.get("retrieved_at"),
    )


def _sources_from_tool_results(results: Any) -> List[SourceReference]:
    if not isinstance(results, list):
        return []

    sources: List[SourceReference] = []
    positions: Dict[Any, int] = {}

    def add(reference: SourceReference) -> None:
        if not reference.title and not reference.url and not reference.source_id:
            return
        key = (reference.title, reference.url)
        if key not in positions:
            positions[key] = len(sources)
            sources.append(reference)
            return

        existing = sources[positions[key]]
        for field in ("source_id", "source", "date"):
            if getattr(existing, field) is None and getattr(reference, field) is not None:
                setattr(existing, field, getattr(reference, field))

    for result in results:
        if not isinstance(result, dict):
            continue
        tool_sources = result.get("sources")
        if isinstance(tool_sources, list):
            for value in tool_sources:
                if isinstance(value, dict):
                    add(_source_reference(value))
        passages = result.get("passages")
        if isinstance(passages, list):
            for passage in passages:
                if isinstance(passage, dict):
                    add(_source_reference(passage, passage=True))

    return sources


def _chat_response(request_id: str, result: Dict[str, Any]) -> ChatResponse:
    answer = result.get("reponse")
    if not isinstance(answer, str):
        raise ValueError("L'agent a retourné un résultat sans texte de réponse.")

    error_message = result.get("erreur")
    anchor = result.get("ancrage")
    is_anchored = isinstance(anchor, dict) and anchor.get("ok") is True
    if result.get("source") == "dalila" and is_anchored and not error_message:
        status = "answered"
        error = None
    elif error_message in (
        "aucune donnée exploitable retournée par les outils",
        "réponse non ancrée",
    ):
        status = "abstained"
        error = ApiError(
            code="insufficient_evidence",
            message="Les résultats disponibles ne permettent pas de vérifier une réponse factuelle.",
        )
    else:
        status = "degraded"
        error = ApiError(
            code="agent_unavailable",
            message="L'agent n'a pas pu produire une réponse vérifiée.",
        )

    return ChatResponse(
        request_id=request_id,
        status=status,
        answer=answer,
        sources=_sources_from_tool_results(result.get("resultats_outils")),
        map_data=None,
        error=error,
    )


class ChatService:
    def __init__(self, agent_factory: AgentFactory):
        self._agent_factory = agent_factory

    def traiter(self, request_id: str, payload: ChatRequest) -> ChatResponse:
        history = [message.model_dump() for message in payload.history]
        context = payload.context.to_agent_context() if payload.context else None
        result = self._agent_factory().repondre(
            payload.message,
            historique=history,
            lang=payload.lang,
            contexte=context,
        )
        return _chat_response(request_id, result)


class MapService:
    def zones(self) -> MapZonesResponse:
        from dalila.traitement.carte import lister_zones_carte

        return MapZonesResponse.model_validate(lister_zones_carte())

    def lots(
        self,
        zone_id: str,
        limit: int,
        after_lot_id: Optional[int],
    ) -> Optional[GeoJSONFeatureCollection]:
        from dalila.traitement.carte import lots_carte

        result = lots_carte(zone_id, limit=limit, after_lot_id=after_lot_id)
        return GeoJSONFeatureCollection.model_validate(result) if result is not None else None
