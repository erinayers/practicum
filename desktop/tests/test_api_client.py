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



def test_start_lab_uses_the_long_lifecycle_timeout(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def fake_post(url, timeout):
        seen["timeout"] = timeout
        return httpx.Response(
            200,
            json={"success": True, "lab": {"id": "abc", "status": "running"}, "errors": []},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ApiClient(timeout=3.0, lifecycle_timeout=120.0)

    client.start_lab("abc")

    assert seen["timeout"] == 120.0


def test_start_lab_explains_timeout_instead_of_raw_exception(monkeypatch) -> None:
    def fake_post(url, timeout):
        raise httpx.ReadTimeout("timed out", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ApiClient()

    result = client.start_lab("abc")

    assert result.success is False
    assert "did not finish starting the lab in time" in result.detail


def test_import_lab_reports_success_with_lab_identity(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def fake_post(url, json, timeout):
        seen["url"] = url
        seen["json"] = json
        return httpx.Response(
            200,
            json={
                "imported": True,
                "lab": {"id": "lab-123", "name": "Static Routing", "status": "defined"},
                "errors": [],
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ApiClient(base_url="http://127.0.0.1:8000")

    result = client.import_lab({"name": "Static Routing"})

    assert seen["url"] == "http://127.0.0.1:8000/labs/import"
    assert seen["json"] == {"name": "Static Routing"}
    assert result.success is True
    assert result.lab_id == "lab-123"
    assert result.lab_name == "Static Routing"
    assert result.errors == []


def test_import_lab_reports_structured_validation_errors(monkeypatch) -> None:
    def fake_post(url, json, timeout):
        return httpx.Response(
            200,
            json={
                "imported": False,
                "lab": None,
                "errors": [
                    {
                        "location": ["nodes", 0, "image"],
                        "message": "Field required",
                        "issue_type": "missing",
                    }
                ],
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ApiClient()

    result = client.import_lab({"name": "broken"})

    assert result.success is False
    assert result.lab_id is None
    assert len(result.errors) == 1
    assert result.errors[0].location == ["nodes", "0", "image"]
    assert result.errors[0].message == "Field required"
    assert result.errors[0].issue_type == "missing"


def test_import_lab_reports_connection_failure_without_errors(monkeypatch) -> None:
    def fake_post(url, json, timeout):
        raise httpx.ConnectError("refused", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ApiClient()

    result = client.import_lab({"name": "x"})

    assert result.success is False
    assert result.errors == []
    assert "Could not connect" in result.detail


def test_import_lab_reports_timeout(monkeypatch) -> None:
    def fake_post(url, json, timeout):
        raise httpx.ReadTimeout("slow", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ApiClient()

    result = client.import_lab({"name": "x"})

    assert result.success is False
    assert "did not respond in time" in result.detail


def test_import_lab_handles_non_object_body_rejection(monkeypatch) -> None:
    def fake_post(url, json, timeout):
        return httpx.Response(
            422, json={"detail": [{"loc": ["body"]}]}, request=httpx.Request("POST", url)
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ApiClient()

    result = client.import_lab({"name": "x"})

    assert result.success is False
    assert "does not contain a lab definition object" in result.detail


def test_import_lab_handles_unexpected_response(monkeypatch) -> None:
    def fake_post(url, json, timeout):
        return httpx.Response(200, content=b"not json", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ApiClient()

    result = client.import_lab({"name": "x"})

    assert result.success is False
    assert "unexpected import response" in result.detail


def _network_body(**overrides):
    conflict = {
        "network_id": "lab-net",
        "subnet": "10.50.0.0/24",
        "reason": "overlaps_leftover",
        "owner_network_name": "practicum-deadbeef-lab-net",
        "owner_subnet": "10.50.0.0/24",
        "owner_lab_id": "deadbeef-0000-0000-0000-000000000000",
        "owner_lab_name": None,
        "owner_lab_status": None,
        "owner_container_count": 1,
        "recommended_subnet": "10.90.0.0/24",
    }
    body = {"lab_id": "abc", "has_conflicts": True, "conflicts": [conflict], "error": None}
    body.update(overrides)
    return body


def test_check_networks_parses_conflicts(monkeypatch) -> None:
    def fake_get(url, timeout):
        assert url.endswith("/labs/abc/networks")
        return httpx.Response(200, json=_network_body(), request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)

    result = ApiClient().check_networks("abc")

    assert result.success is True
    assert result.has_conflicts is True
    conflict = result.conflicts[0]
    assert conflict.network_id == "lab-net"
    assert conflict.reason == "overlaps_leftover"
    assert conflict.owner_network_name == "practicum-deadbeef-lab-net"
    assert conflict.owner_container_count == 1
    assert conflict.recommended_subnet == "10.90.0.0/24"


def test_check_networks_treats_api_side_docker_error_as_unknown(monkeypatch) -> None:
    def fake_get(url, timeout):
        return httpx.Response(
            200,
            json={"lab_id": "abc", "has_conflicts": False, "conflicts": [],
                  "error": "Docker Desktop is not running"},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)

    result = ApiClient().check_networks("abc")

    assert result.success is False
    assert result.detail == "Docker Desktop is not running"


def test_check_networks_reports_connection_failure(monkeypatch) -> None:
    def fake_get(url, timeout):
        raise httpx.ConnectError("refused", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)

    result = ApiClient().check_networks("abc")

    assert result.success is False
    assert "Could not check networks" in result.detail


def test_apply_subnet_recommendation_posts_network_id(monkeypatch) -> None:
    seen = {}

    def fake_post(url, json, timeout):
        seen["url"], seen["json"] = url, json
        return httpx.Response(
            200, json=_network_body(has_conflicts=False, conflicts=[]),
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    result = ApiClient().apply_subnet_recommendation("abc", "lab-net")

    assert seen["url"].endswith("/labs/abc/networks/apply-recommendation")
    assert seen["json"] == {"network_id": "lab-net"}
    assert result.success is True
    assert result.has_conflicts is False


def test_apply_subnet_recommendation_surfaces_409_detail(monkeypatch) -> None:
    def fake_post(url, json, timeout):
        return httpx.Response(
            409, json={"detail": "No recommended subnet is available for network 'lab-net'"},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    result = ApiClient().apply_subnet_recommendation("abc", "lab-net")

    assert result.success is False
    assert result.detail == "No recommended subnet is available for network 'lab-net'"


def test_remove_leftover_network_posts_name_with_lifecycle_timeout(monkeypatch) -> None:
    seen = {}

    def fake_post(url, json, timeout):
        seen["url"], seen["json"], seen["timeout"] = url, json, timeout
        return httpx.Response(
            200, json=_network_body(has_conflicts=False, conflicts=[]),
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    client = ApiClient(lifecycle_timeout=42.0)
    result = client.remove_leftover_network("abc", "practicum-deadbeef-lab-net")

    assert seen["url"].endswith("/labs/abc/networks/remove-leftover")
    assert seen["json"] == {"network_name": "practicum-deadbeef-lab-net"}
    assert seen["timeout"] == 42.0
    assert result.success is True


def test_reset_lab_reports_success_and_runtime_error(monkeypatch) -> None:
    responses = iter([
        {"success": True, "lab": {"id": "abc", "status": "defined"}, "errors": []},
        {"success": False, "lab": {"id": "abc", "status": "error"},
         "errors": [{"message": "Docker is unavailable", "command": ["docker", "rm"]}]},
    ])

    def fake_post(url, timeout):
        assert url.endswith("/labs/abc/reset")
        return httpx.Response(200, json=next(responses), request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ApiClient()

    assert client.reset_lab("abc").success is True
    failed = client.reset_lab("abc")
    assert failed.success is False
    assert failed.detail == "Docker is unavailable"


def test_get_status_parses_resources_and_lab_status(monkeypatch) -> None:
    def fake_get(url, timeout):
        assert url.endswith("/labs/abc/status")
        return httpx.Response(
            200,
            json={
                "lab": {"id": "abc", "status": "running"},
                "resources": [
                    {"kind": "network", "id": "lan", "name": "practicum-abc-lan",
                     "exists": True, "status": "present", "error": None},
                    {"kind": "container", "id": "host-a", "name": "practicum-abc-host-a",
                     "exists": True, "status": "running", "error": None},
                    {"kind": "container", "id": "host-b", "name": "practicum-abc-host-b",
                     "exists": False, "status": None, "error": None},
                ],
                "errors": [],
            },
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)

    result = ApiClient().get_status("abc")

    assert result.success is True
    assert result.lab_status == "running"
    assert [c.id for c in result.containers] == ["host-a", "host-b"]
    assert result.containers[0].name == "practicum-abc-host-a"
    assert result.containers[0].status == "running"
    assert result.containers[1].exists is False


def test_get_status_surfaces_runtime_error_message(monkeypatch) -> None:
    def fake_get(url, timeout):
        return httpx.Response(
            200,
            json={"lab": {"id": "abc", "status": "error"}, "resources": [],
                  "errors": [{"message": "Docker CLI was not found", "command": ["docker"]}]},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)

    result = ApiClient().get_status("abc")

    assert result.success is True
    assert result.resources == []
    assert result.detail == "Docker CLI was not found"


def test_get_status_reports_connection_failure(monkeypatch) -> None:
    def fake_get(url, timeout):
        raise httpx.ConnectError("refused", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)

    result = ApiClient().get_status("abc")

    assert result.success is False
    assert "Could not load the lab status" in result.detail
