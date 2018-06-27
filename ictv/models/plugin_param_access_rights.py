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

from sqlobject import ForeignKey, StringCol, BoolCol

from ictv.models.ictv_object import ICTVObject
from ictv.models.role import UserPermissions


class PluginParamAccessRights(ICTVObject):
    plugin = ForeignKey('Plugin', cascade=True)
    name = StringCol(notNone=True)
    channel_contributor_read = BoolCol(default=False)
    channel_contributor_write = BoolCol(default=False)
    channel_administrator_read = BoolCol(default=True)
    channel_administrator_write = BoolCol(default=False)
    administrator_read = BoolCol(default=True)
    administrator_write = BoolCol(default=True)

    def get_access_rights_for(self, permission_level):
        """
            Returns a tuple of booleans (read_access, write_access) indicating which type of rights
            this permission level gives on this.
        """
        if permission_level is UserPermissions.super_administrator:
            return True, True
        if permission_level is UserPermissions.administrator:
            return self.administrator_read, self.administrator_write
        if permission_level is UserPermissions.channel_administrator:
            return self.channel_administrator_read, self.channel_administrator_write
        if permission_level is UserPermissions.channel_contributor:
            return self.channel_contributor_read, self.channel_contributor_write
        return False, False
