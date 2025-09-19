import asyncio
from datetime import datetime, timezone
import time
from typing import Any

from aiogram_dialog.api.entities import MediaAttachment
from aiogram.types import CallbackQuery, Message, ContentType
from aiogram_dialog import DialogManager, StartMode

from opentelemetry.trace import SpanKind, Status, StatusCode

from internal import interface, model, common


class PublicationDraftDialogService(interface.IPublicationDraftDialogService):
    def __init__(
            self,
            tel: interface.ITelemetry,
            state_repo: interface.IStateRepo,
            kontur_employee_client: interface.IKonturEmployeeClient,
            kontur_organization_client: interface.IKonturOrganizationClient,
            kontur_content_client: interface.IKonturContentClient,
    ):
        self.tracer = tel.tracer()
        self.logger = tel.logger()
        self.state_repo = state_repo
        self.kontur_employee_client = kontur_employee_client
        self.kontur_organization_client = kontur_organization_client
        self.kontur_content_client = kontur_content_client

    async def get_publication_list_data(
            self,
            dialog_manager: DialogManager,
            **kwargs
    ) -> dict:
        """Получение данных для основного окна - сразу показываем первую публикацию"""
        with self.tracer.start_as_current_span(
                "DraftPublicationDialogService.get_publication_list_data",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                state = await self._get_state(dialog_manager)
                employee = await self.kontur_employee_client.get_employee_by_account_id(state.account_id)

                # Получаем черновики публикаций для организации
                publications = await self.kontur_content_client.get_publications_by_organization(
                    organization_id=state.organization_id
                )

                publications = [publication for publication in publications if publication.moderation_status == "draft"]

                if not publications:
                    return {
                        "has_publications": False,
                        "publications_count": 0,
                        "period_text": "",
                    }

                # Сохраняем список для навигации
                dialog_manager.dialog_data["publications_list"] = [publication.to_dict() for publication in publications]

                # Устанавливаем текущий индекс (0 если не был установлен)
                if "current_index" not in dialog_manager.dialog_data:
                    dialog_manager.dialog_data["current_index"] = 0

                current_index = dialog_manager.dialog_data["current_index"]
                current_publication = model.Publication(**dialog_manager.dialog_data["publications_list"][current_index])

                # Форматируем теги
                tags = current_publication.tags or []
                tags_text = ", ".join(tags) if tags else ""

                # Определяем период
                period_text = self._get_period_text(publications)

                # Подготавливаем медиа для изображения
                image_media = None
                if current_publication.image_fid:
                    cache_buster = int(time.time())
                    image_url = f"https://kontur-media.ru/api/content/publication/{current_publication.id}/image/download?v={cache_buster}"
                    image_media = MediaAttachment(
                        url=image_url,
                        type=ContentType.PHOTO
                    )

                data = {
                    "has_publications": True,
                    "period_text": period_text,
                    "publication_name": current_publication.name or "Без названия",
                    "publication_text": current_publication.text or "Текст отсутствует",
                    "has_tags": bool(tags),
                    "publication_tags": tags_text,
                    "created_at": self._format_datetime(current_publication.created_at),
                    "has_image": bool(current_publication.image_fid),
                    "image_media": image_media,
                    "current_index": current_index + 1,
                    "publications_count": len(publications),
                    "has_prev": current_index > 0,
                    "has_next": current_index < len(publications) - 1,
                    "can_publish": False if employee.required_moderation else True,
                    "not_can_publish": True if employee.required_moderation else False
                }

                # Сохраняем данные текущего черновика для редактирования
                dialog_manager.dialog_data["original_publication"] = {
                    "id": current_publication.id,
                    "name": current_publication.name,
                    "text": current_publication.text,
                    "tags": current_publication.tags or [],
                    "image_fid": current_publication.image_fid,
                    "created_at": current_publication.created_at,
                }

                # Копируем в рабочую версию, если ее еще нет
                if "working_publication" not in dialog_manager.dialog_data:
                        dialog_manager.dialog_data["working_publication"] = dict(
                        dialog_manager.dialog_data["original_publication"])

                self.logger.info(
                    "Список черновиков публикаций загружен",
                    {
                        common.TELEGRAM_CHAT_ID_KEY: self._get_chat_id(dialog_manager),
                        "publications_count": len(publications),
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
                "DraftPublicationDialogService.handle_navigate_publication",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                current_index = dialog_manager.dialog_data.get("current_index", 0)
                publications_list = dialog_manager.dialog_data.get("publications_list", [])

                # Определяем направление навигации
                if button.widget_id == "prev_publication":
                    new_index = max(0, current_index - 1)
                else:  # next_publication
                    new_index = min(len(publications_list) - 1, current_index + 1)

                if new_index == current_index:
                    await callback.answer()
                    return

                # Обновляем индекс
                dialog_manager.dialog_data["current_index"] = new_index

                # Сбрасываем рабочие данные для нового черновика
                dialog_manager.dialog_data.pop("working_publication", None)

                self.logger.info(
                    "Навигация по черновикам публикаций",
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

    async def handle_send_to_moderation(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        with self.tracer.start_as_current_span(
                "DraftVideoCutsDialogService.handle_send_to_moderation",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                # Если есть несохраненные изменения, сохраняем их
                if self._has_changes(dialog_manager):
                    await self._save_publication_changes(dialog_manager)

                original_publication = dialog_manager.dialog_data["original_publication"]
                publication_id = original_publication["id"]

                # Отправляем на модерацию через API
                await self.kontur_content_client.send_publication_to_moderation(
                    publication_id=publication_id
                )

                self.logger.info(
                    "Черновик публикация отправлен на модерацию",
                    {
                        common.TELEGRAM_CHAT_ID_KEY: callback.message.chat.id,
                        "publication_id": publication_id,
                    }
                )

                await callback.answer("📤 Отправлено на модерацию!", show_alert=True)

                # Удаляем черновик из списка (он больше не черновик)
                await self._remove_current_publication_from_list(dialog_manager)

                span.set_status(Status(StatusCode.OK))

            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                await callback.answer("❌ Ошибка отправки", show_alert=True)
                raise

    async def handle_publish_now(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        with self.tracer.start_as_current_span(
                "DraftVideoCutsDialogService.handle_publish_now",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                # Если есть несохраненные изменения, сохраняем их
                if self._has_changes(dialog_manager):
                    await self._save_publication_changes(dialog_manager)

                original_publication = dialog_manager.dialog_data["original_publication"]
                publication_id = original_publication["id"]

                # Публикуем немедленно через API
                await self.kontur_content_client.publish_publication(
                    publication_id=publication_id
                )

                self.logger.info(
                    "Черновик публикация опубликован",
                    {
                        common.TELEGRAM_CHAT_ID_KEY: callback.message.chat.id,
                        "publication_id": publication_id,
                    }
                )

                await callback.answer("🚀 Опубликовано!", show_alert=True)

                # Удаляем черновик из списка
                await self._remove_current_publication_from_list(dialog_manager)

                span.set_status(Status(StatusCode.OK))

            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                await callback.answer("❌ Ошибка публикации", show_alert=True)
                raise

    async def handle_delete_publication(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        with self.tracer.start_as_current_span(
                "DraftPublicationDialogService.handle_delete_publication",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                original_publication = dialog_manager.dialog_data["original_publication"]
                publication_id = original_publication["id"]


                await self.kontur_content_client.delete_publication(
                    publication_id=publication_id
                )

                self.logger.info(
                    "Черновик публикация удален",
                    {
                        common.TELEGRAM_CHAT_ID_KEY: callback.message.chat.id,
                        "publication_id": publication_id,
                    }
                )

                await callback.answer("🗑 Черновик удален", show_alert=True)

                # Удаляем из списка
                await self._remove_current_publication_from_list(dialog_manager)

                span.set_status(Status(StatusCode.OK))

            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                await callback.answer("❌ Ошибка удаления", show_alert=True)
                raise

    async def get_edit_preview_data(
            self,
            dialog_manager: DialogManager,
            **kwargs
    ) -> dict:
        """Получение данных для окна редактирования с превью"""
        with self.tracer.start_as_current_span(
                "DraftPublicationDialogService.get_edit_preview_data",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                # Инициализируем рабочую версию если ее нет
                if "working_publication" not in dialog_manager.dialog_data:
                    dialog_manager.dialog_data["working_publication"] = dict(
                        dialog_manager.dialog_data["original_publication"]
                    )

                working_publication = dialog_manager.dialog_data["working_publication"]
                original_publication = dialog_manager.dialog_data["original_publication"]

                # Форматируем теги
                tags = working_publication.get("tags", [])
                tags_text = ", ".join(tags) if tags else ""

                image_media = None
                if working_publication.get("image_fid"):
                    cache_buster = int(time.time())
                    image_url = f"https://kontur-media.ru/api/content/publication/{working_publication.get('id')}/image/download?v={cache_buster}"

                    image_media = MediaAttachment(
                        url=image_url,
                        type=ContentType.PHOTO
                    )

                data = {
                    "created_at": self._format_datetime(original_publication["created_at"]),
                    "publication_name": working_publication["name"] or "Без названия",
                    "publication_text": working_publication["text"] or "Текст отсутствует",
                    "has_tags": bool(tags),
                    "publication_tags": tags_text,
                    "has_image": bool(working_publication.get("image_fid")),
                    "image_media": image_media,
                    "has_changes": self._has_changes(dialog_manager),
                }

                span.set_status(Status(StatusCode.OK))
                return data

            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                raise

    async def handle_save_changes(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        with self.tracer.start_as_current_span(
                "DraftPublicationDialogService.handle_save_changes",
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
                dialog_manager.dialog_data["original_publication"] = dict(dialog_manager.dialog_data["working_publication"])

                await loading_message.edit_text("✅ Изменения сохранены!")
                await asyncio.sleep(2)
                try:
                    await loading_message.delete()
                except:
                    pass

                await dialog_manager.switch_to(model.PublicationDraftStates.publication_list)

                span.set_status(Status(StatusCode.OK))

            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                await callback.answer("❌ Ошибка сохранения", show_alert=True)
                raise

    async def handle_edit_title_save(
            self,
            message: Message,
            widget: Any,
            dialog_manager: DialogManager,
            text: str
    ) -> None:
        with self.tracer.start_as_current_span(
                "DraftPublicationDialogService.handle_edit_title_save",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                new_title = text.strip()

                if not new_title:
                    await message.answer("❌ Название не может быть пустым")
                    return

                if len(new_title) > 200:  # Лимит для публикаций
                    await message.answer("❌ Слишком длинное название (макс. 200 символов)")
                    return

                # Обновляем рабочую версию
                dialog_manager.dialog_data["working_publication"]["name"] = new_title

                await message.delete()
                await message.answer("✅ Название обновлено!")
                await dialog_manager.switch_to(model.PublicationDraftStates.edit_preview)

                span.set_status(Status(StatusCode.OK))

            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                await message.answer("❌ Ошибка при сохранении названия")
                raise

    async def handle_edit_description_save(
            self,
            message: Message,
            widget: Any,
            dialog_manager: DialogManager,
            text: str
    ) -> None:
        with self.tracer.start_as_current_span(
                "DraftPublicationDialogService.handle_edit_description_save",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                new_text = text.strip()

                if not new_text:
                    await message.answer("❌ Текст не может быть пустым")
                    return

                if len(new_text) > 4000:  # Лимит для публикаций
                    await message.answer("❌ Слишком длинный текст (макс. 4000 символов)")
                    return

                # Обновляем рабочую версию
                dialog_manager.dialog_data["working_publication"]["text"] = new_text

                await message.delete()
                await message.answer("✅ Текст обновлен!")
                await dialog_manager.switch_to(model.PublicationDraftStates.edit_preview)

                span.set_status(Status(StatusCode.OK))

            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                await message.answer("❌ Ошибка при сохранении описания")
                raise

    async def handle_edit_tags_save(
            self,
            message: Message,
            widget: Any,
            dialog_manager: DialogManager,
            text: str
    ) -> None:
        with self.tracer.start_as_current_span(
                "DraftPublicationDialogService.handle_edit_tags_save",
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

                    if len(new_tags) > 10:  # Лимит для публикаций
                        await message.answer("❌ Слишком много тегов (макс. 10)")
                        return

                # Обновляем рабочую версию
                dialog_manager.dialog_data["working_publication"]["tags"] = new_tags

                await message.delete()
                await message.answer(f"✅ Теги обновлены ({len(new_tags)} шт.)")
                await dialog_manager.switch_to(model.PublicationDraftStates.edit_preview)

                span.set_status(Status(StatusCode.OK))

            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                await message.answer("❌ Ошибка при сохранении тегов")
                raise


    async def handle_back_to_publication_list(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        with self.tracer.start_as_current_span(
                "DraftPublicationDialogService.handle_back_to_publication_list",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                await dialog_manager.switch_to(model.PublicationDraftStates.publication_list)
                span.set_status(Status(StatusCode.OK))

            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                raise

    async def handle_back_to_content_menu(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        with self.tracer.start_as_current_span(
                "DraftPublicationDialogService.handle_back_to_content_menu",
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
        working_publication = dialog_manager.dialog_data.get("working_publication", {})
        return {
            "current_title": working_publication.get("name", ""),
        }

    async def get_edit_description_data(
            self,
            dialog_manager: DialogManager,
            **kwargs
    ) -> dict:
        """Данные для окна редактирования описания"""
        working_publication = dialog_manager.dialog_data.get("working_publication", {})
        description = working_publication.get("description", "")
        return {
            "current_description_length": len(description),
        }

    async def get_edit_tags_data(
            self,
            dialog_manager: DialogManager,
            **kwargs
    ) -> dict:
        """Данные для окна редактирования тегов"""
        working_publication = dialog_manager.dialog_data.get("working_publication", {})
        tags = working_publication.get("tags", [])
        return {
            "has_tags": bool(tags),
            "current_tags": ", ".join(tags) if tags else "",
        }


    # Вспомогательные методы

    def _has_changes(self, dialog_manager: DialogManager) -> bool:
        """Проверка наличия изменений между оригиналом и рабочей версией"""
        original = dialog_manager.dialog_data.get("original_publication", {})
        working = dialog_manager.dialog_data.get("working_publication", {})

        if not original or not working:
            return False

        # Сравниваем основные поля
        fields_to_compare = ["name", "text", "tags"]
        for field in fields_to_compare:
            if original.get(field) != working.get(field):
                return True

        return False

    async def _save_publication_changes(self, dialog_manager: DialogManager) -> None:
        working_publication = dialog_manager.dialog_data["working_publication"]
        publication_id = working_publication["id"]

        await self.kontur_content_client.change_publication(
            publication_id=publication_id,
            name=working_publication["name"],
            text=working_publication["text"],
            tags=working_publication.get("tags", [])
        )

        self.logger.info(
            "Изменения черновика публикации сохранены",
            {
                "publication_id": publication_id,
                "has_changes": self._has_changes(dialog_manager),
            }
        )

    async def _remove_current_publication_from_list(self, dialog_manager: DialogManager) -> None:
        publications_list = dialog_manager.dialog_data.get("publications_list", [])
        current_index = dialog_manager.dialog_data.get("current_index", 0)

        if publications_list and current_index < len(publications_list):
            publications_list.pop(current_index)

            # Корректируем индекс если нужно
            if current_index >= len(publications_list) and publications_list:
                dialog_manager.dialog_data["current_index"] = len(publications_list) - 1
            elif not publications_list:
                dialog_manager.dialog_data["current_index"] = 0

            # Сбрасываем рабочие данные
            dialog_manager.dialog_data.pop("working_publication", None)
            dialog_manager.dialog_data.pop("original_publication", None)

    def _format_datetime(self, dt: str) -> str:
        """Форматирование даты и времени"""
        try:
            if isinstance(dt, str):
                dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))

            # Форматируем в читаемый вид
            return dt.strftime("%d.%m.%Y %H:%M")
        except:
            return str(dt)

    def _get_period_text(self, publications: list) -> str:
        """Определение периода черновиков"""
        if not publications:
            return "Нет данных"

        # Находим самый старый и новый черновик
        dates = []
        for publication in publications:
            if hasattr(publication, 'created_at') and publication.created_at:
                dates.append(publication.created_at)

        if not dates:
            return "Сегодня"

        # Простое определение периода на основе самого старого черновика
        oldest_date = min(dates)

        try:
            if isinstance(oldest_date, str):
                oldest_dt = datetime.fromisoformat(oldest_date.replace('Z', '+00:00'))
            else:
                oldest_dt = oldest_date

            now = datetime.now(timezone.utc)
            delta = now - oldest_dt
            hours = delta.total_seconds() / 3600

            if hours < 24:
                return "За сегодня"
            elif hours < 48:
                return "За последние 2 дня"
            elif hours < 168:  # неделя
                return "За неделю"
            else:
                return "За месяц"
        except:
            return "За неделю"

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