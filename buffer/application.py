import gi

gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk

import logging
from typing import Callable, Optional

from buffer import const
import buffer.config_manager as config_manager

from buffer.migration_assistant import MigrationAssistant
from buffer.emergency_saves_manager import EmergencySavesManager
from buffer.preferences_dialog import PreferencesDialog
from buffer.widgets import load_widgets
from buffer.window import Window


class Application(Adw.Application):
    development_mode = const.IS_DEVEL
    application_id = const.APP_ID

    def __init__(self, *args):
        super().__init__(
            *args,
            application_id=self.application_id,
            flags=Gio.ApplicationFlags.FLAGS_NONE,
            resource_base_path="/org/gnome/gitlab/cheywood/Buffer",
            register_session=True,
        )

        self.__windows = []
        self.__actions = {}
        self.__emergency_saves_manager = EmergencySavesManager()

        self.__add_cli_options()
        self.__initialise_styling()

        self.__dbus_proxy = Gio.DBusProxy.new_for_bus_sync(
            bus_type=Gio.BusType.SESSION,
            flags=Gio.DBusProxyFlags.NONE,
            info=None,
            name="org.freedesktop.portal.Desktop",
            object_path="/org/freedesktop/portal/desktop",
            interface_name="org.freedesktop.portal.Settings",
            cancellable=None,
        )

        self.connect("handle-local-options", self.__on_handle_local_options)
        self.connect("startup", self.__on_startup)
        self.connect("activate", self.__on_activate)

    def __on_handle_local_options(self, _obj: GObject.Object, options: GLib.VariantDict) -> int:
        """Handle options, setup logging."""
        options = options.end().unpack()

        self.__debug_session = "debug-session" in options

        loglevel = logging.INFO
        if self.development_mode or self.__debug_session:
            loglevel = logging.DEBUG

        logging.basicConfig(
            format="%(asctime)s | %(module)s | %(levelname)s | %(message)s",
            datefmt="%H:%M:%S",
            level=loglevel,
        )

        if "new" in options:
            # Application needs to be registered to send action if remote instance
            self.register()
            if self.get_property("is-remote"):
                self.activate_action("new")
        elif "new-from-clipboard" in options:
            # Application needs to be registered to send action if remote instance
            self.register()
            if self.get_property("is-remote"):
                self.activate_action("new-from-clipboard")
            else:
                self.__windows[0].set_to_paste_during_init()

        # Let default option processing continue
        return -1

    def __on_startup(self, _obj: GObject.Object) -> None:
        """Handle startup."""
        Gtk.Application.do_startup(self)
        Adw.init()

        migration_assistant = MigrationAssistant()
        migration_assistant.handle_version_migration()

        load_widgets()

        self.__setup_actions()

        self.__create_window()

    def __on_activate(self, _obj: GObject.Object) -> None:
        """Handle window activation."""
        self.__apply_css()

        Application.apply_style()

    def __on_style_change(
        self,
        _obj: GObject.Object,
        _value: GObject.ParamSpec,
    ) -> None:
        for window in self.__windows:
            window.update_style()

    def __on_new_buffer(self, _action: Gio.SimpleAction, _param: GLib.Variant) -> None:
        self.__create_window()

    def __on_new_from_clipboard(self, _action: Gio.SimpleAction, _param: GLib.Variant) -> None:
        self.__create_window()

    def __on_close_request(self, window: Window) -> bool:
        if config_manager.get_emergency_recover_files() > 0:
            text = window.get_text()
            if text.strip() != "":
                self.__emergency_saves_manager.save(text)
        self.__windows.remove(window)
        return False

    def __on_quit_shortcut(self, _window: Gtk.Window, _action_param: GLib.Variant) -> None:
        if config_manager.get_quit_closes_window():
            self.get_active_window().close()
        else:
            for window in self.__windows:
                window.close()

    def __initialise_styling(self) -> None:
        self.__base_css_resource = "{}/ui/base_style.css".format(self.props.resource_base_path)
        self.__base_css_provider = None
        self.__index_category_label_css_provider = None
        style_manager = Adw.StyleManager.get_default()
        style_manager.connect("notify::dark", self.__on_style_change)
        style_manager.connect("notify::high-contrast", self.__on_style_change)

    def __add_cli_options(self) -> None:
        self.add_main_option(
            "new",
            ord("n"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            "Create a buffer",
            None,
        )
        self.add_main_option(
            "new-from-clipboard",
            ord("n"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            "Create a buffer with the contents of the clipboard",
            None,
        )

    def __setup_actions(self) -> None:
        def add_action(
            name: str,
            method: Callable,
            shortcut: Optional[str] = None,
            parameter_type: Optional[GLib.VariantType] = None,
        ):
            if parameter_type is None:
                action = Gio.SimpleAction.new(name)
            else:
                action = Gio.SimpleAction.new(name, parameter_type)
            self.add_action(action)
            action.connect("activate", method)
            self.__actions[name] = action
            if shortcut is not None:
                self.set_accels_for_action(f"app.{name}", [shortcut])

        add_action("about", self.__show_about_dialog)
        add_action("quit", self.__on_quit_shortcut, "<Control>q")
        add_action("settings", self.__show_preferences_dialog, "<Control>comma")
        add_action("new", self.__on_new_buffer, "<Control>n")
        add_action("new-from-clipboard", self.__on_new_from_clipboard, "<Control><Shift>v")
        add_action(
            "set-style-variant",
            self.__set_style_variant,
            parameter_type=GLib.VariantType("s"),
        )

    def __create_window(self) -> None:
        window = Window(self, self.__dbus_proxy)
        self.add_window(window)
        window.present()
        window.connect("close-request", self.__on_close_request)
        self.__windows.append(window)

    def __apply_css(self) -> None:
        if self.__base_css_resource is None:
            return

        display = Gdk.Display.get_default()

        if self.__base_css_provider is None:
            self.__base_css_provider = Gtk.CssProvider()
            self.__base_css_provider.load_from_resource(self.__base_css_resource)
        else:
            Gtk.StyleContext.remove_provider_for_display(display, self.__base_css_provider)

        Gtk.StyleContext.add_provider_for_display(
            display, self.__base_css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def __show_about_dialog(self, _action: Gio.SimpleAction, _param: GLib.Variant) -> None:
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/gitlab/cheywood/Buffer/about_dialog.ui")
        about_dialog = builder.get_object("AboutDialog")
        window = self.get_active_window()
        about_dialog.present(window)

    def __show_preferences_dialog(self, _action: Gio.SimpleAction, _param: GLib.Variant) -> None:
        window = self.get_active_window()
        PreferencesDialog().present(window)

    def __set_style_variant(self, _action: Gio.SimpleAction, new_style: str) -> None:
        config_manager.set_style(new_style.get_string())
        Application.apply_style()

    @staticmethod
    def apply_style() -> None:
        """Apply style preference."""
        manager = Adw.StyleManager.get_default()
        style = config_manager.get_style()
        if style == "dark":
            manager.props.color_scheme = Adw.ColorScheme.FORCE_DARK
        elif style == "light":
            manager.props.color_scheme = Adw.ColorScheme.FORCE_LIGHT
        else:
            manager.props.color_scheme = Adw.ColorScheme.DEFAULT