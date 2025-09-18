from aiogram.fsm.state import StatesGroup, State


class PublicationDraftContentStates(StatesGroup):
    """Состояния для диалога управления черновиками публикаций"""
    
    # Основные состояния
    draft_list = State()        # Список черновиков (слайдер как в управлении сотрудниками)
    edit_preview = State()      # Предпросмотр черновика с возможностью редактирования
    
    # Состояния редактирования текста
    edit_text_menu = State()    # Меню редактирования текста
    regenerate_text = State()   # Перегенерация текста с AI
    
    # Состояния редактирования отдельных элементов
    edit_title = State()        # Редактирование заголовка
    edit_tags = State()         # Редактирование тегов  
    edit_content = State()      # Редактирование содержания
    
    # Состояния работы с изображениями
    edit_image_menu = State()   # Меню управления изображением
    generate_image = State()    # Генерация изображения
    upload_image = State()      # Загрузка изображения
