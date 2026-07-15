from app.bot.keyboards import main_keyboard


def test_main_keyboard_contains_all_primary_actions() -> None:
    keyboard = main_keyboard("az")
    callbacks = {
        button.callback_data for row in keyboard.inline_keyboard for button in row
    }
    assert callbacks == {
        "status",
        "health",
        "doctor",
        "metrics",
        "chart",
        "alerts",
        "pods",
        "deployments",
        "hpa",
        "grafana",
        "argocd",
        "workflows",
        "last_deploy",
        "images",
        "incident",
        "daily_report",
        "help",
    }
    assert len(keyboard.inline_keyboard) == 9
