from gi.repository import GObject

import logging
from typing import Callable

import buffer.config_manager as config_manager
from buffer import const


class MigrationAssistant(GObject.Object):

    def __init__(self) -> None:
        self.__version_migrations: dict[str, Callable[[], None]] = {}

    def handle_version_migration(self) -> None:
        previous_version = config_manager.get_last_launched_version()
        current_version = const.VERSION
        if "-" in current_version:
            current_version = current_version.split("-")[0]
        if previous_version != current_version:
            if previous_version != "":
                if current_version > previous_version:
                    logging.info(f"Updating to v{current_version}")
                    if current_version in self.__version_migrations:
                        self.__version_migrations[current_version]()
                else:
                    logging.info(f"Downgrading to v{current_version}?")
            config_manager.set_last_launched_version(current_version)
