from __future__ import annotations

import time
from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any, cast

import structlog
from telegram import Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from app.bot.formatters import format_doctor, format_health, format_status
from app.bot.keyboards import main_keyboard
from app.bot.permissions import authorized
from app.dependencies import RuntimeDependencies
from app.telemetry import COMMAND_FAILURES_TOTAL, COMMANDS_TOTAL
from app.utils.telegram_text import split_message

LOGGER = structlog.get_logger(__name__)
Handler = Callable[[Update, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]


def _runtime(context: ContextTypes.DEFAULT_TYPE) -> RuntimeDependencies:
    return cast(RuntimeDependencies, context.application.bot_data["runtime"])


async def _language(update: Update, runtime: RuntimeDependencies) -> str:
    user_id = update.effective_user.id if update.effective_user else None
    return (
        await runtime.state_repository.get_language(user_id)
        if user_id is not None
        else "en"
    )


async def _reply(update: Update, text: str, **kwargs: Any) -> None:
    if not update.effective_message:
        return
    for index, chunk in enumerate(split_message(text)):
        await update.effective_message.reply_text(
            chunk, **(kwargs if index == 0 else {})
        )


def tracked(command: str) -> Callable[[Handler], Handler]:
    def decorator(handler: Handler) -> Handler:
        @wraps(handler)
        async def wrapper(
            update: Update,
            context: ContextTypes.DEFAULT_TYPE,
            *args: Any,
            **kwargs: Any,
        ) -> None:
            started = time.monotonic()
            COMMANDS_TOTAL.labels(command=command).inc()
            try:
                await handler(update, context, *args, **kwargs)
                LOGGER.info(
                    "telegram_command_completed",
                    command=command,
                    success=True,
                    duration_seconds=round(time.monotonic() - started, 4),
                    user_id=update.effective_user.id if update.effective_user else None,
                    chat_id=update.effective_chat.id if update.effective_chat else None,
                )
            except Exception:
                COMMAND_FAILURES_TOTAL.labels(
                    command=command, category="internal_error"
                ).inc()
                LOGGER.exception(
                    "telegram_command_failed",
                    command=command,
                    success=False,
                    error_category="internal_error",
                    duration_seconds=round(time.monotonic() - started, 4),
                )
                runtime = _runtime(context)
                language = await _language(update, runtime)
                await _reply(update, runtime.localizer.text(language, "generic_error"))

        return wrapper

    return decorator


@tracked("start")
@authorized
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    runtime = _runtime(context)
    language = await _language(update, runtime)
    await _reply(
        update,
        runtime.localizer.text(
            language,
            "start",
            environment=runtime.settings.app_env.title(),
            data_mode=runtime.settings.bot_data_mode.title(),
        ),
        reply_markup=main_keyboard(language),
    )


@tracked("help")
@authorized
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    runtime = _runtime(context)
    language = await _language(update, runtime)
    await _reply(update, runtime.localizer.text(language, "help"))


@tracked("status")
@authorized
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    runtime = _runtime(context)
    language = await _language(update, runtime)
    snapshot = await runtime.data_service.get_snapshot()
    overall = runtime.health_service.overall_status(snapshot)
    await _reply(update, format_status(snapshot, overall, runtime.localizer, language))


@tracked("health")
@authorized
async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    runtime = _runtime(context)
    language = await _language(update, runtime)
    snapshot = await runtime.data_service.get_snapshot()
    await _reply(update, format_health(snapshot, runtime.localizer, language))


@tracked("doctor")
@authorized
async def doctor_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    runtime = _runtime(context)
    language = await _language(update, runtime)
    snapshot = await runtime.data_service.get_snapshot()
    result = runtime.scoring_service.calculate(snapshot)
    await _reply(update, format_doctor(result, runtime.localizer, language))


@tracked("language")
@authorized
async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    runtime = _runtime(context)
    current = await _language(update, runtime)
    arguments = context.args or []
    if len(arguments) != 1 or arguments[0].lower() not in {"en", "az"}:
        await _reply(update, runtime.localizer.text(current, "language_usage"))
        return
    selected = arguments[0].lower()
    if update.effective_user:
        await runtime.state_repository.set_language(update.effective_user.id, selected)
    await _reply(update, runtime.localizer.text(selected, "language_changed"))


@tracked("ask")
@authorized
async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    runtime = _runtime(context)
    language = await _language(update, runtime)
    question = " ".join(context.args or []).strip()
    if not question:
        await _reply(update, runtime.localizer.text(language, "ask_usage"))
        return
    if len(question) > runtime.settings.ai_max_question_length:
        await _reply(
            update,
            runtime.localizer.text(
                language,
                "ask_too_long",
                maximum=runtime.settings.ai_max_question_length,
            ),
        )
        return
    answer = await runtime.ai_service.ask(question)
    if answer.available and answer.text:
        await _reply(update, answer.text)
    elif answer.error_category == "not_configured":
        await _reply(update, runtime.localizer.text(language, "ai_unavailable"))
    else:
        await _reply(update, runtime.localizer.text(language, "ai_temporary_failure"))


@tracked("callback")
@authorized
async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    handlers: dict[str, Handler] = {
        "status": status_command,
        "health": health_command,
        "doctor": doctor_command,
        "metrics": metrics_command,
        "chart": chart_command,
        "alerts": alerts_command,
        "pods": pods_command,
        "deployments": deployments_command,
        "hpa": hpa_command,
        "grafana": grafana_command,
        "argocd": argocd_command,
        "workflows": workflows_command,
        "images": images_command,
        "incident": incident_command,
        "daily_report": daily_report_command,
        "help": help_command,
    }
    handler = handlers.get(query.data or "")
    if handler:
        await handler(update, context)


def register_handlers(application: Any) -> None:
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("health", health_command))
    application.add_handler(CommandHandler("doctor", doctor_command))
    application.add_handler(CommandHandler("language", language_command))
    application.add_handler(CommandHandler("ask", ask_command))
    application.add_handler(CommandHandler("metrics", metrics_command))
    application.add_handler(CommandHandler("chart", chart_command))
    application.add_handler(CommandHandler("alerts", alerts_command))
    application.add_handler(CommandHandler("pods", pods_command))
    application.add_handler(CommandHandler("deployments", deployments_command))
    application.add_handler(CommandHandler("hpa", hpa_command))
    application.add_handler(CommandHandler("grafana", grafana_command))
    application.add_handler(CommandHandler("workflows", workflows_command))
    application.add_handler(CommandHandler("argocd", argocd_command))
    application.add_handler(CommandHandler("last_deploy", last_deploy_command))
    application.add_handler(CommandHandler("images", images_command))
    application.add_handler(CommandHandler("incident", incident_command))
    application.add_handler(CommandHandler("daily_report", daily_report_command))
    application.add_handler(CallbackQueryHandler(menu_callback))


async def _operation_reply(
    update: Update, result: Any, title: str, formatter: Callable[[Any], str]
) -> None:
    if not result.available:
        await _reply(
            update,
            f"{title}\n\nÃƒÂ¢Ã…Â¡Ã‚Â ÃƒÂ¯Ã‚Â¸Ã‚Â {result.safe_error or 'Data source unavailable.'}",
        )
        return
    if not result.items:
        await _reply(
            update, f"{title}\n\nNo resources found in the active environment."
        )
        return
    await _reply(
        update, "\n".join([title, "", *(formatter(item) for item in result.items)])
    )


@tracked("metrics")
@authorized
async def metrics_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    metrics = await _runtime(context).operations_service.metrics()
    if not metrics.available:
        await _reply(
            update,
            f"ÃƒÂ°Ã…Â¸Ã¢â‚¬Å“Ã…Â  Agrivo Metrics\n\nÃƒÂ¢Ã…Â¡Ã‚Â ÃƒÂ¯Ã‚Â¸Ã‚Â {metrics.safe_error}",
        )
        return

    def value(number: float | None, unit: str = "") -> str:
        return "No data" if number is None else f"{number:.2f}{unit}"

    lines = [
        "ÃƒÂ°Ã…Â¸Ã¢â‚¬Å“Ã…Â  Agrivo Metrics (Prometheus)",
        "",
        f"Request rate: {value(metrics.request_rate, '/s')}",
        f"5xx error rate: {value(metrics.error_rate_percent, '%')}",
        f"Backend p95 latency: {value(metrics.p95_latency_ms, ' ms')}",
        f"Process CPU: {value(metrics.cpu_percent, '%')}",
        f"Process memory: {value(metrics.memory_mib, ' MiB')}",
        f"Event loop p99: {value(metrics.event_loop_p99_ms, ' ms')}",
        "",
        "No data means that the metric does not exist yet or has no samples; it is not treated as zero.",
    ]
    await _reply(update, "\n".join(lines))


@tracked("chart")
@authorized
async def chart_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    runtime = _runtime(context)
    raw_hours = (context.args or ["1"])[0]
    try:
        hours = max(1, min(int(raw_hours), 24))
    except ValueError:
        hours = 1
    chart = await runtime.operations_service.chart(hours)
    if chart is None or not update.effective_message:
        await _reply(
            update,
            "ÃƒÂ°Ã…Â¸Ã¢â‚¬Å“Ã‹â€  Chart unavailable: Prometheus has no matching samples or is unreachable.",
        )
        return
    import io

    await update.effective_message.reply_photo(
        photo=io.BytesIO(chart),
        caption=f"ÃƒÂ°Ã…Â¸Ã¢â‚¬Å“Ã‹â€  Agrivo metrics ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“ last {hours} hour(s), {runtime.settings.display_timezone}",
    )


@tracked("alerts")
@authorized
async def alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    result = await _runtime(context).operations_service.alerts()
    await _operation_reply(
        update,
        result,
        "ÃƒÂ°Ã…Â¸Ã…Â¡Ã‚Â¨ Active Alerts",
        lambda item: f"ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢ [{item.severity.upper()}] {item.name}\n  {item.description}",
    )


@tracked("pods")
@authorized
async def pods_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    runtime = _runtime(context)
    result = await runtime.operations_service.pods()
    await _operation_reply(
        update,
        result,
        f"ÃƒÂ¢Ã‹Å“Ã‚Â¸ÃƒÂ¯Ã‚Â¸Ã‚Â Pods Ãƒâ€šÃ‚Â· {runtime.settings.active_namespace}",
        lambda item: f"ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢ {item.name}: {item.phase}, ready {item.ready}, restarts {item.restarts}",
    )


@tracked("deployments")
@authorized
async def deployments_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    runtime = _runtime(context)
    result = await runtime.operations_service.deployments()
    await _operation_reply(
        update,
        result,
        f"ÃƒÂ°Ã…Â¸Ã…Â¡Ã¢â€šÂ¬ Deployments Ãƒâ€šÃ‚Â· {runtime.settings.active_namespace}",
        lambda item: f"ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢ {item.name}: ready {item.ready}, available {item.available}/{item.desired}\n  image: {item.image or 'unknown'}",
    )


@tracked("hpa")
@authorized
async def hpa_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    runtime = _runtime(context)
    result = await runtime.operations_service.hpas()
    await _operation_reply(
        update,
        result,
        f"ÃƒÂ°Ã…Â¸Ã¢â‚¬Å“Ã‚Â Autoscaling Ãƒâ€šÃ‚Â· {runtime.settings.active_namespace}",
        lambda item: f"ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢ {item.name} ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ {item.reference}: {item.current_replicas} replicas ({item.min_replicas}ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“{item.max_replicas})\n  {item.metrics}",
    )


@tracked("grafana")
@authorized
async def grafana_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    runtime = _runtime(context)
    links = runtime.operations_service.grafana_links()
    if not links:
        await _reply(
            update, "ÃƒÂ°Ã…Â¸Ã¢â‚¬Å“Ã…Â  Grafana\n\nNo dashboard URLs are configured."
        )
        return
    lines = [
        "ÃƒÂ°Ã…Â¸Ã¢â‚¬Å“Ã…Â  Grafana Dashboards",
        "",
        *(f"ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢ {name}: {url}" for name, url in links),
    ]
    if not runtime.settings.grafana_render_enabled:
        lines.extend(
            [
                "",
                "Panel image rendering is disabled. Set GRAFANA_RENDER_ENABLED=true after installing/configuring Grafana Image Renderer.",
            ]
        )
    await _reply(update, "\n".join(lines), disable_web_page_preview=True)


@tracked("workflows")
@authorized
async def workflows_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    result = await _runtime(context).operations_service.workflows()
    await _operation_reply(
        update,
        result,
        "ÃƒÂ¢Ã…Â¡Ã¢â€žÂ¢ÃƒÂ¯Ã‚Â¸Ã‚Â GitHub Actions Ãƒâ€šÃ‚Â· latest runs",
        lambda item: f"ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢ {item.name}: {item.conclusion or item.status} Ãƒâ€šÃ‚Â· {item.branch or '?'} Ãƒâ€šÃ‚Â· {item.sha or '?'}\n  {item.url or ''}",
    )


@tracked("argocd")
@authorized
async def argocd_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    result = await _runtime(context).operations_service.argocd_apps()
    await _operation_reply(
        update,
        result,
        "ÃƒÂ°Ã…Â¸Ã¢â‚¬ÂÃ¢â‚¬Å¾ Argo CD Applications",
        lambda item: f"ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢ {item.name}: sync {item.sync}, health {item.health}, revision {item.revision or '?'}",
    )


@tracked("last_deploy")
@authorized
async def last_deploy_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    result = await _runtime(context).operations_service.workflows()
    if not result.available or not result.items:
        await _reply(
            update,
            f"ÃƒÂ°Ã…Â¸Ã…Â¡Ã¢â€šÂ¬ Last deployment\n\nÃƒÂ¢Ã…Â¡Ã‚Â ÃƒÂ¯Ã‚Â¸Ã‚Â {result.safe_error or 'No workflow runs found.'}",
        )
        return
    successful = next(
        (item for item in result.items if item.conclusion == "success"), result.items[0]
    )
    await _reply(
        update,
        f"ÃƒÂ°Ã…Â¸Ã…Â¡Ã¢â€šÂ¬ Last deployment\n\nWorkflow: {successful.name}\nResult: {successful.conclusion or successful.status}\nBranch: {successful.branch or '?'}\nCommit: {successful.sha or '?'}\n{successful.url or ''}",
        disable_web_page_preview=True,
    )


@tracked("images")
@authorized
async def images_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    result = await _runtime(context).operations_service.deployments()
    await _operation_reply(
        update,
        result,
        "ÃƒÂ°Ã…Â¸Ã¢â‚¬Å“Ã‚Â¦ Running container images",
        lambda item: f"ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢ {item.name}\n  {item.image or 'Image unavailable'}",
    )


async def _incident_text(runtime: RuntimeDependencies) -> str:
    snapshot, alerts, pods, metrics, argo = await __import__("asyncio").gather(
        runtime.data_service.get_snapshot(refresh=True),
        runtime.operations_service.alerts(),
        runtime.operations_service.pods(),
        runtime.operations_service.metrics(),
        runtime.operations_service.argocd_apps(),
    )
    overall = runtime.health_service.overall_status(snapshot)
    unhealthy = [
        name
        for name, item in snapshot.components.items()
        if not item.available or item.status.value != "healthy"
    ]
    firing = len(alerts.items) if alerts.available else "unknown"
    bad_pods = (
        sum(item.phase not in {"Running", "Succeeded"} for item in pods.items)
        if pods.available
        else "unknown"
    )
    argo_bad = (
        sum(item.sync != "Synced" or item.health != "Healthy" for item in argo.items)
        if argo.available
        else "unknown"
    )
    p95 = (
        "no data"
        if metrics.p95_latency_ms is None
        else f"{metrics.p95_latency_ms:.1f} ms"
    )
    recommendation = (
        "Continue routine monitoring."
        if overall.value == "operational"
        else "Inspect the listed unhealthy components, active alerts, pod events and the latest deployment before rollback or restart."
    )
    return "\n".join(
        [
            "ÃƒÂ°Ã…Â¸Ã‚Â§Ã‚Â­ Agrivo Incident Analysis",
            "",
            f"Overall: {overall.value.title()}",
            f"Unhealthy/unavailable components: {', '.join(unhealthy) or 'none'}",
            f"Active alerts: {firing}",
            f"Non-running pods: {bad_pods}",
            f"Argo CD unhealthy/out-of-sync apps: {argo_bad}",
            f"Backend p95: {p95}",
            "",
            f"Recommendation: {recommendation}",
            "",
            "This report is deterministic and read-only; no restart, rollback, or deployment was performed.",
        ]
    )


@tracked("incident")
@authorized
async def incident_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    runtime = _runtime(context)
    deterministic = await _incident_text(runtime)
    if runtime.ai_service.configured:
        prompt = (
            "Analyze these confirmed read-only Agrivo incident facts. Separate facts "
            "from hypotheses and propose safe next diagnostic steps only:\n"
            + deterministic
        )
        answer = await runtime.ai_service.ask(prompt)
        if answer.available and answer.text:
            deterministic += "\n\n🤖 Gemini analysis\n\n" + answer.text
        else:
            deterministic += (
                "\n\n🤖 Gemini analysis unavailable; deterministic report shown."
            )
    await _reply(update, deterministic)


@tracked("daily_report")
@authorized
async def daily_report_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    runtime = _runtime(context)
    snapshot = await runtime.data_service.get_snapshot(refresh=True)
    score = runtime.scoring_service.calculate(snapshot)
    metrics = await runtime.operations_service.metrics()
    workflows = await runtime.operations_service.workflows()
    latest = workflows.items[0] if workflows.available and workflows.items else None
    overall = runtime.health_service.overall_status(snapshot)
    await _reply(
        update,
        "\n".join(
            [
                "ÃƒÂ°Ã…Â¸Ã¢â‚¬â€Ã¢â‚¬Å“ Agrivo Daily SRE Report",
                "",
                f"Environment: {runtime.settings.app_env.title()}",
                f"Overall: {overall.value.title()}",
                f"Health score: {score.score}/100",
                f"Data coverage: {score.coverage_percent}%",
                f"Active alerts: {len(snapshot.active_alerts)}",
                f"Backend p95: {'No data' if metrics.p95_latency_ms is None else f'{metrics.p95_latency_ms:.1f} ms'}",
                f"Latest workflow: {'Unavailable' if latest is None else f'{latest.name} Ãƒâ€šÃ‚Â· {latest.conclusion or latest.status} Ãƒâ€šÃ‚Â· {latest.sha or "?"}'}",
                "",
                f"Timezone: {runtime.settings.display_timezone}",
            ]
        ),
    )
