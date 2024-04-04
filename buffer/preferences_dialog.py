from gi.repository import Adw, Gio, GLib, Gtk

import buffer.config_manager as config_manager
from buffer.emergency_saves_manager import EmergencySavesManager


@Gtk.Template(resource_path="/org/gnome/gitlab/cheywood/Buffer/ui/preferences_dialog.ui")
class PreferencesDialog(Adw.PreferencesDialog):
    __gtype_name__ = "PreferencesDialog"

    _show_files_button = Gtk.Template.Child()

    def __init__(self):
        super().__init__()
        self.__app = Gio.Application.get_default()

        self.__build_actions()

    @Gtk.Template.Callback()
    def _on_show_recovery_files(self, _button: Gtk.Button) -> None:
        EmergencySavesManager.show_directory()

    def __build_actions(self) -> None:
        action_group = Gio.SimpleActionGroup.new()

        def build_simple_binary_action(key: str):
            action = config_manager.settings.create_action(key)
            action_group.add_action(action)

        for key in (
            config_manager.USE_MONOSPACE_FONT,
            config_manager.SPELLING_ENABLED,
            config_manager.QUIT_CLOSES_WINDOW,
            config_manager.SHOW_CLOSE_BUTTON,
        ):
            build_simple_binary_action(key)

        key = config_manager.LINE_LENGTH
        setting_maximum = config_manager.get_line_length_max()
        init_state = config_manager.get_line_length() < setting_maximum
        action = Gio.SimpleAction.new_stateful(key, None, GLib.Variant("b", init_state))
        action.connect("change-state", self.__on_line_length_state_change)
        action_group.add_action(action)

        key = config_manager.EMERGENCY_RECOVERY_FILES
        init_state = config_manager.get_emergency_recover_files() > 0
        action = Gio.SimpleAction.new_stateful(key, None, GLib.Variant("b", init_state))
        action.connect("change-state", self.__on_emergency_recovery_files_state_change)
        action_group.add_action(action)
        self.__files_action = action
        self._show_files_button.set_sensitive(init_state)

        self.insert_action_group("settings", action_group)

    def __on_line_length_state_change(self, action: Gio.SimpleAction, state: bool) -> None:
        action.set_state(state)
        setting_maximum = config_manager.get_line_length_max()
        new_value = config_manager.DEFAULT_LINE_LENGTH if state else setting_maximum
        config_manager.set_line_length(new_value)

    def __on_emergency_recovery_files_state_change(
        self, action: Gio.SimpleAction, state: bool
    ) -> None:
        action.set_state(state)
        new_value = EmergencySavesManager.DEFAULT_EMERGENCY_FILES if state else 0
        config_manager.set_emergency_recover_files(new_value)
        self._show_files_button.set_sensitive(state)
