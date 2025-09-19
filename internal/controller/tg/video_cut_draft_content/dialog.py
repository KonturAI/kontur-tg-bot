from aiogram_dialog import Window, Dialog
from aiogram_dialog.widgets.text import Const, Format, Multi, Case
from aiogram_dialog.widgets.kbd import Button, Column, Row, Back, Select, Checkbox
from aiogram_dialog.widgets.input import TextInput, MessageInput
from aiogram_dialog.widgets.media import DynamicMedia

from internal import interface, model


class DraftVideoCutsDialog(interface.IDraftVideoCutsDialog):

    def __init__(
            self,
            tel: interface.ITelemetry,
            draft_video_cuts_service: interface.IDraftVideoCutsDialogService,
    ):
        self.tracer = tel.tracer()
        self.logger = tel.logger()
        self.draft_video_cuts_service = draft_video_cuts_service

    def get_dialog(self) -> Dialog:
        return Dialog(
            self.get_draft_list_window(),
            self.get_edit_preview_window(),
            self.get_edit_title_window(),
            self.get_edit_description_window(),
            self.get_edit_tags_window(),
            self.get_publication_settings_window(),
        )

    def get_draft_list_window(self) -> Window:
        """Окно списка черновиков видео-нарезок - сразу показывает первую нарезку"""
        return Window(
            Multi(
                Const("📹 <b>Мои черновики видео</b>\n\n"),
                Case(
                    {
                        True: Multi(
                            Format("📊 Всего черновиков: <b>{drafts_count}</b>\n"),
                            Format("📅 Период: <b>{period_text}</b>\n\n"),
                            # Показываем информацию о текущей нарезке
                            Format("🎬 <b>{video_name}</b>\n\n"),
                            Format("{video_description}\n\n"),
                            Case(
                                {
                                    True: Format("🏷 Теги: {video_tags}\n"),
                                    False: Const("🏷 Теги: <i>отсутствуют</i>\n"),
                                },
                                selector="has_tags"
                            ),
                            Format("📹 Источник: {youtube_reference_short}\n"),
                            Format("📅 Создано: {created_at}\n"),
                            # Информация о настройках публикации
                            Const("\n🌐 <b>Настройки публикации:</b>\n"),
                            Case(
                                {
                                    True: Const("📺 YouTube Shorts: ✅\n"),
                                    False: Const("📺 YouTube Shorts: ❌\n"),
                                },
                                selector="youtube_enabled"
                            ),
                            Case(
                                {
                                    True: Const("📸 Instagram Reels: ✅"),
                                    False: Const("📸 Instagram Reels: ❌"),
                                },
                                selector="instagram_enabled"
                            ),
                            Const("\n━━━━━━━━━━━━━━━━━━━━"),
                        ),
                        False: Multi(
                            Const("📂 <b>Нет черновиков видео</b>\n\n"),
                            Const("<i>Создайте первую видео-нарезку для работы с черновиками</i>"),
                        ),
                    },
                    selector="has_drafts"
                ),
                sep="",
            ),

            # Навигация со счетчиком
            Row(
                Button(
                    Const("⬅️"),
                    id="prev_draft",
                    on_click=self.draft_video_cuts_service.handle_navigate_draft,
                    when="has_prev",
                ),
                Button(
                    Format("{current_index}/{total_count}"),
                    id="counter",
                    on_click=lambda c, b, d: c.answer(),
                    when="has_drafts",
                ),
                Button(
                    Const("➡️"),
                    id="next_draft",
                    on_click=self.draft_video_cuts_service.handle_navigate_draft,
                    when="has_next",
                ),
                when="has_drafts",
            ),

            # Основные действия
            Column(
                Row(
                    Button(
                        Const("✏️ Редактировать"),
                        id="edit",
                        on_click=lambda c, b, d: d.switch_to(model.DraftVideoCutsStates.edit_preview),
                        when="has_drafts",
                    ),

                ),
                Case(
                    {
                        True: Button(
                            Const("📤 На модерацию"),
                            id="send_to_moderation",
                            on_click=self.draft_video_cuts_service.handle_send_to_moderation,
                        ),
                        False: Button(
                            Const("🚀 Опубликовать"),
                            id="publish_now",
                            on_click=self.draft_video_cuts_service.handle_publish_now,
                        ),
                    },
                    selector="needs_moderation"
                ),
                Row(
                    Button(
                        Const("🗑 Удалить"),
                        id="delete",
                        on_click=self.draft_video_cuts_service.handle_delete_draft,
                        when="has_drafts",
                    ),
                ),
                when="has_drafts",
            ),

            Row(
                Button(
                    Const("◀️ В меню контента"),
                    id="back_to_content_menu",
                    on_click=self.draft_video_cuts_service.handle_back_to_content_menu,
                ),
            ),

            state=model.DraftVideoCutsStates.draft_list,
            getter=self.draft_video_cuts_service.get_draft_list_data,
            parse_mode="HTML",
        )

    def get_edit_preview_window(self) -> Window:
        """Окно редактирования с превью видео-нарезки"""
        return Window(
            Multi(
                Const("✏️ <b>Редактирование видео</b>\n\n"),
                # Показываем саму нарезку
                Format("📅 Создано: {created_at}\n"),
                Format("📹 Источник: {youtube_reference}\n\n"),
                Const("━━━━━━━━━━━━━━━━━━━━\n"),
                Format("🎬 <b>{video_name}</b>\n\n"),
                Format("{video_description}\n\n"),
                Case(
                    {
                        True: Format("🏷 Теги: {video_tags}"),
                        False: Const("🏷 Теги: <i>отсутствуют</i>"),
                    },
                    selector="has_tags"
                ),
                Case(
                    {
                        True: Const("\n\n<i>❗️ Есть несохраненные изменения</i>"),
                        False: Const(""),
                    },
                    selector="has_changes"
                ),
                Const("\n━━━━━━━━━━━━━━━━━━━━\n\n"),
                Const("📌 <b>Выберите, что изменить:</b>"),
                sep="",
            ),

            Column(
                Button(
                    Const("📝 Изменить название"),
                    id="edit_title",
                    on_click=lambda c, b, d: d.switch_to(model.DraftVideoCutsStates.edit_title),
                ),
                Button(
                    Const("📄 Изменить описание"),
                    id="edit_description",
                    on_click=lambda c, b, d: d.switch_to(model.DraftVideoCutsStates.edit_description),
                ),
                Button(
                    Const("🏷 Изменить теги"),
                    id="edit_tags",
                    on_click=lambda c, b, d: d.switch_to(model.DraftVideoCutsStates.edit_tags),
                ),
                Button(
                    Const("⚙️ Настройки публикации"),
                    id="publication_settings",
                    on_click=lambda c, b, d: d.switch_to(model.DraftVideoCutsStates.publication_settings),
                ),
            ),

            Row(
                Button(
                    Const("💾 Сохранить изменения"),
                    id="save_changes",
                    on_click=self.draft_video_cuts_service.handle_save_changes,
                    when="has_changes",
                ),
                Button(
                    Const("◀️ Назад"),
                    id="back_to_draft_list",
                    on_click=self.draft_video_cuts_service.handle_back_to_draft_list,
                ),
            ),

            state=model.DraftVideoCutsStates.edit_preview,
            getter=self.draft_video_cuts_service.get_edit_preview_data,
            parse_mode="HTML",
        )

    def get_edit_title_window(self) -> Window:
        """Окно редактирования названия видео"""
        return Window(
            Multi(
                Const("📝 <b>Изменение названия видео</b>\n\n"),
                Format("Текущее: <b>{current_title}</b>\n\n"),
                Const("✍️ <b>Введите новое название:</b>\n"),
                Const("<i>Максимум 100 символов для YouTube Shorts</i>\n"),
                Const("<i>Максимум 2200 символов для Instagram Reels</i>"),
                sep="",
            ),

            TextInput(
                id="title_input",
                on_success=self.draft_video_cuts_service.handle_edit_title_save,
            ),

            Button(
                Const("◀️ Назад"),
                id="back_to_edit_preview",
                on_click=lambda c, b, d: d.switch_to(model.DraftVideoCutsStates.edit_preview),
            ),

            state=model.DraftVideoCutsStates.edit_title,
            getter=self.draft_video_cuts_service.get_edit_title_data,
            parse_mode="HTML",
        )

    def get_edit_description_window(self) -> Window:
        """Окно редактирования описания видео"""
        return Window(
            Multi(
                Const("📄 <b>Изменение описания видео</b>\n\n"),
                Format("Длина текущего описания: <b>{current_description_length}</b> символов\n\n"),
                Const("✍️ <b>Введите новое описание:</b>\n"),
                Const("<i>Максимум 5000 символов для YouTube</i>\n"),
                Const("<i>Максимум 2200 символов для Instagram</i>\n"),
                Const("<i>Для просмотра текущего описания вернитесь назад</i>"),
                sep="",
            ),

            TextInput(
                id="description_input",
                on_success=self.draft_video_cuts_service.handle_edit_description_save,
            ),

            Button(
                Const("◀️ Назад"),
                id="back_to_edit_preview",
                on_click=lambda c, b, d: d.switch_to(model.DraftVideoCutsStates.edit_preview),
            ),

            state=model.DraftVideoCutsStates.edit_description,
            getter=self.draft_video_cuts_service.get_edit_description_data,
            parse_mode="HTML",
        )

    def get_edit_tags_window(self) -> Window:
        """Окно редактирования тегов видео"""
        return Window(
            Multi(
                Const("🏷 <b>Изменение тегов видео</b>\n\n"),
                Case(
                    {
                        True: Format("Текущие теги: <b>{current_tags}</b>\n\n"),
                        False: Const("Теги отсутствуют\n\n"),
                    },
                    selector="has_tags"
                ),
                Const("✍️ <b>Введите теги через запятую:</b>\n"),
                Const("<i>Например: технологии, обучение, shorts</i>\n"),
                Const("<i>Максимум 15 тегов для YouTube</i>\n"),
                Const("<i>Максимум 30 хештегов для Instagram</i>\n"),
                Const("<i>Оставьте пустым для удаления всех тегов</i>"),
                sep="",
            ),

            TextInput(
                id="tags_input",
                on_success=self.draft_video_cuts_service.handle_edit_tags_save,
            ),

            Button(
                Const("◀️ Назад"),
                id="back_to_edit_preview",
                on_click=lambda c, b, d: d.switch_to(model.DraftVideoCutsStates.edit_preview),
            ),

            state=model.DraftVideoCutsStates.edit_tags,
            getter=self.draft_video_cuts_service.get_edit_tags_data,
            parse_mode="HTML",
        )

    def get_publication_settings_window(self) -> Window:
        """Окно настроек публикации видео"""
        return Window(
            Multi(
                Const("⚙️ <b>Настройки публикации</b>\n\n"),
                Const("🌐 <b>Выберите платформы для публикации:</b>\n"),
                sep="",
            ),

            # Чекбоксы для выбора платформ
            Column(
                Checkbox(
                    Const("📺 YouTube Shorts"),
                    Const("✅ YouTube Shorts"),
                    id="youtube_checkbox",
                    default=True,
                    on_state_changed=self.draft_video_cuts_service.handle_toggle_platform,
                ),
                Checkbox(
                    Const("📸 Instagram Reels"),
                    Const("✅ Instagram Reels"),
                    id="instagram_checkbox",
                    default=True,
                    on_state_changed=self.draft_video_cuts_service.handle_toggle_platform,
                ),
            ),

            Multi(
                Const("\n⏰ <b>Время публикации:</b>\n"),
                Case(
                    {
                        True: Multi(
                            Const("Запланированная публикация: "),
                            Format("<b>{scheduled_time}</b>"),
                        ),
                        False: Const("Публикация: <b>немедленно</b>"),
                    },
                    selector="is_scheduled"
                ),
                sep="",
            ),

            Column(
                Button(
                    Const("📅 Запланировать публикацию"),
                    id="schedule_publication",
                    on_click=self.draft_video_cuts_service.handle_schedule_publication,
                ),
                Button(
                    Const("🗑 Убрать расписание"),
                    id="remove_schedule",
                    on_click=self.draft_video_cuts_service.handle_schedule_publication,
                    when="is_scheduled",
                ),
            ),

            Button(
                Const("◀️ Назад"),
                id="back_to_edit_preview",
                on_click=lambda c, b, d: d.switch_to(model.DraftVideoCutsStates.edit_preview),
            ),

            state=model.DraftVideoCutsStates.publication_settings,
            getter=self.draft_video_cuts_service.get_publication_settings_data,
            parse_mode="HTML",
        )