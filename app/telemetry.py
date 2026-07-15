from prometheus_client import Counter, Gauge, Histogram

COMMANDS_TOTAL = Counter(
    "agrivo_sre_bot_commands_total",
    "Telegram commands processed by Agrivo SRE Assistant.",
    ("command",),
)
COMMAND_FAILURES_TOTAL = Counter(
    "agrivo_sre_bot_command_failures_total",
    "Telegram command failures.",
    ("command", "category"),
)
UNAUTHORIZED_REQUESTS_TOTAL = Counter(
    "agrivo_sre_bot_unauthorized_requests_total",
    "Rejected Telegram requests.",
)
AI_REQUESTS_TOTAL = Counter(
    "agrivo_sre_bot_ai_requests_total", "Requests sent to Gemini."
)
AI_FAILURES_TOTAL = Counter(
    "agrivo_sre_bot_ai_failures_total", "Failed Gemini requests.", ("category",)
)
AI_REQUEST_DURATION_SECONDS = Histogram(
    "agrivo_sre_bot_ai_request_duration_seconds",
    "Gemini request duration in seconds.",
)
MOCK_SCENARIO_INFO = Gauge(
    "agrivo_sre_bot_mock_scenario_info",
    "Currently loaded mock scenario.",
    ("scenario",),
)
HEALTH_SCORE = Gauge(
    "agrivo_sre_bot_health_score", "Latest deterministic Agrivo health score."
)
