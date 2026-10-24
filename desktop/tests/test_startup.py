from __future__ import annotations

from practicum_desktop.api_client import HealthStatus
from practicum_desktop.startup import HEALTH_TIMEOUTS, check_health_with_retries


class FakeClient:
    def __init__(self, answers: list[HealthStatus]) -> None:
        self.answers = list(answers)
        self.timeouts: list[float] = []

    def check_health(self, timeout: float | None = None) -> HealthStatus:
        self.timeouts.append(timeout)
        return self.answers.pop(0)


HEALTHY = HealthStatus(reachable=True, healthy=True, detail="ok")
SLOW = HealthStatus(reachable=False, healthy=False, detail="slow", timed_out=True)
REFUSED = HealthStatus(reachable=False, healthy=False, detail="refused")


def test_healthy_first_answer_is_not_retried() -> None:
    client = FakeClient([HEALTHY])

    assert check_health_with_retries(client) is HEALTHY
    assert client.timeouts == [HEALTH_TIMEOUTS[0]]


def test_timeouts_are_retried_with_longer_waits_until_healthy() -> None:
    client = FakeClient([SLOW, SLOW, HEALTHY])

    assert check_health_with_retries(client) is HEALTHY
    assert client.timeouts == list(HEALTH_TIMEOUTS)


def test_refused_connection_is_not_retried() -> None:
    client = FakeClient([REFUSED])

    assert check_health_with_retries(client) is REFUSED
    assert client.timeouts == [HEALTH_TIMEOUTS[0]]


def test_persistent_timeout_is_reported_after_the_last_attempt() -> None:
    client = FakeClient([SLOW, SLOW, SLOW])

    result = check_health_with_retries(client)

    assert result.timed_out is True
    assert len(client.timeouts) == len(HEALTH_TIMEOUTS)
