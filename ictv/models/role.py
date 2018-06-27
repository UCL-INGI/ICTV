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

from sqlobject import ForeignKey, EnumCol, DatabaseIndex

from ictv.models.ictv_object import ICTVObject
from ictv.common.enum import FlagEnum


class Role(ICTVObject):
    role_id = DatabaseIndex('user', 'channel', unique=True)
    user = ForeignKey('User', cascade=True)
    channel = ForeignKey('PluginChannel', cascade=True)
    permission_level = EnumCol(enumValues=['channel_contributor', 'channel_administrator'])

    def _get_permission_level(self):
        """ Magic method to hide enums from SQLObject into a more elegant abstraction. """
        return UserPermissions[self._SO_get_permission_level()]

    def _set_permission_level(self, value):
        """ Magic method to hide enums from SQLObject into a more elegant abstraction. """
        self._SO_set_permission_level(UserPermissions.get_permission_string(value))


class UserPermissions(FlagEnum):
    """
        UserPermissions is a flaggable enum class.
        This class is used to represent the highest permission level of an user.
        You can test if a user has a specific permission using the `in` operator, e.g. UserPermissions.channel_contributor in user.higher_permission_level.
    """
    no_permission = 0b0000
    channel_contributor = 0b0001
    channel_administrator = 0b0010 | channel_contributor
    screen_administrator = 0b0100
    administrator = 0b1000 | channel_administrator | screen_administrator
    super_administrator = 0b10000 | administrator

    def __hash__(self):
        return self.value

    @classmethod
    def get_permission_string(cls, permission_level):
        """ Returns the string used for the Role SQLObject corresponding to this permission level. """
        if permission_level == UserPermissions.channel_administrator:
            return 'channel_administrator'
        elif permission_level == UserPermissions.channel_contributor:
            return 'channel_contributor'
        raise ValueError('This permission level is not allowed')

    @classmethod
    def get_permission_name(cls, permission_level):
        """ Returns the pretty name of the given permission level. """
        _permission_to_name = {
            UserPermissions.no_permission: 'No permission',
            UserPermissions.channel_contributor: 'Contributor',
            UserPermissions.channel_administrator: 'Channel administrator',
            UserPermissions.screen_administrator: 'Screen administrator',
            UserPermissions.administrator: 'Administrator',
            UserPermissions.super_administrator: 'Super administrator'
        }
        return _permission_to_name[permission_level]
