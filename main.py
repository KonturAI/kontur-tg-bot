import uvicorn
from aiogram import Bot, Dispatcher
import redis.asyncio as redis
from aiogram.fsm.storage.base import DefaultKeyBuilder
from aiogram.fsm.storage.redis import RedisStorage
from aiohttp import ClientTimeout

from infrastructure.pg.pg import PG
from infrastructure.telemetry.telemetry import Telemetry, AlertManager

from pkg.client.internal.kontur_account.client import KonturAccountClient
from pkg.client.internal.kontur_authorization.client import KonturAuthorizationClient
from pkg.client.internal.kontur_employee.client import KonturEmployeeClient
from pkg.client.internal.kontur_organization.client import KonturOrganizationClient
from pkg.client.internal.kontur_content.client import KonturContentClient

from internal.controller.http.middlerware.middleware import HttpMiddleware
from internal.controller.tg.middleware.middleware import TgMiddleware

from internal.controller.tg.command.handler import CommandController
from internal.controller.http.webhook.handler import TelegramWebhookController

from internal.controller.tg.dialog.auth.dialog import AuthDialog
from internal.controller.tg.dialog.main_menu.dialog import MainMenuDialog
from internal.controller.tg.dialog.personal_profile.dialog import PersonalProfileDialog
from internal.controller.tg.dialog.organization_menu.dialog import OrganizationMenuDialog
from internal.controller.tg.dialog.change_employee.dialog import ChangeEmployeeDialog
from internal.controller.tg.dialog.add_employee.dialog import AddEmployeeDialog
from internal.controller.tg.dialog.content_menu.dialog import ContentMenuDialog
from internal.controller.tg.dialog.generate_publication.dialog import GeneratePublicationDialog
from internal.controller.tg.dialog.generate_video_cut.dialog import GenerateVideoCutDialog
from internal.controller.tg.dialog.moderation_publication.dialog import ModerationPublicationDialog
from internal.controller.tg.dialog.video_cut_draft_content.dialog import VideoCutsDraftDialog
from internal.controller.tg.dialog.publication_draft_content.dialog import PublicationDraftDialog

from internal.service.state.service import StateService
from internal.service.auth.service import AuthDialogService
from internal.service.main_menu.service import MainMenuDialogService
from internal.service.personal_profile.service import PersonalProfileDialogService
from internal.service.organization_menu.service import OrganizationMenuDialogService
from internal.service.change_employee.service import ChangeEmployeeDialogService
from internal.service.add_employee.service import AddEmployeeDialogService
from internal.service.content_menu.service import ContentMenuDialogService
from internal.service.generate_publication.service import GeneratePublicationDialogService
from internal.service.generate_video_cut.service import GenerateVideoCutDialogService
from internal.service.moderation_publication.service import ModerationPublicationDialogService
from internal.service.video_cut_draft_content.service import VideoCutsDraftDialogService
from internal.service.publication_draft_content.service import PublicationDraftDialogService

from internal.repo.state.repo import StateRepo

from internal.app.tg.app import NewTg

from internal.config.config import Config

cfg = Config()

# Инициализация мониторинга
alert_manager = AlertManager(
    cfg.alert_tg_bot_token,
    cfg.service_name,
    cfg.alert_tg_chat_id,
    cfg.alert_tg_chat_thread_id,
    cfg.grafana_url,
    cfg.monitoring_redis_host,
    cfg.monitoring_redis_port,
    cfg.monitoring_redis_db,
    cfg.monitoring_redis_password
)

tel = Telemetry(
    cfg.log_level,
    cfg.root_path,
    cfg.environment,
    cfg.service_name,
    cfg.service_version,
    cfg.otlp_host,
    cfg.otlp_port,
    alert_manager
)

bot = Bot(
    cfg.tg_bot_token,
    timeout=ClientTimeout(total=120)
)
redis_client = redis.Redis(
    host=cfg.monitoring_redis_host,
    port=cfg.monitoring_redis_port,
    password=cfg.monitoring_redis_password,
    db=2
)
key_builder = DefaultKeyBuilder(with_destiny=True)
storage = RedisStorage(
    redis=redis_client,
    key_builder=key_builder
)
dp = Dispatcher(storage=storage)

# Инициализация клиентов
db = PG(tel, cfg.db_user, cfg.db_pass, cfg.db_host, cfg.db_port, cfg.db_name)
kontur_account_client = KonturAccountClient(tel, cfg.kontur_account_host, cfg.kontur_account_port)
kontur_authorization_client = KonturAuthorizationClient(tel, cfg.kontur_authorization_host,
                                                        cfg.kontur_authorization_port)
kontur_employee_client = KonturEmployeeClient(tel, cfg.kontur_employee_host, cfg.kontur_employee_port)
kontur_organization_client = KonturOrganizationClient(tel, cfg.kontur_organization_host, cfg.kontur_organization_port)
kontur_content_client = KonturContentClient(tel, cfg.kontur_content_host, cfg.kontur_content_port)

state_repo = StateRepo(tel, db)

state_service = StateService(tel, state_repo)
auth_dialog_service = AuthDialogService(
    tel,
    state_repo,
    cfg.domain,
    kontur_account_client,
    kontur_organization_client,
    kontur_employee_client,
)
main_menu_service = MainMenuDialogService(
    tel,
    state_repo,
    kontur_employee_client,
    kontur_organization_client
)
personal_profile_service = PersonalProfileDialogService(
    tel,
    state_repo,
    kontur_employee_client,
    kontur_organization_client
)
organization_menu_service = OrganizationMenuDialogService(
    tel,
    state_repo,
    kontur_organization_client,
    kontur_employee_client,
    kontur_content_client,
)
change_employee_service = ChangeEmployeeDialogService(
    tel,
    bot,
    state_repo,
    kontur_employee_client,
    kontur_organization_client,
    kontur_content_client
)

add_employee_service = AddEmployeeDialogService(
    tel,
    bot,
    state_repo,
    kontur_employee_client,
)

content_menu_service = ContentMenuDialogService(
    tel,
    state_repo,
    kontur_employee_client,
    kontur_organization_client,
    kontur_content_client,
)

generate_publication_service = GeneratePublicationDialogService(
    tel,
    bot,
    state_repo,
    kontur_employee_client,
    kontur_organization_client,
    kontur_content_client,
)

generate_video_cut_service = GenerateVideoCutDialogService(
    tel,
    state_repo,
    kontur_employee_client,
    kontur_content_client,
)

moderation_publication_service = ModerationPublicationDialogService(
    tel,
    bot,
    state_repo,
    kontur_employee_client,
    kontur_organization_client,
    kontur_content_client,
)

video_cuts_draft_service = VideoCutsDraftDialogService(
    tel,
    state_repo,
    kontur_employee_client,
    kontur_organization_client,
    kontur_content_client,
)

publication_draft_service = PublicationDraftDialogService(
    tel,
    state_repo,
    kontur_employee_client,
    kontur_organization_client,
    kontur_content_client,
)

auth_dialog = AuthDialog(
    tel,
    auth_dialog_service,
)
main_menu_dialog = MainMenuDialog(
    tel,
    main_menu_service
)
personal_profile_dialog = PersonalProfileDialog(
    tel,
    personal_profile_service
)
organization_menu_dialog = OrganizationMenuDialog(
    tel,
    organization_menu_service
)
change_employee_dialog = ChangeEmployeeDialog(
    tel,
    change_employee_service
)

add_employee_dialog = AddEmployeeDialog(
    tel,
    add_employee_service
)

content_menu_dialog = ContentMenuDialog(
    tel,
    content_menu_service
)

generate_publication_dialog = GeneratePublicationDialog(
    tel,
    generate_publication_service
)

generate_video_cut_dialog = GenerateVideoCutDialog(
    tel,
    generate_video_cut_service
)

moderation_publication_dialog = ModerationPublicationDialog(
    tel,
    moderation_publication_service
)

video_cuts_draft_dialog = VideoCutsDraftDialog(
    tel,
    video_cuts_draft_service
)

publication_draft_dialog = PublicationDraftDialog(
    tel,
    publication_draft_service
)

# Инициализация middleware
tg_middleware = TgMiddleware(
    tel,
    state_service,
    bot,
)
http_middleware = HttpMiddleware(
    tel,
    cfg.prefix,
)
tg_webhook_controller = TelegramWebhookController(
    tel,
    dp,
    bot,
    state_service,
    cfg.domain,
    cfg.prefix,
    cfg.interserver_secret_key
)

command_controller = CommandController(tel, state_service)

if __name__ == "__main__":
    app = NewTg(
        db,
        dp,
        http_middleware,
        tg_middleware,
        tg_webhook_controller,
        command_controller,
        auth_dialog,
        main_menu_dialog,
        personal_profile_dialog,
        organization_menu_dialog,
        change_employee_dialog,
        add_employee_dialog,
        content_menu_dialog,
        generate_publication_dialog,
        generate_video_cut_dialog,
        moderation_publication_dialog,
        video_cuts_draft_dialog,
        publication_draft_dialog,
        cfg.prefix,
    )
    uvicorn.run(app, host="0.0.0.0", port=int(cfg.http_port), access_log=False)
