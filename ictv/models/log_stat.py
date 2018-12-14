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

from sqlobject import StringCol, DateTimeCol, SQLObjectNotFound, IntCol

from ictv.models.ictv_object import ICTVObject


class LogStat(ICTVObject):
    logger_name = StringCol(notNone=True, alternateID=True,length=50)
    last_debug = DateTimeCol(default=None)
    last_info = DateTimeCol(default=None)
    last_warning = DateTimeCol(default=None)
    last_error = DateTimeCol(default=None)
    n_entries = IntCol(notNone=True, default=0)

    @property
    def last_activity(self):
        infos = [i for i in [self.last_debug, self.last_info, self.last_warning, self.last_error] if i is not None]
        return max(infos) if infos else None

    @classmethod
    def dump_log_stats(cls, log_stats):
        for name, stats in log_stats.items():
            try:
                log_stat = LogStat.byLogger_name(name)
            except SQLObjectNotFound:
                log_stat = LogStat(logger_name=name)
            for attr_name, stat_name in [("last_debug", "DEBUG"), ("last_info", "INFO"), ("last_warning", "WARNING"),
                                         ("last_error", "ERROR"), ("n_entries", "n_entries")]:
                try:
                    setattr(log_stat, attr_name, stats[stat_name])
                except KeyError:
                    setattr(log_stat, attr_name, None if attr_name != "n_entries" else 0)

    @classmethod
    def load_log_stats(cls):
        result = {}
        for log_stat in LogStat.select():
            result[log_stat.logger_name] = {}
            for attr_name, stat_name in [("last_debug", "DEBUG"), ("last_info", "INFO"), ("last_warning", "WARNING"),
                                         ("last_error", "ERROR"), ("last_activity", "last_activity"),
                                         ("n_entries", "n_entries")]:
                if getattr(log_stat, attr_name) is not None:
                    result[log_stat.logger_name][stat_name] = getattr(log_stat, attr_name)
        return result
