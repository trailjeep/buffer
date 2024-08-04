from gi.repository import GLib, Gtk

from typing import Callable, Optional


@Gtk.Template(resource_path="/org/gnome/gitlab/cheywood/Buffer/ui/timed_revealer_notification.ui")
class TimedRevealerNotification(Gtk.Revealer):
    __gtype_name__ = "TimedRevealerNotification"

    _label = Gtk.Template.Child()
    _button = Gtk.Template.Child()
    _icon = Gtk.Template.Child()

    def __init__(self):
        super().__init__()
        self.__button_callback = None
        self.__finished_callback = None
        self.__event_source_id = None
        self._button.connect("clicked", lambda _o: self.__clicked())
        self.connect("notify::child-revealed", lambda _o, _v: self.__revealed())

    def show(
        self,
        label_text: str,
        duration: float,
        button_text: Optional[str] = None,
        button_callback: Optional[Callable[[], None]] = None,
        finished_callback: Optional[Callable[[], None]] = None,
        show_icon: bool = False,
    ) -> None:
        """Show the notification

        :param str label_text: The text to display
        :param duration float: The duration (in milliseconds) to display the notification for
        :param str button_text: The text to display on the button
        :param button_callback: A function to call when the button is pressed
        :param finished_callback: A function to call when the notification has finished displaying
        :param show_icon: Whether to show the sync icon
        """
        self._label.set_text(label_text)
        self._button.set_visible(button_text is not None)
        self._icon.set_visible(show_icon)
        if self.__event_source_id is not None:
            GLib.source_remove(self.__event_source_id)
            self.__event_source_id = None
        if button_text:
            self._button.set_label(button_text)
        if button_callback:
            self.__button_callback = button_callback
        if finished_callback:
            self.__finished_callback = finished_callback
        if duration > 0.0:
            duration *= 1000.0 + self.get_transition_duration()
            self.__event_source_id = GLib.timeout_add(duration, self.__hide)
        self.set_reveal_child(True)

    def hide_if_revealed(self) -> None:
        """Hide the notification if showing."""
        if self.get_child_revealed():
            self.__clean()
            self.__hide()

    def __hide(self) -> None:
        self.__event_source_id = None
        self.set_reveal_child(False)

    def __clicked(self) -> None:
        self.__clean()
        if self.__button_callback is not None:
            self.__button_callback()
        self.__hide()

    def __revealed(self) -> None:
        if not self.get_child_revealed() and self.__finished_callback:
            self.__finished_callback()
            self.__finished_callback = None

    def __clean(self) -> None:
        self.__finished_callback = None
        if self.__event_source_id is not None:
            GLib.source_remove(self.__event_source_id)
            self.__event_source_id = None
