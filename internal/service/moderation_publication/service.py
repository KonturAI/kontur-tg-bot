import asyncio
import time
from datetime import datetime, timezone
from typing import Any

from aiogram.enums import ParseMode
from aiogram_dialog.api.entities import MediaId, MediaAttachment
from aiogram_dialog.widgets.input import MessageInput

from aiogram import Bot
from aiogram.types import CallbackQuery, Message, ContentType
from aiogram_dialog import DialogManager, StartMode
from aiogram_dialog.widgets.kbd import ManagedCheckbox

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
            kontur_content_client: interface.IKonturContentClient,
            kontur_domain: str
    ):
        self.tracer = tel.tracer()
        self.logger = tel.logger()
        self.bot = bot
        self.state_repo = state_repo
        self.kontur_employee_client = kontur_employee_client
        self.kontur_organization_client = kontur_organization_client
        self.kontur_content_client = kontur_content_client
        self.kontur_domain = kontur_domain

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
                publications = await self.kontur_content_client.get_publications_by_organization(
                    organization_id=state.organization_id
                )

                # Фильтруем только те, что на модерации
                moderation_publications = [
                    pub.to_dict() for pub in publications
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
                current_pub = model.Publication(**moderation_publications[current_index])

                # Получаем информацию об авторе
                author = await self.kontur_employee_client.get_employee_by_account_id(
                    current_pub.creator_id
                )

                # Получаем категорию
                category = await self.kontur_content_client.get_category_by_id(
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
                    cache_buster = int(time.time())
                    image_url = f"https://kontur-media.ru/api/content/publication/{current_pub.id}/image/download?v={cache_buster}"

                    preview_image_media = MediaAttachment(
                        url=image_url,
                        type=ContentType.PHOTO
                    )

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
                    "current_index": current_index + 1,
                    "total_count": len(moderation_publications),
                    "has_prev": current_index > 0,
                    "has_next": current_index < len(moderation_publications) - 1,
                }

                # Сохраняем данные текущей публикации для редактирования
                dialog_manager.dialog_data["original_publication"] = {
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

                # Копируем в рабочую версию, если ее еще нет
                if "working_publication" not in dialog_manager.dialog_data:
                    dialog_manager.dialog_data["working_publication"] = dict(
                        dialog_manager.dialog_data["original_publication"])

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

                # Сбрасываем рабочие данные для новой публикации
                dialog_manager.dialog_data.pop("working_publication", None)

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

    async def handle_publish_publication(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        with self.tracer.start_as_current_span(
                "ModerationPublicationDialogService.handle_publish_publication",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                # Если есть несохраненные изменения, сохраняем их перед одобрением
                if self._has_changes(dialog_manager):
                    await self._save_publication_changes(dialog_manager)

                original_pub = dialog_manager.dialog_data["original_publication"]
                publication_id = original_pub["id"]
                state = await self._get_state(dialog_manager)

                # Одобряем публикацию через API
                await self.kontur_content_client.moderate_publication(
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

                    # Сбрасываем рабочие данные
                    dialog_manager.dialog_data.pop("working_publication", None)

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
                original_pub = dialog_manager.dialog_data.get("original_publication", {})

                # Получаем информацию об авторе
                author = await self.kontur_employee_client.get_employee_by_account_id(
                    original_pub["creator_id"],
                )

                data = {
                    "publication_name": original_pub["name"],
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
                original_pub = dialog_manager.dialog_data["original_publication"]
                publication_id = original_pub["id"]
                reject_comment = dialog_manager.dialog_data.get("reject_comment", "Нет комментария")

                # Отклоняем публикацию через API
                await self.kontur_content_client.moderate_publication(
                    publication_id=publication_id,
                    moderator_id=state.account_id,
                    moderation_status="rejected",
                    moderation_comment=reject_comment,
                )

                await self.bot.send_message(
                    chat_id=original_pub["creator_id"],
                    text=f"Ваша публикация: <b>{original_pub["name"]}</b> была отклонена с комментарием:\n<b>{reject_comment}</b>",
                    parse_mode=ParseMode.HTML,

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

                    # Сбрасываем рабочие данные
                    dialog_manager.dialog_data.pop("working_publication", None)

                # Возвращаемся к основному окну
                await dialog_manager.switch_to(model.ModerationPublicationStates.moderation_list)

                span.set_status(Status(StatusCode.OK))

            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                await callback.answer("❌ Ошибка при отклонении", show_alert=True)
                raise

    async def get_edit_preview_data(
            self,
            dialog_manager: DialogManager,
            **kwargs
    ) -> dict:
        """Получение данных для окна редактирования с превью"""
        with self.tracer.start_as_current_span(
                "ModerationPublicationDialogService.get_edit_preview_data",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                # Инициализируем рабочую версию если ее нет
                if "working_publication" not in dialog_manager.dialog_data:
                    dialog_manager.dialog_data["working_publication"] = dict(
                        dialog_manager.dialog_data["original_publication"]
                    )

                working_pub = dialog_manager.dialog_data["working_publication"]
                original_pub = dialog_manager.dialog_data["original_publication"]

                # Получаем информацию об авторе
                author = await self.kontur_employee_client.get_employee_by_account_id(
                    working_pub["creator_id"]
                )

                # Получаем категорию
                category = await self.kontur_content_client.get_category_by_id(
                    working_pub["category_id"]
                )

                # Форматируем теги
                tags = working_pub.get("tags", [])
                tags_text = ", ".join(tags) if tags else ""

                # Подготавливаем медиа для изображения
                preview_image_media = None
                if working_pub.get("has_image"):
                    if working_pub.get("custom_image_file_id"):
                        preview_image_media = MediaAttachment(
                            file_id=MediaId(working_pub["custom_image_file_id"]),
                            type=ContentType.PHOTO
                        )
                    elif working_pub.get("image_url"):
                        preview_image_media = MediaAttachment(
                            url=working_pub["image_url"],
                            type=ContentType.PHOTO
                        )

                data = {
                    "author_name": author.name,
                    "category_name": category.name,
                    "created_at": self._format_datetime(original_pub["created_at"]),
                    "publication_name": working_pub["name"],
                    "publication_text": working_pub["text"],
                    "has_tags": bool(tags),
                    "publication_tags": tags_text,
                    "has_image": working_pub.get("has_image", False),
                    "preview_image_media": preview_image_media,
                    "has_changes": self._has_changes(dialog_manager),
                }

                span.set_status(Status(StatusCode.OK))
                return data

            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                raise

    async def handle_regenerate_text(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        with self.tracer.start_as_current_span(
                "ModerationPublicationDialogService.handle_regenerate_text",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                await callback.answer()
                loading_message = await callback.message.answer("🔄 Перегенерирую текст, это может занять время...")

                working_pub = dialog_manager.dialog_data["working_publication"]

                # Перегенерация через API
                regenerated_data = await self.kontur_content_client.regenerate_publication_text(
                    category_id=working_pub["category_id"],
                    publication_text=working_pub["text"],
                    prompt=None
                )

                # Обновляем данные
                dialog_manager.dialog_data["working_publication"]["name"] = regenerated_data["name"]
                dialog_manager.dialog_data["working_publication"]["text"] = regenerated_data["text"]
                dialog_manager.dialog_data["working_publication"]["tags"] = regenerated_data["tags"]


                await loading_message.edit_text("✅ Пост успешно сгенерирован!")
                await asyncio.sleep(3)
                try:
                    await loading_message.delete()
                except:
                    pass

                await dialog_manager.switch_to(model.ModerationPublicationStates.edit_preview)

                span.set_status(Status(StatusCode.OK))
            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                await callback.answer("❌ Ошибка при перегенерации", show_alert=True)
                raise

    async def handle_regenerate_text_with_prompt(
            self,
            message: Message,
            widget: Any,
            dialog_manager: DialogManager,
            prompt: str
    ) -> None:
        with self.tracer.start_as_current_span(
                "ModerationPublicationDialogService.handle_regenerate_text",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                loading_message = await message.answer("🔄 Перегенерирую с учетом ваших пожеланий...")

                working_pub = dialog_manager.dialog_data["working_publication"]

                # Перегенерация через API
                regenerated_data = await self.kontur_content_client.regenerate_publication_text(
                    category_id=working_pub["category_id"],
                    publication_text=working_pub["text"],
                    prompt=prompt
                )

                # Обновляем данные
                dialog_manager.dialog_data["working_publication"]["name"] = regenerated_data["name"]
                dialog_manager.dialog_data["working_publication"]["text"] = regenerated_data["text"]
                dialog_manager.dialog_data["working_publication"]["tags"] = regenerated_data["tags"]
                dialog_manager.dialog_data["regenerate_prompt"] = prompt
                dialog_manager.dialog_data["has_regenerate_prompt"] = True

                await loading_message.edit_text("✅ Пост успешно сгенерирован!")
                await asyncio.sleep(3)
                try:
                    await loading_message.delete()
                except:
                    pass

                await dialog_manager.switch_to(model.ModerationPublicationStates.edit_preview)

                span.set_status(Status(StatusCode.OK))
            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                raise

    async def get_regenerate_data(
            self,
            dialog_manager: DialogManager,
            **kwargs
    ) -> dict:
        return {"regenerate_prompt": dialog_manager.dialog_data.get("regenerate_prompt", "")}

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

                # Обновляем рабочую версию
                dialog_manager.dialog_data["working_publication"]["name"] = new_title

                await message.answer("✅ Название обновлено!")
                await dialog_manager.switch_to(model.ModerationPublicationStates.edit_preview)

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

                if not tags_raw:
                    new_tags = []
                else:
                    # Парсим теги
                    new_tags = [tag.strip() for tag in tags_raw.split(",")]
                    new_tags = [tag for tag in new_tags if tag]

                    if len(new_tags) > 10:
                        await message.answer("❌ Слишком много тегов (макс. 10)")
                        return

                # Обновляем рабочую версию
                dialog_manager.dialog_data["working_publication"]["tags"] = new_tags

                await message.answer(f"✅ Теги обновлены ({len(new_tags)} шт.)")
                await dialog_manager.switch_to(model.ModerationPublicationStates.edit_preview)

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

                # Обновляем рабочую версию
                dialog_manager.dialog_data["working_publication"]["text"] = new_text

                await message.answer("✅ Текст обновлен!")
                await dialog_manager.switch_to(model.ModerationPublicationStates.edit_preview)

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

                working_pub = dialog_manager.dialog_data["working_publication"]
                category_id = working_pub["category_id"]
                publication_text = working_pub["text"]

                # Генерация через API
                image_url = await self.kontur_content_client.generate_publication_image(
                    category_id=category_id,
                    publication_text=publication_text,
                    text_reference=publication_text[:200],
                    prompt=None
                )

                # Обновляем рабочую версию
                dialog_manager.dialog_data["working_publication"]["image_url"] = image_url
                dialog_manager.dialog_data["working_publication"]["has_image"] = True
                # Удаляем пользовательское изображение если было
                dialog_manager.dialog_data["working_publication"].pop("custom_image_file_id", None)
                dialog_manager.dialog_data["working_publication"].pop("is_custom_image", None)

                await loading_message.edit_text("✅ Изображение сгенерировано!")
                await asyncio.sleep(2)
                try:
                    await loading_message.delete()
                except:
                    pass

                await dialog_manager.switch_to(model.ModerationPublicationStates.edit_preview)

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

                working_pub = dialog_manager.dialog_data["working_publication"]
                category_id = working_pub["category_id"]
                publication_text = working_pub["text"]

                # Генерация с промптом
                image_url = await self.kontur_content_client.generate_publication_image(
                    category_id=category_id,
                    publication_text=publication_text,
                    text_reference=publication_text[:200],
                    prompt=prompt
                )

                # Обновляем рабочую версию
                dialog_manager.dialog_data["working_publication"]["image_url"] = image_url
                dialog_manager.dialog_data["working_publication"]["has_image"] = True
                # Удаляем пользовательское изображение если было
                dialog_manager.dialog_data["working_publication"].pop("custom_image_file_id", None)
                dialog_manager.dialog_data["working_publication"].pop("is_custom_image", None)

                await loading_message.edit_text("✅ Изображение сгенерировано!")
                await asyncio.sleep(2)
                try:
                    await loading_message.delete()
                except:
                    pass

                await dialog_manager.switch_to(model.ModerationPublicationStates.edit_preview)

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

                    # Обновляем рабочую версию
                    dialog_manager.dialog_data["working_publication"]["custom_image_file_id"] = photo.file_id
                    dialog_manager.dialog_data["working_publication"]["has_image"] = True
                    dialog_manager.dialog_data["working_publication"]["is_custom_image"] = True
                    # Удаляем URL если был
                    dialog_manager.dialog_data["working_publication"].pop("image_url", None)

                    self.logger.info(
                        "Изображение загружено для модерации",
                        {
                            common.TELEGRAM_CHAT_ID_KEY: message.chat.id,
                            "file_id": photo.file_id,
                        }
                    )

                    await message.answer("✅ Изображение загружено!")
                    await dialog_manager.switch_to(model.ModerationPublicationStates.edit_preview)

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
                working_pub = dialog_manager.dialog_data["working_publication"]

                if working_pub.get("has_image"):
                    # Удаляем все данные об изображении из рабочей версии
                    dialog_manager.dialog_data["working_publication"]["has_image"] = False
                    dialog_manager.dialog_data["working_publication"].pop("image_url", None)
                    dialog_manager.dialog_data["working_publication"].pop("custom_image_file_id", None)
                    dialog_manager.dialog_data["working_publication"].pop("is_custom_image", None)

                    await callback.answer("✅ Изображение удалено", show_alert=True)
                else:
                    await callback.answer("ℹ️ Изображение отсутствует", show_alert=True)

                await dialog_manager.switch_to(model.ModerationPublicationStates.edit_preview)

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
                if not self._has_changes(dialog_manager):
                    await callback.answer("ℹ️ Нет изменений для сохранения", show_alert=True)
                    return

                await callback.answer()
                loading_message = await callback.message.answer("💾 Сохраняю изменения...")

                # Сохраняем изменения
                await self._save_publication_changes(dialog_manager)

                # Обновляем оригинальную версию
                dialog_manager.dialog_data["original_publication"] = dialog_manager.dialog_data["working_publication"]

                del dialog_manager.dialog_data["working_publication"]


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

    async def handle_back_to_moderation_list(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        with self.tracer.start_as_current_span(
                "ModerationPublicationDialogService.handle_back_to_moderation_list",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                await dialog_manager.switch_to(model.ModerationPublicationStates.moderation_list)

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

    async def handle_toggle_social_network(
            self,
            callback: CallbackQuery,
            checkbox: ManagedCheckbox,
            dialog_manager: DialogManager
    ) -> None:
        with self.tracer.start_as_current_span(
                "ModerationPublicationDialogService.handle_toggle_social_network",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                # Инициализируем словарь выбранных соцсетей если его нет
                if "selected_social_networks" not in dialog_manager.dialog_data:
                    dialog_manager.dialog_data["selected_social_networks"] = {}

                network_id = checkbox.widget_id
                is_checked = checkbox.is_checked()

                # Сохраняем состояние чекбокса
                dialog_manager.dialog_data["selected_social_networks"][network_id] = is_checked

                self.logger.info(
                    "Социальная сеть переключена в модерации",
                    {
                        common.TELEGRAM_CHAT_ID_KEY: callback.message.chat.id,
                        "network": network_id,
                        "selected": is_checked,
                        "all_selected": dialog_manager.dialog_data["selected_social_networks"]
                    }
                )

                await callback.answer()
                span.set_status(Status(StatusCode.OK))
            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                raise

    async def handle_publish_with_selected_networks(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        with self.tracer.start_as_current_span(
                "ModerationPublicationDialogService.handle_publish_with_selected_networks",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                # Проверяем, что выбрана хотя бы одна соцсеть
                selected_networks = dialog_manager.dialog_data.get("selected_social_networks", {})
                has_selected_networks = any(selected_networks.values())

                if not has_selected_networks:
                    await callback.answer(
                        "⚠️ Выберите хотя бы одну социальную сеть для публикации",
                        show_alert=True
                    )
                    return

                await self._publish_moderated_publication(callback, dialog_manager)
                span.set_status(Status(StatusCode.OK))
            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                await callback.answer("❌ Ошибка при публикации", show_alert=True)
                raise

    async def get_social_network_select_data(
            self,
            dialog_manager: DialogManager,
            **kwargs
    ) -> dict:
        with self.tracer.start_as_current_span(
                "ModerationPublicationDialogService.get_social_network_select_data",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                state = await self._get_state(dialog_manager)

                # Получаем подключенные социальные сети для организации
                social_networks = await self.kontur_content_client.get_social_networks_by_organization(
                    organization_id=state.organization_id
                )

                # Проверяем подключенные сети
                telegram_connected = self._is_network_connected(social_networks, "telegram")
                vkontakte_connected = self._is_network_connected(social_networks, "vkontakte")

                # Получаем текущие выбранные сети
                selected_networks = dialog_manager.dialog_data.get("selected_social_networks", {})
                has_selected_networks = any(selected_networks.values())

                data = {
                    "telegram_connected": telegram_connected,
                    "vkontakte_connected": vkontakte_connected,
                    "all_networks_connected": telegram_connected and vkontakte_connected,
                    "no_connected_networks": not telegram_connected and not vkontakte_connected,
                    "has_available_networks": telegram_connected or vkontakte_connected,
                    "has_selected_networks": has_selected_networks,
                }

                span.set_status(Status(StatusCode.OK))
                return data

            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                raise

    def _is_network_connected(self, social_networks: dict, network_type: str) -> bool:
        if not social_networks:
            return False
        return network_type in social_networks and len(social_networks[network_type]) > 0

    async def _publish_moderated_publication(
            self,
            callback: CallbackQuery,
            dialog_manager: DialogManager
    ) -> None:
        with self.tracer.start_as_current_span(
                "ModerationPublicationDialogService._publish_moderated_publication",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                await callback.answer()
                loading_message = await callback.message.answer("🚀 Публикую пост...")

                # Если есть несохраненные изменения, сохраняем их перед публикацией
                if self._has_changes(dialog_manager):
                    await self._save_publication_changes(dialog_manager)

                original_pub = dialog_manager.dialog_data["original_publication"]
                publication_id = original_pub["id"]
                state = await self._get_state(dialog_manager)

                # Получаем выбранные социальные сети
                selected_networks = dialog_manager.dialog_data.get("selected_social_networks", {})
                tg_source = selected_networks.get("telegram_checkbox", False)
                vk_source = selected_networks.get("vkontakte_checkbox", False)

                # Обновляем публикацию с выбранными соцсетями
                await self.kontur_content_client.change_publication(
                    publication_id=publication_id,
                    tg_source=tg_source,
                    vk_source=vk_source,
                )

                # Одобряем публикацию
                await self.kontur_content_client.moderate_publication(
                    publication_id=publication_id,
                    moderator_id=state.account_id,
                    moderation_status="approved",
                )

                # Формируем сообщение о публикации
                published_networks = []
                if tg_source:
                    published_networks.append("📺 Telegram")
                if vk_source:
                    published_networks.append("🔗 VKontakte")

                networks_text = ", ".join(published_networks)

                self.logger.info(
                    "Публикация одобрена и опубликована",
                    {
                        common.TELEGRAM_CHAT_ID_KEY: callback.message.chat.id,
                        "publication_id": publication_id,
                        "tg_source": tg_source,
                        "vk_source": vk_source,
                    }
                )

                await loading_message.edit_text(
                    f"🚀 Публикация успешно опубликована!\n\n"
                    f"📋 Опубликовано в: {networks_text}"
                )

                await asyncio.sleep(3)
                try:
                    await loading_message.delete()
                except:
                    pass

                # Удаляем опубликованную публикацию из списка
                moderation_list = dialog_manager.dialog_data.get("moderation_list", [])
                current_index = dialog_manager.dialog_data.get("current_index", 0)

                if moderation_list and current_index < len(moderation_list):
                    moderation_list.pop(current_index)

                    # Корректируем индекс если нужно
                    if current_index >= len(moderation_list) and moderation_list:
                        dialog_manager.dialog_data["current_index"] = len(moderation_list) - 1
                    elif not moderation_list:
                        dialog_manager.dialog_data["current_index"] = 0

                    # Сбрасываем рабочие данные
                    dialog_manager.dialog_data.pop("working_publication", None)
                    dialog_manager.dialog_data.pop("selected_social_networks", None)

                # Возвращаемся к списку модерации
                await dialog_manager.switch_to(model.ModerationPublicationStates.moderation_list)

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
        working_pub = dialog_manager.dialog_data.get("working_publication", {})
        return {
            "current_title": working_pub.get("name", ""),
        }

    async def get_edit_tags_data(
            self,
            dialog_manager: DialogManager,
            **kwargs
    ) -> dict:
        """Данные для окна редактирования тегов"""
        working_pub = dialog_manager.dialog_data.get("working_publication", {})
        tags = working_pub.get("tags", [])
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
        working_pub = dialog_manager.dialog_data.get("working_publication", {})
        text = working_pub.get("text", "")
        return {
            "current_text_length": len(text),
        }

    async def get_image_menu_data(
            self,
            dialog_manager: DialogManager,
            **kwargs
    ) -> dict:
        """Данные для меню управления изображением"""
        working_pub = dialog_manager.dialog_data.get("working_publication", {})
        return {
            "has_image": working_pub.get("has_image", False),
            "is_custom_image": working_pub.get("is_custom_image", False),
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

    def _has_changes(self, dialog_manager: DialogManager) -> bool:
        """Проверка наличия изменений между оригиналом и рабочей версией"""
        original = dialog_manager.dialog_data.get("original_publication", {})
        working = dialog_manager.dialog_data.get("working_publication", {})

        if not original or not working:
            return False

        # Сравниваем текстовые поля
        fields_to_compare = ["name", "text", "tags"]
        for field in fields_to_compare:
            if original.get(field) != working.get(field):
                return True

        # Проверяем изменения изображения более детально

        # 1. Проверяем, изменилось ли наличие изображения
        if original.get("has_image", False) != working.get("has_image", False):
            return True

        # 2. Если есть пользовательское изображение - это всегда изменение
        if working.get("custom_image_file_id"):
            # Проверяем, было ли это изображение в оригинале
            if original.get("custom_image_file_id") != working.get("custom_image_file_id"):
                return True

        # 3. Проверяем изменение URL (новое сгенерированное изображение)
        original_url = original.get("image_url", "")
        working_url = working.get("image_url", "")

        # Игнорируем базовый URL и сравниваем только если оба не пустые
        if working_url and original_url:
            # Если URL изменился - это новое изображение
            if original_url != working_url:
                return True
        elif working_url != original_url:
            # Один пустой, другой нет - есть изменения
            return True

        return False

    async def _save_publication_changes(self, dialog_manager: DialogManager) -> None:
        """Сохранение изменений публикации через API"""
        working_pub = dialog_manager.dialog_data["working_publication"]
        original_pub = dialog_manager.dialog_data["original_publication"]
        publication_id = working_pub["id"]

        # Определяем, что делать с изображением
        image_url = None
        image_content = None
        image_filename = None
        should_delete_image = False

        # Проверяем изменения изображения
        original_has_image = original_pub.get("has_image", False)
        working_has_image = working_pub.get("has_image", False)

        if not working_has_image and original_has_image:
            # Изображение было удалено - нужно удалить из storage
            should_delete_image = True

        elif working_has_image:
            # Проверяем, новое ли это изображение
            if working_pub.get("custom_image_file_id"):
                image_content = await self.bot.download(working_pub["custom_image_file_id"])
                image_filename = working_pub["custom_image_file_id"] + ".jpg"

            elif working_pub.get("image_url"):
                # Проверяем, изменился ли URL (новое сгенерированное изображение)
                original_url = original_pub.get("image_url", "")
                working_url = working_pub.get("image_url", "")

                if original_url != working_url:
                    # URL изменился - это новое сгенерированное изображение
                    image_url = working_url

        # Если нужно удалить изображение
        if should_delete_image:
            try:
                await self.kontur_content_client.delete_publication_image(
                    publication_id=publication_id
                )
                self.logger.info(f"Deleted image for publication {publication_id}")
            except Exception as e:
                self.logger.warning(f"Failed to delete image: {str(e)}")

        # Обновляем публикацию через API
        # Передаем изображение только если оно действительно новое
        if image_url or image_content:
            await self.kontur_content_client.change_publication(
                publication_id=publication_id,
                name=working_pub["name"],
                text=working_pub["text"],
                tags=working_pub.get("tags", []),
                image_url=image_url,
                image_content=image_content,
                image_filename=image_filename,
            )
        else:
            # Обновляем только текстовые поля
            await self.kontur_content_client.change_publication(
                publication_id=publication_id,
                name=working_pub["name"],
                text=working_pub["text"],
                tags=working_pub.get("tags", []),
            )

        self.logger.info(
            "Изменения публикации сохранены",
            {
                "publication_id": publication_id,
                "has_changes": self._has_changes(dialog_manager),
                "image_changed": bool(image_url or image_content),
                "image_deleted": should_delete_image,
            }
        )

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