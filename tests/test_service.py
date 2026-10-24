import pytest

from practicum.models import LabDefinition
from practicum.runtime import DockerRuntime
from practicum.service import LabBusyError, LabNotFoundError, LabService


@pytest.fixture
def service() -> LabService:
    return LabService(runtime=DockerRuntime())


def test_create_assigns_a_unique_id(service: LabService, lab_definition: dict) -> None:
    definition = LabDefinition.model_validate(lab_definition)

    first = service.create(definition)
    second = service.create(definition)

    assert first.id != second.id
    assert first.status == "defined"


def test_list_returns_all_created_labs(service: LabService, lab_definition: dict) -> None:
    definition = LabDefinition.model_validate(lab_definition)
    first = service.create(definition)
    second = service.create(definition)

    labs = service.list()

    assert [lab.id for lab in labs] == [first.id, second.id]


def test_get_missing_lab_raises_not_found(service: LabService) -> None:
    with pytest.raises(LabNotFoundError):
        service.get("missing-id")


def test_export_missing_lab_raises_not_found(service: LabService) -> None:
    with pytest.raises(LabNotFoundError):
        service.export("missing-id")


def test_preview_missing_lab_raises_not_found(service: LabService) -> None:
    with pytest.raises(LabNotFoundError):
        service.preview("missing-id")


def test_start_missing_lab_raises_not_found(service: LabService) -> None:
    with pytest.raises(LabNotFoundError):
        service.start("missing-id")


def test_stop_missing_lab_raises_not_found(service: LabService) -> None:
    with pytest.raises(LabNotFoundError):
        service.stop("missing-id")


def test_reset_missing_lab_raises_not_found(service: LabService) -> None:
    with pytest.raises(LabNotFoundError):
        service.reset("missing-id")


def test_status_missing_lab_raises_not_found(service: LabService) -> None:
    with pytest.raises(LabNotFoundError):
        service.status("missing-id")


def test_clear_removes_all_labs(service: LabService, lab_definition: dict) -> None:
    definition = LabDefinition.model_validate(lab_definition)
    service.create(definition)

    service.clear()

    assert service.list() == []


def test_preview_estimates_resources_across_nodes(
    service: LabService, lab_definition: dict
) -> None:
    definition = LabDefinition.model_validate(lab_definition)
    lab = service.create(definition)

    preview = service.preview(lab.id)

    assert preview.required_images == ["alpine:3.21"]
    assert preview.estimated_resources.total_cpu == 2.0
    assert preview.estimated_resources.total_memory_mb == 512


def test_delete_missing_lab_raises_not_found(service: LabService) -> None:
    with pytest.raises(LabNotFoundError):
        service.delete("missing")


def test_delete_forgets_a_never_started_lab_without_docker(
    service: LabService, lab_definition: dict
) -> None:
    lab = service.create(LabDefinition.model_validate(lab_definition))

    service.delete(lab.id)

    assert service.list() == []


def test_restart_missing_lab_raises_not_found(service: LabService) -> None:
    with pytest.raises(LabNotFoundError):
        service.restart("missing")


def test_busy_lab_rejects_every_lifecycle_action(service: LabService, lab_definition: dict) -> None:
    lab = service.create(LabDefinition.model_validate(lab_definition))
    lab.status = "stopping"

    for action in (service.start, service.stop, service.restart, service.reset, service.delete):
        with pytest.raises(LabBusyError):
            action(lab.id)
    assert lab.status == "stopping"


def test_export_strips_local_bookkeeping_fields(service: LabService, lab_definition: dict) -> None:
    lab = service.create(
        LabDefinition.model_validate(lab_definition), origin="imported", source_file="x.json"
    )
    lab.last_error = "boom"

    exported = service.export(lab.id).model_dump()

    for field in ("id", "status", "origin", "source_file", "created_at", "last_started_at", "last_error"):
        assert field not in exported
    assert exported["name"] == lab_definition["name"]
