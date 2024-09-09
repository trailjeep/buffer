from gi.repository import GObject

import logging
from typing import Callable, Dict

import buffer.config_manager as config_manager
from buffer import const


class MigrationAssistant(GObject.Object):

    def __init__(self) -> None:
        self.__version_migrations: Dict[str, Callable[[], None]] = {}

    def handle_version_migration(self) -> None:
        previous_version = config_manager.get_last_launched_version()
        current_version = const.VERSION
        if "-" in current_version:
            current_version = current_version.split("-")[0]
        if previous_version != current_version:
            if previous_version != "":
                if current_version > previous_version:
                    logging.info("Updating to v{}".format(current_version))
                    if current_version in self.__version_migrations:
                        self.__version_migrations[current_version]()
                else:
                    logging.info("Downgrading to v{}?".format(current_version))
            config_manager.set_last_launched_version(current_version)
