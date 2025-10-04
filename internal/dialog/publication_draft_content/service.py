from typing import Any

from aiogram import Bot
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, StartMode

from opentelemetry.trace import SpanKind, Status, StatusCode

from internal import interface, model


class PublicationDraftService(interface.IPublicationDraftService):
    def __init__(
            self,
            tel: interface.ITelemetry,
            bot: Bot,
            state_repo: interface.IStateRepo,
            loom_content_client: interface.ILoomContentClient,
    ):
        self.tracer = tel.tracer()
        self.logger = tel.logger()
        self.bot = bot
        self.state_repo = state_repo
        self.loom_content_client = loom_content_client

    async def handle_select_publication(
            self,
            callback: CallbackQuery,
            widget: Any,
            dialog_manager: DialogManager,
            publication_id: str
    ) -> None:
        """
        🎯 ОБРАБОТЧИК ВЫБОРА ЧЕРНОВИКА
        Сохраняет выбранную публикацию и переходит к превью
        """
        with self.tracer.start_as_current_span(
                "PublicationDraftService.handle_select_publication",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                # 💾 Сохраняем ID выбранной публикации
                dialog_manager.dialog_data["selected_publication_id"] = int(publication_id)
                
                self.logger.info(f"Выбрана публикация для редактирования: {publication_id}")

                # 🔄 Переходим к превью выбранной публикации (как в модерации)
                await dialog_manager.switch_to(model.PublicationDraftStates.edit_preview)

                span.set_status(Status(StatusCode.OK))
            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                await callback.answer("❌ Ошибка при выборе публикации", show_alert=True)
                raise

    async def handle_navigate_publication(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        """
        🎮 НАВИГАЦИЯ между черновиками (стрелки ⬅️➡️)
        Аналогично navigate_employee - переключение между публикациями
        """
        with self.tracer.start_as_current_span(
                "PublicationDraftService.handle_navigate_publication",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                button_id = button.widget_id
                all_publication_ids = dialog_manager.dialog_data.get("all_publication_ids", [])
                current_publication_id = int(dialog_manager.dialog_data.get("selected_publication_id"))

                if not all_publication_ids or current_publication_id not in all_publication_ids:
                    await callback.answer("❌ Ошибка навигации", show_alert=True)
                    return

                current_index = all_publication_ids.index(current_publication_id)

                # 🔄 Определяем новый индекс
                if button_id == "prev_publication" and current_index > 0:
                    new_publication_id = all_publication_ids[current_index - 1]
                elif button_id == "next_publication" and current_index < len(all_publication_ids) - 1:
                    new_publication_id = all_publication_ids[current_index + 1]
                else:
                    return

                # 💾 Обновляем выбранную публикацию
                dialog_manager.dialog_data["selected_publication_id"] = new_publication_id

                await dialog_manager.update(dialog_manager.dialog_data)
                span.set_status(Status(StatusCode.OK))
            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                raise

    async def handle_delete_publication(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        """
        🗑️ УДАЛЕНИЕ ЧЕРНОВИКА
        """
        with self.tracer.start_as_current_span(
                "PublicationDraftService.handle_delete_publication",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                publication_id = int(dialog_manager.dialog_data.get("selected_publication_id"))
                
                # 🗑️ Удаляем через API
                await self.loom_content_client.delete_publication(publication_id)
                
                self.logger.info(f"Черновик публикации удален: {publication_id}")
                
                await callback.answer("✅ Черновик удален!", show_alert=True)
                
                # 🔄 Возвращаемся к списку
                dialog_manager.dialog_data.pop("selected_publication_id", None)
                await dialog_manager.switch_to(model.PublicationDraftStates.publication_list)

                span.set_status(Status(StatusCode.OK))
            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                await callback.answer("❌ Ошибка при удалении", show_alert=True)
                raise

    async def handle_save_changes(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        """
        💾 СОХРАНЕНИЕ ИЗМЕНЕНИЙ в черновике
        """
        with self.tracer.start_as_current_span(
                "PublicationDraftService.handle_save_changes",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                publication_id = int(dialog_manager.dialog_data.get("selected_publication_id"))
                
                # 📝 Получаем измененные данные из dialog_data
                text = dialog_manager.dialog_data.get("publication_content")
                # Обновляем только поддерживаемые поля клиента: текст и изображение (если нужно)
                await self.loom_content_client.change_publication(
                    publication_id=publication_id,
                    text=text,
                )
                
                self.logger.info("Изменения в черновике сохранены")
                
                await callback.answer("✅ Изменения сохранены!", show_alert=True)
                span.set_status(Status(StatusCode.OK))
            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                await callback.answer("❌ Ошибка сохранения", show_alert=True)
                raise

    # 📝 ОБРАБОТЧИКИ РЕДАКТИРОВАНИЯ (копируем из generate_publication)
    
    async def handle_edit_title_save(
            self,
            message: Message,
            widget: Any,
            dialog_manager: DialogManager,
            text: str
    ) -> None:
        """📝 Сохранение нового названия"""
        try:
            await message.delete()
            new_title = text.strip()

            if not new_title:
                dialog_manager.dialog_data["has_void_title"] = True
                await dialog_manager.switch_to(model.PublicationDraftStates.edit_title)
                return

            # ✅ Очищаем ошибки и сохраняем
            dialog_manager.dialog_data.pop("has_void_title", None)
            dialog_manager.dialog_data["publication_title"] = new_title

            # 💾 Сохраняем в API (только название, текст остается прежним)
            publication_id = int(dialog_manager.dialog_data.get("selected_publication_id"))
            current_text = dialog_manager.dialog_data.get("publication_content", "")
            await self.loom_content_client.change_publication(
                publication_id=publication_id,
                text=f"{new_title}\n\n{current_text}" if current_text else new_title
            )

            self.logger.info("Название черновика изменено")
            await dialog_manager.switch_to(model.PublicationDraftStates.edit_preview)
        except Exception as err:
            await message.answer("❌ Ошибка при сохранении названия")
            raise

    async def handle_edit_description_save(
            self,
            message: Message,
            widget: Any,
            dialog_manager: DialogManager,
            text: str
    ) -> None:
        """📝 Сохранение описания"""
        try:
            await message.delete()
            new_description = text.strip()
            
            dialog_manager.dialog_data["publication_description"] = new_description
            self.logger.info("Описание черновика изменено")
            await dialog_manager.switch_to(model.PublicationDraftStates.edit_preview)
        except Exception as err:
            await message.answer("❌ Ошибка при сохранении описания")
            raise

    async def handle_edit_content_save(
            self,
            message: Message,
            widget: Any,
            dialog_manager: DialogManager,
            text: str
    ) -> None:
        """📄 Сохранение основного текста"""
        try:
            await message.delete()
            new_content = text.strip()

            if not new_content:
                dialog_manager.dialog_data["has_void_content"] = True
                await dialog_manager.switch_to(model.PublicationDraftStates.edit_content)
                return

            dialog_manager.dialog_data.pop("has_void_content", None)
            dialog_manager.dialog_data["publication_content"] = new_content

            # 💾 Сохраняем в API
            publication_id = int(dialog_manager.dialog_data.get("selected_publication_id"))
            current_title = dialog_manager.dialog_data.get("publication_title", "")
            await self.loom_content_client.change_publication(
                publication_id=publication_id,
                text=f"{current_title}\n\n{new_content}"  # Объединяем название и текст
            )

            self.logger.info("Содержимое черновика изменено")
            await dialog_manager.switch_to(model.PublicationDraftStates.edit_preview)
        except Exception as err:
            await message.answer("❌ Ошибка при сохранении текста")
            raise

    async def handle_edit_tags_save(
            self,
            message: Message,
            widget: Any,
            dialog_manager: DialogManager,
            text: str
    ) -> None:
        """🏷️ Сохранение тегов"""
        try:
            await message.delete()
            tags_raw = text.strip()
            
            if tags_raw:
                tags = [tag.strip() for tag in tags_raw.split(",")]
                tags = [tag for tag in tags if tag]  # Убираем пустые
            else:
                tags = []
            
            dialog_manager.dialog_data["publication_tags"] = tags
            
            # 💾 Теги сохраняем только локально (API не поддерживает)
            # В будущем можно добавить поддержку тегов в API
            self.logger.info(f"Теги черновика изменены: {tags}")
            await dialog_manager.switch_to(model.PublicationDraftStates.edit_preview)
        except Exception as err:
            await message.answer("❌ Ошибка при сохранении тегов")
            raise

    async def handle_remove_image(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        """🗑️ Удаление изображения из черновика"""
        try:
            publication_id = int(dialog_manager.dialog_data.get("selected_publication_id"))
            
            # Удаляем изображение через API
            await self.loom_content_client.delete_publication_image(publication_id)
            
            # Обновляем флаг
            dialog_manager.dialog_data["has_image"] = False
            
            await callback.answer("✅ Изображение удалено!", show_alert=True)
            await dialog_manager.switch_to(model.PublicationDraftStates.edit_preview)
        except Exception as err:
            await callback.answer("❌ Ошибка удаления изображения", show_alert=True)
            raise

    async def handle_image_upload(
            self,
            message: Message,
            widget: Any,
            dialog_manager: DialogManager
    ) -> None:
        """📤 Загрузка изображения в черновик"""
        try:
            if not message.photo:
                await message.answer("❌ Отправьте изображение")
                return
                
            await message.delete()
            
            publication_id = int(dialog_manager.dialog_data.get("selected_publication_id"))
            photo = message.photo[-1]  # Берем самое большое разрешение
            
            # Скачиваем изображение
            image_content = await self.bot.download(photo.file_id)
            image_filename = f"{photo.file_id}.jpg"
            
            # Обновляем публикацию с новым изображением
            await self.loom_content_client.change_publication(
                publication_id=publication_id,
                image_content=image_content.read(),
                image_filename=image_filename
            )
            
            # Обновляем флаг
            dialog_manager.dialog_data["has_image"] = True
            
            await message.answer("✅ Изображение загружено!")
            await dialog_manager.switch_to(model.PublicationDraftStates.edit_preview)
        except Exception as err:
            await message.answer("❌ Ошибка загрузки изображения")
            raise

    async def handle_edit_image_menu_save(
            self,
            message: Message,
            widget: Any,
            dialog_manager: DialogManager,
            text: str
    ) -> None:
        """🖼️ Генерация изображения по промпту (как в модерации)"""
        try:
            await message.delete()
            prompt = text.strip() if isinstance(text, str) else ""
            dialog_manager.dialog_data.pop("has_void_image_prompt", None)
            dialog_manager.dialog_data.pop("has_small_image_prompt", None)
            dialog_manager.dialog_data.pop("has_big_image_prompt", None)

            if not prompt:
                dialog_manager.dialog_data["has_void_image_prompt"] = True
                return
            if len(prompt) < 5:
                dialog_manager.dialog_data["has_small_image_prompt"] = True
                return
            if len(prompt) > 500:
                dialog_manager.dialog_data["has_big_image_prompt"] = True
                return

            dialog_manager.dialog_data["image_prompt"] = prompt

            # Берём контекст публикации
            publication_id = int(dialog_manager.dialog_data.get("selected_publication_id"))
            category_id = dialog_manager.dialog_data.get("publication_category_id")
            publication_text = dialog_manager.dialog_data.get("publication_content", "")

            # Текущее изображение как подсказка (если есть)
            current_image_content = None
            current_image_filename = None

            # Генерация изображения через API
            images_url = await self.loom_content_client.generate_publication_image(
                category_id=category_id,
                publication_text=publication_text,
                text_reference=dialog_manager.dialog_data.get("publication_title", ""),
                prompt=prompt,
                image_content=current_image_content,
                image_filename=current_image_filename,
            )

            # Обновляем флаги/превью
            dialog_manager.dialog_data["has_image"] = bool(images_url)
            await message.answer("✅ Изображение сгенерировано")
        except Exception as err:
            await message.answer("❌ Ошибка обработки изображения")
            raise

    # 🔄 РЕГЕНЕРАЦИЯ ТЕКСТА
    
    async def handle_regenerate_text(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        """🔄 Полная регенерация текста черновика"""
        try:
            await callback.answer()
            
            # Показываем индикатор загрузки
            dialog_manager.dialog_data["is_regenerating_text"] = True
            dialog_manager.dialog_data["regenerate_prompt"] = ""
            await dialog_manager.show()
            
            publication_id = int(dialog_manager.dialog_data.get("selected_publication_id"))
            
            category_id = dialog_manager.dialog_data.get("publication_category_id")
            publication_text = dialog_manager.dialog_data.get("publication_content", "")

            regenerated_data = await self.loom_content_client.regenerate_publication_text(
                category_id=category_id,
                publication_text=publication_text,
                prompt=None,
            )

            dialog_manager.dialog_data["publication_content"] = regenerated_data["text"]
            dialog_manager.dialog_data["is_regenerating_text"] = False
            
            # Сохраняем в API
            current_title = dialog_manager.dialog_data.get("publication_title", "")
            await self.loom_content_client.change_publication(
                publication_id=publication_id,
                text=f"{current_title}\n\n{regenerated_data['text']}"
            )
            
            await dialog_manager.switch_to(model.PublicationDraftStates.edit_preview)
        except Exception as err:
            await callback.answer("❌ Ошибка регенерации", show_alert=True)
            raise

    async def handle_regenerate_text_with_prompt(
            self,
            message: Message,
            widget: Any,
            dialog_manager: DialogManager,
            prompt: str
    ) -> None:
        """🔄 Регенерация с промптом"""
        try:
            await message.delete()
            
            # Очищаем флаги ошибок
            dialog_manager.dialog_data.pop("has_void_regenerate_prompt", None)
            dialog_manager.dialog_data.pop("has_small_regenerate_prompt", None)
            dialog_manager.dialog_data.pop("has_big_regenerate_prompt", None)
            
            prompt = prompt.strip()
            
            # Валидация промпта
            if not prompt:
                dialog_manager.dialog_data["has_void_regenerate_prompt"] = True
                await dialog_manager.switch_to(model.PublicationDraftStates.regenerate_text)
                return
                
            if len(prompt) < 5:
                dialog_manager.dialog_data["has_small_regenerate_prompt"] = True
                await dialog_manager.switch_to(model.PublicationDraftStates.regenerate_text)
                return
                
            if len(prompt) > 500:
                dialog_manager.dialog_data["has_big_regenerate_prompt"] = True
                await dialog_manager.switch_to(model.PublicationDraftStates.regenerate_text)
                return
                
            # Показываем индикатор загрузки
            dialog_manager.dialog_data["is_regenerating_text"] = True
            dialog_manager.dialog_data["regenerate_prompt"] = prompt
            await dialog_manager.show()
                
            category_id = dialog_manager.dialog_data.get("publication_category_id")
            publication_text = dialog_manager.dialog_data.get("publication_content", "")

            regenerated_data = await self.loom_content_client.regenerate_publication_text(
                category_id=category_id,
                publication_text=publication_text,
                prompt=prompt,
            )

            # Обновляем данные
            dialog_manager.dialog_data["publication_content"] = regenerated_data["text"]
            dialog_manager.dialog_data["is_regenerating_text"] = False
            
            # Сохраняем в API
            publication_id = int(dialog_manager.dialog_data.get("selected_publication_id"))
            current_title = dialog_manager.dialog_data.get("publication_title", "")
            await self.loom_content_client.change_publication(
                publication_id=publication_id,
                text=f"{current_title}\n\n{regenerated_data['text']}"
            )
            
            await dialog_manager.switch_to(model.PublicationDraftStates.edit_preview)
        except Exception as err:
            await message.answer("❌ Ошибка регенерации")
            raise

    # 🌐 СОЦИАЛЬНЫЕ СЕТИ
    
    async def handle_toggle_social_network(
            self,
            callback: CallbackQuery,
            checkbox: Any,
            dialog_manager: DialogManager
    ) -> None:
        """🌐 Переключение соцсетей"""
        try:
            if "selected_social_networks" not in dialog_manager.dialog_data:
                dialog_manager.dialog_data["selected_social_networks"] = {}

            network_id = checkbox.widget_id
            is_checked = checkbox.is_checked()
            dialog_manager.dialog_data["selected_social_networks"][network_id] = is_checked

            await callback.answer()
        except Exception as err:
            await callback.answer("❌ Ошибка", show_alert=True)
            raise

    # 🚀 ПУБЛИКАЦИЯ
    
    async def handle_send_to_moderation_with_networks_publication(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        """📤 Отправка на модерацию"""
        try:
            publication_id = int(dialog_manager.dialog_data.get("selected_publication_id"))
            
            # 📤 Отправляем на модерацию
            await self.loom_content_client.send_publication_to_moderation(publication_id)
            
            await callback.answer("📤 Отправлено на модерацию!", show_alert=True)
            await dialog_manager.start(model.ContentMenuStates.content_menu, mode=StartMode.RESET_STACK)
        except Exception as err:
            await callback.answer("❌ Ошибка отправки", show_alert=True)
            raise

    async def handle_publish_with_selected_networks_publication(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        """🚀 Публикация сейчас (точно как в модерации)"""
        with self.tracer.start_as_current_span(
                "PublicationDraftService.handle_publish_with_selected_networks",
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
                await self.loom_content_client.change_publication(
                    publication_id=publication_id,
                    tg_source=tg_source,
                    vk_source=vk_source,
                )

                # Одобряем публикацию
                await self.loom_content_client.moderate_publication(
                    publication_id=publication_id,
                    moderator_id=state.account_id,
                    moderation_status="approved",
                )

                post_links = await self.loom_content_client.moderate_publication(
                    publication_id,
                    state.account_id,
                    "approved"
                )

                dialog_manager.dialog_data["post_links"] = post_links

                self.logger.info("Черновик опубликован")
                await self._remove_current_publication_from_list(dialog_manager)
                await callback.answer("🎉 Опубликовано!", show_alert=True)

                await dialog_manager.start(model.ContentMenuStates.content_menu, mode=StartMode.RESET_STACK)
                span.set_status(Status(StatusCode.OK))

            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))

                await callback.answer("❌ Ошибка при публикации", show_alert=True)
                raise

    # 🔙 НАВИГАЦИЯ
    
    async def handle_back_to_publication_list(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        """🔙 Возврат к списку черновиков"""
        try:
            await dialog_manager.switch_to(model.PublicationDraftStates.publication_list)
        except Exception as err:
            await callback.answer("❌ Ошибка навигации", show_alert=True)
            raise

    async def handle_back_to_content_menu(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        """🔙 Возврат в контент-меню"""
        try:
            await dialog_manager.start(
                model.ContentMenuStates.content_menu,
                mode=StartMode.RESET_STACK
            )
        except Exception as err:
            await callback.answer("❌ Ошибка навигации", show_alert=True)
            raise

    async def handle_edit_menu_callback(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        """🔥 Обработчик для инлайн меню редактирования (как в модерации)"""
        try:
            # Отправляем инлайн клавиатуру с опциями редактирования
            await self.bot.send_message(
                chat_id=callback.from_user.id,
                text="✏️ <b>Выберите действие для редактирования:</b>",
                reply_markup=self._create_edit_menu_keyboard(callback, dialog_manager),
                parse_mode="HTML"
            )
            await callback.answer()
        except Exception as err:
            await callback.answer("❌ Ошибка", show_alert=True)
            self.logger.error(f"Ошибка в меню редактирования: {err}")
            raise

    def _create_edit_menu_keyboard(self, callback, dialog_manager):
        """📱 Создает инлайн клавиатуру для меню редактирования"""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📝 Изменить текст",
                        callback_data=f"edit_text_{callback.message.message_id}"
                    ),
                    InlineKeyboardButton(
                        text="🖼 Изменить изображение",
                        callback_data=f"edit_image_{callback.message.message_id}"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="🔄 Перегенерировать",
                        callback_data=f"regenerate_{callback.message.message_id}"
                    ),
                ],

                [
                    InlineKeyboardButton(
                        text="◀️ Назад к превью",
                        callback_data=f"back_preview_{callback.message.message_id}"
                    ),
                ],
            ]
        )

    async def handle_prev_image(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        """🖼️ Предыдущее изображение (копия из модерации)"""
        with self.tracer.start_as_current_span(
                "PublicationDraftService.handle_prev_image",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                working_pub = dialog_manager.dialog_data.get("working_publication", {})
                images_url = working_pub.get("generated_images_url", [])
                current_index = working_pub.get("current_image_index", 0)

                if current_index > 0:
                    dialog_manager.dialog_data["working_publication"]["current_image_index"] = current_index - 1
                else:
                    dialog_manager.dialog_data["working_publication"]["current_image_index"] = len(images_url) - 1

                await callback.answer()
                span.set_status(Status(StatusCode.OK))

            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                raise

    async def handle_next_image(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        """🖼️ Следующее изображение (копия из модерации)"""
        with self.tracer.start_as_current_span(
                "PublicationDraftService.handle_next_image",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                working_pub = dialog_manager.dialog_data.get("working_publication", {})
                images_url = working_pub.get("generated_images_url", [])
                current_index = working_pub.get("current_image_index", 0)

                if current_index < len(images_url) - 1:
                    dialog_manager.dialog_data["working_publication"]["current_image_index"] = current_index + 1
                else:
                    dialog_manager.dialog_data["working_publication"]["current_image_index"] = 0

                await callback.answer()
                span.set_status(Status(StatusCode.OK))

            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                raise

    # 🛠️ ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    
    def _has_changes(self, dialog_manager: DialogManager) -> bool:
        """🔍 Проверяет есть ли несохраненные изменения (копия из модерации)"""
        original = dialog_manager.dialog_data.get("original_publication", {})
        working = dialog_manager.dialog_data.get("working_publication", {})

        if not original or not working:
            return False

        # Сравниваем текстовые поля
        fields_to_compare = ["text"]
        for field in fields_to_compare:
            if original.get(field) != working.get(field):
                return True

        # Проверяем изменения изображения
        if original.get("has_image", False) != working.get("has_image", False):
            return True

        # Проверяем изменение URL изображения
        original_url = original.get("image_url", "")
        working_url = working.get("image_url", "")

        if working_url and original_url:
            if original_url != working_url:
                return True
        elif working_url != original_url:
            return True

        return False

    async def _save_publication_changes(self, dialog_manager: DialogManager) -> None:
        """💾 Сохраняет изменения публикации (копия из модерации)"""
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
            # Изображение было удалено
            should_delete_image = True

        elif working_has_image:
            # Проверяем тип изображения и получаем выбранное
            if working_pub.get("custom_image_file_id"):
                # Пользовательское изображение
                image_content = await self.bot.download(working_pub["custom_image_file_id"])
                image_filename = working_pub["custom_image_file_id"] + ".jpg"

            elif working_pub.get("generated_images_url"):
                # Выбранное из множественных сгенерированных
                images_url = working_pub["generated_images_url"]
                current_index = working_pub.get("current_image_index", 0)

                if current_index < len(images_url):
                    selected_url = images_url[current_index]
                    # Проверяем, изменилось ли изображение
                    original_url = original_pub.get("image_url", "")
                    if original_url != selected_url:
                        image_url = selected_url

            elif working_pub.get("image_url"):
                # Одиночное изображение
                original_url = original_pub.get("image_url", "")
                working_url = working_pub.get("image_url", "")

                if original_url != working_url:
                    image_url = working_url

        # Если нужно удалить изображение
        if should_delete_image:
            try:
                await self.loom_content_client.delete_publication_image(
                    publication_id=publication_id
                )
                self.logger.info(f"Deleted image for publication {publication_id}")
            except Exception as e:
                self.logger.warning(f"Failed to delete image: {str(e)}")

        # Обновляем публикацию через API
        if image_url or image_content:
            await self.loom_content_client.change_publication(
                publication_id=publication_id,
                text=working_pub["text"],
                image_url=image_url,
                image_content=image_content,
                image_filename=image_filename,
            )
        else:
            # Обновляем только текстовые поля
            await self.loom_content_client.change_publication(
                publication_id=publication_id,
                text=working_pub["text"],
            )

    async def _remove_current_publication_from_list(self, dialog_manager: DialogManager) -> None:
        """🗑️ Удаляет текущий черновик из списка после публикации"""
        # Для черновиков этого метода может не быть необходимости, 
        # поскольку мы перенаправляем в контент-меню
        pass

    async def _get_state(self, dialog_manager: DialogManager) -> model.UserState:
        """Получение состояния пользователя"""
        if hasattr(dialog_manager.event, 'message') and dialog_manager.event.message:
            chat_id = dialog_manager.event.message.chat.id
        elif hasattr(dialog_manager.event, 'chat'):
            chat_id = dialog_manager.event.chat.id
        else:
            raise ValueError("Cannot extract chat_id from dialog_manager")

        state = await self.state_repo.state_by_id(chat_id)
        if not state:
            raise ValueError(f"State not found for chat_id: {chat_id}")
        return state[0]