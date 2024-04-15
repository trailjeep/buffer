from gettext import gettext as _
import gi

gi.require_version("GtkSource", "5")
from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk, GtkSource, Pango

import logging
import time
from typing import Optional

import buffer.config_manager as config_manager
from buffer import const
from buffer.font_size_selector import FontSizeSelector
from buffer.theme_selector import ThemeSelector


@Gtk.Template(resource_path="/org/gnome/gitlab/cheywood/Buffer/ui/window.ui")
class Window(Adw.ApplicationWindow):
    __gtype_name__ = "Window"

    FONT_SETTING_KEYS = ["monospace-font-name", "document-font-name"]
    MENU_BUTTON_SHOWN_DURATION = 4
    MENU_BUTTON_SHOWN_INIT_DURATION = 2
    SETTING_CHANGE_NOTIFICATION_DURATION = 3.0
    LINE_LENGTH_STEP = 50

    _textview = Gtk.Template.Child()
    _menu_button = Gtk.Template.Child()
    _close_button = Gtk.Template.Child()
    _revealer = Gtk.Template.Child()
    _timed_notification = Gtk.Template.Child()
    _toolbar_view = Gtk.Template.Child()
    _search_header_bar = Gtk.Template.Child()

    def __init__(self, app: Adw.Application, dbus_proxy: Optional[Gio.DBusProxy]):
        super().__init__(application=app)

        self.__dbus_proxy = dbus_proxy

        self.__initialising = True
        self.__font_families = {}
        self.__timeout_signal_id = None
        self.__motion_during_menu_hide_timeout = None
        self.__paste_during_init = False

        self.set_icon_name(const.APP_ID)

        if const.IS_DEVEL:
            self.add_css_class("devel")

        self._menu_button.get_popover().add_child(ThemeSelector(), "theme")
        self.__font_size_selector = FontSizeSelector()
        self._menu_button.get_popover().add_child(self.__font_size_selector, "fontsize")

        self.__setup_actions()

        self.connect("close-request", self.__on_close_request)

        config_manager.settings.bind(
            config_manager.SHOW_CLOSE_BUTTON,
            self._close_button,
            "visible",
            Gio.SettingsBindFlags.DEFAULT,
        )

        (width, height) = config_manager.get_window_size()
        self.set_default_size(width, height)

        if self.__dbus_proxy is None:
            logging.warning("Unable to establish D-Bus proxy for FreeDesktop.org font setting")
        else:
            self.__load_font_family_from_setting()
            self.__dbus_proxy.connect_object("g-signal", self.__on_desktop_setting_changed, None)

        if self.__dbus_proxy is not None:
            config_manager.settings.connect(
                f"changed::{config_manager.USE_MONOSPACE_FONT}", self.__on_font_family_changed
            )

        config_manager.settings.connect(
            f"changed::{config_manager.LINE_LENGTH}", self.__on_line_length_changed
        )

        self.connect("notify::is-active", self.__on_window_active_changed)
        self._menu_button.connect("notify::active", self.__on_menu_active_changed)

        self._search_header_bar.setup(self._textview)
        self.__font_size_selector.setup()
        self.__refresh_line_length_from_setting()
        self.connect("notify::fullscreened", self.__on_window_fullscreened)

        self._search_header_bar.connect("resumed", self.__on_search_resumed)
        self._search_header_bar.connect("open-for-replace", self.__on_enter_replace)

        self.update_style()

        if config_manager.get_spelling_enabled():
            self._textview.spellchecker_enabled = True

    def update_style(self) -> None:
        """Update style for dark mode and high contrast."""
        buffer = self._textview.get_buffer()
        if not buffer:
            return

        style_manager = Adw.StyleManager.get_default()
        scheme_id = "buffer-high-contrast" if style_manager.get_high_contrast() else "buffer"
        scheme_id = f"{scheme_id}-dark" if style_manager.get_dark() else scheme_id

        style_scheme_manager = GtkSource.StyleSchemeManager.get_default()
        scheme = style_scheme_manager.get_scheme(scheme_id)
        buffer.set_style_scheme(scheme)

    def set_to_paste_during_init(self) -> None:
        """Set the buffer to paste from the clipboard upon initialisation."""
        self.__paste_during_init = True

    def get_text(self) -> str:
        """Fetch the buffer contents.

        :return: The text
        :rtype: str
        """
        return self._textview.get_buffer().get_property("text")

    @Gtk.Template.Callback()
    def _on_window_close_clicked(self, _button: Gtk.Button) -> None:
        self.close()

    @Gtk.Template.Callback()
    def _on_motion(self, _obj, x, y) -> None:
        if self._toolbar_view.get_reveal_top_bars():
            return

        if y < self.get_height() / 10:
            self.__reveal_menu()

    @Gtk.Template.Callback()
    def _on_key_pressed(
        self,
        controller: Gtk.EventControllerKey,
        keyval: int,
        keycode: int,
        state: Gdk.ModifierType,
    ) -> bool:
        if not self._revealer.get_reveal_child():
            return Gdk.EVENT_PROPAGATE

        # Prevent some keys from resulting in the menu re-hiding
        if keyval in (
            Gdk.KEY_Tab,
            Gdk.KEY_ISO_Left_Tab,
            Gdk.KEY_Alt_L,
            Gdk.KEY_Alt_R,
            Gdk.KEY_Meta_L,
            Gdk.KEY_Meta_R,
            Gdk.KEY_Control_L,
            Gdk.KEY_Control_R,
            Gdk.KEY_Shift_L,
            Gdk.KEY_Shift_R,
        ):
            return Gdk.EVENT_PROPAGATE

        if not self._menu_button.get_active():
            self.__hide_menu()
        return Gdk.EVENT_PROPAGATE

    @Gtk.Template.Callback()
    def _on_gesture_click(
        self, gesture: Gtk.GestureClick, _n_press: int, x: float, y: float
    ) -> None:
        if gesture.get_current_button() == 1:
            if self._revealer.get_reveal_child() and not self._menu_button.get_active():
                self.__hide_menu()
        elif gesture.get_current_button() == 3:
            self._textview.move_cursor(x, y)
        return Gdk.EVENT_PROPAGATE

    def __on_paste_cb(self, clipboard: Gdk.Clipboard, task: Gio.Task) -> None:
        out = clipboard.read_text_finish(task)
        self._textview.get_buffer().set_text(out)

    def __on_close_request(self, _obj: GObject.Object) -> None:
        """On window destroyed."""
        if not self.is_fullscreen():
            config_manager.set_window_size(self.get_width(), self.get_height())
        self.close()

    def __on_line_length_changed(self, _settings: Gio.Settings, _key: str) -> None:
        length = config_manager.get_line_length()
        logging.debug(f"Line length now {length}px")
        self.__refresh_line_length_from_setting()

    def __on_increase_line_length(self, _action: Gio.SimpleAction, _param: GLib.Variant) -> None:
        setting_max = config_manager.get_line_length_max()
        current_length = config_manager.get_line_length()
        if current_length == setting_max:
            # Translators: Description, notification
            self.__notify_setting_change(_("Line length limit already disabled"))
            return
        else:
            new_length = current_length + self.LINE_LENGTH_STEP
        if new_length < self.get_width() - 2 * self._textview.BASE_MARGIN:
            config_manager.set_line_length(new_length)
            self.__notify_line_length_change(new_length)
        else:
            config_manager.set_line_length(setting_max)
            # Translators: Description, notification
            self.__notify_setting_change(_("Line length limit disabled"))

    def __on_decrease_line_length(self, _action: Gio.SimpleAction, _param: GLib.Variant) -> None:
        setting_max = config_manager.get_line_length_max()
        current_length = config_manager.get_line_length()
        new_length = current_length - self.LINE_LENGTH_STEP
        if current_length == setting_max:
            new_length = min(self.get_width(), config_manager.DEFAULT_LINE_LENGTH)
            config_manager.set_line_length(new_length)
            self.__notify_line_length_change(new_length)
        elif new_length >= self.LINE_LENGTH_STEP:
            config_manager.set_line_length(new_length)
            self.__notify_line_length_change(new_length)

    def __on_line_length_limit_toggle(
        self, _action: Gio.SimpleAction, _param: GLib.Variant
    ) -> None:
        setting_maximum = config_manager.get_line_length_max()
        if config_manager.get_line_length() == setting_maximum:
            config_manager.set_line_length(config_manager.DEFAULT_LINE_LENGTH)
        else:
            config_manager.set_line_length(setting_maximum)

    def __on_font_family_changed(self, _settings: Gio.Settings, _key: str) -> None:
        self.__load_font_family_from_setting()

    def __on_increase_font_size(
        self,
        _obj: GObject.Object,
        _value: GObject.ParamSpec,
    ) -> None:
        if self.__font_size_selector.increase():
            self.__notify_font_size()

    def __on_decrease_font_size(
        self,
        _obj: GObject.Object,
        _value: GObject.ParamSpec,
    ) -> None:
        if self.__font_size_selector.decrease():
            self.__notify_font_size()

    def __on_reset_font_size(
        self,
        _obj: GObject.Object,
        _value: GObject.ParamSpec,
    ) -> None:
        self.__font_size_selector.reset()
        self.__notify_font_size()

    def __on_close_shortcut(
        self,
        _obj: GObject.Object,
        _value: GObject.ParamSpec,
    ) -> None:
        self.close()

    def __on_window_active_changed(self, _obj: GObject.Object, _param: GObject.ParamSpec) -> None:
        if not self.is_active():
            return

        self.__reveal_menu()
        if self.__initialising:
            if self.__paste_during_init:
                clipboard = self._textview.get_primary_clipboard()
                clipboard.read_text_async(None, self.__on_paste_cb)
            self.__initialising = False

    def __on_menu_active_changed(self, _obj: GObject.Object, _param: GObject.ParamSpec) -> None:
        if not self._menu_button.get_active():
            self._textview.grab_focus()

    def __on_window_fullscreened(self, window: Gtk.Window, _param: GObject.ParamSpec) -> None:
        if window.is_fullscreen():
            self.__hide_menu()
        else:
            self.__reveal_menu()

    def __on_toggle_fullscreen(self, _action: Gio.SimpleAction, _param: GLib.Variant) -> None:
        if self.is_fullscreen():
            self.unfullscreen()
        else:
            self.fullscreen()

    def __on_desktop_setting_changed(
        self, _sender_name: str, _signal_name: str, _parameters: str, data: GLib.Variant
    ) -> None:
        if _parameters != "SettingChanged":
            return
        (path, setting_name, value) = data
        if path == "org.gnome.desktop.interface" and setting_name in self.FONT_SETTING_KEYS:
            if value.strip() != "":
                font_description = Pango.font_description_from_string(value)
                self.__font_families[setting_name] = font_description.get_family()
                self.__push_font_updates()

    def __on_enter_search(self, _action: Gio.SimpleAction, _param: GLib.Variant) -> None:
        if not self._search_header_bar.active:
            self.__enter_search(resuming=False, for_replace=False)

    def __on_search_resumed(self, _object: GObject.Object) -> None:
        self.__enter_search(resuming=True, for_replace=False)

    def __on_enter_replace(self, _object: GObject.Object) -> None:
        self.__enter_search(resuming=False, for_replace=True)

    def __on_cancel(self, _action: Gio.SimpleAction, _param: GLib.Variant) -> None:
        if self._toolbar_view.get_reveal_top_bars():
            self.__exit_search()

    def __setup_actions(self) -> None:
        app = Gio.Application.get_default()

        action_group = Gio.SimpleActionGroup.new()

        action = Gio.SimpleAction.new("fullscreen")
        action.connect("activate", self.__on_toggle_fullscreen)
        action_group.add_action(action)
        app.set_accels_for_action("win.fullscreen", ["F11"])

        action = Gio.SimpleAction.new("increase-line-length")
        action.connect("activate", self.__on_increase_line_length)
        action_group.add_action(action)
        app.set_accels_for_action("win.increase-line-length", ["<Control>Up"])

        action = Gio.SimpleAction.new("decrease-line-length")
        action.connect("activate", self.__on_decrease_line_length)
        action_group.add_action(action)
        app.set_accels_for_action("win.decrease-line-length", ["<Control>Down"])

        action = Gio.SimpleAction.new("toggle-line-length-limit")
        action.connect("activate", self.__on_line_length_limit_toggle)
        action_group.add_action(action)
        app.set_accels_for_action("win.toggle-line-length-limit", ["<Shift><Control>l"])

        action = Gio.SimpleAction.new("close")
        action.connect("activate", self.__on_close_shortcut)
        action_group.add_action(action)
        app.set_accels_for_action("win.close", ["<Control>w"])

        action = Gio.SimpleAction.new("enter-search")
        action.connect("activate", self.__on_enter_search)
        action_group.add_action(action)
        app.set_accels_for_action("win.enter-search", ["<Control>f"])

        action = Gio.SimpleAction.new("increase-font-size")
        action.connect("activate", self.__on_increase_font_size)
        action_group.add_action(action)
        app.set_accels_for_action("win.increase-font-size", ["<Control>plus", "<Control>equal"])

        action = Gio.SimpleAction.new("decrease-font-size")
        action.connect("activate", self.__on_decrease_font_size)
        action_group.add_action(action)
        app.set_accels_for_action(
            "win.decrease-font-size", ["<Control>minus", "<Control>underscore"]
        )

        action = Gio.SimpleAction.new("reset-font-size")
        action.connect("activate", self.__on_reset_font_size)
        action_group.add_action(action)
        app.set_accels_for_action("win.reset-font-size", ["<Control>0"])

        action = Gio.SimpleAction.new("go-back-or-cancel")
        action.connect("activate", self.__on_cancel)
        action_group.add_action(action)
        app.set_accels_for_action("win.go-back-or-cancel", ["Escape"])

        self.insert_action_group("win", action_group)
        self.__action_group = action_group

    def __process_desktop_settings(self, variant: GLib.Variant) -> None:
        if variant.get_type_string() != "(a{sa{sv}})":
            return
        for v in variant:
            for key, value in v.items():
                if key == "org.gnome.desktop.interface":
                    for font_key in self.FONT_SETTING_KEYS:
                        if font_key in value:
                            font_description = Pango.font_description_from_string(value[font_key])
                            self.__font_families[font_key] = font_description.get_family()
        self.__push_font_updates()

    def __push_font_updates(self) -> None:
        font_setting = self.__fetch_editor_font_setting_name()
        if font_setting in self.__font_families:
            family = self.__font_families[font_setting]
            self._textview.update_font_family(family)

    def __fetch_editor_font_setting_name(self):
        return (
            "monospace-font-name"
            if config_manager.get_use_monospace_font()
            else "document-font-name"
        )

    def __load_font_family_from_setting(self) -> None:
        if self.__dbus_proxy is None:
            return

        try:
            variant = self.__dbus_proxy.call_sync(
                method_name="ReadAll",
                parameters=GLib.Variant("(as)", ("org.gnome.desktop.*",)),
                flags=Gio.DBusCallFlags.NO_AUTO_START,
                timeout_msec=-1,
                cancellable=None,
            )
        except GLib.GError as e:
            logging.warning("Unable to access D-Bus FreeDesktop.org font family setting: %s", e)
            return

        self.__process_desktop_settings(variant)

    def __refresh_line_length_from_setting(self) -> None:
        length = config_manager.get_line_length()
        length_for_view = -1 if length == config_manager.get_line_length_max() else length
        self._textview.line_length = length_for_view
        self._textview.queue_resize()

    def __hide_menu(self) -> None:
        if self.__motion_during_menu_hide_timeout:
            elapsed = time.time() - self.__motion_during_menu_hide_timeout
            remainder = self.MENU_BUTTON_SHOWN_DURATION - elapsed
            self.__timeout_signal_id = GLib.timeout_add(remainder * 1000, self.__hide_menu)
        else:
            self._revealer.set_reveal_child(False)
            self.__timeout_signal_id = None
        self.__motion_during_menu_hide_timeout = None

    def __reveal_menu(self) -> None:
        if not self._revealer.get_reveal_child():
            self._revealer.set_reveal_child(True)
            duration = (
                self.MENU_BUTTON_SHOWN_INIT_DURATION
                if self.__initialising
                else self.MENU_BUTTON_SHOWN_DURATION
            )
            self.__timeout_signal_id = GLib.timeout_add(duration * 1000, self.__hide_menu)
        else:
            self.__motion_during_menu_hide_timeout = time.time()

    def __notify_line_length_change(self, length: int) -> None:
        # Translators: Description, notification, {0} is a number
        msg = _("Line length now {0}px").format(length)
        self.__notify_setting_change(msg)

    def __notify_font_size(self) -> None:
        size = config_manager.get_font_size()
        # Translators: Description, notification, {0} is a number
        msg = _("Font size now {0}pt").format(size)
        self.__notify_setting_change(msg)

    def __notify_setting_change(self, msg: str) -> None:
        self._timed_notification.show(
            msg,
            self.SETTING_CHANGE_NOTIFICATION_DURATION,
        )

    def __enter_search(self, resuming: bool, for_replace: bool) -> None:
        self._search_header_bar.enter(resuming, for_replace)
        self._toolbar_view.set_reveal_top_bars(True)
        if self._revealer.get_reveal_child():
            self.__hide_menu()

    def __exit_search(self) -> None:
        self._textview.grab_focus()
        self._toolbar_view.set_reveal_top_bars(False)
        self._search_header_bar.exit()
