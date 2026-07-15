from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_keyboard(language: str = "en") -> InlineKeyboardMarkup:
    labels = {
        "en": {
            "status": "System status",
            "health": "Health check",
            "doctor": "Cluster Doctor",
            "metrics": "Metrics",
            "chart": "Chart",
            "alerts": "Alerts",
            "pods": "Pods",
            "deployments": "Deployments",
            "hpa": "Autoscaling",
            "grafana": "Grafana",
            "argocd": "Argo CD",
            "workflows": "Workflows",
            "last_deploy": "Last deployment",
            "images": "Images",
            "incident": "Incident analysis",
            "daily_report": "Daily report",
            "help": "All commands",
        },
        "az": {
            "status": "Sistem statusu",
            "health": "Sağlamlıq yoxlaması",
            "doctor": "Klaster doktoru",
            "metrics": "Metriklər",
            "chart": "Qrafik",
            "alerts": "Alertlər",
            "pods": "Podlar",
            "deployments": "Deploymentlər",
            "hpa": "Avtomatik miqyaslama",
            "grafana": "Grafana",
            "argocd": "Argo CD",
            "workflows": "Workflow-lar",
            "last_deploy": "Son deployment",
            "images": "Image-lər",
            "incident": "İnsident analizi",
            "daily_report": "Gündəlik hesabat",
            "help": "Bütün əmrlər",
        },
    }
    selected = labels.get(language, labels["en"])
    rows = (
        ("status", "health"),
        ("doctor", "metrics"),
        ("chart", "alerts"),
        ("pods", "deployments"),
        ("hpa", "grafana"),
        ("argocd", "workflows"),
        ("last_deploy", "images"),
        ("incident", "daily_report"),
        ("help",),
    )
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(selected[key], callback_data=key) for key in row]
            for row in rows
        ]
    )
