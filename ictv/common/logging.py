# -*- coding: utf-8 -*-
#
#    This file belongs to the ICTV project, written by Nicolas Detienne,
#    Francois Michel, Maxime Piraux, Pierre Reinbold and Ludovic Taffin
#    at Université catholique de Louvain.
#
#    Copyright (C) 2016-2018  Université catholique de Louvain (UCL, Belgium)
#
#    ICTV is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    ICTV is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with ICTV.  If not, see <http://www.gnu.org/licenses/>.

import logging
import logging.handlers
import os
from datetime import datetime

from ictv import get_root_path

from ictv.models.log_stat import LogStat

loggers_stats = {}
_logger_name_to_file = {}


class StatHandler(logging.Handler):
    """ An utility class which keeps track of the latest date where a log message was received. """

    def __init__(self, name, file_path, level=logging.NOTSET):
        _logger_name_to_file[name] = file_path
        self._logger_name = name
        if self._logger_name not in loggers_stats:
            loggers_stats[self._logger_name] = {'n_entries': 0}
        super().__init__(level)

    def emit(self, record):
        now = datetime.now()
        loggers_stats[self._logger_name][record.levelname] = now
        loggers_stats[self._logger_name]['last_activity'] = now
        loggers_stats[self._logger_name]['n_entries'] = 0


def count_entries(logger_name):
    """ Count the number of entries in each log file and return this number for the logger_name """
    n_entries = 0
    try:
        with open(os.path.join(get_root_path(), "logs", "%s.log" % logger_name)) as log_file:
            for line in log_file:
                if line.startswith("DEBUG : ") or line.startswith("INFO : ") or line.startswith(
                        "WARNING : ") or line.startswith("ERROR : "):
                    n_entries += 1
    except FileNotFoundError:   # loggers in db with no log file anymore (the file can be created later): their
        # number of entries will be 0
        pass
    return n_entries


def load_loggers_stats():
    """ return a dictionary containing the information concerning the loggers stored in database """
    for log_stat in LogStat.select():
        log_stat.n_entries = count_entries(log_stat.logger_name)
    loggers_stats.update(LogStat.load_log_stats())


def init_logger(logger_name, level=logging.INFO, rotation_interval=7, backup_count=2):
    if not os.path.exists(os.path.join(get_root_path(), 'logs')):
        os.mkdir(os.path.join(get_root_path(), 'logs'))

    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    formatter = logging.Formatter('%(levelname)s : %(asctime)s - %(message)s')
    logger_file_path = os.path.join(get_root_path(), 'logs', logger_name + os.extsep + 'log')
    file_handler = logging.handlers.TimedRotatingFileHandler(logger_file_path, when='D', interval=rotation_interval, backupCount=backup_count)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(StatHandler(logger_name, logger_file_path))


def get_logger_file_path(logger_name):
    return _logger_name_to_file.get(logger_name)
