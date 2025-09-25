from aiogram_dialog import Window, Dialog
from aiogram_dialog.widgets.text import Const, Format, Multi, Case
from aiogram_dialog.widgets.kbd import Button, Column, Row, Back, ScrollingGroup, Select, NumberedPager, Checkbox
from aiogram_dialog.widgets.input import TextInput, MessageInput
from aiogram_dialog.widgets.media import DynamicMedia

from internal import interface, model


class PublicationDraftDialog(interface.IPublicationDraftDialog):

    def __init__(
            self,
            tel: interface.ITelemetry,
            publication_draft_service: interface.IPublicationDraftService,
            publication_draft_getter: interface.IPublicationDraftGetter,
    ):
        self.tracer = tel.tracer()
        self.logger = tel.logger()
        self.publication_draft_service = publication_draft_service
        self.publication_draft_getter = publication_draft_getter

    def get_dialog(self) -> Dialog:
        return Dialog(
            self.get_publication_list_window(),
            self.get_edit_preview_window(),
            self.get_edit_text_menu_window(),
            self.get_regenerate_text_window(),
            self.get_edit_title_window(),
            self.get_edit_description_window(),
            self.get_edit_content_window(),
            self.get_edit_image_menu_window(),
            self.get_generate_image_window(),
            self.get_upload_image_window(),
            self.get_edit_tags_window(),
            self.get_social_network_select_window(),
        )

    def get_publication_list_window(self) -> Window:
        """
        🏠 ГЛАВНОЕ ОКНО - Список черновиков публикаций
        Этот виджет отображает все сохраненные черновики в виде скролльного списка
        """
        return Window(
            Multi(
                Const("📄 <b>Черновики публикаций</b>\n\n"),
                Case(
                    {
                        True: Multi(
                            Format("📊 Всего черновиков: <b>{publications_count}</b>\n\n"),
                            Const("📋 <i>Выберите публикацию для редактирования:</i>"),
                        ),
                        False: Const("📝 <i>У вас пока нет черновиков публикаций</i>"),
                    },
                    selector="has_publications"
                ),
                sep="",
            ),

            # 📜 СКРОЛЛ-СПИСОК черновиков (аналог change_employee)
            ScrollingGroup(
                Select(
                    # 📌 Каждый элемент списка показывает название + дату создания
                    Format("📄 {item[title]}\n🗓 {item[created_date]}"),
                    id="publication_select",
                    items="publications",  # Список публикаций от геттера
                    item_id_getter=lambda item: str(item["id"]),
                    on_click=self.publication_draft_service.handle_select_publication,
                ),
                id="publication_scroll",
                width=1,
                height=6,  # Показываем 6 элементов за раз
                hide_on_single_page=True,
                when="has_publications",
            ),

            # 📄 ПАГИНАЦИЯ для большого количества черновиков
            NumberedPager(
                scroll="publication_scroll",
                when="show_pager",
            ),

            # ⬅️ КНОПКА НАЗАД в контент-меню
            Button(
                Const("⬅️ Вернуться в меню контента"),
                id="back_to_content_menu",
                on_click=self.publication_draft_service.handle_back_to_content_menu,
            ),

            state=model.PublicationDraftStates.publication_list,
            getter=self.publication_draft_getter.get_publication_list_data,
            parse_mode="HTML",
        )

    def get_edit_preview_window(self) -> Window:
        """
        👁️ ОКНО ПРЕВЬЮ - Отображение черновика + кнопки действий
        Показывает содержимое выбранного черновика и основные действия
        """
        return Window(
            Multi(
                Const("📄 <b>Редактирование черновика</b>\n\n"),
                Format("🏷 Рубрика: <b>{category_name}</b>\n"),
                Const("━━━━━━━━━━━━━━━━━━━━\n"),
                Format("<b>{publication_title}</b>\n\n"),  # Название публикации
                Format("{publication_content}\n\n"),       # Основной текст
                Case(
                    {
                        True: Format("🏷 Теги: {publication_tags}"),
                        False: Const(""),
                    },
                    selector="has_tags"
                ),
                Case(
                    {
                        True: Format("\n🖼 Изображение: есть"),
                        False: Const("\n🖼 Изображение: нет"),
                    },
                    selector="has_image"
                ),
                Const("\n━━━━━━━━━━━━━━━━━━━━"),
                sep="",
            ),

            # 🖼️ ИЗОБРАЖЕНИЕ (если есть)
            DynamicMedia(
                selector="preview_image_media",
                when="has_image",
            ),

            # 🎮 НАВИГАЦИЯ по черновикам (стрелки влево/вправо)
            Row(
                Button(
                    Const("⬅️"),
                    id="prev_publication",
                    on_click=self.publication_draft_service.handle_navigate_publication,
                    when="has_prev",
                ),
                Button(
                    Format("📍 {current_index}/{total_count}"),
                    id="current_position",
                    on_click=None,  # Просто информационная кнопка
                ),
                Button(
                    Const("➡️"),
                    id="next_publication", 
                    on_click=self.publication_draft_service.handle_navigate_publication,
                    when="has_next",
                ),
            ),

            # 🛠️ ОСНОВНЫЕ ДЕЙСТВИЯ С ЧЕРНОВИКОМ
            Column(
                Row(
                    Button(
                        Const("✏️ Редактировать"),
                        id="edit_text_menu",
                        on_click=lambda c, b, d: d.switch_to(model.PublicationDraftStates.edit_text_menu),
                    ),
                    Button(
                        Const("🗑 Удалить"),
                        id="delete_publication",
                        on_click=self.publication_draft_service.handle_delete_publication,
                    ),
                ),
                Button(
                    Const("📤 Отправить на модерацию"),
                    id="send_to_moderation",
                    on_click=self.publication_draft_service.handle_send_to_moderation_with_networks_publication,
                    when="requires_moderation",
                ),
                Button(
                    Const("🚀 Опубликовать сейчас"),
                    id="publish_now",
                    on_click=self.publication_draft_service.handle_publish_with_selected_networks_publication,
                    when="can_publish_directly",
                ),
            ),

            # ◀️ НАЗАД к списку черновиков
            Button(
                Const("◀️ К списку черновиков"),
                id="back_to_list",
                on_click=self.publication_draft_service.handle_back_to_publication_list,
            ),

            state=model.PublicationDraftStates.edit_preview,
            getter=self.publication_draft_getter.get_edit_preview_data,
            parse_mode="HTML",
        )

    def get_edit_text_menu_window(self) -> Window:
        """
        ✏️ МЕНЮ РЕДАКТИРОВАНИЯ - Выбор что именно редактировать
        """
        return Window(
            Multi(
                Const("✏️ <b>Редактирование черновика</b>\n\n"),
                Const("📌 <b>Выберите, что изменить:</b>"),
                sep="",
            ),

            Column(
                Button(
                    Const("🔄 Перегенерировать весь текст"),
                    id="regenerate_all",
                    on_click=self.publication_draft_service.handle_regenerate_text,
                ),
                Button(
                    Const("🔄 Перегенерировать с промптом"),
                    id="regenerate_with_prompt",
                    on_click=lambda c, b, d: d.switch_to(model.PublicationDraftStates.regenerate_text),
                ),
                Button(
                    Const("📝 Изменить название"),
                    id="edit_title",
                    on_click=lambda c, b, d: d.switch_to(model.PublicationDraftStates.edit_title),
                ),
                Button(
                    Const("📄 Изменить текст"),
                    id="edit_content",
                    on_click=lambda c, b, d: d.switch_to(model.PublicationDraftStates.edit_content),
                ),
                Button(
                    Const("🏷 Изменить теги"),
                    id="edit_tags",
                    on_click=lambda c, b, d: d.switch_to(model.PublicationDraftStates.edit_tags),
                ),
                Button(
                    Const("🖼 Управление изображением"),
                    id="edit_image_menu",
                    on_click=lambda c, b, d: d.switch_to(model.PublicationDraftStates.edit_image_menu),
                ),
            ),

            Button(
                Const("◀️ Назад к превью"),
                id="back_to_preview",
                on_click=lambda c, b, d: d.switch_to(model.PublicationDraftStates.edit_preview),
            ),

            state=model.PublicationDraftStates.edit_text_menu,
            getter=self.publication_draft_getter.get_edit_text_menu_data,
            parse_mode="HTML",
        )

    def get_regenerate_text_window(self) -> Window:
        """
        🔄 ПЕРЕГЕНЕРАЦИЯ с промптом (копия из generate_publication)
        """
        return Window(
            Multi(
                Const("🔄 <b>Перегенерация с дополнительными указаниями</b>\n\n"),
                Case(
                    {
                        True: Multi(
                            Format("📌 <b>Ваши указания:</b>\n<i>{regenerate_prompt}</i>\n\n"),
                            Const("⏳ <b>Перегенерирую текст...</b>\n"),
                            Const("Это может занять время. Пожалуйста, ожидайте."),
                        ),
                        False: Multi(
                            Case(
                                {
                                    True: Const("⚠️ <b>Ошибка:</b> Укажите дополнительные пожелания\n\n"),
                                    False: Const(""),
                                },
                                selector="has_void_regenerate_prompt"
                            ),
                            Const("💡 <b>Введите дополнительные пожелания:</b>\n"),
                            Const("<i>Например: сделай текст короче, добавь больше эмоций и т.д.</i>\n\n"),
                            Case(
                                {
                                    True: Format("📌 <b>Ваши указания:</b>\n<i>{regenerate_prompt}</i>"),
                                    False: Const("💬 Ожидание ввода..."),
                                },
                                selector="has_regenerate_prompt"
                            ),
                        ),
                    },
                    selector="is_regenerating_text"
                ),
                sep="",
            ),

            TextInput(
                id="regenerate_prompt_input",
                on_success=self.publication_draft_service.handle_regenerate_text_with_prompt,
            ),

            Button(
                Const("◀️ Назад"),
                id="back_to_edit_menu",
                on_click=lambda c, b, d: d.switch_to(model.PublicationDraftStates.edit_text_menu),
                when="~is_regenerating_text",
            ),

            state=model.PublicationDraftStates.regenerate_text,
            getter=self.publication_draft_getter.get_regenerate_text_data,
            parse_mode="HTML",
        )

    def get_edit_title_window(self) -> Window:
        """
        📝 РЕДАКТИРОВАНИЕ НАЗВАНИЯ
        """
        return Window(
            Multi(
                Const("📝 <b>Изменение названия</b>\n\n"),
                Format("Текущее: <b>{publication_title}</b>\n\n"),
                Case(
                    {
                        True: Const("⚠️ <b>Ошибка:</b> Название не может быть пустым\n\n"),
                        False: Const(""),
                    },
                    selector="has_void_title"
                ),
                Const("✍️ <b>Введите новое название:</b>"),
                sep="",
            ),

            TextInput(
                id="title_input",
                on_success=self.publication_draft_service.handle_edit_title_save,
            ),

            Button(
                Const("◀️ Назад"),
                id="back_to_edit_menu",
                on_click=lambda c, b, d: d.switch_to(model.PublicationDraftStates.edit_text_menu),
            ),

            state=model.PublicationDraftStates.edit_title,
            getter=self.publication_draft_getter.get_edit_title_data,
            parse_mode="HTML",
        )

    def get_edit_description_window(self) -> Window:
        """
        📝 РЕДАКТИРОВАНИЕ ОПИСАНИЯ (если нужно отдельно от контента)
        """
        return Window(
            Multi(
                Const("📝 <b>Изменение описания</b>\n\n"),
                Format("Текущее: <i>{publication_description}</i>\n\n"),
                Const("✍️ <b>Введите новое описание:</b>"),
                sep="",
            ),

            TextInput(
                id="description_input",
                on_success=self.publication_draft_service.handle_edit_description_save,
            ),

            Button(
                Const("◀️ Назад"),
                id="back_to_edit_menu",
                on_click=lambda c, b, d: d.switch_to(model.PublicationDraftStates.edit_text_menu),
            ),

            state=model.PublicationDraftStates.edit_description,
            getter=self.publication_draft_getter.get_edit_description_data,
            parse_mode="HTML",
        )

    def get_edit_content_window(self) -> Window:
        """
        📄 РЕДАКТИРОВАНИЕ ОСНОВНОГО ТЕКСТА
        """
        return Window(
            Multi(
                Const("📄 <b>Изменение текста публикации</b>\n\n"),
                Case(
                    {
                        True: Const("⚠️ <b>Ошибка:</b> Текст не может быть пустым\n\n"),
                        False: Const(""),
                    },
                    selector="has_void_content"
                ),
                Const("✍️ <b>Введите новый текст:</b>\n"),
                Const("<i>Текущий текст показан в предыдущем окне</i>"),
                sep="",
            ),

            TextInput(
                id="content_input",
                on_success=self.publication_draft_service.handle_edit_content_save,
            ),

            Button(
                Const("◀️ Назад"),
                id="back_to_edit_menu",
                on_click=lambda c, b, d: d.switch_to(model.PublicationDraftStates.edit_text_menu),
            ),

            state=model.PublicationDraftStates.edit_content,
            getter=self.publication_draft_getter.get_edit_content_data,
            parse_mode="HTML",
        )




    def get_edit_image_menu_window(self) -> Window:
        """
        🖼️ УПРАВЛЕНИЕ ИЗОБРАЖЕНИЕМ
        """
        return Window(
            Multi(
                Const("🖼 <b>Управление изображением</b>\n\n"),
                Case(
                    {
                        True: Const("✅ <b>Изображение добавлено</b>\n\n"),
                        False: Const("❌ <b>Изображение отсутствует</b>\n\n"),
                    },
                    selector="has_image"
                ),
                Const("📌 <b>Выберите действие:</b>"),
                sep="",
            ),

            Column(
                Button(
                    Const("🎨 Сгенерировать с промптом"),
                    id="generate_image_prompt",
                    on_click=lambda c, b, d: d.switch_to(model.PublicationDraftStates.generate_image),
                ),
                Button(
                    Const("📤 Загрузить своё"),
                    id="upload_image",
                    on_click=lambda c, b, d: d.switch_to(model.PublicationDraftStates.upload_image),
                ),
                Button(
                    Const("🗑 Удалить изображение"),
                    id="remove_image",
                    on_click=self.publication_draft_service.handle_delete_publication,  # Используем существующий метод
                    when="has_image",
                ),
            ),

            Button(
                Const("◀️ Назад"),
                id="back_to_edit_menu",
                on_click=lambda c, b, d: d.switch_to(model.PublicationDraftStates.edit_text_menu),
            ),

            state=model.PublicationDraftStates.edit_image_menu,
            getter=self.publication_draft_getter.get_edit_image_menu_data,
            parse_mode="HTML",
        )

    def get_generate_image_window(self) -> Window:
        """
        🎨 ГЕНЕРАЦИЯ ИЗОБРАЖЕНИЯ с промптом
        """
        return Window(
            Multi(
                Const("🎨 <b>Генерация изображения</b>\n\n"),
                Const("💡 <b>Опишите желаемое изображение:</b>\n"),
                Const("<i>Например: минималистичная иллюстрация в синих тонах</i>\n\n"),
                Case(
                    {
                        True: Format("📌 <b>Ваше описание:</b>\n<i>{image_prompt}</i>"),
                        False: Const("💬 Ожидание ввода..."),
                    },
                    selector="has_image_prompt"
                ),
                sep="",
            ),

            TextInput(
                id="image_prompt_input",
                on_success=self.publication_draft_service.handle_edit_image_menu_save,  # Используем существующий метод
            ),

            Button(
                Const("◀️ Назад"),
                id="back_to_image_menu",
                on_click=lambda c, b, d: d.switch_to(model.PublicationDraftStates.edit_image_menu),
            ),

            state=model.PublicationDraftStates.generate_image,
            getter=self.publication_draft_getter.get_generate_image_data,
            parse_mode="HTML",
        )

    def get_upload_image_window(self) -> Window:
        """
        📤 ЗАГРУЗКА СВОЕГО ИЗОБРАЖЕНИЯ
        """
        return Window(
            Multi(
                Const("📤 <b>Загрузка изображения</b>\n\n"),
                Const("📸 <b>Отправьте изображение:</b>\n"),
                Const("<i>Поддерживаются форматы: JPG, PNG, GIF</i>\n"),
                Const("<i>Максимальный размер: 10 МБ</i>"),
                sep="",
            ),

            MessageInput(
                func=self.publication_draft_service.handle_edit_image_menu_save,  # Используем существующий метод
            ),

            Button(
                Const("◀️ Назад"),
                id="back_to_image_menu",
                on_click=lambda c, b, d: d.switch_to(model.PublicationDraftStates.edit_image_menu),
            ),

            state=model.PublicationDraftStates.upload_image,
            getter=self.publication_draft_getter.get_upload_image_data,
            parse_mode="HTML",
        )

    def get_edit_tags_window(self) -> Window:
        """
        🏷️ РЕДАКТИРОВАНИЕ ТЕГОВ
        """
        return Window(
            Multi(
                Const("🏷 <b>Изменение тегов</b>\n\n"),
                Format("Текущие теги: <b>{publication_tags}</b>\n\n"),
                Const("✍️ <b>Введите теги через запятую:</b>\n"),
                Const("<i>Например: маркетинг, продажи, SMM</i>"),
                sep="",
            ),

            TextInput(
                id="tags_input",
                on_success=self.publication_draft_service.handle_edit_tags_save,
            ),

            Button(
                Const("◀️ Назад"),
                id="back_to_edit_menu",
                on_click=lambda c, b, d: d.switch_to(model.PublicationDraftStates.edit_text_menu),
            ),

            state=model.PublicationDraftStates.edit_tags,
            getter=self.publication_draft_getter.get_edit_tags_data,
            parse_mode="HTML",
        )

    def get_social_network_select_window(self) -> Window:
        """
        🌐 ВЫБОР СОЦСЕТЕЙ для публикации
        """
        return Window(
            Multi(
                Const("🌐 <b>Выбор социальных сетей</b>\n\n"),
                Const("📋 <b>Доступные социальные сети:</b>\n\n"),
                Const("✅ <b>Выберите, где опубликовать:</b>"),
                sep="",
            ),

            Column(
                Checkbox(
                    Const("✅ Telegram"),
                    Const("❌ Telegram"),
                    id="telegram_checkbox",
                    default=False,
                    on_state_changed=self.publication_draft_service.handle_toggle_social_network,
                    when="telegram_connected",
                ),
                Checkbox(
                    Const("✅ VKontakte"),
                    Const("❌ VKontakte"),
                    id="vkontakte_checkbox",
                    default=False,
                    on_state_changed=self.publication_draft_service.handle_toggle_social_network,
                    when="vkontakte_connected",
                ),
            ),

            Row(
                Button(
                    Const("🚀 Опубликовать"),
                    id="publish_with_networks",
                    on_click=self.publication_draft_service.handle_publish_with_selected_networks_publication,
                ),
                Button(
                    Const("◀️ Назад"),
                    id="back_to_preview",
                    on_click=lambda c, b, d: d.switch_to(model.PublicationDraftStates.edit_preview),
                ),
            ),

            state=model.PublicationDraftStates.social_network_select,
            getter=self.publication_draft_getter.get_social_network_select_data,
            parse_mode="HTML",
        )