from gi.repository import GObject

from buffer.editor_search_entry import EditorSearchEntry
from buffer.editor_search_header_bar import EditorSearchHeaderBar
from buffer.editor_text_view import EditorTextView
from buffer.timed_revealer_notification import TimedRevealerNotification


def load_widgets() -> None:
    """Ensure that the types have been registered with the type system.

    Allows them to be used in template UI files.
    """
    GObject.type_ensure(EditorSearchEntry)
    GObject.type_ensure(EditorSearchHeaderBar)
    GObject.type_ensure(EditorTextView)
    GObject.type_ensure(TimedRevealerNotification)
