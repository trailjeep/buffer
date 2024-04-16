from gi.repository import Gio, GLib

from typing import Optional

from buffer import const

settings = Gio.Settings.new(const.APP_ID)

FONT_SIZE = "font-size"
EMERGENCY_RECOVERY_FILES = "emergency-recovery-files"
LAST_LAUNCHED_VERSION = "last-launched-version"
LINE_LENGTH = "line-length"
SHOW_CLOSE_BUTTON = "show-close-button"
SPELLING_ENABLED = "spelling-enabled"
SPELLING_LANGUAGE = "spelling-language"
STYLE = "style-variant"
QUIT_CLOSES_WINDOW = "quit-closes-window"
USE_MONOSPACE_FONT = "use-monospace-font"
WINDOW_SIZE = "window-size"


def get_font_size() -> int:
    """Get font size.

    :return: Size
    :rtype: int
    """
    return settings.get_int(FONT_SIZE)


def set_font_size(value: int) -> None:
    """Set font size.

    :param int value: New value
    """
    settings.set_int(FONT_SIZE, value)


def get_default_font_size() -> int:
    """Get default font size.

    :return: Default size
    :rtype: int
    """
    return settings.get_default_value(FONT_SIZE).get_int32()


def get_emergency_recover_files() -> int:
    """Get the number of emergency recovery files.

    :return: Number to save
    :rtype: int
    """
    return settings.get_int(EMERGENCY_RECOVERY_FILES)


def set_emergency_recover_files(value: int) -> None:
    """Set the number of emergency recovery files.

    :param int value: New value
    """
    settings.set_int(EMERGENCY_RECOVERY_FILES, value)


def get_last_launched_version() -> str:
    """Get the last version which was run.

    :return: Version
    :rtype: str
    """
    return settings.get_string(LAST_LAUNCHED_VERSION)


def set_last_launched_version(value: str) -> None:
    """Set the last version which was run.

    :param str value: New value
    """
    settings.set_string(LAST_LAUNCHED_VERSION, value)


def get_line_length() -> int:
    """Get line length.

    :return: Size in pixels
    :rtype: int
    """
    return settings.get_int(LINE_LENGTH)


def set_line_length(value: int) -> None:
    """Set line length.

    :param int value: New value
    """
    settings.set_int(LINE_LENGTH, value)


def get_line_length_max() -> int:
    """Get line length maximum.

    :return: Size in pixels
    :rtype: int
    """
    return settings.get_property("settings-schema").get_key(LINE_LENGTH).get_range()[1][-1]


def get_use_monospace_font() -> bool:
    """Get whether to use a monospace font.

    :return: Using monospace font
    :rtype: bool
    """
    return settings.get_value(USE_MONOSPACE_FONT)


def set_use_monospace_font(value: bool) -> None:
    """Set whether to use a monospace font.

    :param bool value: New value
    """
    settings.set_boolean(USE_MONOSPACE_FONT, value)


def get_show_close_button() -> bool:
    """Get whether to show a close button on each window.

    :return: Whether to show
    :rtype: bool
    """
    return settings.get_value(SHOW_CLOSE_BUTTON)


def set_show_close_button(value: bool) -> None:
    """Set whether quit only closes the window.

    :param bool value: New value
    """
    settings.set_boolean(SHOW_CLOSE_BUTTON, value)


def get_spelling_enabled() -> bool:
    """Get whether spelling enabled.

    :return: Spelling enabled
    :rtype: bool
    """
    return settings.get_value(SPELLING_ENABLED)


def set_spelling_enabled(value: bool) -> None:
    """Set spelling enabled.

    :param bool value: New value
    """
    settings.set_boolean(SPELLING_ENABLED, value)


def get_spelling_language() -> Optional[str]:
    """Get spelling language.

    :return Language tag or None if empty
    :rtype: str
    """
    lang = settings.get_string(SPELLING_LANGUAGE)
    if lang.strip() == "":
        lang = None
    return lang


def set_spelling_language(value: str) -> None:
    """Set spelling language.

    :param str value: New value
    """
    settings.set_string(SPELLING_LANGUAGE, value)


def get_style() -> str:
    """Get style.

    :return: Style
    :rtype: str
    """
    return settings.get_string(STYLE)


def set_style(value: str) -> None:
    """Set style.

    :param str value: New value
    """
    settings.set_string(STYLE, value)


def get_quit_closes_window() -> bool:
    """Get whether quit only closes the window.

    :return: Quit closes window
    :rtype: bool
    """
    return settings.get_value(QUIT_CLOSES_WINDOW)


def set_quit_closes_window(value: bool) -> None:
    """Set whether quit only closes the window.

    :param bool value: New value
    """
    settings.set_boolean(QUIT_CLOSES_WINDOW, value)


def get_window_size() -> GLib.Variant:
    """Get window size.

    :return: The size
    :rtype: GLib.Variant
    """
    return settings.get_value(WINDOW_SIZE)


def set_window_size(width: int, height: int) -> None:
    """Set window size.

    :param int width: Width
    :param int height: Height
    """
    g_variant = GLib.Variant("ai", (width, height))
    settings.set_value(WINDOW_SIZE, g_variant)
