from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_keyboard(language: str = "en") -> InlineKeyboardMarkup:
    labels = {
        "en": ("System status", "Health check", "Cluster Doctor", "Help"),
        "az": ("Sistem statusu", "Sağlamlıq yoxlaması", "Klaster Doktoru", "Kömək"),
    }
    status, health, doctor, help_text = labels.get(language, labels["en"])
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(status, callback_data="status"),
                InlineKeyboardButton(health, callback_data="health"),
            ],
            [
                InlineKeyboardButton(doctor, callback_data="doctor"),
                InlineKeyboardButton(help_text, callback_data="help"),
            ],
        ]
    )
