from aiogram_dialog import Window, Dialog
from aiogram_dialog.widgets.text import Const, Format, Multi, Case
from aiogram_dialog.widgets.kbd import Button, Column, Row, Back, Select
from aiogram_dialog.widgets.input import TextInput, MessageInput
from aiogram_dialog.widgets.media import DynamicMedia

from internal import interface, model


class ModerationPublicationDialog(interface.IModerationPublicationDialog):

    def __init__(
            self,
            tel: interface.ITelemetry,
            moderation_publication_service: interface.IModerationPublicationDialogService,
    ):
        self.tracer = tel.tracer()
        self.logger = tel.logger()
        self.moderation_publication_service = moderation_publication_service

    def get_dialog(self) -> Dialog:
        return Dialog(
            self.get_moderation_list_window(),
            self.get_publication_review_window(),
            self.get_reject_comment_window(),
            self.get_edit_text_menu_window(),
            self.get_edit_title_window(),
            self.get_edit_tags_window(),
            self.get_edit_content_window(),
            self.get_edit_image_menu_window(),
            self.get_generate_image_window(),
            self.get_upload_image_window(),
        )

    def get_moderation_list_window(self) -> Window:
        """Окно списка публикаций на модерации"""
        return Window(
            Multi(
                Const("🔍 <b>Модерация публикаций</b>\n\n"),
                Case(
                    {
                        True: Multi(
                            Format("📊 Всего на модерации: <b>{publications_count}</b>\n"),
                            Format("📅 Период: <b>{period_text}</b>\n\n"),
                            Const("📝 <b>Выберите публикацию для просмотра:</b>"),
                        ),
                        False: Multi(
                            Const("✅ <b>Нет публикаций на модерации</b>\n\n"),
                            Const("<i>Все публикации обработаны или еще не поступали</i>"),
                        ),
                    },
                    selector="has_publications"
                ),
                sep="",
            ),

            Column(
                Select(
                    Format("{item[emoji]} {item[title]}\n"
                           "👤 {item[author]} | 🏷 {item[category]}\n"
                           "📅 {item[created_at]}"),
                    id="publication_select",
                    items="publications",
                    item_id_getter=lambda item: str(item["id"]),
                    on_click=self.moderation_publication_service.handle_select_publication,
                    when="has_publications",
                ),
            ),

            Row(
                Button(
                    Const("◀️ В меню контента"),
                    id="back_to_content_menu",
                    on_click=self.moderation_publication_service.handle_back_to_content_menu,
                ),
            ),

            state=model.ModerationPublicationStates.moderation_list,
            getter=self.moderation_publication_service.get_moderation_list_data,
            parse_mode="HTML",
        )

    def get_publication_review_window(self) -> Window:
        """Окно просмотра публикации для модерации"""
        return Window(
            Multi(
                Const("🔍 <b>Просмотр публикации</b>\n\n"),
                Format("👤 Автор: <b>{author_name}</b>\n"),
                Format("🏷 Рубрика: <b>{category_name}</b>\n"),
                Format("📅 Создано: {created_at}\n"),
                Format("{current_index}/{total_count}"),
                Case(
                    {
                        True: Format("⏰ Ожидает модерации: <b>{waiting_time}</b>\n"),
                        False: Const(""),
                    },
                    selector="has_waiting_time"
                ),
                Const("━━━━━━━━━━━━━━━━━━━━\n"),
                Format("<b>{publication_name}</b>\n\n"),
                Format("{publication_text}\n\n"),
                Case(
                    {
                        True: Format("🏷 Теги: {publication_tags}"),
                        False: Const(""),
                    },
                    selector="has_tags"
                ),
                Const("\n━━━━━━━━━━━━━━━━━━━━"),
                Case(
                    {
                        True: Format("\n\n📋 <b>История изменений:</b>\n{edit_history}"),
                        False: Const(""),
                    },
                    selector="has_edit_history"
                ),
                sep="",
            ),

            DynamicMedia(
                selector="preview_image_media",
                when="has_image",
            ),

            Column(
                Row(
                    Button(
                        Const("⬅️"),
                        id="prev_publication",
                        on_click=self.moderation_publication_service.handle_navigate_publication,
                        when="has_prev",
                    ),

                    Button(
                        Const("➡️"),
                        id="next_publication",
                        on_click=self.moderation_publication_service.handle_navigate_publication,
                        when="has_next",
                    ),
                ),
                Row(
                    Button(
                        Const("✏️ Редактировать"),
                        id="edit",
                        on_click=lambda c, b, d: d.switch_to(model.ModerationPublicationStates.edit_text_menu),
                    ),
                    Button(
                        Const("✅ Принять"),
                        id="approve",
                        on_click=self.moderation_publication_service.handle_approve_publication,
                    ),
                ),
                Row(
                    Button(
                        Const("💬 Отклонить"),
                        id="reject_with_comment",
                        on_click=lambda c, b, d: d.switch_to(model.ModerationPublicationStates.reject_comment),
                    ),
                ),
            ),

            Button(
                Const("◀️ К списку"),
                id="back_to_list",
                on_click=lambda c, b, d: d.switch_to(model.ModerationPublicationStates.moderation_list),
            ),

            state=model.ModerationPublicationStates.publication_review,
            getter=self.moderation_publication_service.get_publication_review_data,
            parse_mode="HTML",
        )

    def get_reject_comment_window(self) -> Window:
        """Окно ввода комментария при отклонении"""
        return Window(
            Multi(
                Const("❌ <b>Отклонение публикации</b>\n\n"),
                Format("📄 Публикация: <b>{publication_name}</b>\n"),
                Format("👤 Автор: <b>{author_name}</b>\n\n"),
                Const("💬 <b>Укажите причину отклонения:</b>\n"),
                Const("<i>Автор получит уведомление с вашим комментарием</i>\n\n"),
                Case(
                    {
                        True: Multi(
                            Const("📝 <b>Ваш комментарий:</b>\n"),
                            Format("<i>{reject_comment}</i>"),
                        ),
                        False: Const("💭 Ожидание ввода комментария..."),
                    },
                    selector="has_comment"
                ),
                sep="",
            ),

            TextInput(
                id="reject_comment_input",
                on_success=self.moderation_publication_service.handle_reject_comment_input,
            ),

            Row(
                Button(
                    Const("📤 Отправить отклонение"),
                    id="send_rejection",
                    on_click=self.moderation_publication_service.handle_send_rejection,
                    when="has_comment",
                ),
                Back(Const("◀️ Назад")),
            ),

            state=model.ModerationPublicationStates.reject_comment,
            getter=self.moderation_publication_service.get_reject_comment_data,
            parse_mode="HTML",
        )

    def get_edit_text_menu_window(self) -> Window:
        """Меню редактирования текстовых элементов"""
        return Window(
            Multi(
                Const("✏️ <b>Редактирование публикации</b>\n\n"),
                Format("📄 <b>{publication_name}</b>\n"),
                Format("👤 Автор: {author_name}\n\n"),
                Const("📌 <b>Выберите, что изменить:</b>"),
                sep="",
            ),

            Column(
                Button(
                    Const("📝 Изменить название"),
                    id="edit_title",
                    on_click=lambda c, b, d: d.switch_to(model.ModerationPublicationStates.edit_title),
                ),
                Button(
                    Const("🏷 Изменить теги"),
                    id="edit_tags",
                    on_click=lambda c, b, d: d.switch_to(model.ModerationPublicationStates.edit_tags),
                ),
                Button(
                    Const("📄 Изменить текст"),
                    id="edit_content",
                    on_click=lambda c, b, d: d.switch_to(model.ModerationPublicationStates.edit_content),
                ),
                Button(
                    Const("🖼 Управление изображением"),
                    id="edit_image",
                    on_click=lambda c, b, d: d.switch_to(model.ModerationPublicationStates.edit_image_menu),
                ),
            ),

            Row(
                Button(
                    Const("💾 Сохранить изменения"),
                    id="save_edits",
                    on_click=self.moderation_publication_service.handle_save_edits,
                    when="has_changes",
                ),
                Back(Const("◀️ Назад к просмотру")),
            ),

            state=model.ModerationPublicationStates.edit_text_menu,
            getter=self.moderation_publication_service.get_edit_menu_data,
            parse_mode="HTML",
        )

    def get_edit_title_window(self) -> Window:
        """Окно редактирования названия"""
        return Window(
            Multi(
                Const("📝 <b>Изменение названия</b>\n\n"),
                Format("Текущее: <b>{current_title}</b>\n\n"),
                Const("✍️ <b>Введите новое название:</b>\n"),
                Const("<i>Максимум 200 символов</i>"),
                sep="",
            ),

            TextInput(
                id="title_input",
                on_success=self.moderation_publication_service.handle_edit_title_save,
            ),

            Back(Const("◀️ Назад")),

            state=model.ModerationPublicationStates.edit_title,
            getter=self.moderation_publication_service.get_edit_title_data,
            parse_mode="HTML",
        )

    def get_edit_tags_window(self) -> Window:
        """Окно редактирования тегов"""
        return Window(
            Multi(
                Const("🏷 <b>Изменение тегов</b>\n\n"),
                Case(
                    {
                        True: Format("Текущие теги: <b>{current_tags}</b>\n\n"),
                        False: Const("Теги отсутствуют\n\n"),
                    },
                    selector="has_tags"
                ),
                Const("✍️ <b>Введите теги через запятую:</b>\n"),
                Const("<i>Например: маркетинг, продажи, SMM</i>\n"),
                Const("<i>Оставьте пустым для удаления всех тегов</i>"),
                sep="",
            ),

            TextInput(
                id="tags_input",
                on_success=self.moderation_publication_service.handle_edit_tags_save,
            ),

            Back(Const("◀️ Назад")),

            state=model.ModerationPublicationStates.edit_tags,
            getter=self.moderation_publication_service.get_edit_tags_data,
            parse_mode="HTML",
        )

    def get_edit_content_window(self) -> Window:
        """Окно редактирования основного текста"""
        return Window(
            Multi(
                Const("📄 <b>Изменение текста публикации</b>\n\n"),
                Format("Длина текущего текста: <b>{current_text_length}</b> символов\n\n"),
                Const("✍️ <b>Введите новый текст:</b>\n"),
                Const("<i>Минимум 50, максимум 4000 символов</i>\n"),
                Const("<i>Для просмотра текущего текста вернитесь назад</i>"),
                sep="",
            ),

            TextInput(
                id="content_input",
                on_success=self.moderation_publication_service.handle_edit_content_save,
            ),

            Back(Const("◀️ Назад")),

            state=model.ModerationPublicationStates.edit_content,
            getter=self.moderation_publication_service.get_edit_content_data,
            parse_mode="HTML",
        )

    def get_edit_image_menu_window(self) -> Window:
        """Меню управления изображением при редактировании"""
        return Window(
            Multi(
                Const("🖼 <b>Управление изображением</b>\n\n"),
                Case(
                    {
                        True: Multi(
                            Const("✅ <b>Изображение присутствует</b>\n"),
                            Case(
                                {
                                    True: Const("📸 Тип: пользовательское\n"),
                                    False: Const("🎨 Тип: сгенерированное\n"),
                                },
                                selector="is_custom_image"
                            ),
                        ),
                        False: Const("❌ <b>Изображение отсутствует</b>\n"),
                    },
                    selector="has_image"
                ),
                Const("\n📌 <b>Выберите действие:</b>"),
                sep="",
            ),

            Column(
                Button(
                    Const("🎨 Сгенерировать новое"),
                    id="generate_image",
                    on_click=self.moderation_publication_service.handle_generate_new_image,
                ),
                Button(
                    Const("🎨 Сгенерировать с описанием"),
                    id="generate_image_prompt",
                    on_click=lambda c, b, d: d.switch_to(model.ModerationPublicationStates.generate_image),
                ),
                Button(
                    Const("📤 Загрузить изображение"),
                    id="upload_image",
                    on_click=lambda c, b, d: d.switch_to(model.ModerationPublicationStates.upload_image),
                ),
                Button(
                    Const("🗑 Удалить изображение"),
                    id="remove_image",
                    on_click=self.moderation_publication_service.handle_remove_image,
                    when="has_image",
                ),
            ),

            Back(Const("◀️ Назад к редактированию")),

            state=model.ModerationPublicationStates.edit_image_menu,
            getter=self.moderation_publication_service.get_image_menu_data,
            parse_mode="HTML",
        )

    def get_generate_image_window(self) -> Window:
        """Окно генерации изображения с промптом"""
        return Window(
            Multi(
                Const("🎨 <b>Генерация изображения</b>\n\n"),
                Const("💡 <b>Опишите желаемое изображение:</b>\n"),
                Const("<i>Например: минималистичная иллюстрация в синих тонах, деловой стиль</i>\n"),
                Const("<i>Или: абстрактная композиция с элементами технологий</i>\n\n"),
                Case(
                    {
                        True: Format("📌 <b>Ваше описание:</b>\n<i>{image_prompt}</i>"),
                        False: Const("💬 Ожидание ввода описания..."),
                    },
                    selector="has_image_prompt"
                ),
                sep="",
            ),

            TextInput(
                id="image_prompt_input",
                on_success=self.moderation_publication_service.handle_generate_image_with_prompt,
            ),

            Back(Const("◀️ Назад")),

            state=model.ModerationPublicationStates.generate_image,
            getter=self.moderation_publication_service.get_image_prompt_data,
            parse_mode="HTML",
        )

    def get_upload_image_window(self) -> Window:
        """Окно загрузки собственного изображения"""
        return Window(
            Multi(
                Const("📤 <b>Загрузка изображения</b>\n\n"),
                Const("📸 <b>Отправьте изображение для публикации:</b>\n\n"),
                Const("✅ Поддерживаемые форматы: JPG, PNG, GIF\n"),
                Const("📏 Максимальный размер: 10 МБ\n"),
                Const("📐 Рекомендуемое соотношение: 16:9 или 1:1\n\n"),
                Const("<i>Изображение будет автоматически оптимизировано</i>"),
                sep="",
            ),

            MessageInput(
                func=self.moderation_publication_service.handle_image_upload,
                content_types=["photo"],
            ),

            Back(Const("◀️ Назад")),

            state=model.ModerationPublicationStates.upload_image,
            parse_mode="HTML",
        )