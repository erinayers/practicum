import pytest

from practicum.models import LabDefinition
from practicum.runtime import DockerRuntime
from practicum.service import LabNotFoundError, LabService


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
