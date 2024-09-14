from gi.repository import Gio, Gtk

import buffer.config_manager as config_manager


@Gtk.Template(resource_path="/org/gnome/gitlab/cheywood/Buffer/ui/theme_selector.ui")
class ThemeSelector(Gtk.Box):
    __gtype_name__ = "ThemeSelector"

    _follow = Gtk.Template.Child()
    _light = Gtk.Template.Child()
    _dark = Gtk.Template.Child()

    def __init__(self) -> None:
        super().__init__()
        self.__populate()
        config_manager.settings.connect(
            f"changed::{config_manager.STYLE}", lambda _o, _k: self.__populate()
        )

    @Gtk.Template.Callback()
    def _on_option_selected(self, _widget: Gtk.CheckButton) -> None:
        name = None
        if self._follow.get_active():
            name = "follow"
        elif self._light.get_active():
            name = "light"
        elif self._dark.get_active():
            name = "dark"
        # Name can be null when checkbutton is unchecked for radio group. A positive check will
        # follow.
        if name and config_manager.get_style() != name:
            config_manager.set_style(name)
            app = Gio.Application.get_default()
            app.apply_style()

    def __populate(self) -> None:
        style = config_manager.get_style()
        if style == "follow":
            self._follow.set_active(True)
        elif style == "light":
            self._light.set_active(True)
        else:
            self._dark.set_active(True)
