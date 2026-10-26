import httpx

from practicum_desktop.api_client import ApiClient, PortMappingInfo


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
    def fake_post(url, json, timeout, **kwargs):
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
    def fake_post(url, json, timeout, **kwargs):
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
    def fake_post(url, timeout, **kwargs):
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
    def fake_post(url, timeout, **kwargs):
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
    def fake_post(url, timeout, **kwargs):
        raise httpx.ConnectError("refused", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ApiClient()

    result = client.start_lab("abc")

    assert result.success is False


def test_validate_lab_reports_valid(monkeypatch) -> None:
    def fake_post(url, json, timeout, **kwargs):
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
    def fake_post(url, json, timeout, **kwargs):
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
    def fake_post(url, json, timeout, **kwargs):
        raise httpx.ConnectError("refused", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ApiClient()

    result = client.validate_lab({"name": "Test Lab"})

    assert result.success is False


def test_create_lab_reports_success(monkeypatch) -> None:
    def fake_post(url, json, timeout, **kwargs):
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
    def fake_post(url, json, timeout, **kwargs):
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
    def fake_post(url, json, timeout, **kwargs):
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

    def fake_post(url, timeout, **kwargs):
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
    def fake_post(url, timeout, **kwargs):
        raise httpx.ReadTimeout("timed out", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ApiClient()

    result = client.start_lab("abc")

    assert result.success is False
    assert "did not finish starting the lab in time" in result.detail


def test_import_lab_reports_success_with_lab_identity(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def fake_post(url, json, timeout, **kwargs):
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
    def fake_post(url, json, timeout, **kwargs):
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
    def fake_post(url, json, timeout, **kwargs):
        raise httpx.ConnectError("refused", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ApiClient()

    result = client.import_lab({"name": "x"})

    assert result.success is False
    assert result.errors == []
    assert "Could not connect" in result.detail


def test_import_lab_reports_timeout(monkeypatch) -> None:
    def fake_post(url, json, timeout, **kwargs):
        raise httpx.ReadTimeout("slow", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ApiClient()

    result = client.import_lab({"name": "x"})

    assert result.success is False
    assert "did not respond in time" in result.detail


def test_import_lab_handles_non_object_body_rejection(monkeypatch) -> None:
    def fake_post(url, json, timeout, **kwargs):
        return httpx.Response(
            422, json={"detail": [{"loc": ["body"]}]}, request=httpx.Request("POST", url)
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ApiClient()

    result = client.import_lab({"name": "x"})

    assert result.success is False
    assert "does not contain a lab definition object" in result.detail


def test_import_lab_handles_unexpected_response(monkeypatch) -> None:
    def fake_post(url, json, timeout, **kwargs):
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

    def fake_post(url, json, timeout, **kwargs):
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
    def fake_post(url, json, timeout, **kwargs):
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

    def fake_post(url, json, timeout, **kwargs):
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

    def fake_post(url, timeout, **kwargs):
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


# ----- lifecycle enablers: stop / restart / delete / async start / progress -----------------


def _action_body(
    status: str = "running", success: bool = True, pending: bool = False, errors=None
):
    return {
        "success": success,
        "pending": pending,
        "lab": {"id": "abc", "status": status},
        "errors": errors or [],
    }


def test_stop_restart_reset_post_to_their_endpoints_with_lifecycle_timeout(monkeypatch) -> None:
    seen: list[tuple[str, float]] = []

    def fake_post(url, timeout, **kwargs):
        seen.append((url, timeout))
        return httpx.Response(
            200, json=_action_body("stopped"), request=httpx.Request("POST", url)
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ApiClient(base_url="http://api", lifecycle_timeout=123.0)

    assert client.stop_lab("abc").success is True
    assert client.restart_lab("abc").detail == "Lab restarted."
    assert client.reset_lab("abc").detail == "Lab reset."
    assert seen == [
        ("http://api/labs/abc/stop", 123.0),
        ("http://api/labs/abc/restart", 123.0),
        ("http://api/labs/abc/reset", 123.0),
    ]


def test_lifecycle_call_reports_busy_on_409(monkeypatch) -> None:
    def fake_post(url, timeout, **kwargs):
        return httpx.Response(
            409,
            json={"detail": "Lab 'X' is already starting; wait for that to finish"},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    result = ApiClient().stop_lab("abc")

    assert result.success is False
    assert result.busy is True
    assert result.detail == "Lab 'X' is already starting; wait for that to finish"


def test_stop_lab_reports_runtime_error_and_status(monkeypatch) -> None:
    def fake_post(url, timeout, **kwargs):
        return httpx.Response(
            200,
            json=_action_body(
                "error", success=False, errors=[{"message": "Container could not stop"}]
            ),
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    result = ApiClient().stop_lab("abc")

    assert result.success is False
    assert result.detail == "Container could not stop"
    assert result.lab_status == "error"


def test_start_lab_without_wait_sends_flag_and_reports_pending(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def fake_post(url, timeout, **kwargs):
        seen["params"] = kwargs.get("params")
        return httpx.Response(
            202, json=_action_body("starting", pending=True), request=httpx.Request("POST", url)
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    result = ApiClient().start_lab("abc", wait=False)

    assert seen["params"] == {"wait": "false"}
    assert result.success is True
    assert result.pending is True
    assert result.lab_status == "starting"
    assert result.detail == "Start requested."


def test_start_lab_with_wait_sends_no_params(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def fake_post(url, timeout, **kwargs):
        seen["params"] = kwargs.get("params")
        return httpx.Response(200, json=_action_body(), request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)

    result = ApiClient().start_lab("abc")

    assert seen["params"] is None
    assert result.pending is False


def test_delete_lab_reports_success_on_204_and_already_gone_on_404(monkeypatch) -> None:
    codes = iter([204, 404])
    seen: list[str] = []

    def fake_delete(url, timeout):
        seen.append(url)
        return httpx.Response(next(codes), request=httpx.Request("DELETE", url))

    monkeypatch.setattr(httpx, "delete", fake_delete)
    client = ApiClient(base_url="http://api")

    first = client.delete_lab("abc")
    second = client.delete_lab("abc")

    assert seen == ["http://api/labs/abc", "http://api/labs/abc"]
    assert first.success is True
    assert second.success is True
    assert second.detail == "The lab was already gone."


def test_delete_lab_surfaces_409_detail_and_connection_failure(monkeypatch) -> None:
    def fake_delete(url, timeout):
        return httpx.Response(
            409,
            json={"detail": "Could not remove the lab's Docker resources: boom"},
            request=httpx.Request("DELETE", url),
        )

    monkeypatch.setattr(httpx, "delete", fake_delete)
    kept = ApiClient().delete_lab("abc")
    assert kept.success is False
    assert kept.detail == "Could not remove the lab's Docker resources: boom"

    def failing_delete(url, timeout):
        raise httpx.ConnectError("refused", request=httpx.Request("DELETE", url))

    monkeypatch.setattr(httpx, "delete", failing_delete)
    failed = ApiClient().delete_lab("abc")
    assert failed.success is False
    assert failed.detail.startswith("Could not delete the lab")


def test_create_lab_sends_origin_and_import_sends_source_file(monkeypatch) -> None:
    seen: list[dict] = []

    def fake_post(url, json, timeout, **kwargs):
        seen.append({"url": url, "params": kwargs.get("params")})
        if url.endswith("/import"):
            return httpx.Response(
                200,
                json={"imported": True, "lab": {"id": "i1", "name": "N"}, "errors": []},
                request=httpx.Request("POST", url),
            )
        return httpx.Response(201, json={"id": "c1"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ApiClient(base_url="http://api")

    client.create_lab({"name": "N"})
    client.create_lab({"name": "N"}, origin="quick_start")
    client.import_lab({"name": "N"})
    client.import_lab({"name": "N"}, source_file="static-routing.json")

    assert [s["params"] for s in seen] == [
        {"origin": "designer"},
        {"origin": "quick_start"},
        None,
        {"source_file": "static-routing.json"},
    ]


def test_list_labs_parses_origin_timestamps_and_counts(monkeypatch) -> None:
    def fake_get(url, timeout):
        return httpx.Response(
            200,
            json=[
                {
                    "id": "a",
                    "name": "Imported One",
                    "status": "stopped",
                    "origin": "imported",
                    "source_file": "one.json",
                    "created_at": "2026-10-23T10:00:00Z",
                    "last_started_at": "2026-10-23T11:30:00+00:00",
                    "last_error": None,
                    "nodes": [{"id": "x"}, {"id": "y"}],
                    "networks": [{"id": "n"}],
                    "description": "Two hosts.",
                },
                {"id": "b", "name": "Old Server", "status": "defined"},
            ],
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)

    labs = ApiClient().list_labs().labs

    assert labs[0].origin == "imported"
    assert labs[0].source_file == "one.json"
    assert labs[0].created_at.isoformat() == "2026-10-23T10:00:00+00:00"
    assert labs[0].last_started_at.hour == 11
    assert labs[0].node_count == 2
    assert labs[0].network_count == 1
    assert labs[0].description == "Two hosts."
    # An older API without the bookkeeping fields still parses.
    assert labs[1].origin == "designer"
    assert labs[1].created_at is None
    assert labs[1].node_count == 0


def test_get_status_parses_progress_and_last_error(monkeypatch) -> None:
    def fake_get(url, timeout):
        return httpx.Response(
            200,
            json={
                "lab": {"id": "abc", "status": "starting", "last_error": None},
                "resources": [],
                "errors": [],
                "progress": [
                    {"node_id": "a", "image": "alpine", "step": "ready"},
                    {
                        "node_id": "b",
                        "image": "ubuntu",
                        "step": "pulling_image",
                        "percent": 42,
                        "detail": "3 of 7 layers",
                    },
                ],
            },
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)

    result = ApiClient().get_status("abc")

    assert result.lab_status == "starting"
    assert [(p.node_id, p.step, p.percent, p.detail) for p in result.progress] == [
        ("a", "ready", None, None),
        ("b", "pulling_image", 42, "3 of 7 layers"),
    ]
    assert result.last_error is None
    assert result.running_container_count == 0


# ----- edit / export -----------------------------------------------------------------------------


def test_get_lab_and_export_lab_return_the_definition(monkeypatch) -> None:
    seen: list[str] = []

    def fake_get(url, timeout):
        seen.append(url)
        body = {"name": "Routing", "nodes": [{"id": "a"}]}
        if not url.endswith("/export"):
            body |= {"id": "abc", "status": "stopped"}
        return httpx.Response(200, json=body, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    client = ApiClient(base_url="http://api")

    lab = client.get_lab("abc")
    exported = client.export_lab("abc")

    assert seen == ["http://api/labs/abc", "http://api/labs/abc/export"]
    assert lab.success and lab.name == "Routing" and lab.status == "stopped"
    assert lab.definition["id"] == "abc"
    assert exported.success and "id" not in exported.definition


def test_get_lab_reports_missing_and_connection_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        httpx, "get", lambda url, timeout: httpx.Response(404, request=httpx.Request("GET", url))
    )
    assert ApiClient().get_lab("x").detail == "That lab is no longer in the list."

    def failing(url, timeout):
        raise httpx.ConnectError("refused", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", failing)
    result = ApiClient().export_lab("x")
    assert result.success is False and "Could not export the lab" in result.detail


def test_update_lab_puts_and_parses_success_validation_and_conflict(monkeypatch) -> None:
    responses = iter(
        [
            httpx.Response(200, json={"id": "abc", "name": "N"}),
            httpx.Response(
                422, json={"detail": [{"loc": ["body", "name"], "msg": "too short", "type": "x"}]}
            ),
            httpx.Response(409, json={"detail": "Lab 'N' is running; stop it before editing"}),
        ]
    )
    seen: list[tuple[str, float]] = []

    def fake_put(url, json, timeout):
        seen.append((url, timeout))
        response = next(responses)
        response._request = httpx.Request("PUT", url)
        return response

    monkeypatch.setattr(httpx, "put", fake_put)
    client = ApiClient(base_url="http://api", lifecycle_timeout=77.0)

    ok = client.update_lab("abc", {"name": "N"})
    invalid = client.update_lab("abc", {"name": ""})
    running = client.update_lab("abc", {"name": "N"})

    assert seen[0] == ("http://api/labs/abc", 77.0)
    assert ok.success and ok.lab_id == "abc"
    assert invalid.success is False and invalid.errors[0].message == "too short"
    assert running.success is False and "stop it before editing" in running.detail


# ----- docker engine / node os + shell (phase 8) ----------------------------------------------


def test_get_docker_engine_parses_the_engine_mode(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def fake_get(url, timeout):
        seen["url"], seen["timeout"] = url, timeout
        return httpx.Response(
            200,
            json={
                "available": True,
                "os_type": "windows",
                "server_version": "27.3.1",
                "operating_system": "Windows 11 Pro",
                "kernel_version": "10.0 22631 (x)",
                "host_build": 22631,
                "isolation": "hyperv",
                "detail": "Docker 27.3.1 is serving Windows containers.",
            },
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)

    result = ApiClient().get_docker_engine()

    assert seen["url"].endswith("/docker/engine")
    assert seen["timeout"] == 20.0  # `docker info` may be slow while Docker restarts
    assert result.success is True and result.available is True
    assert result.os_type == "windows" and result.host_build == 22631
    assert result.isolation == "hyperv"


def test_get_docker_engine_reports_an_unreachable_daemon_and_api_failures(monkeypatch) -> None:
    def fake_get(url, timeout):
        return httpx.Response(
            200,
            json={"available": False, "os_type": None, "detail": "Docker is not running."},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    down = ApiClient().get_docker_engine()
    assert down.success is True and down.available is False
    assert down.detail == "Docker is not running."

    def failing_get(url, timeout):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx, "get", failing_get)
    failed = ApiClient().get_docker_engine()
    assert failed.success is False and "Could not check Docker" in failed.detail


def test_get_preview_carries_container_os_and_node_shells(monkeypatch) -> None:
    def fake_get(url, timeout):
        return httpx.Response(
            200,
            json={
                "id": "abc",
                "status": "defined",
                "schema_version": "1.0",
                "name": "Windows Quick Start",
                "container_os": "windows",
                "required_images": ["mcr.microsoft.com/windows/servercore:ltsc2022"],
                "estimated_resources": {"exposed_ports": [], "port_mappings": []},
                "topology": {
                    "nodes": [
                        {
                            "id": "host",
                            "image": "mcr.microsoft.com/windows/servercore:ltsc2022",
                            "os": "windows",
                            "shell": "powershell",
                        }
                    ],
                    "networks": [],
                    "interfaces": [],
                },
            },
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)

    result = ApiClient().get_preview("abc")

    assert result.container_os == "windows"
    assert result.topology.nodes[0].os == "windows"
    assert result.topology.nodes[0].shell == "powershell"


def test_get_preview_defaults_older_nodes_to_linux(monkeypatch) -> None:
    def fake_get(url, timeout):
        return httpx.Response(
            200,
            json={
                "id": "abc",
                "status": "defined",
                "schema_version": "1.0",
                "name": "Old",
                "required_images": [],
                "estimated_resources": {},
                "topology": {
                    "nodes": [{"id": "h", "image": "alpine"}],
                    "networks": [],
                    "interfaces": [],
                },
            },
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)

    result = ApiClient().get_preview("abc")

    assert result.container_os == "linux"
    assert result.topology.nodes[0].os == "linux" and result.topology.nodes[0].shell is None


def test_list_labs_reads_the_container_os_from_the_nodes(monkeypatch) -> None:
    def fake_get(url, timeout):
        return httpx.Response(
            200,
            json=[
                {
                    "id": "w",
                    "name": "Win",
                    "status": "defined",
                    "nodes": [{"id": "h", "os": "windows"}],
                },
                {"id": "l", "name": "Lin", "status": "defined", "nodes": [{"id": "h"}]},
            ],
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)

    result = ApiClient().list_labs()

    assert [lab.container_os for lab in result.labs] == ["windows", "linux"]


def test_import_lab_reads_the_container_os_of_the_imported_lab(monkeypatch) -> None:
    def fake_post(url, json, timeout, params=None):
        return httpx.Response(
            200,
            json={
                "imported": True,
                "lab": {"id": "w", "name": "Win", "nodes": [{"id": "host", "os": "windows"}]},
                "errors": [],
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    result = ApiClient().import_lab({"name": "Win"})

    assert result.success is True and result.container_os == "windows"


def test_get_preview_carries_each_machines_published_ports(monkeypatch) -> None:
    def fake_get(url, timeout):
        return httpx.Response(
            200,
            json={
                "id": "abc",
                "status": "defined",
                "schema_version": "1.0",
                "name": "Two desktops",
                "required_images": [],
                "estimated_resources": {
                    "port_mappings": [
                        {"host": 3000, "container": 3000, "protocol": "tcp"},
                        {"host": 3002, "container": 3000, "protocol": "tcp"},
                    ]
                },
                "topology": {
                    "nodes": [
                        {
                            "id": "desktop-1",
                            "image": "webtop",
                            "resources": {
                                "port_mappings": [
                                    {"host": 3000, "container": 3000, "protocol": "tcp"}
                                ],
                                "exposed_ports": [8080],
                            },
                        },
                        {
                            "id": "desktop-2",
                            "image": "webtop",
                            "resources": {
                                "port_mappings": [
                                    {"host": 3002, "container": 3000, "protocol": "tcp"}
                                ]
                            },
                        },
                        {"id": "router", "image": "alpine"},
                    ],
                    "networks": [],
                    "interfaces": [],
                },
            },
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)

    result = ApiClient().get_preview("abc")

    by_node = {n.id: n.port_mappings for n in result.topology.nodes}
    assert by_node["desktop-1"] == [
        PortMappingInfo(3000, 3000, "tcp", node_id="desktop-1"),
        PortMappingInfo(8080, 8080, "tcp", node_id="desktop-1"),
    ]
    assert by_node["desktop-2"] == [PortMappingInfo(3002, 3000, "tcp", node_id="desktop-2")]
    assert by_node["router"] == []
    assert [m.host for m in result.port_mappings] == [3000, 3002]  # the flat list still parses


def test_apply_port_recommendation_sends_a_chosen_port_and_surfaces_the_refusal(
    monkeypatch,
) -> None:
    bodies: list[dict] = []

    def fake_post(url, json, timeout, **kwargs):
        bodies.append(json)
        if json.get("new_host_port") == 8000:
            return httpx.Response(
                409,
                json={"detail": "Port 8000/tcp is reserved by the Practicum API"},
                request=httpx.Request("POST", url),
            )
        return httpx.Response(
            200,
            json={"lab_id": "abc", "has_conflicts": False, "conflicts": []},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ApiClient()

    ok = client.apply_port_recommendation("abc", "router", 2222, "tcp", new_host_port=9022)
    assert ok.success is True
    assert bodies[-1] == {
        "node_id": "router",
        "host_port": 2222,
        "protocol": "tcp",
        "new_host_port": 9022,
    }

    refused = client.apply_port_recommendation("abc", "router", 2222, "tcp", new_host_port=8000)
    assert refused.success is False
    assert refused.detail == "Port 8000/tcp is reserved by the Practicum API"

    client.apply_port_recommendation("abc", "router", 2222, "tcp")
    assert "new_host_port" not in bodies[-1]  # the recommendation path is unchanged


def test_port_and_network_fix_results_carry_machines_reset(monkeypatch) -> None:
    def fake_post(url, json, timeout, **kwargs):
        return httpx.Response(
            200,
            json={
                "lab_id": "abc",
                "has_conflicts": False,
                "conflicts": [],
                "machines_reset": True,
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ApiClient()

    assert client.apply_port_recommendation("abc", "router", 2222, "tcp").machines_reset is True
    assert client.apply_subnet_recommendation("abc", "lan").machines_reset is True

    def fake_get(url, timeout):
        return httpx.Response(
            200,
            json={"lab_id": "abc", "has_conflicts": False, "conflicts": []},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    assert client.check_ports("abc").machines_reset is False  # plain checks never reset
