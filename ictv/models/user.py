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

from ictv.common import utils
from sqlobject import StringCol, BoolCol, SQLMultipleJoin, SQLRelatedJoin, SQLRelatedJoin

from ictv.models.ictv_object import ICTVObject
from ictv.models.role import UserPermissions, Role
from ictv.models.subscription import Subscription


class User(ICTVObject):
    username = StringCol(unique=True, default=None)
    fullname = StringCol(default=None)
    email = StringCol(notNone=True, alternateID=True)
    super_admin = BoolCol(notNone=True, default=False)
    admin = BoolCol(notNone=True, default=False)
    disabled = BoolCol(notNone=True, default=True)
    capsules = SQLMultipleJoin('Capsule', joinColumn='owner_id')
    screens = SQLRelatedJoin('Screen')
    authorized_channels = SQLRelatedJoin('Channel')
    roles = SQLMultipleJoin('Role', joinColumn='user_id')
    password = StringCol(default=None)  # Used for local login
    reset_secret = StringCol(notNone=True)  # Used for local login to reset password
    has_toured = BoolCol(default=False)  # Has the user completed the app tour

    def __init__(self, *args, **kwargs):
        kwargs['reset_secret'] = utils.generate_secret()
        super().__init__(**kwargs)

    def _get_log_name(self):
        """ Returns a log friendly and unique name for this user. """
        return "%s (%d)" % (self.fullname if self.fullname else self.email, self.id)

    def _get_readable_name(self):
        """ Returns a user friendly and unique name for this user. """
        return self.fullname if self.fullname is not None else self.username if self.username is not None else self.email

    def _get_highest_permission_level(self):
        """ Return the highest permission level of this user. """
        if self.super_admin:
            return UserPermissions.super_administrator
        if self.admin:
            return UserPermissions.administrator
        highest = UserPermissions.no_permission
        for role in self.roles:
            if role.permission_level not in highest:
                highest = role.permission_level
            if highest == UserPermissions.channel_administrator:
                break
        if self.owns_screen():
            highest = highest | UserPermissions.screen_administrator
        return highest

    def get_channels_with_permission_level(self, permission_level):
        """ Returns the channels which precisely grants this permission level to the user. """
        return Role.selectBy(user=self, permission_level=UserPermissions.get_permission_string(permission_level)).throughTo.channel

    def owns_screen(self):
        """ Return wheter or not this user is owner of screens. """
        return self.screens.count() > 0

    def get_subscriptions_of_owned_screens(self):
        """ Return the subscriptions of the screens possessed by this user. """
        if UserPermissions.administrator in self.highest_permission_level:
            return Subscription.select()
        return self.screens.throughTo.subscriptions

    class sqlmeta:
        table = "user_table"   # prevent table name to collide with reserved keywords of some databases
