from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.dependencies import Localizer
from app.models.health import DoctorResult, OverallStatus, SystemSnapshot

COMPONENT_ORDER = (
    "frontend",
    "backend",
    "database",
    "kubernetes",
    "prometheus",
    "grafana",
    "alertmanager",
    "argocd",
)

AZERBAIJAN_TIMEZONE = timezone(timedelta(hours=4), name="AZT")


def _timestamp(value: datetime | None) -> str:
    if value is None:
        return "Unknown"
    return value.astimezone(AZERBAIJAN_TIMEZONE).strftime("%d %B %Y, %H:%M AZT")


def _status(localizer: Localizer, language: str, status: str) -> str:
    key = f"statuses.{status.lower()}"
    try:
        return localizer.text(language, key)
    except KeyError:
        return status.title()


def format_status(
    snapshot: SystemSnapshot,
    overall: OverallStatus,
    localizer: Localizer,
    language: str,
) -> str:
    lines = [
        localizer.text(language, "status.title"),
        "",
        localizer.text(
            language, "status.environment", value=snapshot.environment.title()
        ),
        localizer.text(language, "status.data_mode", value=snapshot.source.title()),
        *(
            [localizer.text(language, "mock_warning")]
            if snapshot.source == "mock"
            else []
        ),
        "",
    ]
    for name in COMPONENT_ORDER:
        component = snapshot.components.get(name)
        label = localizer.text(language, f"components.{name}")
        if component is None or not component.available:
            value = localizer.text(language, "data_unavailable")
        elif name == "argocd" and component.sync_status:
            value = component.sync_status
        else:
            value = _status(localizer, language, component.status.value)
        lines.append(f"{label}: {value}")
    lines.extend(
        [
            "",
            localizer.text(
                language,
                "status.active_alerts",
                count=sum(
                    alert.status.lower() == "firing" for alert in snapshot.active_alerts
                ),
            ),
            localizer.text(
                language,
                "status.last_deployment",
                value=_status(localizer, language, snapshot.deployment.status),
            ),
            "",
            localizer.text(
                language,
                "status.overall",
                value=_status(localizer, language, overall.value),
            ),
            localizer.text(
                language, "status.observed", value=_timestamp(snapshot.observed_at)
            ),
        ]
    )
    return "\n".join(lines)


def format_health(snapshot: SystemSnapshot, localizer: Localizer, language: str) -> str:
    lines = [
        localizer.text(language, "health.title"),
        *(
            [localizer.text(language, "mock_warning")]
            if snapshot.source == "mock"
            else []
        ),
        "",
    ]
    for name in COMPONENT_ORDER:
        component = snapshot.components.get(name)
        label = localizer.text(language, f"components.{name}")
        lines.append(label)
        if component is None or not component.available:
            lines.append(f"  {localizer.text(language, 'data_unavailable')}")
            if component and component.safe_error:
                lines.append(f"  {component.safe_error}")
            continue
        lines.append(
            f"  {localizer.text(language, 'health.status')}: "
            f"{_status(localizer, language, component.status.value)}"
        )
        if component.latency_ms is not None:
            lines.append(
                f"  {localizer.text(language, 'health.latency')}: "
                f"{component.latency_ms:g} ms"
            )
        lines.append(
            f"  {localizer.text(language, 'health.observed')}: "
            f"{_timestamp(component.observed_at or snapshot.observed_at)}"
        )
    return "\n".join(lines)


def format_doctor(result: DoctorResult, localizer: Localizer, language: str) -> str:
    lines = [
        localizer.text(language, "doctor.title"),
        "",
        localizer.text(language, "doctor.score", score=result.score),
        localizer.text(language, "doctor.coverage", coverage=result.coverage_percent),
        "",
        localizer.text(language, "doctor.deductions"),
    ]
    lines.extend(f"- {deduction}" for deduction in result.deductions)
    lines.extend(
        [
            "",
            localizer.text(language, "doctor.recommendation"),
            result.recommendation,
        ]
    )
    return "\n".join(lines)
