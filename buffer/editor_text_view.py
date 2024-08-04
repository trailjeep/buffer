import gi

gi.require_version("GtkSource", "5")
from gi.repository import Gdk, GLib, GObject, Gtk, GtkSource

import locale
import logging
import re
from typing import Callable, Optional

import buffer.config_manager as config_manager


@Gtk.Template(resource_path="/org/gnome/gitlab/cheywood/Buffer/ui/editor_text_view.ui")
class EditorTextView(GtkSource.View):
    __gtype_name__ = "EditorTextView"

    __gsignals__ = {
        "size-allocated": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    # k is the token, v is the continuation
    BULLET_LIST_TOKENS = {
        "- [ ] ": "- [ ] ",
        "- [x] ": "- [ ] ",
        "- ": "- ",
        "+ ": "+ ",
        "* ": "* ",
    }

    BASE_MARGIN = 36
    MINIMUM_MARGIN = 10
    DEFAULT_LINE_LENGTH = 800

    def __init__(self):
        super().__init__()

        self.__css_provider = None
        self.__line_length = -1
        self.__font_family = "monospace"

        self.__spellchecker = None
        self.__spelling_adapter = None
        if config_manager.get_spelling_enabled():
            self.__init_spellchecker()

        config_manager.settings.connect(
            f"changed::{config_manager.SPELLING_ENABLED}",
            lambda _o, _v: self.__on_spelling_toggled(),
        )
        config_manager.settings.connect(
            f"changed::{config_manager.FONT_SIZE}", lambda _o, _k: self.__update_font()
        )
        config_manager.settings.connect(
            f"changed::{config_manager.SHOW_LINE_NUMBERS}",
            lambda _o, _v: self.set_property(
                "show-line-numbers", config_manager.get_show_line_numbers()
            ),
        )
        self.set_property("show-line-numbers", config_manager.get_show_line_numbers())

        controller = Gtk.EventControllerKey()
        controller.connect("key-pressed", self.__on_key_pressed)
        self.add_controller(controller)

    def do_size_allocate(self, width: int, height: int, baseline: int) -> None:
        """Allocates widget with a transformation that translates the origin to the position in
        allocation.

        :param int width: Width of the allocation
        :param int height: Height of the allocation
        :param int allocation: The baseline of the child
        """
        GtkSource.View.do_size_allocate(self, width, height, baseline)

        # Update top and bottom margin
        min_width_for_y_margin = 400
        max_width_for_y_margin = self.__line_length if self.__line_length > 500 else 800
        if width <= min_width_for_y_margin:
            y_margin = self.MINIMUM_MARGIN
        elif width < max_width_for_y_margin:
            value_range = max_width_for_y_margin - min_width_for_y_margin
            y_range = float(self.BASE_MARGIN - self.MINIMUM_MARGIN)
            in_range = width - min_width_for_y_margin
            y_margin = self.MINIMUM_MARGIN + int(in_range / value_range * y_range)
        else:
            y_margin = self.BASE_MARGIN
        if self.props.top_margin != y_margin:
            self.set_top_margin(y_margin)
            self.set_bottom_margin(y_margin)

        # Update side margins
        if width < 1:
            return
        if self.__line_length > 0 and width - 2 * self.BASE_MARGIN > self.__line_length:
            x_margin = (width - self.__line_length) / 2
        else:
            x_margin = y_margin
        if self.get_left_margin() != x_margin:
            self.set_left_margin(x_margin)
            self.set_right_margin(x_margin)

        self.emit("size-allocated")

    def move_cursor(self, x: float, y: float) -> None:
        # Move the cursor before the popup menu is shown, needed for libspelling to display
        # updated suggestions
        (buffer_x, buffer_y) = self.window_to_buffer_coords(Gtk.TextWindowType.TEXT, x, y)
        (_within, click_iter) = self.get_iter_at_location(buffer_x, buffer_y)
        buffer = self.get_buffer()
        buffer.place_cursor(click_iter)

    def update_font_family(self, font_family: str) -> None:
        """Update font family from system preference.

        :param str font_family: The font family
        """
        self.__font_family = font_family
        self.__update_font()

    def jump_to_insertion_point(self) -> None:
        """Jump to the insertion point.

        This jump is used to avoid issues with height allocation in `scroll_to_mark` when the
        buffer contains lines of varying height.
        """
        buffer = self.get_buffer()
        insert_iter = buffer.get_iter_at_mark(buffer.get_insert())
        location = self.get_iter_location(insert_iter)
        adjustment = self.get_vadjustment()
        adjustment.set_value(location.y)

    @GObject.Property(type=int, default=-1)
    def line_length(self) -> int:
        return self.__line_length

    @line_length.setter
    def line_length(self, value: int) -> None:
        self.__line_length = value

    @GObject.Property(type=bool, default=False)
    def spellchecker_enabled(self) -> bool:
        if self.__spelling_adapter is not None:
            return self.__spelling_adapter.get_enabled()
        return False

    @spellchecker_enabled.setter
    def spellchecker_enabled(self, value: bool) -> None:
        if self.__spelling_adapter is not None:
            self.__spelling_adapter.set_enabled(value)

    def __on_key_pressed(
        self,
        controller: Gtk.EventControllerKey,
        keyval: int,
        keycode: int,
        state: Gdk.ModifierType,
    ) -> bool:
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_ISO_Enter):
            if self.__process_newline():
                return Gdk.EVENT_STOP
        elif keyval in (Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab):
            self.__handle_tab(state != Gdk.ModifierType.SHIFT_MASK)
            return Gdk.EVENT_STOP

        return Gdk.EVENT_PROPAGATE

    def __on_spelling_toggled(self) -> None:
        if config_manager.get_spelling_enabled():
            self.__init_spellchecker()
            self.spellchecker_enabled = True
        else:
            self.spellchecker_enabled = False

    def __update_font(self) -> None:
        if not self.__css_provider:
            self.__css_provider = Gtk.CssProvider()
            self.get_style_context().add_provider(
                self.__css_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER
            )

        size = config_manager.get_font_size()
        style = f"""
        .editor-textview {{
            font-size: {size}pt;
            font-family: {self.__font_family}, monospace;
        }}"""
        self.__css_provider.load_from_data(style, -1)

    def __init_spellchecker(self) -> None:
        if self.__spellchecker is not None:
            return

        gi.require_version("Spelling", "1")
        from gi.repository import Spelling

        pref_language = config_manager.get_spelling_language()
        if pref_language is not None:
            language = pref_language
            logging.debug(f'Attempting to use spelling language from preference "{pref_language}"')
        else:
            language = locale.getdefaultlocale()[0]
            logging.debug(f'Attempting to use locale default spelling language "{language}"')

        self.__spellchecker = Spelling.Checker.get_default()
        self.__spellchecker.set_language(language)

        buffer = self.get_buffer()

        self.__spelling_adapter = Spelling.TextBufferAdapter.new(buffer, self.__spellchecker)

        extra_menu = self.__spelling_adapter.get_menu_model()
        self.set_extra_menu(extra_menu)
        self.insert_action_group("spelling", self.__spelling_adapter)

        self.spellchecker_enabled = False
        if pref_language is not None:
            self.__verify_preferred_language_in_use(pref_language)
        self.__spellchecker.connect(
            "notify::language", lambda _o, _v: self.__spelling_language_changed()
        )

    def __verify_preferred_language_in_use(self, pref_language: str) -> None:
        language_in_use = self.__spellchecker.get_language()
        if language_in_use != pref_language:
            logging.warning(
                f'Spelling language from preference "{pref_language}" not found, clearing'
                " preference"
            )

            logging.info("Available languages:")
            provider = Spelling.Provider.get_default()
            for language_info in provider.list_languages():
                logging.info(" - %s (%5s)" % (language_info.get_name(), language_info.get_code()))

            config_manager.set_spelling_language("")

    def __spelling_language_changed(self) -> None:
        language = self.__spellchecker.get_language()
        logging.info(f'New spelling language "{language}"')
        config_manager.set_spelling_language(language)
        self.__spelling_adapter.invalidate_all()

    def __check_line_for_bullet_list_item(self, searchterm: str) -> re.Match:
        term = r"^\s*("
        escaped_tokens = []
        for token in self.BULLET_LIST_TOKENS.keys():
            escaped_tokens.append(re.escape(token))
        term += "|".join(escaped_tokens)
        term += ")"
        return re.search(term, searchterm)

    def __check_line_for_ordered_list_item(self, searchterm: str) -> re.Match:
        term = r"^(\s*)([a-zA-Z]{1}|[0-9]+)([\.\)]){1}[ ]+"
        return re.search(term, searchterm)

    def __process_newline(self) -> bool:
        handled = False
        buffer = self.get_buffer()
        mark = buffer.get_insert()
        insert_iter = buffer.get_iter_at_mark(mark)

        line_start = insert_iter.copy()
        line_start.set_line_offset(0)
        previous_line = line_start.get_text(insert_iter)

        # TODO look at changing to use the GtkSourceLanguage context?
        regex_match = self.__check_line_for_bullet_list_item(previous_line)
        if regex_match is not None:
            handled = self.__extend_bullet_list(regex_match.group(), insert_iter, line_start)
        else:
            regex_match = self.__check_line_for_ordered_list_item(previous_line)
            if regex_match is not None:
                handled = self.__extend_ordered_list(regex_match.groups(), insert_iter, line_start)

        if handled:
            # Attempt to track cursor in viewport
            mark = buffer.get_insert()
            insert_iter = buffer.get_iter_at_mark(mark)
            buffer_coords = self.get_iter_location(insert_iter)
            visible_rect = self.get_visible_rect()
            if buffer_coords.y + buffer_coords.height >= visible_rect.y + visible_rect.height:
                # Without adding as an idle task we sometimes end up with an insufficient scroll
                GLib.idle_add(self.emit, "move-viewport", Gtk.ScrollStep.STEPS, 1)

        return handled

    def __extend_bullet_list(
        self, matched_list_item: str, insert_iter: Gtk.TextIter, line_start: Gtk.TextIter
    ) -> bool:
        buffer = self.get_buffer()
        previous_line = line_start.get_text(insert_iter)

        # If the list already continues after our newline, don't add the next item markup.
        # Caters for accidentally deleting a line break in the middle of a list and then
        # pressing enter to revert that.
        cur_line_end = insert_iter.copy()
        if not cur_line_end.ends_line():
            cur_line_end.forward_to_line_end()
        cur_line_text = insert_iter.get_text(cur_line_end)
        if self.__check_line_for_bullet_list_item(cur_line_text) is not None:
            return False

        def generate_sequence_previous_item() -> Optional[str]:
            return matched_list_item

        empty_list_line = self.inserted_empty_item_at_end_of_list(
            previous_line, matched_list_item, line_start, generate_sequence_previous_item
        )
        if empty_list_line:
            # An empty list line has been entered, remove it from the list end
            buffer.delete(line_start, insert_iter)
            buffer.insert_at_cursor("\n")
        else:
            dict_key = matched_list_item.lstrip()
            spacing = matched_list_item[0 : len(matched_list_item) - len(dict_key)]
            new_entry = f"\n{spacing}{self.BULLET_LIST_TOKENS[dict_key]}"
            buffer.insert_at_cursor(new_entry)
        return True

    def __extend_ordered_list(
        self, regex_groups: tuple, insert_iter: Gtk.TextIter, line_start: Gtk.TextIter
    ) -> bool:
        buffer = self.get_buffer()
        spacing = regex_groups[0]
        index = regex_groups[1]
        marker = regex_groups[2]
        previous_line = line_start.get_text(insert_iter)

        def generate_sequence_previous_item() -> Optional[str]:
            # Verify there's more than one list item. This allows inserting lines with list start
            # tokens and nothing else.
            previous_index = EditorTextView.calculate_ordered_list_index(index, -1)
            if previous_index is None:
                return None
            else:
                return self.format_ordered_list_item(spacing, previous_index, marker)

        empty_list_line = self.inserted_empty_item_at_end_of_list(
            previous_line, "".join(regex_groups), line_start, generate_sequence_previous_item
        )
        if empty_list_line:
            # An empty list line has been entered, remove it from the list end
            buffer.delete(line_start, insert_iter)
            buffer.insert_at_cursor("\n")
        else:
            sequence_next = self.calculate_ordered_list_index(index, 1)
            # Handle value of Z, ending sequence
            if sequence_next is None:
                return False
            new_entry = "\n" + self.format_ordered_list_item(spacing, sequence_next, marker)
            buffer.insert(insert_iter, new_entry)

        return True

    def __handle_tab(self, increase: bool) -> None:
        buffer = self.get_buffer()
        if buffer.get_has_selection():
            begin, end = buffer.get_selection_bounds()
            begin.order(end)
            multi_line = "\n" in buffer.get_text(begin, end, False)
            if multi_line:
                line_iter = begin.copy()
                line_mark = buffer.create_mark(None, line_iter)
                end_mark = buffer.create_mark(None, end)
                while line_iter.compare(end) < 0:
                    self.__modify_single_line_indent(line_iter, increase, multi_line)
                    line_iter = buffer.get_iter_at_mark(line_mark)
                    line_iter.forward_line()
                    buffer.delete_mark(line_mark)
                    line_mark = buffer.create_mark(None, line_iter)
                    end = buffer.get_iter_at_mark(end_mark)
                buffer.delete_mark(line_mark)
                buffer.delete_mark(end_mark)
            else:
                self.__modify_single_line_indent(begin, increase, multi_line)
        else:
            mark = buffer.get_insert()
            begin = buffer.get_iter_at_mark(mark)
            self.__modify_single_line_indent(begin, increase, False)

    def __modify_single_line_indent(
        self, location: Gtk.TextIter, increase: bool, multi_line: bool
    ) -> None:
        buffer = self.get_buffer()
        line_start = location.copy()
        line_start.set_line_offset(0)
        line_end = location.copy()
        if not line_end.ends_line():
            line_end.forward_to_line_end()
        line_contents = buffer.get_text(line_start, line_end, False)

        # Don't process empty lines
        if multi_line and line_contents == "":
            return

        list_item = (
            self.__check_line_for_bullet_list_item(line_contents) is not None
            or self.__check_line_for_ordered_list_item(line_contents) is not None
        )
        indent_chars = "  " if list_item else "\t"

        if increase:
            if multi_line or list_item:
                buffer.insert(line_start, indent_chars)
            else:
                buffer.insert(location, indent_chars)
        else:
            if line_contents.startswith(indent_chars):
                end_deletion = line_start.copy()
                end_deletion.forward_chars(len(indent_chars))
                buffer.delete(line_start, end_deletion)

    @staticmethod
    def inserted_empty_item_at_end_of_list(
        line_text: str,
        matched_list_item: str,
        previous_line_start: Gtk.TextIter,
        fetch_sequence_previous: Callable[[], Optional[str]],
    ) -> bool:
        """Determine whether we have inserted an empty item at the end of a list

        The list needs to have at least one previous item.

        :param str line_text: The full line text
        :param str matched_list_item: Our matched list marker
        :param Gtk.TextIter previous_line_start: The start of the previous line
        :param Callable[], Optional[str]] fetch_sequence_previous: A function to fetch a previous
            line's marker
        :return: Whether we've inserted an empty line
        :rtype: bool
        """

        # Check if entered line contains only the list item markup
        if line_text.strip() != matched_list_item.strip():
            return False

        # Fetch what a previous item in the sequence would have been, for the check below. The
        # callable is used to prevent calculating this before we even know if match above will
        # pass (while sharing logic for bullet and ordered lists).
        sequence_previous_item = fetch_sequence_previous()
        if sequence_previous_item is None:
            return False

        # Verify there's more than one list item. This allows inserting lines with list start
        # tokens and nothing else.
        two_prev_start = previous_line_start.copy()
        two_prev_start.backward_line()
        two_prev_start.set_line_offset(0)
        two_prev_line = two_prev_start.get_text(previous_line_start)
        return two_prev_line.startswith(sequence_previous_item)

    @staticmethod
    def calculate_ordered_list_index(reference: str, direction: int) -> Optional[str]:
        """Calculate an item in an ordered list sequence.

        :param str reference: The element to start from
        :param str direction: The direction, 1 or -1
        :return: The item
        :rtype: Optional[str]
        """
        sequence_next = None
        if reference.isdigit():
            sequence_next = str(int(reference) + direction)
            if sequence_next == 0:
                sequence_next = None
        elif direction > 0 and reference.upper() != "Z":
            sequence_next = chr(ord(reference) + 1)
        elif direction < 0 and reference.upper() != "A":
            sequence_next = chr(ord(reference) - 1)
        return sequence_next

    @staticmethod
    def format_ordered_list_item(spacing: str, index: str, delimiter: str) -> str:
        """Generate string for list item.

        :param str spacing: Pre marker spacing
        :param str index: Item index
        :param str delimiter: The delimiter before the item text
        :return: The build string
        :rtype: str
        """
        return f"{spacing}{index}{delimiter} "
