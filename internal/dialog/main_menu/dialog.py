from aiogram_dialog import Window, Dialog
from aiogram_dialog.widgets.text import Const, Format
from aiogram_dialog.widgets.kbd import Button, Column, Row

from internal import interface, model


class MainMenuDialog(interface.IMainMenuDialog):
    def __init__(
            self,
            tel: interface.ITelemetry,
            main_menu_service: interface.IMainMenuService,
            main_menu_getter: interface.IMainMenuGetter,
    ):
        self.tracer = tel.tracer()
        self.logger = tel.logger()
        self.main_menu_service = main_menu_service
        self.main_menu_getter = main_menu_getter

    def get_dialog(self) -> Dialog:
        return Dialog(
            self.get_main_menu_window(),
        )

    def get_main_menu_window(self) -> Window:
        return Window(
            Format("🎉 <b>Добро пожаловать, {name}!</b>\n\n"),
            Format("🏢 <b>Я помогу тебе быстро создать и опубликовать пост с помощью искусственного интеллекта. </b>\n"),
            Format("💰 <b>Просто отправь текст или голосовое сообщение — и начнём магию! ✨</b>\n\n"),
            Format("🤖 <b>Я помогу вам создавать и публиковать контент с помощью ИИ.</b>\n"),
            Format("<b>Для создания коротких видео отправь ссылку на YouTube-видео</b>\n\n"),
            Format("👇 <b>Готов? Тогда жду твоего сообщения!</b> 👇"),

            Column(
                Row(
                    Button(
                        Const("👤 Личный кабинет"),
                        id="personal_profile",
                        on_click=self.main_menu_service.handle_go_to_personal_profile,
                    ),
                    Button(
                        Const("📰 Организация"),
                        id="organization",
                        on_click=self.main_menu_service.handle_go_to_organization,
                    ),
                ),
                Button(
                    Const("✍️ Контент"),
                    id="content_generation",
                    on_click=self.main_menu_service.handle_go_to_content,
                ),
            ),
            state=model.MainMenuStates.main_menu,
            getter=self.main_menu_getter.get_main_menu_data,
            parse_mode="HTML",
        )
