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

import tempfile
import threading

from sqlobject import connectionForURI
from sqlobject import sqlhub

from ictv.models.asset import Asset
from ictv.models.building import Building
from ictv.models.channel import Channel, PluginChannel, ChannelBundle
from ictv.models.ictv_object import DBVersion
from ictv.models.log_stat import LogStat
from ictv.models.plugin import Plugin
from ictv.models.plugin_param_access_rights import PluginParamAccessRights
from ictv.models.role import Role
from ictv.models.screen import Screen, ScreenMac
from ictv.models.subscription import Subscription
from ictv.models.template import Template
from ictv.models.user import User
from ictv.common.utils import is_test

database_version = 0
if is_test():
    database_path = 'sqlite://' + tempfile.mkstemp()[1]
else:
    database_path = None


class SQLObjectThreadConnection(object):
    _local = threading.local()

    @classmethod
    def get_conn(cls):
        if 'conn' not in cls._local.__dict__:
            cls._local.conn = create_connection()

        return cls._local.conn


def create_connection():
    return setup_connection(connectionForURI(database_path, cache=False))


def setup_connection(conn):
    if database_path.startswith('sqlite:'):
        conn.queryOne('PRAGMA foreign_keys = ON;')
        assert conn.queryOne('PRAGMA foreign_keys;') == (1,)
        conn.queryOne('PRAGMA busy_timeout = 100000;')
    return conn


def setup_database():
    sqlhub.processConnection = create_connection()


def close_database():
    try:
        sqlhub.threadConnection.close()
    except AttributeError:
        pass
    sqlhub.processConnection.close()


def create_database():
    Building.createTable()
    Channel.createTable()
    Plugin.createTable()
    User.createTable()
    PluginChannel.createTable()
    ChannelBundle.createTable()
    Role.createTable()
    Screen.createTable()
    ScreenMac.createTable()
    Subscription.createTable()
    Template.createTable()
    Asset.createTable()
    PluginParamAccessRights.createTable()
    LogStat.createTable()
    DBVersion.createTable()
    DBVersion(version=database_version)
    User(username="admin", fullname="ICTV Admin", email="admin@ictv", super_admin=True, disabled=False)


def update_database():
    sqlhub.processConnection = create_connection()
    conn = sqlhub.processConnection
    if not DBVersion.tableExists():
        DBVersion.createTable()
        DBVersion(version=database_version)
    db_version = DBVersion.select().getOne().version
    if db_version < 1:
        print('Updating database to version %d' % 1)
        column_sql = PluginChannel.sqlmeta.getColumns()['drop_silently_non_complying_slides'].sqliteCreateSQL()
        table = PluginChannel.sqlmeta.table
        assert conn.queryOne('ALTER TABLE %s ADD %s' % (table, column_sql)) is None
        db_version = 1
    DBVersion.select().getOne().set(version=db_version)


def load_plugins():
    from ictv.plugin_manager.plugin_manager import PluginManager
    Plugin.update_plugins(PluginManager.list_plugins())
    for module in PluginManager.get_plugins_modules():
        if hasattr(module, 'install'):
            getattr(module, 'install')()
