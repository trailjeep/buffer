from gi.repository import Gio, GObject, Gtk

import buffer.config_manager as config_manager


@Gtk.Template(resource_path="/org/gnome/gitlab/cheywood/Buffer/ui/font_size_selector.ui")
class FontSizeSelector(Gtk.Box):
    __gtype_name__ = "FontSizeSelector"

    _label = Gtk.Template.Child()

    VALID_SIZES = [
        6,
        7,
        8,
        9,
        10,
        11,
        12,
        13,
        14,
        15,
        16,
        17,
        18,
        20,
        22,
        24,
        26,
        28,
        30,
        34,
        38,
    ]

    def __init__(self):
        super().__init__()
        self.__increase_action = None
        self.__decrease_action = None
        config_manager.settings.connect(
            f"changed::{config_manager.FONT_SIZE}", self.__on_setting_changed
        )

    def setup(self):
        self.__setup_actions()
        self.__refresh_from_setting()

    def increase(self) -> bool:
        if not self.__increase_action.get_enabled():
            return False

        previous_size = config_manager.get_font_size()
        ind = self.VALID_SIZES.index(previous_size)
        config_manager.set_font_size(self.VALID_SIZES[ind + 1])
        return True

    def decrease(self) -> bool:
        if not self.__decrease_action.get_enabled():
            return False

        previous_size = config_manager.get_font_size()
        ind = self.VALID_SIZES.index(previous_size)
        config_manager.set_font_size(self.VALID_SIZES[ind - 1])
        return True

    def reset(self) -> bool:
        previous_size = config_manager.get_font_size()
        default_size = config_manager.get_default_font_size()
        if previous_size != default_size:
            config_manager.set_font_size(default_size)

    def __setup_actions(self) -> None:
        action_group = Gio.SimpleActionGroup.new()
        app = Gio.Application.get_default()

        action = Gio.SimpleAction.new("increase")
        action.connect("activate", self.__on_increase)
        action_group.add_action(action)
        self.__increase_action = action

        action = Gio.SimpleAction.new("decrease")
        action.connect("activate", self.__on_decrease)
        action_group.add_action(action)
        self.__decrease_action = action

        action = Gio.SimpleAction.new("reset")
        action.connect("activate", self.__on_reset)
        action_group.add_action(action)

        app.get_active_window().insert_action_group("font-size-selector", action_group)
        self.__action_group = action_group

    def __on_increase(
        self,
        _obj: GObject.Object,
        _value: GObject.ParamSpec,
    ) -> None:
        self.increase()

    def __on_decrease(
        self,
        _obj: GObject.Object,
        _value: GObject.ParamSpec,
    ) -> None:
        self.decrease()

    def __on_reset(
        self,
        _obj: GObject.Object,
        _value: GObject.ParamSpec,
    ) -> None:
        self.reset()

    def __on_setting_changed(self, _settings: Gio.Settings, _key: str) -> None:
        self.__refresh_from_setting()

    def __refresh_from_setting(self) -> None:
        size = config_manager.get_font_size()
        self._label.set_label("{}pt".format(size))
        ind = self.VALID_SIZES.index(size)
        self.__increase_action.set_enabled(ind + 1 < len(self.VALID_SIZES))
        self.__decrease_action.set_enabled(ind - 1 >= 0)
