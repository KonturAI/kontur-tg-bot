from aiogram.fsm.state import StatesGroup, State


class PublicationDraftStates(StatesGroup):
    """Стейты для диалога управления черновиками публикаций"""

    # Основное окно со списком черновиков и отображением публикаций
    publication_list = State()

    # Окно редактирования с превью
    edit_preview = State()

    # Окна редактирования конкретных полей
    edit_title = State()
    edit_description = State()
    edit_tags = State()