from aiogram_dialog import Window, Dialog
from aiogram_dialog.widgets.text import Const, Format
from aiogram_dialog.widgets.kbd import Button, Back
from aiogram_dialog.widgets.input import MessageInput

from internal import interface, model


class GenerateVideoCutDialog(interface.IGenerateVideoCutDialog):
    def __init__(
            self,
            tel: interface.ITelemetry,
            generate_video_cut_service: interface.IGenerateVideoCutDialogService,
    ):
        self.tracer = tel.tracer()
        self.logger = tel.logger()
        self.generate_video_cut_service = generate_video_cut_service

    def get_dialog(self) -> Dialog:
        return Dialog(
            self.get_youtube_link_input_window(),
        )

    def get_youtube_link_input_window(self) -> Window:
        return Window(
            Const("🎬 <b>Создание коротких видео из YouTube</b>\n\n"),
            Const("📝 <b>Инструкция:</b>\n"),
            Const("• Отправьте ссылку на YouTube видео\n"),
            Const("• Я создам из него короткие видео-нарезки\n"),
            Const("• Готовые видео появятся в разделе \"Черновики\"\n\n"),
            Const("🔗 Введите ссылку на YouTube видео:"),

            MessageInput(
                func=self.generate_video_cut_service.handle_youtube_link_input,
                content_types=["text"],
            ),

            Button(
                Const("🏠 В меню контента"),
                id="to_content_menu",
                on_click=lambda c, b, d: d.start(
                    model.ContentMenuStates.content_menu,
                    mode=d.StartMode.RESET_STACK
                ),
            ),

            state=model.GenerateVideoCutStates.input_youtube_link,
            getter=self.generate_video_cut_service.get_youtube_input_data,
            parse_mode="HTML",
        )