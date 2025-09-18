from abc import abstractmethod
from typing import Protocol, Any
from aiogram_dialog import DialogManager, Dialog, Window
from aiogram.types import CallbackQuery, Message
from aiogram_dialog.widgets.input import MessageInput

from internal import model


class IPublicationDraftContentDialog(Protocol):
    """Интерфейс для диалога управления черновиками публикаций"""
    
    @abstractmethod
    def get_dialog(self) -> Dialog:
        """Получить основной диалог"""
        pass
    
    @abstractmethod
    def get_draft_list_window(self) -> Window:
        """Окно со списком черновиков (слайдер как в управлении сотрудниками)"""
        pass

    # Окна редактирования
    @abstractmethod
    def get_edit_preview_window(self) -> Window:
        """Окно предпросмотра черновика с возможностью редактирования"""
        pass

    @abstractmethod
    def get_edit_text_menu_window(self) -> Window:
        """Меню редактирования текста черновика"""
        pass

    @abstractmethod
    def get_regenerate_text_window(self) -> Window:
        """Окно перегенерации текста с AI"""
        pass

    @abstractmethod
    def get_edit_title_window(self) -> Window:
        """Окно редактирования заголовка"""
        pass

    @abstractmethod
    def get_edit_tags_window(self) -> Window:
        """Окно редактирования тегов"""
        pass

    @abstractmethod
    def get_edit_content_window(self) -> Window:
        """Окно редактирования содержания"""
        pass

    @abstractmethod
    def get_edit_image_menu_window(self) -> Window:
        """Меню управления изображением"""
        pass

    @abstractmethod
    def get_generate_image_window(self) -> Window:
        """Окно генерации изображения"""
        pass

    @abstractmethod
    def get_upload_image_window(self) -> Window:
        """Окно загрузки изображения"""
        pass


class IPublicationDraftContentDialogService(Protocol):
    """Интерфейс сервиса для управления черновиками публикаций"""
    
    # Геттеры данных для основных окон
    @abstractmethod
    async def get_draft_list_data(
            self,
            dialog_manager: DialogManager,
    ) -> dict:
        """Получить данные для списка черновиков"""
        pass

    @abstractmethod
    async def get_edit_preview_data(
            self,
            dialog_manager: DialogManager,
    ) -> dict:
        """Получить данные для предпросмотра черновика"""
        pass

    # Обработчики для списка черновиков
    @abstractmethod
    async def handle_navigate_draft(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        """Навигация между черновиками"""
        pass

    # Основные действия с черновиками (из требований Jira)
    @abstractmethod
    async def handle_send_to_moderation(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        """Отправить на модерацию (как в генерации публикации)"""
        pass

    @abstractmethod
    async def handle_publish_now(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        """Опубликовать сейчас (как в генерации публикации)"""
        pass

    @abstractmethod
    async def handle_delete_draft(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        """Удалить черновик"""
        pass

    # Обработчики для перегенерации текста
    @abstractmethod
    async def handle_regenerate_text(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        """Перегенерировать текст с AI"""
        pass

    @abstractmethod
    async def handle_regenerate_text_with_prompt(
            self,
            message: Message,
            widget: Any,
            dialog_manager: DialogManager,
            prompt: str
    ) -> None:
        """Перегенерировать текст с пользовательским промптом"""
        pass

    @abstractmethod
    async def get_regenerate_data(
            self,
            dialog_manager: DialogManager,
    ) -> dict:
        """Получить данные для окна перегенерации"""
        pass

    # Обработчики редактирования текста
    @abstractmethod
    async def handle_edit_title_save(
            self,
            message: Message,
            widget: Any,
            dialog_manager: DialogManager,
            text: str
    ) -> None:
        """Сохранить отредактированный заголовок"""
        pass

    @abstractmethod
    async def handle_edit_tags_save(
            self,
            message: Message,
            widget: Any,
            dialog_manager: DialogManager,
            text: str
    ) -> None:
        """Сохранить отредактированные теги"""
        pass

    @abstractmethod
    async def handle_edit_content_save(
            self,
            message: Message,
            widget: Any,
            dialog_manager: DialogManager,
            text: str
    ) -> None:
        """Сохранить отредактированное содержание"""
        pass

    # Обработчики для изображений
    @abstractmethod
    async def handle_generate_new_image(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        """Генерировать новое изображение"""
        pass

    @abstractmethod
    async def handle_generate_image_with_prompt(
            self,
            message: Message,
            widget: Any,
            dialog_manager: DialogManager,
            prompt: str
    ) -> None:
        """Генерировать изображение с промптом"""
        pass

    @abstractmethod
    async def handle_image_upload(
            self,
            message: Message,
            widget: MessageInput,
            dialog_manager: DialogManager
    ) -> None:
        """Обработчик загрузки изображения"""
        pass

    @abstractmethod
    async def handle_remove_image(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        """Удалить изображение"""
        pass

    # Сохранение изменений
    @abstractmethod
    async def handle_save_edits(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        """Сохранить все изменения черновика"""
        pass

    # Навигация
    @abstractmethod
    async def handle_back_to_draft_list(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        """Вернуться к списку черновиков"""
        pass

    @abstractmethod
    async def handle_back_to_content_menu(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        """Вернуться в контент меню"""
        pass

    # Дополнительные геттеры для окон редактирования
    @abstractmethod
    async def get_edit_title_data(
            self,
            dialog_manager: DialogManager,
    ) -> dict:
        """Получить данные для редактирования заголовка"""
        pass

    @abstractmethod
    async def get_edit_tags_data(
            self,
            dialog_manager: DialogManager,
    ) -> dict:
        """Получить данные для редактирования тегов"""
        pass

    @abstractmethod
    async def get_edit_content_data(
            self,
            dialog_manager: DialogManager,
    ) -> dict:
        """Получить данные для редактирования содержания"""
        pass

    @abstractmethod
    async def get_image_menu_data(
            self,
            dialog_manager: DialogManager,
    ) -> dict:
        """Получить данные для меню изображений"""
        pass

    @abstractmethod
    async def get_image_prompt_data(
            self,
            dialog_manager: DialogManager,
    ) -> dict:
        """Получить данные для промпта изображения"""
        pass
