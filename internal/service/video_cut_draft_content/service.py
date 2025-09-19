import asyncio
from datetime import datetime, timezone, timedelta
import time
from typing import Any

from aiogram import Bot
from aiogram_dialog.api.entities import MediaId, MediaAttachment
from aiogram.types import CallbackQuery, Message, ContentType
from aiogram_dialog import DialogManager, StartMode

from opentelemetry.trace import SpanKind, Status, StatusCode

from internal import interface, model, common


class VideoCutsDraftDialogService(interface.IDraftVideoCutsDialogService):
    def __init__(
            self,
            tel: interface.ITelemetry,
            bot: Bot,
            state_repo: interface.IStateRepo,
            kontur_employee_client: interface.IKonturEmployeeClient,
            kontur_organization_client: interface.IKonturOrganizationClient,
            kontur_content_client: interface.IKonturContentClient,
    ):
        self.tracer = tel.tracer()
        self.logger = tel.logger()
        self.bot = bot
        self.state_repo = state_repo
        self.kontur_employee_client = kontur_employee_client
        self.kontur_organization_client = kontur_organization_client
        self.kontur_content_client = kontur_content_client

    async def get_video_cut_list_data(
            self,
            dialog_manager: DialogManager,
            **kwargs
    ) -> dict:
        """Получение данных для основного окна - сразу показываем первую видео-нарезку"""
        with self.tracer.start_as_current_span(
                "DraftVideoCutsDialogService.get_video_cut_list_data",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                state = await self._get_state(dialog_manager)

                # Получаем черновики видео-нарезок для организации
                video_cuts = await self.kontur_content_client.get_video_cuts_by_organization(
                    organization_id=state.organization_id
                )

                if not video_cuts:
                    return {
                        "has_video_cut": False,
                        "video_cut_count": 0,
                        "period_text": "",
                    }

                # Сохраняем список для навигации
                dialog_manager.dialog_data["video_cuts_list"] = [video_cut.to_dict() for video_cut in video_cuts]

                # Устанавливаем текущий индекс (0 если не был установлен)
                if "current_index" not in dialog_manager.dialog_data:
                    dialog_manager.dialog_data["current_index"] = 0

                current_index = dialog_manager.dialog_data["current_index"]
                current_video_cut = model.VideoCut(**dialog_manager.dialog_data["video_cuts_list"][current_index])

                # Форматируем теги
                tags = current_video_cut.tags or []
                tags_text = ", ".join(tags) if tags else ""

                # Определяем период
                period_text = self._get_period_text(video_cuts)

                # Подготавливаем медиа для видео (основное изменение)
                video_media = None
                if current_video_cut.video_fid:
                    cache_buster = int(time.time())
                    video_url = f"https://kontur-media.ru/api/content/video-cut/{current_video_cut.id}/download?v={cache_buster}"

                    video_media = MediaAttachment(
                        url=video_url,
                        type=ContentType.VIDEO
                    )


                data = {
                    "has_video_cuts": True,
                    "period_text": period_text,
                    "video_name": current_video_cut.name or "Без названия",
                    "video_description": current_video_cut.description or "Описание отсутствует",
                    "has_tags": bool(tags),
                    "video_tags": tags_text,
                    "youtube_reference_short": current_video_cut.youtube_video_reference,
                    "created_at": self._format_datetime(current_video_cut.created_at),
                    "youtube_enabled": current_video_cut.youtube_source_id,
                    "instagram_enabled": current_video_cut.inst_source_id,
                    "has_video": bool(current_video_cut.video_fid),
                    "video_media": video_media,  # Новое поле для отображения видео
                    "current_index": current_index + 1,
                    "total_count": len(video_cuts),
                    "has_prev": current_index > 0,
                    "has_next": current_index < len(video_cuts) - 1,
                }

                # Сохраняем данные текущего черновика для редактирования
                dialog_manager.dialog_data["original_video_cut"] = {
                    "id": current_video_cut.id,
                    "name": current_video_cut.name,
                    "description": current_video_cut.description,
                    "tags": current_video_cut.tags or [],
                    "youtube_reference_url": current_video_cut.youtube_video_reference,
                    "video_fid": current_video_cut.video_fid,
                    "created_at": current_video_cut.created_at,
                }

                # Копируем в рабочую версию, если ее еще нет
                if "working_video_cut" not in dialog_manager.dialog_data:
                    dialog_manager.dialog_data["working_video_cut"] = dict(
                        dialog_manager.dialog_data["original_video_cut"])

                self.logger.info(
                    "Список черновиков видео загружен",
                    {
                        common.TELEGRAM_CHAT_ID_KEY: self._get_chat_id(dialog_manager),
                        "video_cuts_count": len(video_cuts),
                        "current_index": current_index,
                    }
                )

                span.set_status(Status(StatusCode.OK))
                return data

            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                raise

    async def handle_navigate_video_cut(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        with self.tracer.start_as_current_span(
                "DraftVideoCutsDialogService.handle_navigate_video_cut",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                current_index = dialog_manager.dialog_data.get("current_index", 0)
                video_cuts_list = dialog_manager.dialog_data.get("video_cuts_list", [])

                # Определяем направление навигации
                if button.widget_id == "prev_video_cut":
                    new_index = max(0, current_index - 1)
                else:  # next_video_cut
                    new_index = min(len(video_cuts_list) - 1, current_index + 1)

                if new_index == current_index:
                    await callback.answer()
                    return

                # Обновляем индекс
                dialog_manager.dialog_data["current_index"] = new_index

                # Сбрасываем рабочие данные для нового черновика
                dialog_manager.dialog_data.pop("working_video_cut", None)

                self.logger.info(
                    "Навигация по черновикам видео",
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
                    await self._save_video_cut_changes(dialog_manager)

                original_video_cut = dialog_manager.dialog_data["original_video_cut"]
                video_cut_id = original_video_cut["id"]

                # Отправляем на модерацию через API
                await self.kontur_content_client.send_video_cut_to_moderation(
                    video_cut_id=video_cut_id
                )

                self.logger.info(
                    "Черновик видео отправлен на модерацию",
                    {
                        common.TELEGRAM_CHAT_ID_KEY: callback.message.chat.id,
                        "video_cut_id": video_cut_id,
                    }
                )

                await callback.answer("📤 Отправлено на модерацию!", show_alert=True)

                # Удаляем черновик из списка (он больше не черновик)
                await self._remove_current_video_cut_from_list(dialog_manager)

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
                    await self._save_video_cut_changes(dialog_manager)

                original_video_cut = dialog_manager.dialog_data["original_video_cut"]
                video_cut_id = original_video_cut["id"]

                # Публикуем немедленно через API
                # await self.kontur_content_client.publish_video_cut_now(
                #     video_cut_id=video_cut_id
                # )

                self.logger.info(
                    "Черновик видео опубликован",
                    {
                        common.TELEGRAM_CHAT_ID_KEY: callback.message.chat.id,
                        "video_cut_id": video_cut_id,
                    }
                )

                await callback.answer("🚀 Опубликовано!", show_alert=True)

                # Удаляем черновик из списка
                await self._remove_current_video_cut_from_list(dialog_manager)

                span.set_status(Status(StatusCode.OK))

            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                await callback.answer("❌ Ошибка публикации", show_alert=True)
                raise

    async def handle_delete_video_cut(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        with self.tracer.start_as_current_span(
                "DraftVideoCutsDialogService.handle_delete_video_cut",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                original_video_cut = dialog_manager.dialog_data["original_video_cut"]
                video_cut_id = original_video_cut["id"]

                # Удаляем черновик через API
                # await self.kontur_content_client.delete_video_cut_video_cut(
                #     video_cut_id=video_cut_id
                # )

                self.logger.info(
                    "Черновик видео удален",
                    {
                        common.TELEGRAM_CHAT_ID_KEY: callback.message.chat.id,
                        "video_cut_id": video_cut_id,
                    }
                )

                await callback.answer("🗑 Черновик удален", show_alert=True)

                # Удаляем из списка
                await self._remove_current_video_cut_from_list(dialog_manager)

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
                "DraftVideoCutsDialogService.get_edit_preview_data",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                # Инициализируем рабочую версию если ее нет
                if "working_video_cut" not in dialog_manager.dialog_data:
                    dialog_manager.dialog_data["working_video_cut"] = dict(
                        dialog_manager.dialog_data["original_video_cut"]
                    )

                working_video_cut = dialog_manager.dialog_data["working_video_cut"]
                original_video_cut = dialog_manager.dialog_data["original_video_cut"]

                # Форматируем теги
                tags = working_video_cut.get("tags", [])
                tags_text = ", ".join(tags) if tags else ""

                video_media = None
                if working_video_cut.get("video_fid"):
                    cache_buster = int(time.time())
                    video_url = f"https://kontur-media.ru/api/content/video-cut/{working_video_cut.get("id")}/download?v={cache_buster}"

                    video_media = MediaAttachment(
                        url=video_url,
                        type=ContentType.VIDEO
                    )

                data = {
                    "created_at": self._format_datetime(original_video_cut["created_at"]),
                    "youtube_reference": working_video_cut["youtube_reference_url"],
                    "video_name": working_video_cut["name"] or "Без названия",
                    "video_description": working_video_cut["description"] or "Описание отсутствует",
                    "has_tags": bool(tags),
                    "video_tags": tags_text,
                    "has_video": bool(working_video_cut.get("video_file_id") or working_video_cut.get("video_url")),
                    "video_media": video_media,
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
                "DraftVideoCutsDialogService.handle_save_changes",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                if not self._has_changes(dialog_manager):
                    await callback.answer("ℹ️ Нет изменений для сохранения", show_alert=True)
                    return

                await callback.answer()
                loading_message = await callback.message.answer("💾 Сохраняю изменения...")

                # Сохраняем изменения
                await self._save_video_cut_changes(dialog_manager)

                # Обновляем оригинальную версию
                dialog_manager.dialog_data["original_video_cut"] = dict(dialog_manager.dialog_data["working_video_cut"])

                await loading_message.edit_text("✅ Изменения сохранены!")
                await asyncio.sleep(2)
                try:
                    await loading_message.delete()
                except:
                    pass

                await dialog_manager.switch_to(model.DraftVideoCutsStates.video_cut_list)

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
                "DraftVideoCutsDialogService.handle_edit_title_save",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                new_title = text.strip()

                if not new_title:
                    await message.answer("❌ Название не может быть пустым")
                    return

                if len(new_title) > 100:  # YouTube Shorts лимит
                    await message.answer("❌ Слишком длинное название (макс. 100 символов для YouTube)")
                    return

                # Обновляем рабочую версию
                dialog_manager.dialog_data["working_video_cut"]["name"] = new_title

                await message.delete()
                await message.answer("✅ Название обновлено!")
                await dialog_manager.switch_to(model.DraftVideoCutsStates.edit_preview)

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
                "DraftVideoCutsDialogService.handle_edit_description_save",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                new_description = text.strip()

                if not new_description:
                    await message.answer("❌ Описание не может быть пустым")
                    return

                if len(new_description) > 2200:  # Instagram лимит
                    await message.answer("❌ Слишком длинное описание (макс. 2200 символов для Instagram)")
                    return

                # Обновляем рабочую версию
                dialog_manager.dialog_data["working_video_cut"]["description"] = new_description

                await message.delete()
                await message.answer("✅ Описание обновлено!")
                await dialog_manager.switch_to(model.DraftVideoCutsStates.edit_preview)

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
                "DraftVideoCutsDialogService.handle_edit_tags_save",
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

                    if len(new_tags) > 15:  # YouTube лимит
                        await message.answer("❌ Слишком много тегов (макс. 15 для YouTube)")
                        return

                # Обновляем рабочую версию
                dialog_manager.dialog_data["working_video_cut"]["tags"] = new_tags

                await message.delete()
                await message.answer(f"✅ Теги обновлены ({len(new_tags)} шт.)")
                await dialog_manager.switch_to(model.DraftVideoCutsStates.edit_preview)

                span.set_status(Status(StatusCode.OK))

            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                await message.answer("❌ Ошибка при сохранении тегов")
                raise

    async def handle_toggle_platform(
            self,
            callback: CallbackQuery,
            checkbox: Any,
            dialog_manager: DialogManager
    ) -> None:
        with self.tracer.start_as_current_span(
                "DraftVideoCutsDialogService.handle_toggle_platform",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                working_video_cut = dialog_manager.dialog_data["working_video_cut"]
                settings = working_video_cut.get("publication_settings", {})

                # Переключаем платформу
                if checkbox.widget_id == "youtube_checkbox":
                    settings["youtube_enabled"] = not settings.get("youtube_enabled", True)
                elif checkbox.widget_id == "instagram_checkbox":
                    settings["instagram_enabled"] = not settings.get("instagram_enabled", True)

                # Проверяем, что хотя бы одна платформа включена
                if not settings.get("youtube_enabled", True) and not settings.get("instagram_enabled", True):
                    await callback.answer("❌ Должна быть выбрана хотя бы одна платформа", show_alert=True)
                    return

                dialog_manager.dialog_data["working_video_cut"]["publication_settings"] = settings

                await callback.answer()
                span.set_status(Status(StatusCode.OK))

            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                await callback.answer("❌ Ошибка переключения", show_alert=True)
                raise

    async def handle_schedule_publication(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        with self.tracer.start_as_current_span(
                "DraftVideoCutsDialogService.handle_schedule_publication",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                working_video_cut = dialog_manager.dialog_data["working_video_cut"]
                settings = working_video_cut.get("publication_settings", {})

                if button.widget_id == "remove_schedule":
                    # Убираем расписание
                    settings.pop("scheduled_time", None)
                    await callback.answer("⏰ Расписание убрано", show_alert=True)
                else:
                    # Устанавливаем расписание на завтра в 10:00 (простая реализация)
                    tomorrow = datetime.now() + timedelta(days=1)
                    scheduled_time = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)
                    settings["scheduled_time"] = scheduled_time.isoformat()
                    await callback.answer("📅 Публикация запланирована на завтра 10:00", show_alert=True)

                dialog_manager.dialog_data["working_video_cut"]["publication_settings"] = settings

                span.set_status(Status(StatusCode.OK))

            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                await callback.answer("❌ Ошибка планирования", show_alert=True)
                raise

    async def handle_back_to_video_cut_list(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        with self.tracer.start_as_current_span(
                "DraftVideoCutsDialogService.handle_back_to_video_cut_list",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                await dialog_manager.switch_to(model.DraftVideoCutsStates.video_cut_list)
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
                "DraftVideoCutsDialogService.handle_back_to_content_menu",
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
        working_video_cut = dialog_manager.dialog_data.get("working_video_cut", {})
        return {
            "current_title": working_video_cut.get("name", ""),
        }

    async def get_edit_description_data(
            self,
            dialog_manager: DialogManager,
            **kwargs
    ) -> dict:
        """Данные для окна редактирования описания"""
        working_video_cut = dialog_manager.dialog_data.get("working_video_cut", {})
        description = working_video_cut.get("description", "")
        return {
            "current_description_length": len(description),
        }

    async def get_edit_tags_data(
            self,
            dialog_manager: DialogManager,
            **kwargs
    ) -> dict:
        """Данные для окна редактирования тегов"""
        working_video_cut = dialog_manager.dialog_data.get("working_video_cut", {})
        tags = working_video_cut.get("tags", [])
        return {
            "has_tags": bool(tags),
            "current_tags": ", ".join(tags) if tags else "",
        }

    async def get_publication_settings_data(
            self,
            dialog_manager: DialogManager,
            **kwargs
    ) -> dict:
        """Данные для окна настроек публикации"""
        working_video_cut = dialog_manager.dialog_data.get("working_video_cut", {})
        settings = working_video_cut.get("publication_settings", {})

        # Проверяем наличие запланированного времени
        scheduled_time = settings.get("scheduled_time")
        is_scheduled = bool(scheduled_time)
        scheduled_time_text = ""

        if is_scheduled:
            try:
                dt = datetime.fromisoformat(scheduled_time)
                scheduled_time_text = dt.strftime("%d.%m.%Y %H:%M")
            except:
                scheduled_time_text = scheduled_time

        return {
            "youtube_enabled": settings.get("youtube_enabled", True),
            "instagram_enabled": settings.get("instagram_enabled", True),
            "is_scheduled": is_scheduled,
            "scheduled_time": scheduled_time_text,
        }

    # Вспомогательные методы

    def _has_changes(self, dialog_manager: DialogManager) -> bool:
        """Проверка наличия изменений между оригиналом и рабочей версией"""
        original = dialog_manager.dialog_data.get("original_video_cut", {})
        working = dialog_manager.dialog_data.get("working_video_cut", {})

        if not original or not working:
            return False

        # Сравниваем основные поля
        fields_to_compare = ["name", "description", "tags"]
        for field in fields_to_compare:
            if original.get(field) != working.get(field):
                return True

        # Сравниваем настройки публикации
        original_settings = original.get("publication_settings", {})
        working_settings = working.get("publication_settings", {})

        if original_settings != working_settings:
            return True

        return False

    async def _save_video_cut_changes(self, dialog_manager: DialogManager) -> None:
        working_video_cut = dialog_manager.dialog_data["working_video_cut"]
        video_cut_id = working_video_cut["id"]

        # Обновляем черновик через API
        await self.kontur_content_client.change_video_cut(
            video_cut_id=video_cut_id,
            name=working_video_cut["name"],
            description=working_video_cut["description"],
            tags=working_video_cut.get("tags", []),
        )

        self.logger.info(
            "Изменения черновика видео сохранены",
            {
                "video_cut_id": video_cut_id,
                "has_changes": self._has_changes(dialog_manager),
            }
        )

    async def _remove_current_video_cut_from_list(self, dialog_manager: DialogManager) -> None:
        video_cuts_list = dialog_manager.dialog_data.get("video_cuts_list", [])
        current_index = dialog_manager.dialog_data.get("current_index", 0)

        if video_cuts_list and current_index < len(video_cuts_list):
            video_cuts_list.pop(current_index)

            # Корректируем индекс если нужно
            if current_index >= len(video_cuts_list) and video_cuts_list:
                dialog_manager.dialog_data["current_index"] = len(video_cuts_list) - 1
            elif not video_cuts_list:
                dialog_manager.dialog_data["current_index"] = 0

            # Сбрасываем рабочие данные
            dialog_manager.dialog_data.pop("working_video_cut", None)
            dialog_manager.dialog_data.pop("original_video_cut", None)

    def _format_datetime(self, dt: str) -> str:
        """Форматирование даты и времени"""
        try:
            if isinstance(dt, str):
                dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))

            # Форматируем в читаемый вид
            return dt.strftime("%d.%m.%Y %H:%M")
        except:
            return str(dt)

    def _get_period_text(self, video_video_cuts: list) -> str:
        """Определение периода черновиков"""
        if not video_video_cuts:
            return "Нет данных"

        # Находим самый старый и новый черновик
        dates = []
        for video_cut in video_video_cuts:
            if hasattr(video_cut, 'created_at') and video_cut.created_at:
                dates.append(video_cut.created_at)

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