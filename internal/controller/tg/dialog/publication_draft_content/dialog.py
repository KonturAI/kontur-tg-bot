# internal/controller/tg/dialog/publication_draft_content/dialog.py
from aiogram_dialog import Window, Dialog
from aiogram_dialog.widgets.text import Const, Format, Multi, Case
from aiogram_dialog.widgets.kbd import Button, Column, Row
from aiogram_dialog.widgets.input import TextInput
from aiogram_dialog.widgets.media import DynamicMedia

from internal import interface, model


class PublicationDraftDialog(interface.IPublicationDraftDialog):

    def __init__(
            self,
            tel: interface.ITelemetry,
            publication_draft_service: interface.IPublicationDraftDialogService,
    ):
        self.tracer = tel.tracer()
        self.logger = tel.logger()
        self.publication_draft_service = publication_draft_service

    def get_dialog(self) -> Dialog:
        return Dialog(
            self.get_publication_list_window(),
            self.get_edit_preview_window(),
            self.get_edit_title_window(),
            self.get_edit_description_window(),
            self.get_edit_tags_window(),
        )

    def get_publication_list_window(self) -> Window:
        """Окно списка черновиков публикаций с отображением изображений"""
        return Window(
            Multi(
                Const("📄 <b>Мои черновики публикаций</b>\n\n"),
                Case(
                    {
                        True: Multi(
                            Format("📊 Всего черновиков: <b>{publications_count}</b>\n"),
                            Format("📅 Период: <b>{period_text}</b>\n\n"),
                            # Отображаем изображение ПЕРЕД информацией о публикации
                            Case(
                                {
                                    True: Const("🖼 <b>Превью изображения:</b>\n"),
                                    False: Const("⚠️ <i>Изображение отсутствует</i>\n"),
                                },
                                selector="has_image"
                            ),
                            Const("━━━━━━━━━━━━━━━━━━━━\n"),
                            # Информация о текущей публикации
                            Format("📄 <b>{publication_name}</b>\n\n"),
                            Format("{publication_text}\n\n"),
                            Case(
                                {
                                    True: Format("🏷 Теги: {publication_tags}\n"),
                                    False: Const("🏷 Теги: <i>отсутствуют</i>\n"),
                                },
                                selector="has_tags"
                            ),

                            Format("📅 Создано: {created_at}\n"),
                            Const("\n━━━━━━━━━━━━━━━━━━━━"),
                        ),
                        False: Multi(
                            Const("📂 <b>Нет черновиков публикаций</b>\n\n"),
                            Const("<i>Создайте первую публикацию для работы с черновиками</i>"),
                        ),
                    },
                    selector="has_publications"
                ),
                sep="",
            ),

            # Добавляем динамическое медиа для отображения изображения
            DynamicMedia(
                "image_media",
                when="has_image"
            ),

            # Навигация со счетчиком
            Row(
                Button(
                    Const("⬅️"),
                    id="prev_publication",
                    on_click=self.publication_draft_service.handle_navigate_publication,
                    when="has_prev",
                ),
                Button(
                    Format("{current_index}/{publications_count}"),
                    id="counter",
                    on_click=lambda c, b, d: c.answer("📊 Навигация по черновикам"),
                    when="has_publications",
                ),
                Button(
                    Const("➡️"),
                    id="next_publication",
                    on_click=self.publication_draft_service.handle_navigate_publication,
                    when="has_next",
                ),
                when="has_publications",
            ),

            # Основные действия
            Column(
                Row(
                    Button(
                        Const("✏️ Редактировать"),
                        id="edit",
                        on_click=lambda c, b, d: d.switch_to(model.PublicationDraftStates.edit_preview),
                        when="has_publications",
                    ),
                ),
                Button(
                    Const("📤 На модерацию"),
                    id="send_to_moderation",
                    on_click=self.publication_draft_service.handle_send_to_moderation,
                    when="not_can_publish",  # инвертированное условие
                ),
                Button(
                    Const("🚀 Опубликовать"),
                    id="publish_now",
                    on_click=self.publication_draft_service.handle_publish_now,
                    when="can_publish",
                ),
                Row(
                    Button(
                        Const("🗑 Удалить"),
                        id="delete",
                        on_click=self.publication_draft_service.handle_delete_publication,
                        when="has_publications",
                    ),
                ),
                when="has_publications",
            ),

            Row(
                Button(
                    Const("◀️ В меню контента"),
                    id="back_to_content_menu",
                    on_click=self.publication_draft_service.handle_back_to_content_menu,
                ),
            ),

            state=model.PublicationDraftStates.publication_list,
            getter=self.publication_draft_service.get_publication_list_data,
            parse_mode="HTML",
        )

    def get_edit_preview_window(self) -> Window:
        """Окно редактирования с превью публикации"""
        return Window(
            Multi(
                Const("✏️ <b>Редактирование публикации</b>\n\n"),
                # Сначала показываем само изображение
                Case(
                    {
                        True: Const("🖼 <b>Превью публикации:</b>\n"),
                        False: Const("⚠️ <i>Превью недоступно</i>\n"),
                    },
                    selector="has_image"
                ),
                Const("━━━━━━━━━━━━━━━━━━━━\n"),
                Format("📅 Создано: {created_at}\n"),
                Const("━━━━━━━━━━━━━━━━━━━━\n"),
                Format("📄 <b>{publication_name}</b>\n\n"),
                Format("{publication_text}\n\n"),
                Case(
                    {
                        True: Format("🏷 Теги: {publication_tags}"),
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

            # Добавляем медиа и в окно редактирования
            DynamicMedia(
                "image_media",
                when="has_image"
            ),

            Column(
                Button(
                    Const("📝 Изменить название"),
                    id="edit_title",
                    on_click=lambda c, b, d: d.switch_to(model.PublicationDraftStates.edit_title),
                ),
                Button(
                    Const("📄 Изменить описание"),
                    id="edit_description",
                    on_click=lambda c, b, d: d.switch_to(model.PublicationDraftStates.edit_description),
                ),
                Button(
                    Const("🏷 Изменить теги"),
                    id="edit_tags",
                    on_click=lambda c, b, d: d.switch_to(model.PublicationDraftStates.edit_tags),
                ),
            ),

            Row(
                Button(
                    Const("💾 Сохранить изменения"),
                    id="save_changes",
                    on_click=self.publication_draft_service.handle_save_changes,
                    when="has_changes",
                ),
                Button(
                    Const("◀️ Назад"),
                    id="back_to_publication_list",
                    on_click=self.publication_draft_service.handle_back_to_publication_list,
                ),
            ),

            state=model.PublicationDraftStates.edit_preview,
            getter=self.publication_draft_service.get_edit_preview_data,
            parse_mode="HTML",
        )

    def get_edit_title_window(self) -> Window:
        """Окно редактирования названия публикации"""
        return Window(
            Multi(
                Const("📝 <b>Изменение названия публикации</b>\n\n"),
                Format("Текущее: <b>{current_title}</b>\n\n"),
                Const("✍️ <b>Введите новое название:</b>\n"),
                Const("<i>Максимум 200 символов</i>\n"),
                sep="",
            ),

            TextInput(
                id="title_input",
                on_success=self.publication_draft_service.handle_edit_title_save,
            ),

            Button(
                Const("◀️ Назад"),
                id="back_to_edit_preview",
                on_click=lambda c, b, d: d.switch_to(model.PublicationDraftStates.edit_preview),
            ),

            state=model.PublicationDraftStates.edit_title,
            getter=self.publication_draft_service.get_edit_title_data,
            parse_mode="HTML",
        )

    def get_edit_description_window(self) -> Window:
        """Окно редактирования текста публикации"""
        return Window(
            Multi(
                Const("📄 <b>Изменение текста публикации</b>\n\n"),
                Format("Длина текущего текста: <b>{current_description_length}</b> символов\n\n"),
                Const("✍️ <b>Введите новый текст:</b>\n"),
                Const("<i>Максимум 4000 символов</i>\n"),
                Const("<i>Для просмотра текущего текста вернитесь назад</i>"),
                sep="",
            ),

            TextInput(
                id="description_input",
                on_success=self.publication_draft_service.handle_edit_description_save,
            ),

            Button(
                Const("◀️ Назад"),
                id="back_to_edit_preview",
                on_click=lambda c, b, d: d.switch_to(model.PublicationDraftStates.edit_preview),
            ),

            state=model.PublicationDraftStates.edit_description,
            getter=self.publication_draft_service.get_edit_description_data,
            parse_mode="HTML",
        )

    def get_edit_tags_window(self) -> Window:
        """Окно редактирования тегов публикации"""
        return Window(
            Multi(
                Const("🏷 <b>Изменение тегов публикации</b>\n\n"),
                Case(
                    {
                        True: Format("Текущие теги: <b>{current_tags}</b>\n\n"),
                        False: Const("Теги отсутствуют\n\n"),
                    },
                    selector="has_tags"
                ),
                Const("✍️ <b>Введите теги через запятую:</b>\n"),
                Const("<i>Например: маркетинг, продажи, SMM</i>\n"),
                Const("<i>Максимум 10 тегов</i>\n"),
                Const("<i>Оставьте пустым для удаления всех тегов</i>"),
                sep="",
            ),

            TextInput(
                id="tags_input",
                on_success=self.publication_draft_service.handle_edit_tags_save,
            ),

            Button(
                Const("◀️ Назад"),
                id="back_to_edit_preview",
                on_click=lambda c, b, d: d.switch_to(model.PublicationDraftStates.edit_preview),
            ),

            state=model.PublicationDraftStates.edit_tags,
            getter=self.publication_draft_service.get_edit_tags_data,
            parse_mode="HTML",
        )