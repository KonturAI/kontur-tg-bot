from aiogram_dialog import Window, Dialog, ShowMode
from aiogram_dialog.widgets.text import Const, Format, Multi, Case
from aiogram_dialog.widgets.kbd import Button, Column, Back, Checkbox
from aiogram_dialog.widgets.input import TextInput

from internal import interface, model


class AddSocialNetworkDialog(interface.IAddSocialNetworkDialog):

    def __init__(
            self,
            tel: interface.ITelemetry,
            add_social_network_service: interface.IAddSocialNetworkService,
            add_social_network_getter: interface.IAddSocialNetworkGetter,
    ):
        self.tracer = tel.tracer()
        self.logger = tel.logger()
        self.add_social_network_service = add_social_network_service
        self.add_social_network_getter = add_social_network_getter

    def get_dialog(self) -> Dialog:
        return Dialog(
            self.get_select_network_window(),
            self.get_telegram_main_window(),
            self.get_telegram_connect_window(),
            self.get_telegram_edit_window(),
            self.get_telegram_change_username_window(),
            self.get_vkontakte_setup_window(),
            self.get_youtube_setup_window(),
            self.get_instagram_setup_window(),
        )

    def get_select_network_window(self) -> Window:
        return Window(
            Multi(
                Const("🌐 <b>Подключение социальных сетей</b>\n\n"),
                Const("📱 <b>Выберите платформу для подключения или изменения:</b>\n"),
                Const("💡 <i>Подключенные сети помечены зеленым цветом</i>\n"),
                Const("🤖 <i>Звездочка (*) означает автовыбор для публикации</i>"),
                sep="",
            ),

            Column(
                Button(
                    Case(
                        {
                            "connected_autoselect": Const("✅ Telegram*"),
                            "connected_no_autoselect": Const("✅ Telegram"),
                            "not_connected": Const("📱 Telegram"),
                        },
                        selector="telegram_status"
                    ),
                    id="select_telegram",
                    on_click=lambda c, b, d: d.switch_to(model.AddSocialNetworkStates.telegram_main, ShowMode.EDIT),
                ),
                Button(
                    Case(
                        {
                            "connected_autoselect": Const("✅ ВКонтакте*"),
                            "connected_no_autoselect": Const("✅ ВКонтакте"),
                            "not_connected": Const("🔵 ВКонтакте"),
                        },
                        selector="vkontakte_status"
                    ),
                    id="select_vkontakte",
                    on_click=lambda c, b, d: d.switch_to(model.AddSocialNetworkStates.vkontakte_setup, ShowMode.EDIT),
                ),
                Button(
                    Case(
                        {
                            "connected_autoselect": Const("✅ YouTube*"),
                            "connected_no_autoselect": Const("✅ YouTube"),
                            "not_connected": Const("🎥 YouTube"),
                        },
                        selector="youtube_status"
                    ),
                    id="select_youtube",
                    on_click=lambda c, b, d: d.switch_to(model.AddSocialNetworkStates.youtube_setup, ShowMode.EDIT),
                ),
                Button(
                    Case(
                        {
                            "connected_autoselect": Const("✅ Instagram*"),
                            "connected_no_autoselect": Const("✅ Instagram"),
                            "not_connected": Const("📷 Instagram"),
                        },
                        selector="instagram_status"
                    ),
                    id="select_instagram",
                    on_click=lambda c, b, d: d.switch_to(model.AddSocialNetworkStates.instagram_setup, ShowMode.EDIT),
                ),
            ),

            Button(
                Const("◀️ К управлению организацией"),
                id="go_to_organization_menu",
                on_click=self.add_social_network_service.handle_go_to_organization_menu,
            ),

            state=model.AddSocialNetworkStates.select_network,
            getter=self.add_social_network_getter.get_select_network_data,
            parse_mode="HTML",
        )

    def get_telegram_main_window(self) -> Window:
        return Window(
            Multi(
                Const("📱 <b>Telegram</b>\n\n"),
                Case(
                    {
                        True: Multi(
                            Const("✅ <b>Подключен</b>\n\n"),
                            Format("📣 <b>Канал:</b> @{tg_channel_username}\n"),
                            Case(
                                {
                                    True: Const("🤖 <b>Автовыбор:</b> ✅ включен\n"),
                                    False: Const("🤖 <b>Автовыбор:</b> ❌ выключен\n"),
                                },
                                selector="telegram_autoselect"
                            ),
                            Const(
                                "\n💡 <i>Автовыбор означает, что новый контент будет автоматически предназначен для этого канала</i>"),
                        ),
                        False: Multi(
                            Const("❌ <b>Не подключен</b>\n\n"),
                            Const("📝 <b>Для подключения:</b>\n"),
                            Const("1️⃣ Создайте канал в Telegram\n"),
                            Const("2️⃣ Добавьте бота @KonturContentBot в администраторы\n"),
                            Const("3️⃣ Нажмите кнопку «Подключить»\n\n"),
                            Const("⚠️ <b>Важно:</b> У канала должен быть публичный username"),
                        ),
                    },
                    selector="telegram_connected"
                ),
                sep="",
            ),

            Column(
                # Кнопки для подключенного канала
                Button(
                    Const("✏️ Изменить"),
                    id="edit_telegram",
                    on_click=lambda c, b, d: d.switch_to(model.AddSocialNetworkStates.telegram_edit, ShowMode.EDIT),
                    when="telegram_connected"
                ),
                Button(
                    Const("🗑️ Удалить"),
                    id="delete_telegram",
                    on_click=self.add_social_network_service.handle_disconnect_telegram,
                    when="telegram_connected"
                ),

                # Кнопка для подключения
                Button(
                    Const("🔗 Подключить"),
                    id="connect_telegram",
                    on_click=lambda c, b, d: d.switch_to(model.AddSocialNetworkStates.telegram_connect, ShowMode.EDIT),
                    when="telegram_not_connected"
                ),
            ),

            Back(Const("◀️ Назад")),

            state=model.AddSocialNetworkStates.telegram_main,
            getter=self.add_social_network_getter.get_telegram_main_data,
            parse_mode="HTML",
        )

    def get_telegram_connect_window(self) -> Window:
        return Window(
            Multi(
                Const("🔗 <b>Подключение Telegram канала</b>\n\n"),

                # Шаг 1: Ввод логина
                Case(
                    {
                        False: Const("📝 <b>Шаг 1:</b> Введите username канала (без @)\n\n⌨️ <i>Введите username:</i>"),
                        True: Format("✅ <b>Шаг 1:</b> Username введен (@{tg_channel_username})\n\n"),
                    },
                    selector="has_username"
                ),

                # Шаг 2: Автовыбор (показывается только после ввода username)
                Case(
                    {
                        True: Const(
                            "🤖 <b>Шаг 2:</b> Настройка автовыбора\n\n💡 <i>Если включить автовыбор, новый контент будет автоматически предназначен для этого канала</i>"),
                        False: Const(""),
                    },
                    selector="has_username"
                ),

                # Ошибки валидации
                Case(
                    {
                        True: Const("\n\n❌ <b>Ошибка:</b> Username канала не может быть пустым"),
                        False: Const(""),
                    },
                    selector="has_void_tg_channel_username"
                ),
                Case(
                    {
                        True: Const(
                            "\n\n❌ <b>Ошибка:</b> Неверный формат username. Используйте латиницу, цифры и подчеркивания (5-32 символа)"),
                        False: Const(""),
                    },
                    selector="has_invalid_tg_channel_username"
                ),
                Case(
                    {
                        True: Const("\n\n❌ <b>Ошибка:</b> Канал не найден или бот не добавлен в администраторы"),
                        False: Const(""),
                    },
                    selector="has_channel_not_found"
                ),
                sep="",
            ),

            TextInput(
                id="tg_channel_username_input",
                on_success=self.add_social_network_service.handle_tg_channel_username_input,
            ),

            Column(
                Checkbox(
                    Const("🤖 Включить автовыбор"),
                    Const("🤖 Автовыбор включен"),
                    id="autoselect_checkbox",
                    default=False,
                    when="has_username"
                ),

                Button(
                    Const("💾 Подключить канал"),
                    id="save_telegram_connection",
                    on_click=self.add_social_network_service.handle_save_telegram_connection,
                    when="has_username"
                ),
            ),

            Back(Const("◀️ Назад")),

            state=model.AddSocialNetworkStates.telegram_connect,
            getter=self.add_social_network_getter.get_telegram_connect_data,
            parse_mode="HTML",
        )

    def get_telegram_edit_window(self) -> Window:
        return Window(
            Multi(
                Const("✏️ <b>Редактирование Telegram канала</b>\n\n"),
                Format("📣 <b>Текущий канал:</b> @{tg_channel_username}\n"),
                Case(
                    {
                        True: Const("🤖 <b>Автовыбор:</b> ✅ включен\n\n"),
                        False: Const("🤖 <b>Автовыбор:</b> ❌ выключен\n\n"),
                    },
                    selector="telegram_autoselect"
                ),
                Const("⚙️ <b>Доступные настройки:</b>"),
                sep="",
            ),

            Column(
                # Кнопка изменения логина
                Button(
                    Const("📝 Изменить логин канала"),
                    id="change_username",
                    on_click=lambda c, b, d: d.switch_to(model.AddSocialNetworkStates.telegram_change_username, ShowMode.EDIT),
                ),

                # Чекбокс автовыбора
                Checkbox(
                    Const("🤖 Включить автовыбор"),
                    Const("🤖 Автовыбор включен"),
                    id="telegram_autoselect_checkbox",
                    default=False,
                ),

                # Кнопка сохранения изменений автовыбора
                Button(
                    Const("💾 Сохранить изменения"),
                    id="save_changes",
                    on_click=self.add_social_network_service.handle_save_telegram_changes,
                    when="has_changes"
                ),
            ),

            Back(Const("◀️ Назад")),

            state=model.AddSocialNetworkStates.telegram_edit,
            getter=self.add_social_network_getter.get_telegram_edit_data,
            parse_mode="HTML",
        )

    def get_telegram_change_username_window(self) -> Window:
        return Window(
            Multi(
                Const("📝 <b>Изменение логина Telegram канала</b>\n\n"),
                Format("📣 <b>Текущий канал:</b> @{tg_channel_username}\n\n"),
                Const("⌨️ <b>Введите новый username канала (без @):</b>\n"),
                Const("💡 <i>Бот должен быть добавлен в администраторы нового канала</i>\n"),

                # Ошибки валидации
                Case(
                    {
                        True: Const("\n❌ <b>Ошибка:</b> Username канала не может быть пустым"),
                        False: Const(""),
                    },
                    selector="has_void_tg_channel_username"
                ),
                Case(
                    {
                        True: Const(
                            "\n❌ <b>Ошибка:</b> Неверный формат username. Используйте латиницу, цифры и подчеркивания (5-32 символа)"),
                        False: Const(""),
                    },
                    selector="has_invalid_tg_channel_username"
                ),
                Case(
                    {
                        True: Const("\n❌ <b>Ошибка:</b> Канал не найден или бот не добавлен в администраторы"),
                        False: Const(""),
                    },
                    selector="has_channel_not_found"
                ),
                sep="",
            ),

            # Поле ввода нового username
            TextInput(
                id="new_tg_channel_username_input",
                on_success=self.add_social_network_service.handle_new_tg_channel_username_input,
            ),

            Back(Const("◀️ Назад")),

            state=model.AddSocialNetworkStates.telegram_change_username,
            getter=self.add_social_network_getter.get_telegram_change_username_data,
            parse_mode="HTML",
        )

    def get_vkontakte_setup_window(self) -> Window:
        return Window(
            Multi(
                Const("🔵 <b>Настройка ВКонтакте</b>\n\n"),
                Const("🔜 <i>Функционал находится в разработке</i>\n"),
                Const("📅 <b>Скоро будет доступно:</b>\n"),
                Const("• Автоматическая публикация в группу\n"),
                Const("• Настройка времени постинга\n"),
                Const("• Статистика охватов\n"),
                Const("• Настройки автовыбора"),
                sep="",
            ),

            Back(Const("◀️ Назад")),

            state=model.AddSocialNetworkStates.vkontakte_setup,
            getter=self.add_social_network_getter.get_vkontakte_setup_data,
            parse_mode="HTML",
        )

    def get_youtube_setup_window(self) -> Window:
        return Window(
            Multi(
                Const("🎥 <b>Настройка YouTube</b>\n\n"),
                Const("🔜 <i>Функционал находится в разработке</i>\n"),
                Const("📅 <b>Скоро будет доступно:</b>\n"),
                Const("• Подключение канала YouTube\n"),
                Const("• Автоматическая публикация видео\n"),
                Const("• Настройки автовыбора для видеоконтента\n"),
                Const("• Управление описаниями и тегами"),
                sep="",
            ),

            Back(Const("◀️ Назад")),

            state=model.AddSocialNetworkStates.youtube_setup,
            getter=self.add_social_network_getter.get_youtube_setup_data,
            parse_mode="HTML",
        )

    def get_instagram_setup_window(self) -> Window:
        return Window(
            Multi(
                Const("📷 <b>Настройка Instagram</b>\n\n"),
                Const("🔜 <i>Функционал находится в разработке</i>\n"),
                Const("📅 <b>Скоро будет доступно:</b>\n"),
                Const("• Подключение бизнес-аккаунта Instagram\n"),
                Const("• Автоматическая публикация постов и stories\n"),
                Const("• Настройки автовыбора для визуального контента\n"),
                Const("• Планирование публикаций"),
                sep="",
            ),

            Back(Const("◀️ Назад")),

            state=model.AddSocialNetworkStates.instagram_setup,
            getter=self.add_social_network_getter.get_instagram_setup_data,
            parse_mode="HTML",
        )