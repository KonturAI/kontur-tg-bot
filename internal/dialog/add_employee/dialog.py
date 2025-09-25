from aiogram_dialog import Window, Dialog, ShowMode
from aiogram_dialog.widgets.text import Const, Format, Multi, Case
from aiogram_dialog.widgets.kbd import Button, Column, Row, Back, Select
from aiogram_dialog.widgets.input import TextInput

from internal import interface, model


class AddEmployeeDialog(interface.IAddEmployeeDialog):

    def __init__(
            self,
            tel: interface.ITelemetry,
            add_employee_service: interface.IAddEmployeeService,
            add_employee_getter: interface.IAddEmployeeGetter,
    ):
        self.tracer = tel.tracer()
        self.logger = tel.logger()
        self.add_employee_service = add_employee_service
        self.add_employee_getter = add_employee_getter

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
            Multi(
                Const("👤 <b>Добавление нового сотрудника</b>\n\n"),
                Const("📝 <b>Шаг 1/4:</b> Введите ID аккаунта сотрудника\n\n"),
                Const("💡 <b>Как найти ID аккаунта:</b>\n"),
                Const("• Попросите пользователя написать боту любое сообщение\n"),
                Const("• ID отобразится в системе после регистрации\n\n"),
                Const("⚠️ <i>Убедитесь, что пользователь уже зарегистрирован в системе</i>"),
                Case(
                    {
                        True: Const("\n\n❌ <b>Ошибка:</b> ID аккаунта не может быть пустым"),
                        False: Const(""),
                    },
                    selector="has_void_account_id"
                ),
                Case(
                    {
                        True: Const("\n\n❌ <b>Ошибка:</b> ID аккаунта должен быть положительным числом"),
                        False: Const(""),
                    },
                    selector="has_invalid_account_id"
                ),
                Const("\n\n🔢 <b>Введите ID аккаунта:</b>"),
                Case(
                    {
                        True: Format("\n📌 <b>Введенный ID:</b> <code>{account_id}</code>"),
                        False: Const("\n⌨️ <i>Ожидание ввода ID аккаунта...</i>"),
                    },
                    selector="has_account_id"
                ),
                sep="",
            ),

            TextInput(
                id="account_id_input",
                on_success=self.add_employee_service.handle_account_id_input,
            ),

            Row(
                Button(
                    Const("➡️ Далее"),
                    id="next_to_name",
                    on_click=lambda c, b, d: d.switch_to(model.AddEmployeeStates.enter_name, ShowMode.EDIT),
                    when="has_account_id"
                ),
                Button(
                    Const("◀️ К управлению организацией"),
                    id="go_to_organization_menu",
                    on_click=self.add_employee_service.handle_go_to_organization_menu,
                ),
            ),

            state=model.AddEmployeeStates.enter_account_id,
            getter=self.add_employee_getter.get_enter_account_id_data,
            parse_mode="HTML",
        )

    def get_enter_name_window(self) -> Window:
        return Window(
            Multi(
                Const("👤 <b>Добавление нового сотрудника</b>\n\n"),
                Const("📝 <b>Шаг 2/4:</b> Введите имя сотрудника\n\n"),
                Format("🔢 <b>ID аккаунта:</b> <code>{account_id}</code>\n\n"),
                Const("👋 <b>Введите полное имя сотрудника:</b>\n"),
                Const("💡 <i>Это имя будет отображаться в системе и уведомлениях</i>"),
                Case(
                    {
                        True: Const("\n\n❌ <b>Ошибка:</b> Имя не может быть пустым"),
                        False: Const(""),
                    },
                    selector="has_void_name"
                ),
                Case(
                    {
                        True: Const("\n\n📏 <b>Неверная длина имени</b>\n⚠️ <i>Имя должно быть от 2 до 100 символов</i>"),
                        False: Const(""),
                    },
                    selector="has_invalid_name_length"
                ),
                Case(
                    {
                        True: Format("\n\n📌 <b>Введенное имя:</b> {name}"),
                        False: Const("\n\n⌨️ <i>Ожидание ввода имени...</i>"),
                    },
                    selector="has_name"
                ),
                sep="",
            ),

            TextInput(
                id="name_input",
                on_success=self.add_employee_service.handle_name_input,
            ),

            Row(
                Button(
                    Const("➡️ Далее"),
                    id="next_to_role",
                    on_click=lambda c, b, d: d.switch_to(model.AddEmployeeStates.enter_role, ShowMode.EDIT),
                    when="has_name"
                ),
                Back(Const("◀️ Назад")),
            ),

            state=model.AddEmployeeStates.enter_name,
            getter=self.add_employee_getter.get_enter_name_data,
            parse_mode="HTML",
        )

    def get_enter_role_window(self) -> Window:
        return Window(
            Multi(
                Const("👤 <b>Добавление нового сотрудника</b>\n\n"),
                Const("📝 <b>Шаг 3/4:</b> Выберите роль сотрудника\n\n"),
                Format("🔢 <b>ID аккаунта:</b> <code>{account_id}</code>\n"),
                Format("👤 <b>Имя:</b> {name}\n\n"),
                Const("🎭 <b>Выберите подходящую роль:</b>\n"),
                Const("💡 <i>Роль определяет базовый набор разрешений сотрудника</i>"),
                Case(
                    {
                        True: Format("\n\n📌 <b>Выбранная роль:</b> {selected_role_display}"),
                        False: Const("\n\n👇 <i>Выберите роль из списка ниже...</i>"),
                    },
                    selector="has_selected_role"
                ),
                sep="",
            ),

            Column(
                Select(
                    Format("🎯 {item[title]}"),
                    id="role_select",
                    items="roles",
                    item_id_getter=lambda item: item["value"],
                    on_click=self.add_employee_service.handle_role_selection,
                ),
            ),

            Row(
                Button(
                    Const("➡️ Настроить разрешения"),
                    id="next_to_permissions",
                    on_click=lambda c, b, d: d.switch_to(model.AddEmployeeStates.set_permissions, ShowMode.EDIT),
                    when="has_selected_role"
                ),
                Back(Const("◀️ Назад")),
            ),

            state=model.AddEmployeeStates.enter_role,
            getter=self.add_employee_getter.get_enter_role_data,
            parse_mode="HTML",
        )

    def get_set_permissions_window(self) -> Window:
        return Window(
            Multi(
                Const("👤 <b>Добавление нового сотрудника</b>\n\n"),
                Const("📝 <b>Шаг 4/4:</b> Настройте разрешения сотрудника\n\n"),
                Format("🔢 <b>ID аккаунта:</b> <code>{account_id}</code>\n"),
                Format("👤 <b>Имя:</b> {name}\n"),
                Format("🎭 <b>Роль:</b> {role}\n\n"),
                Const("⚙️ <b>Разрешения сотрудника:</b>\n"),
                Const("👆 <i>Нажмите на разрешение, чтобы включить или выключить его</i>"),
                sep="",
            ),

            Column(
                Button(
                    Format("{required_moderation_icon} Публикации без модерации"),
                    id="toggle_required_moderation",
                    on_click=self.add_employee_service.handle_toggle_permission,
                ),
                Button(
                    Format("{autoposting_icon} Автоматический постинг"),
                    id="toggle_autoposting",
                    on_click=self.add_employee_service.handle_toggle_permission,
                ),
                Button(
                    Format("{add_employee_icon} Добавление сотрудников"),
                    id="toggle_add_employee",
                    on_click=self.add_employee_service.handle_toggle_permission,
                ),
                Button(
                    Format("{edit_permissions_icon} Управление разрешениями"),
                    id="toggle_edit_permissions",
                    on_click=self.add_employee_service.handle_toggle_permission,
                ),
                Button(
                    Format("{top_up_balance_icon} Пополнение баланса"),
                    id="toggle_top_up_balance",
                    on_click=self.add_employee_service.handle_toggle_permission,
                ),
                Button(
                    Format("{sign_up_social_networks_icon} Подключение соцсетей"),
                    id="toggle_sign_up_social_networks",
                    on_click=self.add_employee_service.handle_toggle_permission,
                ),
            ),

            Row(
                Button(
                    Const("➡️ К подтверждению"),
                    id="next_to_confirm",
                    on_click=lambda c, b, d: d.switch_to(model.AddEmployeeStates.confirm_employee, ShowMode.EDIT),
                ),
                Back(Const("◀️ Назад")),
            ),

            state=model.AddEmployeeStates.set_permissions,
            getter=self.add_employee_getter.get_permissions_data,
            parse_mode="HTML",
        )

    def get_confirm_employee_window(self) -> Window:
        return Window(
            Multi(
                Const("✅ <b>Подтверждение создания сотрудника</b>\n\n"),
                Const("📋 <b>Проверьте введенные данные:</b>\n\n"),
                Format("🔢 <b>ID аккаунта:</b> <code>{account_id}</code>\n"),
                Format("👤 <b>Имя:</b> {name}\n"),
                Format("🎭 <b>Роль:</b> {role}\n\n"),
                Const("⚙️ <b>Разрешения сотрудника:</b>\n"),
                Format("{permissions_text}\n\n"),
                Const("❓ <b>Всё корректно? Создать сотрудника?</b>"),
                sep="",
            ),

            Row(
                Button(
                    Const("✅ Создать сотрудника"),
                    id="create_employee",
                    on_click=self.add_employee_service.handle_create_employee,
                ),
                Back(
                    Const("✏️ Изменить данные"),
                ),
            ),

            state=model.AddEmployeeStates.confirm_employee,
            getter=self.add_employee_getter.get_confirm_data,
            parse_mode="HTML",
        )