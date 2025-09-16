# internal/controller/tg/dialog/add_employee/dialog.py
from aiogram_dialog import Window, Dialog
from aiogram_dialog.widgets.text import Const, Format, Multi
from aiogram_dialog.widgets.kbd import Button, Column, Row, Back, Select
from aiogram_dialog.widgets.input import TextInput

from internal import interface, model


class AddEmployeeDialog(interface.IAddEmployeeDialog):

    def __init__(
            self,
            tel: interface.ITelemetry,
            add_employee_service: interface.IAddEmployeeDialogService,
    ):
        self.tracer = tel.tracer()
        self.logger = tel.logger()
        self.add_employee_service = add_employee_service

    def get_dialog(self) -> Dialog:
        return Dialog(
            self.get_enter_account_id_window(),
            self.get_enter_name_window(),
            self.get_enter_role_window(),
            self.get_set_permissions_window(),
            self.get_confirm_employee_window(),
        )

    def get_enter_account_id_window(self) -> Window:
        return Window(
            Const("👤 <b>Добавление нового сотрудника</b>\n\n"),
            Const("📝 <b>Шаг 1/4: Введите ID аккаунта сотрудника</b>\n\n"),
            Const("⚠️ <i>Убедитесь, что пользователь уже зарегистрирован в системе</i>"),

            TextInput(
                id="account_id_input",
                on_success=self.add_employee_service.handle_account_id_input,
            ),

            Back(Const("◀️ Назад")),

            state=model.AddEmployeeStates.enter_account_id,
            getter=self.add_employee_service.get_enter_account_id_data,
            parse_mode="HTML",
        )

    def get_enter_name_window(self) -> Window:
        """Окно ввода имени сотрудника"""
        return Window(
            Multi(
                Const("👤 <b>Добавление нового сотрудника</b>\n\n"),
                Const("📝 <b>Шаг 2/4: Введите имя сотрудника</b>\n\n"),
                Format("ID Аккаунта: <b>{account_id}</b>\n\n"),
                Const("Введите полное имя сотрудника:"),
                sep="",
            ),

            TextInput(
                id="name_input",
                on_success=self.add_employee_service.handle_name_input,
            ),

            Back(Const("◀️ Назад")),

            state=model.AddEmployeeStates.enter_name,
            getter=self.add_employee_service.get_enter_name_data,
            parse_mode="HTML",
        )

    def get_enter_role_window(self) -> Window:
        """Окно выбора роли сотрудника"""
        return Window(
            Multi(
                Const("👤 <b>Добавление нового сотрудника</b>\n\n"),
                Const("📝 <b>Шаг 3/4: Выберите роль сотрудника</b>\n\n"),
                Format("ID Аккаунта: <b>{account_id}</b>\n"),
                Format("Имя: <b>{name}</b>\n\n"),
                Const("Выберите роль для сотрудника:"),
                sep="",
            ),

            Column(
                Select(
                    Format("{item[title]}"),
                    id="role_select",
                    items="roles",
                    item_id_getter=lambda item: item["value"],
                    on_click=self.add_employee_service.handle_role_selection,
                ),
            ),

            Back(Const("◀️ Назад")),

            state=model.AddEmployeeStates.enter_role,
            getter=self.add_employee_service.get_enter_role_data,
            parse_mode="HTML",
        )

    def get_set_permissions_window(self) -> Window:
        """Окно настройки разрешений сотрудника"""
        return Window(
            Multi(
                Const("👤 <b>Добавление нового сотрудника</b>\n\n"),
                Const("📝 <b>Шаг 4/4: Настройте разрешения сотрудника</b>\n\n"),
                Format("ID Аккаунта: <b>{account_id}</b>\n"),
                Format("Имя: <b>{name}</b>\n"),
                Format("Роль: <b>{role}</b>\n\n"),
                Const("⚙️ <b>Разрешения:</b>"),
                sep="",
            ),

            Column(
                # Публикации без одобрения
                Row(
                    Button(
                        Format("{no_moderation_icon}"),
                        id="toggle_no_moderation",
                        on_click=self.add_employee_service.handle_toggle_permission,
                    ),
                    Button(
                        Const("Публикации без одобрения"),
                        id="no_moderation_label",
                        on_click=self.add_employee_service.handle_toggle_permission,
                    ),
                ),

                # Включить авто-постинг
                Row(
                    Button(
                        Format("{autoposting_icon}"),
                        id="toggle_autoposting",
                        on_click=self.add_employee_service.handle_toggle_permission,
                    ),
                    Button(
                        Const("Включить авто-постинг"),
                        id="autoposting_label",
                        on_click=self.add_employee_service.handle_toggle_permission,
                    ),
                ),

                # Добавлять сотрудников
                Row(
                    Button(
                        Format("{add_employee_icon}"),
                        id="toggle_add_employee",
                        on_click=self.add_employee_service.handle_toggle_permission,
                    ),
                    Button(
                        Const("Добавлять сотрудников"),
                        id="add_employee_label",
                        on_click=self.add_employee_service.handle_toggle_permission,
                    ),
                ),

                # Изменять разрешения сотрудников
                Row(
                    Button(
                        Format("{edit_permissions_icon}"),
                        id="toggle_edit_permissions",
                        on_click=self.add_employee_service.handle_toggle_permission,
                    ),
                    Button(
                        Const("Изменять разрешения сотрудников"),
                        id="edit_permissions_label",
                        on_click=self.add_employee_service.handle_toggle_permission,
                    ),
                ),

                # Пополнять баланс
                Row(
                    Button(
                        Format("{top_up_balance_icon}"),
                        id="toggle_top_up_balance",
                        on_click=self.add_employee_service.handle_toggle_permission,
                    ),
                    Button(
                        Const("Пополнять баланс"),
                        id="top_up_balance_label",
                        on_click=self.add_employee_service.handle_toggle_permission,
                    ),
                ),

                # Подключать социальные сети
                Row(
                    Button(
                        Format("{social_networks_icon}"),
                        id="toggle_social_networks",
                        on_click=self.add_employee_service.handle_toggle_permission,
                    ),
                    Button(
                        Const("Подключать социальные сети"),
                        id="social_networks_label",
                        on_click=self.add_employee_service.handle_toggle_permission,
                    ),
                ),

                Button(
                    Const("➡️ Далее"),
                    id="next_to_confirm",
                    on_click=lambda c, b, d: d.switch_to(model.AddEmployeeStates.confirm_employee),
                ),
            ),

            Back(Const("◀️ Назад")),

            state=model.AddEmployeeStates.set_permissions,
            getter=self.add_employee_service.get_permissions_data,
            parse_mode="HTML",
        )

    def get_confirm_employee_window(self) -> Window:
        """Окно подтверждения создания сотрудника"""
        return Window(
            Multi(
                Const("👤 <b>Подтверждение создания сотрудника</b>\n\n"),
                Const("📋 <b>Проверьте введенные данные:</b>\n\n"),
                Format("ID Аккаунта: <b>{account_id}</b>\n"),
                Format("Имя: <b>{name}</b>\n"),
                Format("Роль: <b>{role}</b>\n\n"),
                Const("⚙️ <b>Разрешения:</b>\n"),
                Format("{permissions_text}\n\n"),
                Const("❓ Всё правильно?"),
                sep="",
            ),

            Row(
                Button(
                    Const("✅ Создать сотрудника"),
                    id="create_employee",
                    on_click=self.add_employee_service.handle_create_employee,
                ),
                Back(Const("✏️ Изменить")),
            ),

            state=model.AddEmployeeStates.confirm_employee,
            getter=self.add_employee_service.get_confirm_data,
            parse_mode="HTML",
        )