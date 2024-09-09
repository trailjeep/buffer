from gi.repository import Gtk

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

    def __populate(self) -> None:
        style = config_manager.get_style()
        self._follow.set_active(style == "follow")
        self._light.set_active(style == "light")
        self._dark.set_active(style == "dark")
