import gi

gi.require_version("GtkSource", "5")
from gi.repository import Gio, GObject, Gtk, GtkSource

from typing import Optional


@Gtk.Template(resource_path="/org/gnome/gitlab/cheywood/Buffer/ui/editor_search_header_bar.ui")
class EditorSearchHeaderBar(Gtk.Box):
    __gtype_name__ = "EditorSearchHeaderBar"
    __gsignals__ = {
        "resumed": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "open-for-replace": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    _search_entry = Gtk.Template.Child()
    _backward_button = Gtk.Template.Child()
    _forward_button = Gtk.Template.Child()
    _revealer = Gtk.Template.Child()
    _replace_entry = Gtk.Template.Child()
    _replace_toggle = Gtk.Template.Child()

    def __init__(self) -> None:
        super().__init__()

        self.__settings = GtkSource.SearchSettings.new()
        self.__settings.set_wrap_around(True)
        self._search_entry.text.bind_property(
            "text",
            self.__settings,
            "search-text",
        )
        self.__context: Optional[GtkSource.SearchContext] = None
        self.__offset_when_entered = 0
        self.__context_signal_handler_id = None
        self.__cursor_signal_handler_id = None
        self.__current_match_tag = None
        self.__avoid_jumping_during_replace = False
        self.__active = False
        self.__restarting_with_nonempty_term = False

        self._search_entry.text.connect(
            "notify::text", lambda _o, _v: self.__on_search_text_changed()
        )

        self._revealer.bind_property(
            "child-revealed", self._replace_toggle, "active", GObject.BindingFlags.SYNC_CREATE
        )

    def setup(self, sourceview: GtkSource.View) -> None:
        """Perform initial setup."""
        self.__setup_actions()
        self.__sourceview = sourceview

    def enter(self, resuming: bool, for_replace: bool) -> None:
        """Enter search.

        :param bool resuming: Whether resuming search
        :param bool for_replace: Whether opening directly from a ctrl-h shortcut
        """
        buffer = self.__sourceview.get_buffer()
        self.__context = GtkSource.SearchContext.new(buffer, self.__settings)
        insert_iter = buffer.get_iter_at_mark(buffer.get_insert())
        self.__offset_when_entered = insert_iter.get_offset()
        self.__setup_current_match_styling()
        if for_replace:
            self._revealer.set_reveal_child(True)

        # Ensure when restarting search any term remains selected so it can be easily replaced by
        # typing.
        self.__restarting_with_nonempty_term = not resuming and self._search_entry.get_text() != ""

        self._search_entry.text.grab_focus()
        if resuming:
            self._search_entry.text.set_position(-1)
        elif self._search_entry.get_text() != "":
            self._search_entry.text.select_region(0, -1)

        self.__context_signal_handler_id = self.__context.connect(
            "notify::occurrences-count", lambda _o, _v: self.__occurrences_count_changed()
        )
        self.__cursor_signal_handler_id = buffer.connect(
            "cursor-moved", lambda _o: self.__on_cursor_moved()
        )
        self.__replace_action.set_enabled(False)
        self.__active = True

    def exit(self) -> None:
        """Exit search."""
        buffer = self.__sourceview.get_buffer()
        buffer.disconnect(self.__cursor_signal_handler_id)
        if self.__context:
            self.__context.disconnect(self.__context_signal_handler_id)
            self.__context = None
        begin, end = buffer.get_bounds()
        if self.__current_match_tag:
            buffer.remove_tag(self.__current_match_tag, begin, end)
            self.__current_match_tag = None
        self._revealer.set_reveal_child(False)
        self.__active = False

    def disable_actions(self) -> None:
        """Disable actions."""
        self.__action_group.lookup_action("backward").set_enabled(False)
        self.__action_group.lookup_action("forward").set_enabled(False)

    def refocus_search_and_select(self) -> None:
        """Grab focus to search entry and select any text."""
        self._search_entry.text.grab_focus()
        if self._search_entry.get_text() != "":
            self._search_entry.text.select_region(0, -1)

    @GObject.Property(type=bool, default=False)
    def active(self) -> bool:
        return self.__active

    @Gtk.Template.Callback()
    def _on_search_entry_activate(self, _obj: GObject.Object) -> None:
        self.__move_forward()

    @Gtk.Template.Callback()
    def _on_replace_entry_activate(self, _obj: GObject.Object) -> None:
        if self.__replace_action.get_enabled():
            self.__replace_selection()

    def __setup_actions(self) -> None:
        action_group = Gio.SimpleActionGroup.new()
        app = Gio.Application.get_default()

        action = Gio.SimpleAction.new("forward")
        action.connect("activate", lambda _o, _v: self.__move_forward())
        action_group.add_action(action)
        app.set_accels_for_action("editor-search.forward", ["<Control>g"])
        action.set_enabled(False)

        action = Gio.SimpleAction.new("backward")
        action.connect("activate", lambda _o, _v: self.__move_backward())
        action_group.add_action(action)
        app.set_accels_for_action("editor-search.backward", ["<Shift><Control>g"])
        action.set_enabled(False)

        action = Gio.SimpleAction.new("toggle-replace")
        action.connect("activate", lambda _o, _v: self.__toggle_replace_visible())
        action_group.add_action(action)
        app.set_accels_for_action("editor-search.toggle-replace", ["<Control>h"])

        action = Gio.SimpleAction.new("replace")
        action.connect("activate", lambda _o, _v: self.__replace_selection())
        action_group.add_action(action)
        self.__replace_action = action

        self.__action_group = action_group
        app.get_active_window().insert_action_group("editor-search", action_group)

    def __on_context_forward(
        self, context: GtkSource.SearchContext, result: Gio.AsyncResult
    ) -> None:
        if not self.__current_match_tag:
            return
        success, match_start, match_end, __ = context.forward_finish(result)
        if success:
            buffer = self.__sourceview.get_buffer()
            if self.__restarting_with_nonempty_term:
                buffer.place_cursor(match_start)
            else:
                buffer.select_range(match_start, match_end)
                self.__current_match_tag.set_priority(buffer.get_tag_table().get_size() - 1)
                self.__update_for_current_match(match_start, match_end)
            self.__sourceview.jump_to_insertion_point()
        if self.__restarting_with_nonempty_term:
            self.__restarting_with_nonempty_term = False
        self.__replace_action.set_enabled(success)

    def __on_context_backward(
        self, context: GtkSource.SearchContext, result: Gio.AsyncResult
    ) -> None:
        if not self.__current_match_tag:
            return
        success, match_start, match_end, __ = context.backward_finish(result)
        if success:
            buffer = self.__sourceview.get_buffer()
            buffer.select_range(match_start, match_end)
            self.__current_match_tag.set_priority(buffer.get_tag_table().get_size() - 1)
            self.__sourceview.jump_to_insertion_point()
            self.__update_for_current_match(match_start, match_end)
        self.__replace_action.set_enabled(success)

    def __on_cursor_moved(self) -> None:
        self.__update_for_current_match(None, None)
        self.__replace_action.set_enabled(False)

    def __on_search_text_changed(self) -> None:
        self.__replace_action.set_enabled(False)
        self._search_entry.set_occurrence_count(0)
        self._search_entry.set_occurrence_position(0)
        # Clear any tagged matches when deleting the search term
        buffer = self.__sourceview.get_buffer()
        begin, end = buffer.get_bounds()
        buffer.remove_tag(self.__current_match_tag, begin, end)

    def __occurrences_count_changed(self) -> None:
        if not self.__context:
            return
        count = self.__context.get_occurrences_count()
        self._search_entry.set_occurrence_count(count)
        self._search_entry.set_occurrence_position(0)
        search_can_move = count > 0

        if not self.__sourceview.has_focus():
            if search_can_move and not self.__avoid_jumping_during_replace:
                self.__jump_to_first()
            elif self.__restarting_with_nonempty_term:
                self.__restarting_with_nonempty_term = False

        self.__action_group.lookup_action("backward").set_enabled(search_can_move)
        self.__action_group.lookup_action("forward").set_enabled(search_can_move)
        self.__avoid_jumping_during_replace = False

    def __jump_to_first(self) -> None:
        buffer = self.__sourceview.get_buffer()
        start_iter = buffer.get_iter_at_offset(self.__offset_when_entered)
        self.__move_forward(start_iter)

    def __move_forward(self, from_iter: Optional[Gtk.TextIter] = None) -> None:
        """Move to next search match."""
        if self.__context is None:
            if self._search_entry.get_text() != "":
                self.emit("resumed")
            else:
                return
        if not from_iter:
            buffer = self.__sourceview.get_buffer()
            if buffer.get_has_selection():
                begin, end = buffer.get_selection_bounds()
                begin.order(end)
                from_iter = end
            else:
                mark = buffer.get_insert()
                from_iter = buffer.get_iter_at_mark(mark)
        if self.__context:
            self.__context.forward_async(from_iter, None, self.__on_context_forward)

    def __move_backward(self) -> None:
        """Move to previous search match."""
        if self.__context is None:
            if self._search_entry.get_text() != "":
                self.emit("resumed")
            else:
                return
        buffer = self.__sourceview.get_buffer()
        if buffer.get_has_selection():
            begin, end = buffer.get_selection_bounds()
            begin.order(end)
        else:
            mark = buffer.get_insert()
            begin = buffer.get_iter_at_mark(mark)
        if self.__context:
            self.__context.backward_async(begin, None, self.__on_context_backward)

    def __toggle_replace_visible(self) -> None:
        if not self.__active:
            self.emit("open-for-replace")
            return
        reveal = not self._revealer.get_child_revealed()
        self._revealer.set_reveal_child(reveal)
        if reveal:
            # Clearing the replace entry here to avoid the current match selection in the buffer
            # being removed, which would result in replace not working until the match is
            # re-navigated to. Ideally selection wouldn't be used to identify the current search
            # match
            self._replace_entry.set_text("")
            self._replace_entry.grab_focus()
            self.__replace_action.set_enabled(self.__have_search_term_selection())

    def __update_for_current_match(
        self, match_start: Optional[Gtk.TextIter], match_end: Optional[Gtk.TextIter]
    ) -> None:
        if not self.__context:
            return
        if not self.__current_match_tag:
            return
        buffer = self.__sourceview.get_buffer()

        new_position = 0
        if buffer.get_has_selection():
            bounds = buffer.get_selection_bounds()
            if len(bounds) == 2:
                begin, end = bounds
                begin.order(end)
                new_position = self.__context.get_occurrence_position(begin, end)
        self._search_entry.set_occurrence_position(new_position)

        if self.__current_match_tag is not None:
            begin, end = buffer.get_bounds()
            buffer.remove_tag(self.__current_match_tag, begin, end)
        if match_start is not None and match_end is not None:
            buffer.apply_tag(self.__current_match_tag, match_start, match_end)
            self.__current_match_tag.set_priority(buffer.get_tag_table().get_size() - 1)

    def __setup_current_match_styling(self) -> None:
        buffer = self.__sourceview.get_buffer()
        table = buffer.get_tag_table()
        scheme = buffer.get_style_scheme()

        if self.__current_match_tag is not None:
            table.remove(self.__current_match_tag)
        self.__current_match_tag = buffer.create_tag()
        if not self.__current_match_tag:
            return

        if scheme is not None:
            style = scheme.get_style("current-search-match")
            if style is not None:
                style.apply(self.__current_match_tag)
        self.__current_match_tag.set_priority(table.get_size() - 1)

    def __replace_selection(self) -> None:
        buffer = self.__sourceview.get_buffer()
        if not self.__have_search_term_selection():
            return
        (start, end) = buffer.get_selection_bounds()
        self.__avoid_jumping_during_replace = True
        buffer.delete(start, end)
        new_text = self._replace_entry.get_text()
        if new_text != "":
            buffer.insert(start, new_text)
        self.__move_forward()

    def __have_search_term_selection(self) -> bool:
        buffer = self.__sourceview.get_buffer()
        if not buffer.get_has_selection():
            return False
        (start, end) = buffer.get_selection_bounds()
        return start.get_text(end).lower() == self._search_entry.get_text().lower()
