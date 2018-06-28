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

import os

from ictv.app import sidebar
from ictv.common.logging import loggers_stats, get_logger_file_path
from ictv.pages.utils import ICTVAuthPage, PermissionGate
from ictv.common.utils import timesince, pretty_print_size
from ictv.common import get_root_path


class LogsPage(ICTVAuthPage):
    @PermissionGate.super_administrator
    @sidebar
    def GET(self):
        for name in loggers_stats:
            try:
                size = os.path.getsize(os.path.join(get_root_path(), "logs", "%s.log" % name))
            except FileNotFoundError:
                size = 0
            loggers_stats[name]["size"] = pretty_print_size(size)
        return self.renderer.logs(loggers_stats, time_since=timesince)


class ServeLog(ICTVAuthPage):
    @PermissionGate.super_administrator
    def GET(self, log_name):
        log_path = get_logger_file_path(log_name)
        if log_path and os.path.exists(log_path):
            with open(log_path, 'r') as f:
                return f.read()
        return ''
