from gettext import gettext as _
from gi.repository import GObject, Gtk


@Gtk.Template(resource_path="/org/gnome/gitlab/cheywood/Buffer/ui/editor_search_entry.ui")
class EditorSearchEntry(Gtk.Box):
    __gtype_name__ = "EditorSearchEntry"
    __gsignals__ = {
        "activate": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    text = Gtk.Template.Child()
    _info = Gtk.Template.Child()

    def __init__(self):
        self.__occurrence_count = 0
        self.__occurrence_position = 0
        super().__init__()

    def set_occurrence_count(self, count: int) -> None:
        """Set the number of search term occurrences.

        :param int count: New value
        """
        self.__occurrence_count = count
        self.__update_position()

    def set_occurrence_position(self, position: int) -> None:
        """Set the current search term occurrence.

        :param int position: New value
        """
        self.__occurrence_position = position
        self.__update_position()

    def select_all_and_focus(self) -> None:
        """Select and focus all text."""
        if self.text.get_text() != "":
            self.text.select_region(0, -1)
        self.text.grab_focus()

    def get_text(self) -> str:
        """Fetch the text from the entry.

        :return: Unaccented form
        :rtype: str
        """
        return self.text.get_text()

    def set_text(self, text: str) -> None:
        """Set the text on the entry.

        :param str text: New value
        """
        return self.text.set_text(text)

    @Gtk.Template.Callback()
    def _on_activate(self, _obj: GObject.Object) -> None:
        self.emit("activate")

    def __update_position(self) -> None:
        if self.__occurrence_count == 0:
            occurrence_str = ""
        else:
            # Translators: Description, {0} the current position in {1} a number of search results
            occurrence_str = _("{0} of {1}").format(
                self.__occurrence_position, self.__occurrence_count
            )
        self._info.set_label(occurrence_str)
