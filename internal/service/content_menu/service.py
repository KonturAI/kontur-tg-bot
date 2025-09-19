from typing import Any
from aiogram.types import CallbackQuery
from aiogram_dialog import DialogManager, StartMode

from opentelemetry.trace import SpanKind, Status, StatusCode

from internal import interface, model, common


class ContentMenuDialogService(interface.IContentMenuDialogService):
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

    async def get_content_menu_data(
            self,
            dialog_manager: DialogManager,
            **kwargs
    ) -> dict:
        with self.tracer.start_as_current_span(
                "ContentMenuDialogService.get_content_menu_data",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                state = await self._get_state(dialog_manager)

                # Получаем данные сотрудника
                employee = await self.kontur_employee_client.get_employee_by_account_id(
                    state.account_id
                )

                # Получаем статистику публикаций
                publications = await self.kontur_content_client.get_publications_by_organization(
                    employee.organization_id
                )

                # Получаем статистику видео-нарезок
                video_cuts = await self.kontur_content_client.get_video_cuts_by_organization(
                    employee.organization_id
                )

                # Подсчитываем статистику
                drafts_count = 0
                moderation_count = 0
                approved_count = 0
                published_count = 0
                total_generations = 0

                video_cut_count = 0
                publication_count = 0

                # Статистика публикаций
                for pub in publications:
                    total_generations += 1
                    publication_count += 1

                    if pub.moderation_status == "draft":
                        drafts_count += 1
                    elif pub.moderation_status == "moderation":
                        moderation_count += 1
                    elif pub.moderation_status == "approved":
                        approved_count += 1
                    elif pub.moderation_status == "published":
                        published_count += 1

                # Статистика видео-нарезок
                for video in video_cuts:
                    total_generations += 1
                    video_cut_count += 1

                    if video.moderation_status == "draft":
                        drafts_count += 1
                    elif video.moderation_status == "moderation":
                        moderation_count += 1
                    elif video.moderation_status == "approved":
                        approved_count += 1
                    elif video.moderation_status == "published":
                        published_count += 1

                data = {
                    "drafts_count": drafts_count,
                    "moderation_count": moderation_count,
                    "approved_count": approved_count,
                    "published_count": published_count,
                    "total_generations": total_generations,
                    "video_cut_count": video_cut_count,
                    "publication_count": publication_count,
                }

                self.logger.info(
                    "Данные меню контента загружены",
                    {
                        common.TELEGRAM_CHAT_ID_KEY: self._get_chat_id(dialog_manager),
                        "drafts_count": drafts_count,
                        "moderation_count": moderation_count,
                        "approved_count": approved_count,
                        "published_count": published_count,
                        "total_generations": total_generations,
                        "video_cut_count": video_cut_count,
                        "publication_count": publication_count,
                    }
                )

                span.set_status(Status(StatusCode.OK))
                return data

            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                raise err

    async def handle_go_to_publication_generation(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        with self.tracer.start_as_current_span(
                "ContentMenuDialogService.handle_go_to_publication_generation",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                # Запускаем диалог генерации публикации
                await dialog_manager.start(
                    model.GeneratePublicationStates.select_category,
                    mode=StartMode.RESET_STACK
                )

                self.logger.info(
                    "Переход к созданию публикации",
                    {
                        common.TELEGRAM_CHAT_ID_KEY: callback.message.chat.id,
                    }
                )

                span.set_status(Status(StatusCode.OK))
            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                await callback.answer("❌ Ошибка при переходе к созданию публикации", show_alert=True)
                raise

    async def handle_go_to_video_cut_generation(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        with self.tracer.start_as_current_span(
                "ContentMenuDialogService.handle_go_to_video_cut_generation",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                # Запускаем диалог генерации видео-нарезки
                await dialog_manager.start(
                    model.GenerateVideoCutStates.input_youtube_link,
                    mode=StartMode.RESET_STACK
                )

                self.logger.info(
                    "Переход к созданию видео-нарезки",
                    {
                        common.TELEGRAM_CHAT_ID_KEY: callback.message.chat.id,
                    }
                )

                span.set_status(Status(StatusCode.OK))
            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                await callback.answer("❌ Ошибка при переходе к созданию видео-нарезки", show_alert=True)
                raise

    async def handle_go_to_publication_drafts(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        with self.tracer.start_as_current_span(
                "ContentMenuDialogService.handle_go_to_publication_drafts",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                # Запускаем диалог черновиков публикаций
                await dialog_manager.start(
                    model.PublicationDraftStates.publication_list,
                    mode=StartMode.RESET_STACK
                )

                self.logger.info(
                    "Переход к черновикам публикаций",
                    {
                        common.TELEGRAM_CHAT_ID_KEY: callback.message.chat.id,
                    }
                )

                span.set_status(Status(StatusCode.OK))
            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                await callback.answer("❌ Ошибка при переходе к черновикам публикаций", show_alert=True)
                raise

    async def handle_go_to_video_drafts(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        with self.tracer.start_as_current_span(
                "ContentMenuDialogService.handle_go_to_video_drafts",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                # Запускаем диалог черновиков видео-нарезок
                await dialog_manager.start(
                    model.VideoCutsDraftStates.video_cut_list,
                    mode=StartMode.RESET_STACK
                )

                self.logger.info(
                    "Переход к черновикам видео-нарезок",
                    {
                        common.TELEGRAM_CHAT_ID_KEY: callback.message.chat.id,
                    }
                )

                span.set_status(Status(StatusCode.OK))
            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                await callback.answer("❌ Ошибка при переходе к черновикам видео", show_alert=True)
                raise

    async def handle_go_to_publication_moderation(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        with self.tracer.start_as_current_span(
                "ContentMenuDialogService.handle_go_to_publication_moderation",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                state = await self._get_state(dialog_manager)

                # Проверяем права доступа к модерации
                employee = await self.kontur_employee_client.get_employee_by_account_id(
                    state.account_id
                )

                can_moderate = (
                        employee.role in ["moderator", "admin", "owner"] or
                        employee.edit_employee_perm_permission
                )

                if not can_moderate:
                    await callback.answer(
                        "❌ У вас нет прав для доступа к модерации",
                        show_alert=True
                    )
                    return

                # Запускаем диалог модерации публикаций
                await dialog_manager.start(
                    model.ModerationPublicationStates.moderation_list,
                    mode=StartMode.RESET_STACK
                )

                self.logger.info(
                    "Переход к модерации публикаций",
                    {
                        common.TELEGRAM_CHAT_ID_KEY: callback.message.chat.id,
                        "employee_role": employee.role,
                    }
                )

                span.set_status(Status(StatusCode.OK))
            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                await callback.answer("❌ Ошибка при переходе к модерации публикаций", show_alert=True)
                raise

    async def handle_go_to_video_moderation(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        with self.tracer.start_as_current_span(
                "ContentMenuDialogService.handle_go_to_video_moderation",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                state = await self._get_state(dialog_manager)

                # Проверяем права доступа к модерации
                employee = await self.kontur_employee_client.get_employee_by_account_id(
                    state.account_id
                )

                can_moderate = (
                        employee.role in ["moderator", "admin", "owner"] or
                        employee.edit_employee_perm_permission
                )

                if not can_moderate:
                    await callback.answer(
                        "❌ У вас нет прав для доступа к модерации",
                        show_alert=True
                    )
                    return

                # Запускаем диалог модерации видео-нарезок
                await dialog_manager.start(
                    model.ModerationVideoCutStates.video_moderation_list,
                    mode=StartMode.RESET_STACK
                )

                self.logger.info(
                    "Переход к модерации видео-нарезок",
                    {
                        common.TELEGRAM_CHAT_ID_KEY: callback.message.chat.id,
                        "employee_role": employee.role,
                    }
                )

                span.set_status(Status(StatusCode.OK))
            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                await callback.answer("❌ Ошибка при переходе к модерации видео", show_alert=True)
                raise

    async def handle_go_to_main_menu(
            self,
            callback: CallbackQuery,
            button: Any,
            dialog_manager: DialogManager
    ) -> None:
        with self.tracer.start_as_current_span(
                "ContentMenuDialogService.handle_go_to_main_menu",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                await dialog_manager.start(
                    model.MainMenuStates.main_menu,
                    mode=StartMode.RESET_STACK
                )

                self.logger.info(
                    "Переход в главное меню",
                    {
                        common.TELEGRAM_CHAT_ID_KEY: callback.message.chat.id,
                    }
                )

                span.set_status(Status(StatusCode.OK))
            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                raise

    async def handle_go_to_content_menu(
                self,
                callback: CallbackQuery,
                button: Any,
                dialog_manager: DialogManager
        ) -> None:
            with self.tracer.start_as_current_span(
                    "ContentMenuDialogService.handle_go_to_content_menu",
                    kind=SpanKind.INTERNAL
            ) as span:
                try:
                    await dialog_manager.start(
                        model.ContentMenuStates.content_menu,
                        mode=StartMode.RESET_STACK
                    )

                    self.logger.info(
                        "Переход в контент меню",
                        {
                            common.TELEGRAM_CHAT_ID_KEY: callback.message.chat.id,
                        }
                    )

                    span.set_status(Status(StatusCode.OK))
                except Exception as err:
                    span.record_exception(err)
                    span.set_status(Status(StatusCode.ERROR, str(err)))
                    raise

    # Вспомогательные методы

    # Добавить эти методы в класс ContentMenuDialogService

    async def get_drafts_type_data(
            self,
            dialog_manager: DialogManager,
            **kwargs
    ) -> dict:
        with self.tracer.start_as_current_span(
                "ContentMenuDialogService.get_drafts_type_data",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                state = await self._get_state(dialog_manager)

                # Получаем данные сотрудника
                employee = await self.kontur_employee_client.get_employee_by_account_id(
                    state.account_id
                )

                # Получаем публикации организации
                publications = await self.kontur_content_client.get_publications_by_organization(
                    employee.organization_id
                )

                # Получаем видео-нарезки организации
                video_cuts = await self.kontur_content_client.get_video_cuts_by_organization(
                    employee.organization_id
                )

                # Подсчитываем черновики
                publication_drafts_count = sum(1 for pub in publications if pub.moderation_status == "draft")
                video_drafts_count = sum(1 for video in video_cuts if video.moderation_status == "draft")

                data = {
                    "publication_drafts_count": publication_drafts_count,
                    "video_drafts_count": video_drafts_count,
                }

                self.logger.info(
                    "Данные типов черновиков загружены",
                    {
                        common.TELEGRAM_CHAT_ID_KEY: self._get_chat_id(dialog_manager),
                        "publication_drafts_count": publication_drafts_count,
                        "video_drafts_count": video_drafts_count,
                    }
                )

                span.set_status(Status(StatusCode.OK))
                return data

            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                # В случае ошибки возвращаем данные по умолчанию
                return {
                    "publication_drafts_count": 0,
                    "video_drafts_count": 0,
                }

    async def get_moderation_type_data(
            self,
            dialog_manager: DialogManager,
            **kwargs
    ) -> dict:
        with self.tracer.start_as_current_span(
                "ContentMenuDialogService.get_moderation_type_data",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                state = await self._get_state(dialog_manager)

                # Получаем данные сотрудника
                employee = await self.kontur_employee_client.get_employee_by_account_id(
                    state.account_id
                )

                # Получаем публикации организации
                publications = await self.kontur_content_client.get_publications_by_organization(
                    employee.organization_id
                )

                # Получаем видео-нарезки организации
                video_cuts = await self.kontur_content_client.get_video_cuts_by_organization(
                    employee.organization_id
                )

                # Подсчитываем элементы на модерации
                publication_moderation_count = sum(1 for pub in publications if pub.moderation_status == "pending")
                video_moderation_count = sum(1 for video in video_cuts if video.moderation_status == "pending")

                data = {
                    "publication_moderation_count": publication_moderation_count,
                    "video_moderation_count": video_moderation_count,
                }

                self.logger.info(
                    "Данные типов модерации загружены",
                    {
                        common.TELEGRAM_CHAT_ID_KEY: self._get_chat_id(dialog_manager),
                        "publication_moderation_count": publication_moderation_count,
                        "video_moderation_count": video_moderation_count,
                    }
                )

                span.set_status(Status(StatusCode.OK))
                return data

            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                # В случае ошибки возвращаем данные по умолчанию
                return {
                    "publication_moderation_count": 0,
                    "video_moderation_count": 0,
                }

    async def _get_state(self, dialog_manager: DialogManager) -> model.UserState:
        """Получить состояние текущего пользователя"""
        chat_id = self._get_chat_id(dialog_manager)
        state = await self.state_repo.state_by_id(chat_id)
        if not state:
            raise ValueError(f"State not found for chat_id: {chat_id}")
        return state[0]

    def _get_chat_id(self, dialog_manager: DialogManager) -> int:
        """Получить chat_id из dialog_manager"""
        if hasattr(dialog_manager.event, 'message') and dialog_manager.event.message:
            return dialog_manager.event.message.chat.id
        elif hasattr(dialog_manager.event, 'chat'):
            return dialog_manager.event.chat.id
        else:
            raise ValueError("Cannot extract chat_id from dialog_manager")
