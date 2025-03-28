from enum import Enum

class LogType(Enum):
    USER_REGISTERED = "USER_REGISTERED"
    USER_LOGGED_IN = "USER_LOGGED_IN"
    LOGIN_FAILED = "LOGIN_FAILED"
    USER_DELETED = "USER_DELETED"
    PASSWORD_RESET_LINK_SENT = "PASSWORD_RESET_LINK_SENT"
    PASSWORD_CHANGED = "PASSWORD_CHANGED"
    USER_LOGGED_OUT = "USER_LOGGED_OUT"
    USER_UPDATED = "USER_UPDATED"
    USERNAME_CHANGED = "USERNAME_CHANGED"
    GOOGLE_LOGIN = "GOOGLE_LOGIN"
