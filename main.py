import uvicorn
from aiogram import Bot, Dispatcher
import redis.asyncio as redis
from aiogram.fsm.storage.base import DefaultKeyBuilder
from aiogram.fsm.storage.redis import RedisStorage
from sulguk import AiogramSulgukMiddleware

from infrastructure.pg.pg import PG
from infrastructure.telemetry.telemetry import Telemetry, AlertManager

from pkg.client.internal.loom_account.client import LoomAccountClient
from pkg.client.internal.loom_authorization.client import LoomAuthorizationClient
from pkg.client.internal.loom_employee.client import LoomEmployeeClient
from pkg.client.internal.loom_organization.client import LoomOrganizationClient
from pkg.client.internal.loom_content.client import LoomContentClient


from internal.controller.http.middlerware.middleware import HttpMiddleware
from internal.controller.tg.middleware.middleware import TgMiddleware

from internal.controller.tg.command.handler import CommandController
from internal.controller.http.webhook.handler import TelegramWebhookController

from internal.dialog.auth.dialog import AuthDialog
from internal.dialog.main_menu.dialog import MainMenuDialog
from internal.dialog.organization_menu.dialog import OrganizationMenuDialog
from internal.dialog.personal_profile.dialog import PersonalProfileDialog
from internal.dialog.change_employee.dialog import ChangeEmployeeDialog
from internal.dialog.add_employee.dialog import AddEmployeeDialog
from internal.dialog.add_social_netwok.dialog import AddSocialNetworkDialog
from internal.dialog.content_menu.dialog import ContentMenuDialog
from internal.dialog.generate_publication.dialog import GeneratePublicationDialog
from internal.dialog.generate_video_cut.dialog import GenerateVideoCutDialog
from internal.dialog.moderation_publication.dialog import ModerationPublicationDialog
from internal.dialog.video_cut_draft_content.dialog import VideoCutsDraftDialog
from internal.dialog.moderation_video_cut.dialog import VideoCutModerationDialog
from internal.dialog.publication_draft_content.dialog import PublicationDraftDialog

from internal.service.state.service import StateService
from internal.dialog.auth.service import AuthService
from internal.dialog.main_menu.service import MainMenuService
from internal.dialog.organization_menu.service import OrganizationMenuService
from internal.dialog.content_menu.service import ContentMenuService
from internal.dialog.personal_profile.service import PersonalProfileService
from internal.dialog.change_employee.service import ChangeEmployeeService
from internal.dialog.add_employee.service import AddEmployeeService
from internal.dialog.add_social_netwok.service import AddSocialNetworkService
from internal.dialog.generate_publication.service import GeneratePublicationService
from internal.dialog.generate_video_cut.service import GenerateVideoCutService
from internal.dialog.moderation_publication.service import ModerationPublicationService
from internal.dialog.video_cut_draft_content.service import VideoCutsDraftService
from internal.dialog.moderation_video_cut.service import VideoCutModerationService
from internal.dialog.publication_draft_content.service import PublicationDraftService

from internal.dialog.auth.getter import AuthGetter
from internal.dialog.main_menu.getter import MainMenuGetter
from internal.dialog.organization_menu.getter import OrganizationMenuGetter
from internal.dialog.content_menu.getter import ContentMenuGetter
from internal.dialog.personal_profile.getter import PersonalProfileGetter
from internal.dialog.change_employee.getter import ChangeEmployeeGetter
from internal.dialog.add_employee.getter import AddEmployeeGetter
from internal.dialog.add_social_netwok.getter import AddSocialNetworkGetter
from internal.dialog.generate_publication.getter import GeneratePublicationDataGetter
from internal.dialog.moderation_publication.getter import ModerationPublicationGetter
from internal.dialog.generate_video_cut.getter import GenerateVideoCutGetter
from internal.dialog.video_cut_draft_content.getter import VideoCutsDraftGetter
from internal.dialog.moderation_video_cut.getter import VideoCutModerationGetter
from internal.dialog.publication_draft_content.getter import PublicationDraftGetter

from internal.repo.state.repo import StateRepo

from internal.app.tg.app import NewTg
from internal.app.server.app import NewServer

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
bot = Bot(token=cfg.tg_bot_token)
bot.session.middleware(AiogramSulgukMiddleware())

# Инициализация клиентов
db = PG(tel, cfg.db_user, cfg.db_pass, cfg.db_host, cfg.db_port, cfg.db_name)
loom_account_client = LoomAccountClient(tel, cfg.loom_account_host, cfg.loom_account_port)
loom_authorization_client = LoomAuthorizationClient(tel, cfg.loom_authorization_host,
                                                        cfg.loom_authorization_port)
loom_employee_client = LoomEmployeeClient(tel, cfg.loom_employee_host, cfg.loom_employee_port)
loom_organization_client = LoomOrganizationClient(tel, cfg.loom_organization_host, cfg.loom_organization_port)
loom_content_client = LoomContentClient(tel, cfg.loom_content_host, cfg.loom_content_port)

state_repo = StateRepo(tel, db)

# Инициализация геттеров
auth_getter = AuthGetter(
    tel,
    state_repo,
    cfg.domain
)

main_menu_getter = MainMenuGetter(
    tel,
    state_repo
)

organization_menu_getter = OrganizationMenuGetter(
    tel,
    state_repo,
    loom_organization_client,
    loom_employee_client,
    loom_content_client,
)

content_menu_getter = ContentMenuGetter(
    tel,
    state_repo,
    loom_employee_client,
    loom_content_client,
)
generate_publication_getter = GeneratePublicationDataGetter(
    tel,
    state_repo,
    loom_employee_client,
    loom_content_client,
)

moderation_publication_getter = ModerationPublicationGetter(
    tel,
    state_repo,
    loom_employee_client,
    loom_content_client,
    cfg.domain,
)

video_cut_moderation_getter = VideoCutModerationGetter(
    tel,
    state_repo,
    loom_employee_client,
    loom_content_client,
)

generate_video_cut_getter = GenerateVideoCutGetter(
    tel,
    state_repo
)

change_employee_getter = ChangeEmployeeGetter(
    tel,
    state_repo,
    loom_employee_client,
    loom_organization_client,
    loom_content_client
)

personal_profile_getter = PersonalProfileGetter(
    tel,
    state_repo,
    loom_employee_client,
    loom_organization_client,
    loom_content_client
)

video_cuts_draft_getter = VideoCutsDraftGetter(
    tel,
    state_repo,
    loom_employee_client,
    loom_organization_client,
    loom_content_client,
)

publication_draft_getter = PublicationDraftGetter(
    tel,
    state_repo,
    loom_employee_client,
    loom_content_client,
    cfg.domain,
)

add_employee_getter = AddEmployeeGetter(
    tel,
    state_repo,
    loom_employee_client,
)

add_social_network_getter = AddSocialNetworkGetter(
    tel,
    state_repo,
    loom_content_client,
)

# Инициализация сервисов
state_service = StateService(tel, state_repo)
auth_service = AuthService(
    tel,
    state_repo,
    loom_account_client,
    loom_employee_client,
)
main_menu_service = MainMenuService(
    tel,
    bot,
    state_repo,
    loom_content_client,
)
organization_menu_service = OrganizationMenuService(
    tel,
    state_repo
)
personal_profile_service = PersonalProfileService(
    tel,
)
change_employee_service = ChangeEmployeeService(
    tel,
    bot,
    state_repo,
    loom_employee_client
)

add_employee_service = AddEmployeeService(
    tel,
    state_repo,
    loom_employee_client,
)

content_menu_service = ContentMenuService(
    tel,
    state_repo,
    loom_employee_client,
)

generate_publication_service = GeneratePublicationService(
    tel,
    bot,
    state_repo,
    loom_content_client,
)

generate_video_cut_service = GenerateVideoCutService(
    tel,
    state_repo,
    loom_content_client,
)

moderation_publication_service = ModerationPublicationService(
    tel,
    bot,
    state_repo,
    loom_content_client,
)

video_cuts_draft_service = VideoCutsDraftService(
    tel,
    state_repo,
    loom_content_client,
)

publication_draft_service = PublicationDraftService(
    tel,
    bot,
    state_repo,
    loom_content_client,
)

video_cut_moderation_service = VideoCutModerationService(
    tel,
    bot,
    state_repo,
    loom_content_client,
)

add_social_network_service = AddSocialNetworkService(
    tel,
    state_repo,
    loom_content_client,
)

# Инициализация диалогов
auth_dialog = AuthDialog(
    tel,
    auth_service,
    auth_getter,
)
main_menu_dialog = MainMenuDialog(
    tel,
    main_menu_service,
    main_menu_getter
)
personal_profile_dialog = PersonalProfileDialog(
    tel,
    personal_profile_service,
    personal_profile_getter,
)
organization_menu_dialog = OrganizationMenuDialog(
    tel,
    organization_menu_service,
    organization_menu_getter
)
change_employee_dialog = ChangeEmployeeDialog(
    tel,
    change_employee_service,
    change_employee_getter
)

add_employee_dialog = AddEmployeeDialog(
    tel,
    add_employee_service,
    add_employee_getter,
)

content_menu_dialog = ContentMenuDialog(
    tel,
    content_menu_service,
    content_menu_getter,
)

generate_publication_dialog = GeneratePublicationDialog(
    tel,
    generate_publication_service,
    generate_publication_getter
)

generate_video_cut_dialog = GenerateVideoCutDialog(
    tel,
    generate_video_cut_service,
    generate_video_cut_getter,
)

moderation_publication_dialog = ModerationPublicationDialog(
    tel,
    moderation_publication_service,
    moderation_publication_getter,
)

video_cuts_draft_dialog = VideoCutsDraftDialog(
    tel,
    video_cuts_draft_service,
    video_cuts_draft_getter
)

publication_draft_dialog = PublicationDraftDialog(
    tel,
    publication_draft_service,
    publication_draft_getter,
)

video_cut_moderation_dialog = VideoCutModerationDialog(
    tel,
    video_cut_moderation_service,
    video_cut_moderation_getter,
)

add_social_network_dialog = AddSocialNetworkDialog(
    tel,
    add_social_network_service,
    add_social_network_getter,
)

command_controller = CommandController(tel, state_service)

dialog_bg_factory = NewTg(
    dp,
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
    video_cut_moderation_dialog,
    video_cuts_draft_dialog,
    publication_draft_dialog,
add_social_network_dialog
)

# Инициализация middleware
tg_middleware = TgMiddleware(
    tel,
    state_service,
    bot,
    dialog_bg_factory
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
    dialog_bg_factory,
    cfg.domain,
    cfg.prefix,
    cfg.interserver_secret_key
)

if __name__ == "__main__":
    app = NewServer(
        db,
        http_middleware,
        tg_webhook_controller,
        cfg.prefix,
    )
    uvicorn.run(app, host="0.0.0.0", port=int(cfg.http_port), access_log=False)
