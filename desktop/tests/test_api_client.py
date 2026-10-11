import httpx

from practicum_desktop.api_client import ApiClient


def test_check_health_reports_healthy_when_api_ok(monkeypatch) -> None:
    def fake_get(url, timeout):
        return httpx.Response(200, json={"status": "ok"}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    client = ApiClient(base_url="http://127.0.0.1:8000")

    status = client.check_health()

    assert status.reachable is True
    assert status.healthy is True


def test_check_health_reports_unreachable_on_connect_error(monkeypatch) -> None:
    def fake_get(url, timeout):
        raise httpx.ConnectError("refused", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    client = ApiClient()

    status = client.check_health()

    assert status.reachable is False
    assert status.healthy is False


def test_check_health_reports_unreachable_on_timeout(monkeypatch) -> None:
    def fake_get(url, timeout):
        raise httpx.TimeoutException("timed out", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    client = ApiClient()

    status = client.check_health()

    assert status.reachable is False
    assert status.healthy is False


def test_check_health_reports_unhealthy_on_non_200(monkeypatch) -> None:
    def fake_get(url, timeout):
        return httpx.Response(500, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    client = ApiClient()

    status = client.check_health()

    assert status.reachable is True
    assert status.healthy is False


def test_check_health_reports_unhealthy_on_bad_status_field(monkeypatch) -> None:
    def fake_get(url, timeout):
        return httpx.Response(200, json={"status": "degraded"}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    client = ApiClient()

    status = client.check_health()

    assert status.healthy is False


def test_list_labs_returns_summaries(monkeypatch) -> None:
    def fake_get(url, timeout):
        return httpx.Response(
            200,
            json=[{"id": "abc", "name": "Static Routing", "status": "defined"}],
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    client = ApiClient()

    result = client.list_labs()

    assert result.success is True
    assert result.labs[0].id == "abc"
    assert result.labs[0].name == "Static Routing"
    assert result.labs[0].status == "defined"


def test_list_labs_reports_failure_on_connection_error(monkeypatch) -> None:
    def fake_get(url, timeout):
        raise httpx.ConnectError("refused", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    client = ApiClient()

    result = client.list_labs()

    assert result.success is False
    assert result.labs == []


def test_list_labs_reports_failure_on_non_200(monkeypatch) -> None:
    def fake_get(url, timeout):
        return httpx.Response(503, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    client = ApiClient()

    result = client.list_labs()

    assert result.success is False


def test_check_ports_reports_no_conflicts(monkeypatch) -> None:
    def fake_get(url, timeout):
        return httpx.Response(
            200,
            json={"lab_id": "abc", "has_conflicts": False, "conflicts": []},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    client = ApiClient()

    result = client.check_ports("abc")

    assert result.success is True
    assert result.has_conflicts is False
    assert result.conflicts == []


def test_check_ports_reports_conflicts_with_recommendation(monkeypatch) -> None:
    def fake_get(url, timeout):
        return httpx.Response(
            200,
            json={
                "lab_id": "abc",
                "has_conflicts": True,
                "conflicts": [
                    {
                        "node_id": "router",
                        "host_port": 2222,
                        "container_port": 22,
                        "protocol": "tcp",
                        "reason": "in_use_on_host",
                        "recommended_port": 2223,
                    }
                ],
            },
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    client = ApiClient()

    result = client.check_ports("abc")

    assert result.has_conflicts is True
    assert result.conflicts[0].node_id == "router"
    assert result.conflicts[0].recommended_port == 2223


def test_check_ports_reports_failure_on_missing_lab(monkeypatch) -> None:
    def fake_get(url, timeout):
        return httpx.Response(404, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    client = ApiClient()

    result = client.check_ports("missing")

    assert result.success is False


def test_apply_port_recommendation_returns_updated_result(monkeypatch) -> None:
    def fake_post(url, json, timeout):
        return httpx.Response(
            200,
            json={"lab_id": "abc", "has_conflicts": False, "conflicts": []},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ApiClient()

    result = client.apply_port_recommendation("abc", "router", 2222, "tcp")

    assert result.success is True
    assert result.has_conflicts is False


def test_apply_port_recommendation_surfaces_detail_on_conflict_error(monkeypatch) -> None:
    def fake_post(url, json, timeout):
        return httpx.Response(
            409,
            json={"detail": "No recommended port is available"},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ApiClient()

    result = client.apply_port_recommendation("abc", "router", 2222, "tcp")

    assert result.success is False
    assert result.detail == "No recommended port is available"


def test_start_lab_reports_success(monkeypatch) -> None:
    def fake_post(url, timeout):
        return httpx.Response(
            200,
            json={"success": True, "lab": {"id": "abc", "status": "running"}, "errors": []},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ApiClient()

    result = client.start_lab("abc")

    assert result.success is True


def test_start_lab_reports_runtime_error(monkeypatch) -> None:
    def fake_post(url, timeout):
        return httpx.Response(
            200,
            json={
                "success": False,
                "lab": {"id": "abc", "status": "error"},
                "errors": [{"message": "Docker is unavailable", "command": ["docker", "ps"]}],
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ApiClient()

    result = client.start_lab("abc")

    assert result.success is False
    assert result.detail == "Docker is unavailable"


def test_start_lab_reports_connection_failure(monkeypatch) -> None:
    def fake_post(url, timeout):
        raise httpx.ConnectError("refused", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ApiClient()

    result = client.start_lab("abc")

    assert result.success is False


def test_validate_lab_reports_valid(monkeypatch) -> None:
    def fake_post(url, json, timeout):
        return httpx.Response(
            200,
            json={"valid": True, "lab": json, "errors": []},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ApiClient()

    result = client.validate_lab({"name": "Test Lab"})

    assert result.success is True
    assert result.valid is True
    assert result.errors == []


def test_validate_lab_reports_field_errors(monkeypatch) -> None:
    def fake_post(url, json, timeout):
        return httpx.Response(
            200,
            json={
                "valid": False,
                "errors": [
                    {"location": ["nodes"], "message": "Field required", "issue_type": "missing"}
                ],
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ApiClient()

    result = client.validate_lab({"name": "Test Lab"})

    assert result.success is True
    assert result.valid is False
    assert result.errors[0].location == ["nodes"]
    assert result.errors[0].message == "Field required"


def test_validate_lab_reports_connection_failure(monkeypatch) -> None:
    def fake_post(url, json, timeout):
        raise httpx.ConnectError("refused", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ApiClient()

    result = client.validate_lab({"name": "Test Lab"})

    assert result.success is False


def test_create_lab_reports_success(monkeypatch) -> None:
    def fake_post(url, json, timeout):
        return httpx.Response(
            201,
            json={"id": "abc", "name": "Test Lab", "status": "defined"},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ApiClient()

    result = client.create_lab({"name": "Test Lab"})

    assert result.success is True
    assert result.lab_id == "abc"


def test_create_lab_reports_validation_errors(monkeypatch) -> None:
    def fake_post(url, json, timeout):
        return httpx.Response(
            422,
            json={"detail": [{"loc": ["body", "nodes"], "msg": "Field required", "type": "missing"}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ApiClient()

    result = client.create_lab({"name": "Test Lab"})

    assert result.success is False
    assert result.errors[0].location == ["body", "nodes"]
    assert result.errors[0].message == "Field required"


def test_create_lab_reports_connection_failure(monkeypatch) -> None:
    def fake_post(url, json, timeout):
        raise httpx.ConnectError("refused", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ApiClient()

    result = client.create_lab({"name": "Test Lab"})

    assert result.success is False


def test_get_preview_returns_manual_sections(monkeypatch) -> None:
    def fake_get(url, timeout):
        return httpx.Response(
            200,
            json={
                "id": "abc",
                "status": "defined",
                "schema_version": "1.0",
                "name": "Static Routing",
                "required_images": [],
                "estimated_resources": {"exposed_ports": [], "port_mappings": []},
                "topology": {"nodes": [], "networks": [], "interfaces": []},
                "manual": {
                    "sections": [
                        {
                            "id": "overview",
                            "title": "Overview",
                            "content_markdown": "## Goal",
                            "tasks": [{"id": "verify-topology", "text": "Review the topology."}],
                        }
                    ]
                },
            },
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    client = ApiClient()

    result = client.get_preview("abc")

    assert result.success is True
    assert result.name == "Static Routing"
    assert result.manual_sections[0].id == "overview"
    assert result.manual_sections[0].tasks[0].text == "Review the topology."


def test_get_preview_returns_port_mappings(monkeypatch) -> None:
    def fake_get(url, timeout):
        return httpx.Response(
            200,
            json={
                "id": "abc",
                "status": "defined",
                "schema_version": "1.0",
                "name": "Ubuntu Quick Start",
                "required_images": [],
                "estimated_resources": {
                    "exposed_ports": [],
                    "port_mappings": [{"host": 3001, "container": 3001, "protocol": "tcp"}],
                },
                "topology": {"nodes": [], "networks": [], "interfaces": []},
                "manual": None,
            },
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    client = ApiClient()

    result = client.get_preview("abc")

    assert result.success is True
    assert result.port_mappings[0].host == 3001
    assert result.port_mappings[0].container == 3001
    assert result.port_mappings[0].protocol == "tcp"


def test_get_preview_returns_no_sections_when_manual_absent(monkeypatch) -> None:
    def fake_get(url, timeout):
        return httpx.Response(
            200,
            json={
                "id": "abc",
                "status": "defined",
                "schema_version": "1.0",
                "name": "Static Routing",
                "required_images": [],
                "estimated_resources": {"exposed_ports": [], "port_mappings": []},
                "topology": {"nodes": [], "networks": [], "interfaces": []},
                "manual": None,
            },
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    client = ApiClient()

    result = client.get_preview("abc")

    assert result.success is True
    assert result.manual_sections == []


def test_get_preview_reports_failure_on_missing_lab(monkeypatch) -> None:
    def fake_get(url, timeout):
        return httpx.Response(404, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    client = ApiClient()

    result = client.get_preview("missing")

    assert result.success is False


def test_get_preview_reports_connection_failure(monkeypatch) -> None:
    def fake_get(url, timeout):
        raise httpx.ConnectError("refused", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    client = ApiClient()

    result = client.get_preview("abc")

    assert result.success is False

