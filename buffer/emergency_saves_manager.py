from gi.repository import Gio, GObject, GLib

import datetime
import logging
import os
from pathlib import Path
from typing import Optional

import buffer.config_manager as config_manager


class EmergencySavesManager(GObject.Object):

    DEFAULT_EMERGENCY_FILES = 10
    DIRECTORY = os.path.join(GLib.get_user_data_dir(), "buffer", "recovery")

    def __init__(self) -> None:
        super().__init__()

    def save(self, contents: str) -> None:
        """Save to file.

        :param str contents: Buffer contents
        """
        if config_manager.get_emergency_recover_files() == 0:
            return
        if not self.__init_export_dir():
            return

        filename = self.__get_unique_filename()
        if filename:
            self.__save(filename, contents)
            self.__trim()

    def __init_export_dir(self) -> bool:
        if not os.path.exists(self.DIRECTORY):
            try:
                os.makedirs(self.DIRECTORY)
            except OSError as e:
                logging.warning(
                    f"Failed to create emergency recovery directory {self.DIRECTORY}: %s", e
                )
                return False
        return True

    def __get_unique_filename(self) -> Optional[str]:
        attempts = 0
        success = False
        while attempts < 100:
            ts = datetime.datetime.now()
            location = os.path.join(self.DIRECTORY, ts.strftime("%Y-%m-%dT%H%M%S.%f.txt"))
            if not os.path.exists(location):
                success = True
                break
            attempts += 1
        return location if success else None

    def __save(self, filename: str, contents: str) -> None:
        try:
            with open(filename, "w") as f:
                f.write(contents)
        except OSError as e:
            logging.warning(f"Failed to save to {filename}: %s", e)
            return
        logging.info(f"Saved to {filename}")

    def __trim(self) -> None:
        paths = sorted(Path(self.DIRECTORY).iterdir(), key=os.path.getmtime)
        paths = [x for x in paths if x.suffix == ".txt"]
        limit = config_manager.get_emergency_recover_files()
        if len(paths) > limit:
            for path in paths[: len(paths) - limit]:
                try:
                    logging.debug(f"Trimming {path}")
                    Path.unlink(path)
                except OSError as e:
                    logging.warning(
                        f"Failed to remove {path} for emergency recovery trimming: %s", e
                    )
        else:
            logging.debug(f"Not trimming recovery files, count {len(paths)} < {limit}")

    @staticmethod
    def show_directory() -> None:
        """Show saves directory in file manager."""
        if os.path.exists(EmergencySavesManager.DIRECTORY):
            Gio.AppInfo.launch_default_for_uri(f"file://{EmergencySavesManager.DIRECTORY}", None)
