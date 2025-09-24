from aiogram_dialog import Window, Dialog
from aiogram_dialog.widgets.text import Const, Format, Multi, Case
from aiogram_dialog.widgets.kbd import Button, Column
from aiogram_dialog.widgets.input import MessageInput

from internal import interface, model


class GenerateVideoCutDialog(interface.IGenerateVideoCutDialog):
    def __init__(
            self,
            tel: interface.ITelemetry,
            generate_video_cut_service: interface.IGenerateVideoCutService,
            generate_video_cut_getter: interface.IGenerateVideoCutGetter,
    ):
        self.tracer = tel.tracer()
        self.logger = tel.logger()
        self.generate_video_cut_service = generate_video_cut_service
        self.generate_video_cut_getter = generate_video_cut_getter

    def get_dialog(self) -> Dialog:
        return Dialog(
            self.get_youtube_link_input_window(),
            self.get_video_generated_alert_window(),
        )

    def get_youtube_link_input_window(self) -> Window:
        return Window(
            Multi(
                Const("🎬 <b>Создание коротких видео из YouTube</b>\n\n"),

                # Показываем разное содержимое в зависимости от состояния
                Case(
                    {
                        True: Multi(
                            Format("🔗 <b>Ваша ссылка:</b>\n<code>{youtube_url}</code>\n\n"),
                            Const("⏳ <b>Видео обрабатывается...</b>\n\n"),
                            Const("🤖 Я создаю короткие видео из вашей ссылки\n"),
                            Const("⏱️ Это может занять <u>несколько минут</u>\n\n"),
                            Const("📬 <b>Я уведомлю вас, как только видео будут готовы!</b>\n\n"),
                            Const("📁 Готовые видео появятся в разделе:\n"),
                            Const("└ 📝 <i>\"Черновики\"</i> → <i>\"Черновики видео-нарезок\"</i>"),
                        ),
                        False: Multi(
                            # Error messages
                            Case(
                                {
                                    True: Const("❌ <b>Ошибка:</b> <i>Неверная ссылка на YouTube</i>\n\n"),
                                    False: Const(""),
                                },
                                selector="has_invalid_youtube_url"
                            ),
                            Case(
                                {
                                    True: Const(
                                        "❌ <b>Ошибка:</b> <i>Не удалось обработать видео.</i> 🔄 <u>Попробуйте еще раз</u>\n\n"),
                                    False: Const(""),
                                },
                                selector="has_processing_error"
                            ),

                            # Instructions
                            Const("📋 <b>Инструкция:</b>\n"),
                            Const("┌ 🔗 Отправьте ссылку на YouTube видео\n"),
                            Const("├ ✂️ Я создам из него короткие видео-нарезки\n"),
                            Const("└ 📁 Готовые видео появятся в разделе <i>\"Черновики\"</i>\n\n"),
                            Const("🎯 <b>Введите ссылку на YouTube видео:</b>\n"),
                            Const("💡 <i>Например:</i> <code>https://www.youtube.com/watch?v=VIDEO_ID</code>\n\n"),

                            Case(
                                {
                                    True: Format("📌 <b>Введенная ссылка:</b>\n<code>{youtube_url}</code>"),
                                    False: Const("⌨️ <i>Ожидание ввода ссылки на YouTube...</i>"),
                                },
                                selector="has_youtube_url"
                            ),
                        ),
                    },
                    selector="is_processing_video"
                ),
                sep="",
            ),

            MessageInput(
                func=self.generate_video_cut_service.handle_youtube_link_input,
                content_types=["text"],
            ),

            Column(
                Button(
                    Const("🏠 В меню контента"),
                    id="to_content_menu",
                    on_click=self.generate_video_cut_service.handle_go_to_content_menu,
                ),
            ),

            state=model.GenerateVideoCutStates.input_youtube_link,
            getter=self.generate_video_cut_getter.get_youtube_input_data,
            parse_mode="HTML",
        )

    def get_video_generated_alert_window(self) -> Window:
        """Окно со списком готовых видео"""
        return Window(
            Multi(
                Case(
                    {
                        True: Multi(
                            Const("🎉 <b>Ваши видео готовы!</b>\n\n"),
                            Format("📊 У вас готово <b>{alerts_count}</b> {alerts_word}:\n\n"),
                            # Список всех алертов
                            Format("📋 <b>Список готовых видео:</b>\n{alerts_text}"),
                        ),
                        False: Multi(
                            Const("🎉 <b>Ваше видео готово!</b>\n\n"),
                            Format("✅ Успешно сгенерировано <b>{video_count}</b> {video_word} из видео:\n"),
                            Format("🎬 <a href='{youtube_video_reference}'>📺 Исходное видео</a>\n\n"),
                        ),
                    },
                    selector="has_multiple_alerts"
                ),
                Const("👉 <u>Перейдите в черновики</u>, чтобы посмотреть результат! 🎯"),
                sep="",
            ),

            Column(
                Button(
                    Const("📝 Черновики нарезок"),
                    id="to_video_drafts_from_alert",
                    on_click=self.generate_video_cut_service.handle_go_to_video_drafts,
                ),
                Button(
                    Const("🏠 Главное меню"),
                    id="to_main_menu_from_alert",
                    on_click=self.generate_video_cut_service.handle_go_to_main_menu,
                ),
            ),

            state=model.GenerateVideoCutStates.video_generated_alert,
            getter=self.generate_video_cut_getter.get_video_alert_data,
            parse_mode="HTML",
        )