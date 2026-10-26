import logging
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Response, status
from pydantic import ValidationError

from practicum.models import (
    ApplyPortRecommendationRequest,
    ApplySubnetRecommendationRequest,
    DockerEngineInfo,
    ImportResult,
    Lab,
    LabDefinition,
    LabOrigin,
    LabPreview,
    LeftoverSweepResult,
    NetworkCheckResult,
    PortCheckResult,
    RemoveLeftoverNetworkRequest,
    RuntimeActionResult,
    RuntimeStatusResult,
    ValidationIssue,
    ValidationResult,
)
from practicum.service import (
    LabBusyError,
    LabDeleteError,
    LabNotFoundError,
    LabRunningError,
    LabService,
    LeftoverNetworkNotRemovableError,
    PortRecommendationUnavailableError,
    SubnetRecommendationUnavailableError,
)

logger = logging.getLogger("uvicorn.error")  # shows up in the API window


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Labs are in memory only: whatever Practicum containers/networks exist when the API
    # starts belong to a previous session and can never be used again. Remove them (D-40).
    result = service.sweep_leftovers()
    if result.error:
        logger.info("leftover sweep skipped: %s", result.error)
    elif result.removed_containers or result.removed_networks or result.errors:
        logger.info(
            "leftover sweep: removed %d container(s), %d network(s); %d error(s)",
            len(result.removed_containers),
            len(result.removed_networks),
            len(result.errors),
        )
    yield


app = FastAPI(
    title="Practicum API",
    description="Local orchestration for reproducible academic network labs.",
    version="0.1.0",
    lifespan=lifespan,
)
service = LabService()


@app.post("/docker/sweep-leftovers", response_model=LeftoverSweepResult)
def sweep_leftovers() -> LeftoverSweepResult:
    """Removes Practicum containers/networks whose lab this API does not know (also run at
    startup). `error` is set when Docker could not be queried."""
    return service.sweep_leftovers()


@app.get("/docker/engine", response_model=DockerEngineInfo)
def docker_engine() -> DockerEngineInfo:
    """Which kind of container the active Docker daemon serves (Linux or Windows), from a
    read-only `docker info`. The desktop uses it to gate Windows Quick Start; Practicum never
    switches Docker Desktop's engine itself (windows-desktop-windows-container-readiness)."""
    return service.docker_engine()


def validation_issues(exc: ValidationError) -> list[ValidationIssue]:
    return [
        ValidationIssue(
            location=[str(part) for part in error["loc"]],
            message=error["msg"],
            issue_type=error["type"],
        )
        for error in exc.errors(include_url=False, include_context=False)
    ]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/labs/validate")
def validate_lab(definition: dict[str, object]) -> ValidationResult:
    try:
        lab = LabDefinition.model_validate(definition)
    except ValidationError as exc:
        return ValidationResult(valid=False, errors=validation_issues(exc))

    return ValidationResult(valid=True, lab=lab)


@app.post("/labs", response_model=Lab, status_code=status.HTTP_201_CREATED)
def create_lab(
    definition: LabDefinition,
    origin: Annotated[
        LabOrigin,
        Query(description="How this lab was authored on this machine (dashboard bookkeeping)."),
    ] = "designer",
) -> Lab:
    return service.create(definition, origin=origin)


@app.post("/labs/import")
def import_lab(
    definition: dict[str, object],
    source_file: Annotated[
        str | None,
        Query(
            max_length=260,
            description="Name of the file the lab was imported from, shown on the dashboard.",
        ),
    ] = None,
) -> ImportResult:
    try:
        lab_definition = LabDefinition.model_validate(definition)
    except ValidationError as exc:
        return ImportResult(imported=False, errors=validation_issues(exc))

    return ImportResult(
        imported=True,
        lab=service.create(lab_definition, origin="imported", source_file=source_file),
    )


@app.get("/labs", response_model=list[Lab])
def list_labs() -> list[Lab]:
    return service.list()


@app.get("/labs/{lab_id}", response_model=Lab)
def get_lab(lab_id: str) -> Lab:
    try:
        return service.get(lab_id)
    except LabNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Lab not found") from exc


@app.put("/labs/{lab_id}", response_model=Lab)
def replace_lab(lab_id: str, definition: LabDefinition) -> Lab:
    """Edits a lab: the whole definition is replaced (validated like POST /labs); id, origin and
    timestamps are kept. 409 while the lab is running or busy, or when its old Docker resources
    cannot be removed."""
    try:
        return service.replace(lab_id, definition)
    except LabNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Lab not found") from exc
    except (LabRunningError, LabBusyError, LabDeleteError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.delete("/labs/{lab_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lab(lab_id: str) -> Response:
    try:
        service.delete(lab_id)
    except LabNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Lab not found") from exc
    except LabBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except LabDeleteError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/labs/{lab_id}/export", response_model=LabDefinition)
def export_lab(lab_id: str) -> LabDefinition:
    try:
        return service.export(lab_id)
    except LabNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Lab not found") from exc


@app.get("/labs/{lab_id}/preview", response_model=LabPreview)
def preview_lab(lab_id: str) -> LabPreview:
    try:
        return service.preview(lab_id)
    except LabNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Lab not found") from exc


@app.post("/labs/{lab_id}/start", response_model=RuntimeActionResult)
def start_lab(
    lab_id: str,
    response: Response,
    wait: Annotated[
        bool,
        Query(
            description=(
                "true: block until the lab is running or failed (default). false: return at "
                "once with status 'starting' (HTTP 202) and poll GET /labs/{lab_id}/status."
            )
        ),
    ] = True,
) -> RuntimeActionResult:
    try:
        result = service.start(lab_id, wait=wait)
    except LabNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Lab not found") from exc
    except LabBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if result.pending:
        response.status_code = status.HTTP_202_ACCEPTED
    return result


@app.post("/labs/{lab_id}/stop", response_model=RuntimeActionResult)
def stop_lab(lab_id: str) -> RuntimeActionResult:
    try:
        return service.stop(lab_id)
    except LabNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Lab not found") from exc
    except LabBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/labs/{lab_id}/restart", response_model=RuntimeActionResult)
def restart_lab(lab_id: str) -> RuntimeActionResult:
    """Stop then Start as one action; a lab that is not running is simply started."""
    try:
        return service.restart(lab_id)
    except LabNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Lab not found") from exc
    except LabBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/labs/{lab_id}/reset", response_model=RuntimeActionResult)
def reset_lab(lab_id: str) -> RuntimeActionResult:
    try:
        return service.reset(lab_id)
    except LabNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Lab not found") from exc
    except LabBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/labs/{lab_id}/status", response_model=RuntimeStatusResult)
def lab_status(lab_id: str) -> RuntimeStatusResult:
    try:
        return service.status(lab_id)
    except LabNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Lab not found") from exc


@app.get("/labs/{lab_id}/ports", response_model=PortCheckResult)
def get_lab_ports(lab_id: str) -> PortCheckResult:
    try:
        return service.check_ports(lab_id)
    except LabNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Lab not found") from exc


@app.post("/labs/{lab_id}/ports/apply-recommendation", response_model=PortCheckResult)
def apply_port_recommendation(
    lab_id: str, request: ApplyPortRecommendationRequest
) -> PortCheckResult:
    try:
        return service.apply_port_recommendation(
            lab_id, request.node_id, request.host_port, request.protocol, request.new_host_port
        )
    except LabNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Lab not found") from exc
    except (PortRecommendationUnavailableError, LabBusyError, LabDeleteError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/labs/{lab_id}/networks", response_model=NetworkCheckResult)
def get_lab_networks(lab_id: str) -> NetworkCheckResult:
    try:
        return service.check_networks(lab_id)
    except LabNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Lab not found") from exc


@app.post("/labs/{lab_id}/networks/apply-recommendation", response_model=NetworkCheckResult)
def apply_subnet_recommendation(
    lab_id: str, request: ApplySubnetRecommendationRequest
) -> NetworkCheckResult:
    try:
        return service.apply_subnet_recommendation(lab_id, request.network_id)
    except LabNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Lab not found") from exc
    except (SubnetRecommendationUnavailableError, LabBusyError, LabDeleteError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/labs/{lab_id}/networks/remove-leftover", response_model=NetworkCheckResult)
def remove_leftover_network(
    lab_id: str, request: RemoveLeftoverNetworkRequest
) -> NetworkCheckResult:
    try:
        return service.remove_leftover_network(lab_id, request.network_name)
    except LabNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Lab not found") from exc
    except LeftoverNetworkNotRemovableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
