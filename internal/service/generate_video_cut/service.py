import re
from typing import Any
from aiogram.types import Message
from aiogram_dialog import DialogManager, StartMode

from opentelemetry.trace import SpanKind, Status, StatusCode

from internal import interface, model


class GenerateVideoCutService(interface.IGenerateVideoCutService):
    def __init__(
            self,
            tel: interface.ITelemetry,
            state_repo: interface.IStateRepo,
            kontur_content_client: interface.IKonturContentClient,
    ):
        self.tracer = tel.tracer()
        self.logger = tel.logger()
        self.state_repo = state_repo
        self.kontur_content_client = kontur_content_client

    async def handle_youtube_link_input(
            self,
            message: Message,
            message_input: Any,
            dialog_manager: DialogManager
    ) -> None:
        with self.tracer.start_as_current_span(
                "GenerateVideoCutService.handle_youtube_link_input",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                youtube_url = message.text.strip()

                # Валидация YouTube ссылки
                if not self._is_valid_youtube_url(youtube_url):
                    await message.answer(
                        "❌ <b>Неверная ссылка на YouTube</b>\n\n"
                        "Пожалуйста, отправьте корректную ссылку на YouTube видео.\n"
                        "Например: https://www.youtube.com/watch?v=VIDEO_ID",
                        parse_mode="HTML"
                    )
                    return

                # Получаем состояние пользователя
                state = await self._get_state(dialog_manager)

                # Запускаем обработку видео асинхронно
                await self.kontur_content_client.generate_video_cut(
                    state.organization_id,
                    state.account_id,
                    youtube_url,
                )

                # Отправляем уведомление о начале обработки
                await message.answer(
                    "⏳ <b>Видео обрабатывается</b>\n\n"
                    "Я создам короткие видео из вашей ссылки.\n"
                    "Это может занять несколько минут.\n\n"
                    "📩 <b>Я уведомлю вас, как только видео будут готовы!</b>\n"
                    "Готовые видео появятся в разделе \"Черновики\" → \"Черновики видео-нарезок\"",
                    parse_mode="HTML"
                )

                # Возвращаем пользователя в главное меню
                await dialog_manager.start(
                    model.MainMenuStates.main_menu,
                    mode=StartMode.RESET_STACK
                )

                self.logger.info("YouTube ссылка принята к обработке")

                span.set_status(Status(StatusCode.OK))

            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                raise err

    def _is_valid_youtube_url(self, url: str) -> bool:
        youtube_regex = re.compile(
            r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/'
            r'(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})'
        )
        return bool(youtube_regex.match(url))

    async def _get_state(self, dialog_manager: DialogManager) -> model.UserState:
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
