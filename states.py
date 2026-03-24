from enum import IntEnum, auto


class AdminStates(IntEnum):
    # Event creation
    EV_NAME = auto()
    EV_DATE = auto()
    EV_TIME = auto()
    EV_LOCATION = auto()
    EV_DESCRIPTION = auto()
    EV_PAID = auto()
    EV_PRICE = auto()
    EV_CHANNELS = auto()
    EV_ADD_CHANNEL = auto()
    EV_QUESTIONS_MENU = auto()
    EV_ADD_QUESTION_TEXT = auto()
    EV_ADD_QUESTION_TYPE = auto()
    EV_ADD_QUESTION_CHOICES = auto()
    EV_ADD_QUESTION_MIN = auto()
    EV_SUCCESS_MSG = auto()
    EV_PAYMENT_MSG = auto()
    EV_PAYMENT_CONFIRMED_MSG = auto()
    EV_SECTIONS_MENU = auto()
    EV_SECTIONS_IMAGE = auto()
    EV_SECTION_NAME = auto()
    EV_SECTION_PRICE = auto()
    EV_SECTION_SEATS = auto()
    EV_CONFIRM = auto()

    # Edit event
    EDIT_SELECT = auto()
    EDIT_FIELD = auto()
    EDIT_VALUE = auto()

    # Broadcast
    BC_TARGET = auto()
    BC_EVENT_SELECT = auto()
    BC_USER_SEARCH = auto()
    BC_MESSAGE = auto()
    BC_CONFIRM = auto()

    # Admin management
    ADM_ADD_ID = auto()
    ADM_PERMISSIONS = auto()

    # Question reorder
    Q_REORDER = auto()

    # Sub-section for adding choices
    EV_CHOICES_DONE = auto()


class UserStates(IntEnum):
    MAIN = auto()
    REG_QUESTION = auto()
    REG_SECTION_SELECT = auto()
    PAYMENT_WAITING = auto()
    SUPPORT_CHAT = auto()
