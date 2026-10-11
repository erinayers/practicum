from fastapi import FastAPI, HTTPException, status
from pydantic import ValidationError

from practicum.models import (
    ApplyPortRecommendationRequest,
    ImportResult,
    Lab,
    LabDefinition,
    LabPreview,
    PortCheckResult,
    RuntimeActionResult,
    RuntimeStatusResult,
    ValidationIssue,
    ValidationResult,
)
from practicum.service import LabNotFoundError, LabService, PortRecommendationUnavailableError

app = FastAPI(
    title="Practicum API",
    description="Local orchestration for reproducible academic network labs.",
    version="0.1.0",
)
service = LabService()


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
def create_lab(definition: LabDefinition) -> Lab:
    return service.create(definition)


@app.post("/labs/import")
def import_lab(definition: dict[str, object]) -> ImportResult:
    try:
        lab_definition = LabDefinition.model_validate(definition)
    except ValidationError as exc:
        return ImportResult(imported=False, errors=validation_issues(exc))

    return ImportResult(imported=True, lab=service.create(lab_definition))


@app.get("/labs", response_model=list[Lab])
def list_labs() -> list[Lab]:
    return service.list()


@app.get("/labs/{lab_id}", response_model=Lab)
def get_lab(lab_id: str) -> Lab:
    try:
        return service.get(lab_id)
    except LabNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Lab not found") from exc


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
def start_lab(lab_id: str) -> RuntimeActionResult:
    try:
        return service.start(lab_id)
    except LabNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Lab not found") from exc


@app.post("/labs/{lab_id}/stop", response_model=RuntimeActionResult)
def stop_lab(lab_id: str) -> RuntimeActionResult:
    try:
        return service.stop(lab_id)
    except LabNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Lab not found") from exc


@app.post("/labs/{lab_id}/reset", response_model=RuntimeActionResult)
def reset_lab(lab_id: str) -> RuntimeActionResult:
    try:
        return service.reset(lab_id)
    except LabNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Lab not found") from exc


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
            lab_id, request.node_id, request.host_port, request.protocol
        )
    except LabNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Lab not found") from exc
    except PortRecommendationUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
