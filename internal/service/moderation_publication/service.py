import asyncio
from datetime import datetime, timezone
from typing import Any

from aiogram_dialog.widgets.input import MessageInput

from aiogram import Bot
from aiogram.types import CallbackQuery, Message, ContentType
from aiogram_dialog import DialogManager, StartMode

from opentelemetry.trace import SpanKind, Status, StatusCode

from internal import interface, model, common


class ModerationPublicationDialogService(interface.IModerationPublicationDialogService):
    def __init__(
            self,
            tel: interface.ITelemetry,
            bot: Bot,
            state_repo: interface.IStateRepo,
            kontur_employee_client: interface.IKonturEmployeeClient,
            kontur_organization_client: interface.IKonturOrganizationClient,
            kontur_publication_client: interface.IKonturPublicationClient,
    ):
        self.tracer = tel.tracer()
        self.logger = tel.logger()
        self.bot = bot
        self.state_repo = state_repo
        self.kontur_employee_client = kontur_employee_client
        self.kontur_organization_client = kontur_organization_client
        self.kontur_publication_client = kontur_publication_client

    async def get_moderation_list_data(
            self,
            dialog_manager: DialogManager,
            **kwargs
    ) -> dict:
        """Получение данных для основного окна - сразу показываем первую публикацию"""
        with self.tracer.start_as_current_span(
                "ModerationPublicationDialogService.get_moderation_list_data",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                state = await self._get_state(dialog_manager)

                # Получаем публикации на модерации для организации
                publications = await self.kontur_publication_client.get_publications_by_organization(
                    organization_id=state.organization_id
                )

                # Фильтруем только те, что на модерации
                moderation_publications = [
                    pub for pub in publications
                    if pub.moderation_status == "moderation"
                ]

                if not moderation_publications:
                    return {
                        "has_publications": False,
                        "publications_count": 0,
                        "period_text": "",
                    }

                # Сохраняем список для навигации
                dialog_manager.dialog_data["moderation_list"] = moderation_publications

                # Устанавливаем текущий индекс (0 если не был установлен)
                if "current_index" not in dialog_manager.dialog_data:
                    dialog_manager.dialog_data["current_index"] = 0

                current_index = dialog_manager.dialog_data["current_index"]
                current_pub = moderation_publications[current_index]

                # Получаем информацию об авторе
                author = await self.kontur_employee_client.get_employee_by_account_id(
                    current_pub.creator_id
                )

                # Получаем категорию
                category = await self.kontur_publication_client.get_category_by_id(
                    current_pub.category_id
                )

                # Форматируем теги
                tags = current_pub.tags or []
                tags_text = ", ".join(tags) if tags else ""

                # Рассчитываем время ожидания
                waiting_time = self._calculate_waiting_time_text(current_pub.created_at)

                # Подготавливаем медиа для изображения
                preview_image_media = None
                if current_pub.image_fid:
                    from aiogram_dialog.api.entities import MediaAttachment
                    preview_image_media = MediaAttachment(
                        url=f"https://kontur-media.ru/api/publication/{current_pub.id}/image/download",
                        type=ContentType.PHOTO
                    )

                # Форматируем историю изменений
                edit_history = dialog_manager.dialog_data.get("edit_history", [])
                edit_history_text = self._format_edit_history(edit_history)

                # Определяем период
                period_text = self._get_period_text(moderation_publications)

                data = {
                    "has_publications": True,
                    "publications_count": len(moderation_publications),
                    "period_text": period_text,
                    "author_name": author.name,
                    "category_name": category.name,
                    "created_at": self._format_datetime(current_pub.created_at),
                    "has_waiting_time": bool(waiting_time),
                    "waiting_time": waiting_time,
                    "publication_name": current_pub.name,
                    "publication_text": current_pub.text,
                    "has_tags": bool(tags),
                    "publication_tags": tags_text,
                    "has_image": bool(current_pub.image_fid),
                    "preview_image_media": preview_image_media,
                    "has_edit_history": len(edit_history) > 0,
                    "edit_history": edit_history_text,
                    "current_index": current_index + 1,
                    "total_count": len(moderation_publications),
                    "has_prev": current_index > 0,
                    "has_next": current_index < len(moderation_publications) - 1,
                }

                # Сохраняем данные текущей публикации
                dialog_manager.dialog_data["publication_data"] = {
                    "id": current_pub.id,
                    "creator_id": current_pub.creator_id,
                    "name": current_pub.name,
                    "text": current_pub.text,
                    "tags": current_pub.tags or [],
                    "category_id": current_pub.category_id,
                    "image_url": f"https://kontur-media.ru/api/publication/{current_pub.id}/image/download" if current_pub.image_fid else None,
                    "has_image": bool(current_pub.image_fid),
                    "moderation_status": current_pub.moderation_status,
                    "created_at": current_pub.created_at,
                }

                self.logger.info(
                    "Список модерации загружен",
                    {
                        common.TELEGRAM_CHAT_ID_KEY: self._get_chat_id(dialog_manager),
                        "publications_count": len(moderation_publications),
                        "current_index": current_index,
                    }
                )

                span.set_status(Status(StatusCode.OK))
                return data

            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                raise

    async def handle_select_publication(
            self,
            callback: CallbackQuery,
            widget: Any,
            dialog_manager: DialogManager,
            publication_id: str
    ) -> None:
        """Этот метод больше не используется, но оставляем для совместимости"""
        pass

    async def get_publication_review_data(
            self,
            dialog_manager: DialogManager,
            **kwargs
    ) -> dict:
        """Этот метод больше не используется, данные теперь в get_moderation_list_data"""
        return {}

    async def handle_navigate_publication(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        with self.tracer.start_as_current_span(
                "ModerationPublicationDialogService.handle_navigate_publication",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                current_index = dialog_manager.dialog_data.get("current_index", 0)
                moderation_list = dialog_manager.dialog_data.get("moderation_list", [])

                # Определяем направление навигации
                if button.widget_id == "prev_publication":
                    new_index = max(0, current_index - 1)
                else:  # next_publication
                    new_index = min(len(moderation_list) - 1, current_index + 1)

                if new_index == current_index:
                    await callback.answer()
                    return

                # Обновляем индекс
                dialog_manager.dialog_data["current_index"] = new_index

                # Сбрасываем историю изменений для новой публикации
                dialog_manager.dialog_data["has_changes"] = False
                dialog_manager.dialog_data["edit_history"] = []

                self.logger.info(
                    "Навигация по публикациям",
                    {
                        common.TELEGRAM_CHAT_ID_KEY: callback.message.chat.id,
                        "from_index": current_index,
                        "to_index": new_index,
                    }
                )

                await callback.answer()
                span.set_status(Status(StatusCode.OK))

            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                await callback.answer("❌ Ошибка навигации", show_alert=True)
                raise

    async def handle_approve_publication(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        with self.tracer.start_as_current_span(
                "ModerationPublicationDialogService.handle_approve_publication",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                publication_data = dialog_manager.dialog_data["publication_data"]
                publication_id = publication_data["id"]

                # Если были изменения, сохраняем их
                if dialog_manager.dialog_data.get("has_changes"):
                    await self._save_publication_changes(dialog_manager)

                state = await self._get_state(dialog_manager)

                # Одобряем публикацию через API
                await self.kontur_publication_client.moderate_publication(
                    publication_id=publication_id,
                    moderator_id=state.account_id,
                    moderation_status="approved",
                )

                self.logger.info(
                    "Публикация одобрена",
                    {
                        common.TELEGRAM_CHAT_ID_KEY: callback.message.chat.id,
                        "publication_id": publication_id,
                    }
                )

                await callback.answer("✅ Публикация одобрена!", show_alert=True)

                # Удаляем одобренную публикацию из списка
                moderation_list = dialog_manager.dialog_data.get("moderation_list", [])
                current_index = dialog_manager.dialog_data.get("current_index", 0)

                if moderation_list and current_index < len(moderation_list):
                    moderation_list.pop(current_index)

                    # Корректируем индекс если нужно
                    if current_index >= len(moderation_list) and moderation_list:
                        dialog_manager.dialog_data["current_index"] = len(moderation_list) - 1
                    elif not moderation_list:
                        dialog_manager.dialog_data["current_index"] = 0

                # Обновляем экран (останемся в том же состоянии)
                span.set_status(Status(StatusCode.OK))

            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                await callback.answer("❌ Ошибка при одобрении", show_alert=True)
                raise

    async def get_reject_comment_data(
            self,
            dialog_manager: DialogManager,
            **kwargs
    ) -> dict:
        with self.tracer.start_as_current_span(
                "ModerationPublicationDialogService.get_reject_comment_data",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                publication_data = dialog_manager.dialog_data.get("publication_data", {})

                # Получаем информацию об авторе
                author = await self.kontur_employee_client.get_employee_by_account_id(
                    publication_data["creator_id"],
                )

                data = {
                    "publication_name": publication_data["name"],
                    "author_name": author.name,
                    "has_comment": bool(dialog_manager.dialog_data.get("reject_comment")),
                    "reject_comment": dialog_manager.dialog_data.get("reject_comment", ""),
                }

                span.set_status(Status(StatusCode.OK))
                return data

            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                raise

    async def handle_reject_comment_input(
            self,
            message: Message,
            widget: Any,
            dialog_manager: DialogManager,
            comment: str
    ) -> None:
        with self.tracer.start_as_current_span(
                "ModerationPublicationDialogService.handle_reject_comment_input",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                comment = comment.strip()

                if not comment:
                    await message.answer("❌ Комментарий не может быть пустым")
                    return

                if len(comment) < 10:
                    await message.answer("❌ Слишком короткий комментарий. Укажите причину подробнее.")
                    return

                if len(comment) > 500:
                    await message.answer("❌ Слишком длинный комментарий (макс. 500 символов)")
                    return

                dialog_manager.dialog_data["reject_comment"] = comment

                # Удаляем сообщение с комментарием
                await message.delete()

                self.logger.info(
                    "Комментарий отклонения введен",
                    {
                        common.TELEGRAM_CHAT_ID_KEY: message.chat.id,
                        "comment_length": len(comment),
                    }
                )

                span.set_status(Status(StatusCode.OK))

            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                await message.answer("❌ Ошибка при сохранении комментария")
                raise

    async def handle_send_rejection(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        with self.tracer.start_as_current_span(
                "ModerationPublicationDialogService.handle_send_rejection",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                state = await self._get_state(dialog_manager)
                publication_data = dialog_manager.dialog_data["publication_data"]
                publication_id = publication_data["id"]
                reject_comment = dialog_manager.dialog_data.get("reject_comment", "Нет комментария")

                # Отклоняем публикацию через API
                await self.kontur_publication_client.moderate_publication(
                    publication_id=publication_id,
                    moderator_id=state.account_id,
                    moderation_status="rejected",
                    moderation_comment=reject_comment,
                )

                self.logger.info(
                    "Публикация отклонена",
                    {
                        common.TELEGRAM_CHAT_ID_KEY: callback.message.chat.id,
                        "publication_id": publication_id,
                        "reason": reject_comment,
                    }
                )

                await callback.answer("❌ Публикация отклонена", show_alert=True)

                # Удаляем отклоненную публикацию из списка
                moderation_list = dialog_manager.dialog_data.get("moderation_list", [])
                current_index = dialog_manager.dialog_data.get("current_index", 0)

                if moderation_list and current_index < len(moderation_list):
                    moderation_list.pop(current_index)

                    # Корректируем индекс если нужно
                    if current_index >= len(moderation_list) and moderation_list:
                        dialog_manager.dialog_data["current_index"] = len(moderation_list) - 1
                    elif not moderation_list:
                        dialog_manager.dialog_data["current_index"] = 0

                # Возвращаемся к основному окну
                await dialog_manager.switch_to(model.ModerationPublicationStates.moderation_list)

                span.set_status(Status(StatusCode.OK))

            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                await callback.answer("❌ Ошибка при отклонении", show_alert=True)
                raise

    async def get_edit_menu_data(
            self,
            dialog_manager: DialogManager,
            **kwargs
    ) -> dict:
        """Получение данных для меню редактирования"""
        with self.tracer.start_as_current_span(
                "ModerationPublicationDialogService.get_edit_menu_data",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                publication_data = dialog_manager.dialog_data.get("publication_data", {})

                # Получаем информацию об авторе
                author = await self.kontur_employee_client.get_employee_by_account_id(
                    publication_data["creator_id"]
                )

                data = {
                    "publication_name": publication_data["name"],
                    "author_name": author.name,
                    "has_changes": dialog_manager.dialog_data.get("has_changes", False),
                }

                span.set_status(Status(StatusCode.OK))
                return data

            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                raise

    async def handle_edit_title_save(
            self,
            message: Message,
            widget: Any,
            dialog_manager: DialogManager,
            text: str
    ) -> None:
        with self.tracer.start_as_current_span(
                "ModerationPublicationDialogService.handle_edit_title_save",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                new_title = text.strip()

                if not new_title:
                    await message.answer("❌ Название не может быть пустым")
                    return

                if len(new_title) > 200:
                    await message.answer("❌ Слишком длинное название (макс. 200 символов)")
                    return

                old_title = dialog_manager.dialog_data["publication_data"]["name"]

                if old_title != new_title:
                    # Сохраняем изменение
                    dialog_manager.dialog_data["publication_data"]["name"] = new_title
                    dialog_manager.dialog_data["has_changes"] = True

                    # Добавляем в историю изменений
                    self._add_to_edit_history(
                        dialog_manager,
                        "название",
                        old_title,
                        new_title
                    )

                    await message.answer("✅ Название обновлено!")
                else:
                    await message.answer("ℹ️ Название не изменилось")

                await dialog_manager.switch_to(model.ModerationPublicationStates.edit_text_menu)

                span.set_status(Status(StatusCode.OK))

            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                await message.answer("❌ Ошибка при сохранении названия")
                raise

    async def handle_edit_tags_save(
            self,
            message: Message,
            widget: Any,
            dialog_manager: DialogManager,
            text: str
    ) -> None:
        with self.tracer.start_as_current_span(
                "ModerationPublicationDialogService.handle_edit_tags_save",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                tags_raw = text.strip()
                old_tags = dialog_manager.dialog_data["publication_data"].get("tags", [])

                if not tags_raw:
                    new_tags = []
                else:
                    # Парсим теги
                    new_tags = [tag.strip() for tag in tags_raw.split(",")]
                    new_tags = [tag for tag in new_tags if tag]

                    if len(new_tags) > 10:
                        await message.answer("❌ Слишком много тегов (макс. 10)")
                        return

                if set(old_tags) != set(new_tags):
                    # Сохраняем изменение
                    dialog_manager.dialog_data["publication_data"]["tags"] = new_tags
                    dialog_manager.dialog_data["has_changes"] = True

                    # Добавляем в историю изменений
                    self._add_to_edit_history(
                        dialog_manager,
                        "теги",
                        ", ".join(old_tags) if old_tags else "отсутствовали",
                        ", ".join(new_tags) if new_tags else "удалены"
                    )

                    await message.answer(f"✅ Теги обновлены ({len(new_tags)} шт.)")
                else:
                    await message.answer("ℹ️ Теги не изменились")

                await dialog_manager.switch_to(model.ModerationPublicationStates.edit_text_menu)

                span.set_status(Status(StatusCode.OK))

            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                await message.answer("❌ Ошибка при сохранении тегов")
                raise

    async def handle_edit_content_save(
            self,
            message: Message,
            widget: Any,
            dialog_manager: DialogManager,
            text: str
    ) -> None:
        with self.tracer.start_as_current_span(
                "ModerationPublicationDialogService.handle_edit_content_save",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                new_text = text.strip()

                if not new_text:
                    await message.answer("❌ Текст не может быть пустым")
                    return

                if len(new_text) < 50:
                    await message.answer("❌ Слишком короткий текст (мин. 50 символов)")
                    return

                if len(new_text) > 4000:
                    await message.answer("❌ Слишком длинный текст (макс. 4000 символов)")
                    return

                old_text = dialog_manager.dialog_data["publication_data"]["text"]

                if old_text != new_text:
                    # Сохраняем изменение
                    dialog_manager.dialog_data["publication_data"]["text"] = new_text
                    dialog_manager.dialog_data["has_changes"] = True

                    # Добавляем в историю изменений
                    self._add_to_edit_history(
                        dialog_manager,
                        "текст",
                        f"{len(old_text)} символов",
                        f"{len(new_text)} символов"
                    )

                    await message.answer("✅ Текст обновлен!")
                else:
                    await message.answer("ℹ️ Текст не изменился")

                await dialog_manager.switch_to(model.ModerationPublicationStates.edit_text_menu)

                span.set_status(Status(StatusCode.OK))

            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                await message.answer("❌ Ошибка при сохранении текста")
                raise

    async def handle_generate_new_image(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        with self.tracer.start_as_current_span(
                "ModerationPublicationDialogService.handle_generate_new_image",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                await callback.answer()
                loading_message = await callback.message.answer("🔄 Генерирую изображение...")

                publication_data = dialog_manager.dialog_data["publication_data"]
                category_id = publication_data["category_id"]
                publication_text = publication_data["text"]

                # Генерация через API
                image_url = await self.kontur_publication_client.generate_publication_image(
                    category_id=category_id,
                    publication_text=publication_text,
                    text_reference=publication_text[:200],  # Используем начало текста как референс
                    prompt=None
                )

                # Обновляем данные
                dialog_manager.dialog_data["publication_data"]["image_url"] = image_url
                dialog_manager.dialog_data["publication_data"]["has_image"] = True
                dialog_manager.dialog_data["has_changes"] = True

                # Удаляем пользовательское изображение если было
                dialog_manager.dialog_data["publication_data"].pop("custom_image_file_id", None)
                dialog_manager.dialog_data["publication_data"].pop("is_custom_image", None)

                # Добавляем в историю изменений
                self._add_to_edit_history(
                    dialog_manager,
                    "изображение",
                    "отсутствовало" if not publication_data.get("has_image") else "заменено",
                    "сгенерировано новое"
                )

                await loading_message.edit_text("✅ Изображение сгенерировано!")
                await asyncio.sleep(2)
                try:
                    await loading_message.delete()
                except:
                    pass

                await dialog_manager.switch_to(model.ModerationPublicationStates.edit_image_menu)

                span.set_status(Status(StatusCode.OK))

            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                await callback.answer("❌ Ошибка генерации", show_alert=True)
                raise

    async def handle_generate_image_with_prompt(
            self,
            message: Message,
            widget: Any,
            dialog_manager: DialogManager,
            prompt: str
    ) -> None:
        with self.tracer.start_as_current_span(
                "ModerationPublicationDialogService.handle_generate_image_with_prompt",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                if not prompt.strip():
                    await message.answer("❌ Введите описание изображения")
                    return

                loading_message = await message.answer("🔄 Генерирую изображение по вашему описанию...")

                publication_data = dialog_manager.dialog_data["publication_data"]
                category_id = publication_data["category_id"]
                publication_text = publication_data["text"]

                # Генерация с промптом
                image_url = await self.kontur_publication_client.generate_publication_image(
                    category_id=category_id,
                    publication_text=publication_text,
                    text_reference=publication_text[:200],
                    prompt=prompt
                )

                # Обновляем данные
                dialog_manager.dialog_data["publication_data"]["image_url"] = image_url
                dialog_manager.dialog_data["publication_data"]["has_image"] = True
                dialog_manager.dialog_data["has_changes"] = True

                # Удаляем пользовательское изображение если было
                dialog_manager.dialog_data["publication_data"].pop("custom_image_file_id", None)
                dialog_manager.dialog_data["publication_data"].pop("is_custom_image", None)

                # Добавляем в историю изменений
                self._add_to_edit_history(
                    dialog_manager,
                    "изображение",
                    "отсутствовало" if not publication_data.get("has_image") else "заменено",
                    f"сгенерировано с промптом"
                )

                await loading_message.edit_text("✅ Изображение сгенерировано!")
                await asyncio.sleep(2)
                try:
                    await loading_message.delete()
                except:
                    pass

                await dialog_manager.switch_to(model.ModerationPublicationStates.edit_image_menu)

                span.set_status(Status(StatusCode.OK))

            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                await message.answer("❌ Ошибка генерации")
                raise

    async def handle_image_upload(
            self,
            message: Message,
            widget: MessageInput,
            dialog_manager: DialogManager
    ) -> None:
        with self.tracer.start_as_current_span(
                "ModerationPublicationDialogService.handle_image_upload",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                if message.content_type != ContentType.PHOTO:
                    await message.answer("❌ Пожалуйста, отправьте изображение")
                    return

                if message.photo:
                    photo = message.photo[-1]  # Берем наибольшее разрешение

                    # Проверяем размер
                    if hasattr(photo, 'file_size') and photo.file_size:
                        if photo.file_size > 10 * 1024 * 1024:  # 10 МБ
                            await message.answer("❌ Файл слишком большой (макс. 10 МБ)")
                            return

                    await message.answer("📸 Загружаю изображение...")

                    # Сохраняем file_id
                    publication_data = dialog_manager.dialog_data["publication_data"]
                    dialog_manager.dialog_data["publication_data"]["custom_image_file_id"] = photo.file_id
                    dialog_manager.dialog_data["publication_data"]["has_image"] = True
                    dialog_manager.dialog_data["publication_data"]["is_custom_image"] = True
                    dialog_manager.dialog_data["has_changes"] = True

                    # Удаляем URL если был
                    dialog_manager.dialog_data["publication_data"].pop("image_url", None)

                    # Добавляем в историю изменений
                    self._add_to_edit_history(
                        dialog_manager,
                        "изображение",
                        "отсутствовало" if not publication_data.get("has_image") else "заменено",
                        "загружено пользовательское"
                    )

                    self.logger.info(
                        "Изображение загружено для модерации",
                        {
                            common.TELEGRAM_CHAT_ID_KEY: message.chat.id,
                            "file_id": photo.file_id,
                        }
                    )

                    await message.answer("✅ Изображение загружено!")
                    await dialog_manager.switch_to(model.ModerationPublicationStates.edit_image_menu)

                span.set_status(Status(StatusCode.OK))

            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                await message.answer("❌ Ошибка загрузки")
                raise

    async def handle_remove_image(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        with self.tracer.start_as_current_span(
                "ModerationPublicationDialogService.handle_remove_image",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                publication_data = dialog_manager.dialog_data["publication_data"]

                if publication_data.get("has_image"):
                    # Удаляем все данные об изображении
                    dialog_manager.dialog_data["publication_data"]["has_image"] = False
                    dialog_manager.dialog_data["publication_data"].pop("image_url", None)
                    dialog_manager.dialog_data["publication_data"].pop("custom_image_file_id", None)
                    dialog_manager.dialog_data["publication_data"].pop("is_custom_image", None)
                    dialog_manager.dialog_data["has_changes"] = True

                    # Добавляем в историю изменений
                    self._add_to_edit_history(
                        dialog_manager,
                        "изображение",
                        "присутствовало",
                        "удалено"
                    )

                    await callback.answer("✅ Изображение удалено", show_alert=True)
                else:
                    await callback.answer("ℹ️ Изображение отсутствует", show_alert=True)

                await dialog_manager.switch_to(model.ModerationPublicationStates.edit_image_menu)

                span.set_status(Status(StatusCode.OK))

            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                await callback.answer("❌ Ошибка удаления", show_alert=True)
                raise

    async def handle_save_edits(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        with self.tracer.start_as_current_span(
                "ModerationPublicationDialogService.handle_save_edits",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                if not dialog_manager.dialog_data.get("has_changes"):
                    await callback.answer("ℹ️ Нет изменений для сохранения", show_alert=True)
                    return

                await callback.answer()
                loading_message = await callback.message.answer("💾 Сохраняю изменения...")

                # Сохраняем изменения
                await self._save_publication_changes(dialog_manager)

                # Сбрасываем флаг изменений
                dialog_manager.dialog_data["has_changes"] = False

                await loading_message.edit_text("✅ Изменения сохранены!")
                await asyncio.sleep(2)
                try:
                    await loading_message.delete()
                except:
                    pass

                await dialog_manager.switch_to(model.ModerationPublicationStates.moderation_list)

                span.set_status(Status(StatusCode.OK))

            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                await callback.answer("❌ Ошибка сохранения", show_alert=True)
                raise

    async def handle_back_to_content_menu(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        with self.tracer.start_as_current_span(
                "ModerationPublicationDialogService.handle_back_to_content_menu",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                await dialog_manager.start(
                    model.ContentMenuStates.content_menu,
                    mode=StartMode.RESET_STACK
                )

                span.set_status(Status(StatusCode.OK))

            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                raise

    async def get_edit_title_data(
            self,
            dialog_manager: DialogManager,
            **kwargs
    ) -> dict:
        """Данные для окна редактирования названия"""
        publication_data = dialog_manager.dialog_data.get("publication_data", {})
        return {
            "current_title": publication_data.get("name", ""),
        }

    async def get_edit_tags_data(
            self,
            dialog_manager: DialogManager,
            **kwargs
    ) -> dict:
        """Данные для окна редактирования тегов"""
        publication_data = dialog_manager.dialog_data.get("publication_data", {})
        tags = publication_data.get("tags", [])
        return {
            "has_tags": bool(tags),
            "current_tags": ", ".join(tags) if tags else "",
        }

    async def get_edit_content_data(
            self,
            dialog_manager: DialogManager,
            **kwargs
    ) -> dict:
        """Данные для окна редактирования текста"""
        publication_data = dialog_manager.dialog_data.get("publication_data", {})
        text = publication_data.get("text", "")
        return {
            "current_text_length": len(text),
        }

    async def get_image_menu_data(
            self,
            dialog_manager: DialogManager,
            **kwargs
    ) -> dict:
        """Данные для меню управления изображением"""
        publication_data = dialog_manager.dialog_data.get("publication_data", {})
        return {
            "has_image": publication_data.get("has_image", False),
            "is_custom_image": publication_data.get("is_custom_image", False),
        }

    async def get_image_prompt_data(
            self,
            dialog_manager: DialogManager,
            **kwargs
    ) -> dict:
        """Данные для окна генерации с промптом"""
        return {
            "has_image_prompt": bool(dialog_manager.dialog_data.get("image_prompt")),
            "image_prompt": dialog_manager.dialog_data.get("image_prompt", ""),
        }

    # Вспомогательные методы

    async def _save_publication_changes(self, dialog_manager: DialogManager) -> None:
        """Сохранение изменений публикации через API"""
        publication_data = dialog_manager.dialog_data["publication_data"]
        publication_id = publication_data["id"]

        # Подготавливаем изображение если есть
        image_url = publication_data.get("image_url")
        image_content = None
        image_filename = None

        # Если есть пользовательское изображение
        if publication_data.get("custom_image_file_id"):
            file_id = publication_data["custom_image_file_id"]
            file = await self.bot.get_file(file_id)
            file_data = await self.bot.download_file(file.file_path)
            image_content = file_data.read()
            image_filename = f"moderated_image_{file_id[:8]}.jpg"

        # Обновляем публикацию через API
        await self.kontur_publication_client.change_publication(
            publication_id=publication_id,
            name=publication_data["name"],
            text=publication_data["text"],
            tags=publication_data.get("tags", []),
            image_url=image_url,
            image_content=image_content,
            image_filename=image_filename,
        )

        self.logger.info(
            "Изменения публикации сохранены",
            {
                "publication_id": publication_id,
                "changes_count": len(dialog_manager.dialog_data.get("edit_history", [])),
            }
        )

    def _add_to_edit_history(
            self,
            dialog_manager: DialogManager,
            field: str,
            old_value: str,
            new_value: str
    ) -> None:
        """Добавление записи в историю изменений"""
        if "edit_history" not in dialog_manager.dialog_data:
            dialog_manager.dialog_data["edit_history"] = []

        dialog_manager.dialog_data["edit_history"].append({
            "field": field,
            "old": old_value,
            "new": new_value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def _format_edit_history(self, history: list) -> str:
        """Форматирование истории изменений для отображения"""
        if not history:
            return ""

        lines = []
        for item in history:
            lines.append(f"• {item['field']}: {item['old']} → {item['new']}")

        return "\n".join(lines)

    def _get_status_emoji(self, status: str) -> str:
        """Получение эмодзи для статуса"""
        status_map = {
            "moderation": "🔍",
            "approved": "✅",
            "rejected": "❌",
            "published": "🚀",
            "draft": "📝",
        }
        return status_map.get(status, "📄")

    def _format_datetime(self, dt: str) -> str:
        """Форматирование даты и времени"""
        try:
            if isinstance(dt, str):
                dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))

            # Форматируем в читаемый вид
            return dt.strftime("%d.%m.%Y %H:%M")
        except:
            return dt

    def _calculate_waiting_hours(self, created_at: str) -> int:
        """Расчет количества часов ожидания"""
        try:
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))

            now = datetime.now(timezone.utc)
            delta = now - created_at
            return int(delta.total_seconds() / 3600)
        except:
            return 0

    def _calculate_waiting_time_text(self, created_at: str) -> str:
        """Расчет и форматирование времени ожидания"""
        hours = self._calculate_waiting_hours(created_at)

        if hours == 0:
            return "менее часа"
        elif hours == 1:
            return "1 час"
        elif hours < 24:
            return f"{hours} часов"
        else:
            days = hours // 24
            if days == 1:
                return "1 день"
            else:
                return f"{days} дней"

    def _get_period_text(self, publications: list) -> str:
        """Определение периода публикаций"""
        if not publications:
            return "Нет данных"

        # Находим самую старую и новую публикацию
        dates = []
        for pub in publications:
            if hasattr(pub, 'created_at') and pub.created_at:
                dates.append(pub.created_at)

        if not dates:
            return "Сегодня"

        # Простое определение периода на основе самой старой публикации
        oldest_date = min(dates)
        waiting_hours = self._calculate_waiting_hours(oldest_date)

        if waiting_hours < 24:
            return "За сегодня"
        elif waiting_hours < 48:
            return "За последние 2 дня"
        elif waiting_hours < 168:  # неделя
            return "За неделю"
        else:
            return "За месяц"

    def _truncate_text(self, text: str, max_length: int) -> str:
        """Обрезка текста с многоточием"""
        if len(text) <= max_length:
            return text
        return text[:max_length - 3] + "..."

    async def _get_state(self, dialog_manager: DialogManager) -> model.UserState:
        """Получение состояния пользователя"""
        chat_id = self._get_chat_id(dialog_manager)
        return await self._get_state_by_chat_id(chat_id)

    async def _get_state_by_chat_id(self, chat_id: int) -> model.UserState:
        """Получение состояния по chat_id"""
        state = await self.state_repo.state_by_id(chat_id)
        if not state:
            raise ValueError(f"State not found for chat_id: {chat_id}")
        return state[0]

    def _get_chat_id(self, dialog_manager: DialogManager) -> int:
        """Получение chat_id из dialog_manager"""
        if hasattr(dialog_manager.event, 'message') and dialog_manager.event.message:
            return dialog_manager.event.message.chat.id
        elif hasattr(dialog_manager.event, 'chat'):
            return dialog_manager.event.chat.id
        else:
            raise ValueError("Cannot extract chat_id from dialog_manager")