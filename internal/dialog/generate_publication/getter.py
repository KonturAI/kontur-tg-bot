from aiogram.types import ContentType
from aiogram_dialog import DialogManager
from aiogram_dialog.api.entities import MediaAttachment, MediaId
from aiogram_dialog.widgets.kbd import ManagedCheckbox

from opentelemetry.trace import SpanKind, Status, StatusCode

from internal import interface, model


class GeneratePublicationDataGetter(interface.IGeneratePublicationGetter):
    def __init__(
            self,
            tel: interface.ITelemetry,
            state_repo: interface.IStateRepo,
            loom_employee_client: interface.ILoomEmployeeClient,
            loom_content_client: interface.ILoomContentClient,
    ):
        self.tracer = tel.tracer()
        self.logger = tel.logger()
        self.state_repo = state_repo
        self.loom_employee_client = loom_employee_client
        self.loom_content_client = loom_content_client

    async def get_preview_data(
            self,
            dialog_manager: DialogManager,
            **kwargs
    ) -> dict:
        with self.tracer.start_as_current_span(
                "GeneratePublicationDataGetter.get_preview_data",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                state = await self._get_state(dialog_manager)
                employee = await self.loom_employee_client.get_employee_by_account_id(
                    state.account_id
                )

                text = dialog_manager.dialog_data.get("publication_text", "")

                # Check for image presence
                has_image = False
                preview_image_media = None
                has_multiple_images = False
                current_image_index = 0
                total_images = 0

                # Priority: custom image > generated images
                if dialog_manager.dialog_data.get("custom_image_file_id"):
                    has_image = True
                    file_id = dialog_manager.dialog_data["custom_image_file_id"]
                    preview_image_media = MediaAttachment(
                        file_id=MediaId(file_id),
                        type=ContentType.PHOTO
                    )
                elif dialog_manager.dialog_data.get("publication_images_url"):
                    has_image = True
                    images_url = dialog_manager.dialog_data["publication_images_url"]
                    current_image_index = dialog_manager.dialog_data.get("current_image_index", 0)
                    total_images = len(images_url)
                    has_multiple_images = total_images > 1

                    if current_image_index < len(images_url):
                        preview_image_media = MediaAttachment(
                            url=images_url[current_image_index],
                            type=ContentType.PHOTO
                        )

                selected_networks = dialog_manager.dialog_data.get("selected_social_networks", {})

                if not selected_networks:
                    social_networks = await self.loom_content_client.get_social_networks_by_organization(
                        organization_id=state.organization_id
                    )

                    telegram_connected = self._is_network_connected(social_networks, "telegram")
                    vkontakte_connected = self._is_network_connected(social_networks, "vkontakte")

                    if vkontakte_connected:
                        widget_id = "vkontakte_checkbox"
                        autoselect = social_networks["vkontakte"][0].get("autoselect", False)
                        selected_networks[widget_id] = autoselect

                    if telegram_connected:
                        widget_id = "telegram_checkbox"
                        autoselect = social_networks["telegram"][0].get("autoselect", False)
                        selected_networks[widget_id] = autoselect

                    dialog_manager.dialog_data["selected_social_networks"] = selected_networks

                requires_moderation = employee.required_moderation
                can_publish_directly = not requires_moderation

                data = {
                    "category_name": dialog_manager.dialog_data.get("category_name", ""),
                    "publication_text": text,
                    "has_scheduled_time": False,
                    "publish_time": "",
                    "has_image": has_image,
                    "preview_image_media": preview_image_media,
                    "has_multiple_images": has_multiple_images,
                    "current_image_index": current_image_index + 1,  # Show to user starting from 1
                    "total_images": total_images,
                    "requires_moderation": requires_moderation,
                    "can_publish_directly": can_publish_directly,
                    "is_custom_image": dialog_manager.dialog_data.get("is_custom_image", False),
                }

                span.set_status(Status(StatusCode.OK))
                return data
            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                raise

    async def get_social_network_select_data(
            self,
            dialog_manager: DialogManager,
            **kwargs
    ) -> dict:
        with self.tracer.start_as_current_span(
                "GeneratePublicationDataGetter.get_social_network_select_data",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                state = await self._get_state(dialog_manager)

                social_networks = await self.loom_content_client.get_social_networks_by_organization(
                    organization_id=state.organization_id
                )

                telegram_connected = self._is_network_connected(social_networks, "telegram")
                vkontakte_connected = self._is_network_connected(social_networks, "vkontakte")

                selected_networks = dialog_manager.dialog_data.get("selected_social_networks", {})

                if vkontakte_connected:
                    widget_id = "vkontakte_checkbox"
                    vkontakte_checkbox: ManagedCheckbox = dialog_manager.find(widget_id)
                    await vkontakte_checkbox.set_checked(selected_networks[widget_id])

                if telegram_connected:
                    widget_id = "telegram_checkbox"
                    telegram_checkbox: ManagedCheckbox = dialog_manager.find(widget_id)
                    await telegram_checkbox.set_checked(selected_networks[widget_id])

                data = {
                    "telegram_connected": telegram_connected,
                    "vkontakte_connected": vkontakte_connected,
                    "no_connected_networks": not telegram_connected and not vkontakte_connected,
                    "has_available_networks": telegram_connected or vkontakte_connected,
                }

                span.set_status(Status(StatusCode.OK))
                return data

            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                raise

    async def get_input_text_data(
            self,
            dialog_manager: DialogManager,
            **kwargs
    ) -> dict:
        return {
            "category_name": dialog_manager.dialog_data.get("category_name", ""),
            "input_text": dialog_manager.dialog_data.get("input_text", ""),
            "has_input_text": dialog_manager.dialog_data.get("has_input_text", False),
            "voice_transcribe": dialog_manager.dialog_data.get("voice_transcribe", False),
            # Text input error flags
            "has_void_input_text": dialog_manager.dialog_data.get("has_void_input_text", False),
            "has_small_input_text": dialog_manager.dialog_data.get("has_small_input_text", False),
            "has_big_input_text": dialog_manager.dialog_data.get("has_big_input_text", False),
            # Voice input error flags
            "has_invalid_voice_type": dialog_manager.dialog_data.get("has_invalid_voice_type", False),
            "has_long_voice_duration": dialog_manager.dialog_data.get("has_long_voice_duration", False),
            "has_empty_voice_text": dialog_manager.dialog_data.get("has_empty_voice_text", False),
        }

    async def get_categories_data(
            self,
            dialog_manager: DialogManager,
            **kwargs
    ) -> dict:
        with self.tracer.start_as_current_span(
                "GeneratePublicationDataGetter.get_categories_data",
                kind=SpanKind.INTERNAL
        ) as span:
            try:
                state = await self._get_state(dialog_manager)
                employee = await self.loom_employee_client.get_employee_by_account_id(
                    state.account_id
                )

                categories = await self.loom_content_client.get_categories_by_organization(
                    employee.organization_id
                )

                categories_data = []
                for category in categories:
                    categories_data.append({
                        "id": category.id,
                        "name": category.name,
                        "image_style": category.prompt_for_image_style,
                    })

                data = {
                    "categories": categories_data,
                    "has_categories": len(categories_data) > 0,
                }

                self.logger.info("Категории загружены")

                span.set_status(Status(StatusCode.OK))
                return data
            except Exception as err:
                span.record_exception(err)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                raise

    async def get_edit_text_data(
            self,
            dialog_manager: DialogManager,
            **kwargs
    ) -> dict:
        return {
            "publication_text": dialog_manager.dialog_data.get("publication_text", ""),
            "regenerate_prompt": dialog_manager.dialog_data.get("regenerate_prompt", ""),
            "has_regenerate_prompt": bool(dialog_manager.dialog_data.get("regenerate_prompt", "")),
            "is_regenerating_text": dialog_manager.dialog_data.get("is_regenerating_text", False),
            # Error flags
            "has_void_text": dialog_manager.dialog_data.get("has_void_text", False),
            "has_small_text": dialog_manager.dialog_data.get("has_small_text", False),
            "has_big_text": dialog_manager.dialog_data.get("has_big_text", False),
        }

    async def get_image_menu_data(
            self,
            dialog_manager: DialogManager,
            **kwargs
    ) -> dict:
        has_image = False
        preview_image_media = None

        # Priority: custom image > generated images
        if dialog_manager.dialog_data.get("custom_image_file_id"):
            has_image = True
            file_id = dialog_manager.dialog_data["custom_image_file_id"]
            preview_image_media = MediaAttachment(
                file_id=MediaId(file_id),
                type=ContentType.PHOTO
            )
        elif dialog_manager.dialog_data.get("publication_images_url"):
            has_image = True
            images_url = dialog_manager.dialog_data["publication_images_url"]
            current_image_index = dialog_manager.dialog_data.get("current_image_index", 0)

            if current_image_index < len(images_url):
                preview_image_media = MediaAttachment(
                    url=images_url[current_image_index],
                    type=ContentType.PHOTO
                )

        return {
            "has_image": has_image,
            "is_custom_image": dialog_manager.dialog_data.get("is_custom_image", False),
            "has_image_prompt": dialog_manager.dialog_data.get("image_prompt", "") != "",
            "image_prompt": dialog_manager.dialog_data.get("image_prompt", ""),
            "is_generating_image": dialog_manager.dialog_data.get("is_generating_image", False),
            "preview_image_media": preview_image_media,
            # Error flags
            "has_void_image_prompt": dialog_manager.dialog_data.get("has_void_image_prompt", False),
            "has_small_image_prompt": dialog_manager.dialog_data.get("has_small_image_prompt", False),
            "has_big_image_prompt": dialog_manager.dialog_data.get("has_big_image_prompt", False),
        }

    async def get_upload_image_data(
            self,
            dialog_manager: DialogManager,
            **kwargs
    ) -> dict:
        return {
            # Error flags
            "has_invalid_image_type": dialog_manager.dialog_data.get("has_invalid_image_type", False),
            "has_big_image_size": dialog_manager.dialog_data.get("has_big_image_size", False),
            "has_image_processing_error": dialog_manager.dialog_data.get("has_image_processing_error", False),
        }

    async def get_publication_success_data(
            self,
            dialog_manager: DialogManager,
            **kwargs
    ) -> dict:
        post_links = dialog_manager.dialog_data.get("post_links", {})

        telegram_link = post_links.get("telegram")
        vkontakte_link = post_links.get("vkontakte")

        return {
            "has_post_links": bool(post_links),
            "has_telegram_link": bool(telegram_link),
            "has_vkontakte_link": bool(vkontakte_link),
            "telegram_link": telegram_link or "",
            "vkontakte_link": vkontakte_link or "",
        }

    # Helper methods
    def _is_network_connected(self, social_networks: dict, network_type: str) -> bool:
        if not social_networks:
            return False
        return network_type in social_networks and len(social_networks[network_type]) > 0

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
