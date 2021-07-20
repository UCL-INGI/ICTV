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

import json
from abc import abstractmethod

import builtins
from abc import abstractmethod

import itertools
from sqlobject import ForeignKey, StringCol, DatabaseIndex, SQLRelatedJoin, EnumCol, JSONCol, SQLMultipleJoin, BoolCol, IntCol
from sqlobject.inheritance import InheritableSQLObject

import ictv.common.utils as utils
from ictv.models.plugin_param_access_rights import PluginParamAccessRights
from ictv.models.role import Role, UserPermissions
from ictv.models.user import User


class Channel(InheritableSQLObject):
    name = StringCol(notNone=True, unique=True, length=100)
    description = StringCol(default=None)
    enabled = BoolCol(notNone=True, default=True)
    subscription_right = EnumCol(enumValues=['public', 'restricted', 'private'])
    authorized_subscribers = SQLRelatedJoin('User')
    secret = StringCol(notNone=True, default=lambda: utils.generate_secret())
    subscriptions = SQLMultipleJoin('Subscription')
    bundles = SQLRelatedJoin('ChannelBundle')

    def can_subscribe(self, usr):
        """ Return whether this user has sufficient permission to be able to subscribe to this channel or not. """
        if isinstance(usr,dict):
            # Retreive User instance when called from template
            user = User.get(usr["id"])
        else:
            user = usr
        return self.subscription_right == 'public' or UserPermissions.administrator in user.highest_permission_level or user in self.authorized_subscribers

    def safe_add_user(self, user):
        """ Avoid user duplication in channel authorized subscribers. """
        if user not in self.authorized_subscribers:
            self.addUser(user)

    @classmethod
    def get_channels_authorized_subscribers_as_json(cls, channels):
        """
            Return the string representation of a dictionary in the form
                {
                    channel.id:
                    [
                        user.id,
                        ...
                    ]
                }
        """
        channels_authorized_subscribers = {}
        for channel in channels:
            channels_authorized_subscribers[channel.id] = [u.id for u in channel.authorized_subscribers]
        return json.dumps(channels_authorized_subscribers)

    @classmethod
    def get_visible_channels_of(cls, user):
        """
            Returns the channels that are accessible for the user (public channels or channels
            with the user specified in authorized_subscribers, or all channels if the user is superadmin)
            :param user: The user to retrieve the accessible channels.
            :return: A iterable with the accessible channels (iterable of sqlobjects)
        """
        if UserPermissions.administrator in user.highest_permission_level:
            return set(Channel.select())
        public_channels = set(Channel.selectBy(subscription_right='public')) if UserPermissions.screen_administrator in \
                                                                                user.highest_permission_level else set()
        return public_channels | set(Role.selectBy(user=user).throughTo.channel) | set(
            User.selectBy(id=user.id).throughTo.authorized_channels)

    @classmethod
    def get_screens_channels_from(cls, user):
        """
            Return the intersection between 3 sets of channels: all the public channels,
            all the channel this user is authorized to subscribe
            and all the channel the screens this user has access are subscribed to.
            The resulting data type is a set of Channel instances.
        """
        if user.super_admin:
            return set(Channel.select())
        return set(c for c in Channel.selectBy(subscription_right='public')) | \
               set(c for c in user.authorized_channels) | \
               set(c for c in user.screens.throughTo.subscriptions.throughTo.channel)

    def get_preview_link(self):
        """ Returns the secret preview link of this channel. """
        return '/preview/channels/' + str(self.id) + '/' + self.secret

    @abstractmethod
    def flatten(self, keep_disabled_channels=False):
        """ Returns all the channels contained in this channel and the channels it contains as an Iterable[Channel]"""

    @abstractmethod
    def get_type_name(self):
        """ Returns a string representing the name of the subtype to be used in the UI for this class. """


class PluginChannel(Channel):
    plugin = ForeignKey('Plugin', cascade=True)
    plugin_config = JSONCol(notNone=True, default={})
    assets = SQLMultipleJoin('Asset')
    cache_activated = BoolCol(default=None)
    cache_validity = IntCol(default=None)
    keep_noncomplying_capsules = BoolCol(default=None)
    drop_silently_non_complying_slides = BoolCol(default=False)

    def give_permission_to_user(self, user: User,
                                permission_level: UserPermissions = UserPermissions.channel_contributor) -> None:
        """
        Give permission to the user or modify existing permission previously given.
        :param user: The user receiving the permission level on this channel.
        :param permission_level: The level of permission to give on this channel.
        :return: None
        """
        role = Role.selectBy(user=user, channel=self).getOne(None)
        if role is None:
            Role(user=user, channel=self, permission_level=permission_level)
        else:
            role.permission_level = permission_level

    def remove_permission_to_user(self, user: User) -> None:
        """
        Remove previously given permission to the user
        :param user: The user to withdraw permission on this channel.
        :return:
        """
        role = Role.selectBy(user=user, channel=self).getOne(None)
        if role is not None:
            role.destroySelf()

    def get_channel_permissions_of(self, user):
        """
        Return the permission level of this user on this channel.
        :return: UserPermissions
        """
        role = Role.selectBy(user=user, channel=self).getOne(None)
        if role is not None:
            return role.permission_level
        return UserPermissions.no_permission

    def has_admin(self, user):
        """ Return whether this user has sufficient permission to be considered as admin of this channel. """
        return UserPermissions.channel_administrator in self.get_channel_permissions_of(user)

    def has_contrib(self, user):
        """ Return whether this user has sufficient permission to be considered as contributor of this channel. """
        return UserPermissions.channel_contributor in self.get_channel_permissions_of(user)

    def _get_users_with_permissions(self, permission_level):
        """ Return a list of users with sufficient permission on this channel. """
        return Role.selectBy(channel=self, permission_level=UserPermissions.get_permission_string(
            permission_level)).throughTo.user

    def get_admins(self):
        """ Return a list of users with administrator permission on this channel. """
        return self._get_users_with_permissions(UserPermissions.channel_administrator)

    def get_contribs(self):
        """ Return a list of users with contributor permission on this channel. """
        return self._get_users_with_permissions(UserPermissions.channel_contributor)

    def _get_users_as_dict(self):
        """
            Return a dictionary in the form
                {
                    user.id: UserPermissions integer value,
                    ...
                }
        """
        return {role.user.id: role.permission_level.value for role in Role.selectBy(channel=self)}

    def get_users_as_json(self):
        """
            Return the string representation of a JSON object in the form
                {
                    user.id: UserPermissions integer value,
                    ...
                }
        """
        return json.dumps(self._get_users_as_dict())

    @classmethod
    def get_channels_users_as_json(cls, channels):
        """
            Return the string representation of a JSON object in the form
                {
                    channel.id:
                    {
                        user.id: UserPermissions integer value,
                        ...
                    }
                }
        """
        return json.dumps({c.id: c._get_users_as_dict() for c in channels})

    def get_config_param(self, param):
        """
            Returns the value of the given parameter according to this channel configuration
            or the default value in the plugin configuration if one exists. Otherwise raises a KeyError
        """
        default = self.plugin.channels_params[param]['default']
        value_type = self.plugin.channels_params[param]['type']
        if param not in self.plugin_config and (type(default) is not str or len(default) > 0):
            return vars(builtins)[value_type](default) if value_type in vars(builtins) else default
        if param in self.plugin_config:
            if value_type in vars(builtins):
                return vars(builtins)[value_type](self.plugin_config[param])
            return self.plugin_config[param]

    def has_visible_params_for(self, user):
        """ Returns true if the given user has access to one or more parameters of this channel. """
        if user.super_admin:
            return True
        if user.admin:
            return PluginParamAccessRights.selectBy(plugin=self.plugin, administrator_read=True).count() > 0
        if self.has_admin(user):
            return PluginParamAccessRights.selectBy(plugin=self.plugin, channel_administrator_read=True).count() > 0
        if self.has_contrib(user):
            return PluginParamAccessRights.selectBy(plugin=self.plugin, channel_contributor_read=True).count() > 0
        return False

    def get_access_rights_for(self, param_name, user):
        """
            Returns a tuple of booleans (read_access, write_access) indicating which type of rights
            this user has on the given param of this channel depending on they role and the param access configuration.
        """
        if user.super_admin:
            return True, True
        rights = PluginParamAccessRights.selectBy(plugin=self.plugin, name=param_name).getOne((False, False))
        if user.admin:
            return rights.administrator_read, rights.administrator_write
        if self.has_admin(user):
            return rights.channel_administrator_read, rights.channel_administrator_write
        if self.has_contrib(user):
            return rights.channel_contributor_read, rights.channel_contributor_write
        return False, False

    def _get_cache_activated(self):
        value = self._SO_get_cache_activated()
        if value is None:
            return self.plugin.cache_activated_default
        return value

    def _get_cache_validity(self):
        value = self._SO_get_cache_validity()
        if value is None:
            return self.plugin.cache_validity_default
        return value

    def _get_keep_noncomplying_capsules(self):
        value = self._SO_get_keep_noncomplying_capsules()
        if value is None:
            return self.plugin.keep_noncomplying_capsules_default
        return value

    def flatten(self, keep_disabled_channels=False):
        return [self] if self.enabled or keep_disabled_channels else []

    def get_type_name(self):
        """ Returns a string representing the name of the subtype to be used in the UI for this class. """
        return 'Plugin %s' % self.plugin.name


class ChannelBundle(Channel):
    _bundled_channels = SQLRelatedJoin('Channel')

    @property
    def bundled_channels(self):
        """
            Fixes getting the bundled channels when using SQLRelatedJoin.
            Do NOT use directly the attribute but use this method instead.
        """
        return ChannelBundle.selectBy(id=self).throughTo._bundled_channels

    def add_channel(self, channel):
        """ Avoids channel duplication in bundled channels. """
        if channel not in self.bundled_channels and self.has_no_cycles(list(self.bundled_channels) + [channel]):
            self.addChannel(channel)

    def remove_channel(self, channel):
        if channel in self.bundled_channels:
            self.removeChannel(channel)

    def flatten(self, keep_disabled_channels=False):
        channels_iterable_list = []
        for channel in self.bundled_channels:
            if channel.enabled or keep_disabled_channels:
                channels_iterable_list.append(channel.flatten(keep_disabled_channels=keep_disabled_channels))
        return itertools.chain.from_iterable(channels_iterable_list)

    def get_type_name(self):
        return 'Bundle'

    def has_no_cycles(self, channels, marked=None):
        if marked is None:
            marked = set()
        if self.id in marked:
            raise ValueError('A cycle was found with channel %s' % self.name)
        marked.add(self.id)
        for c in channels:
            if type(c) == ChannelBundle:
                c.has_no_cycles(c.bundled_channels, marked)
        marked.remove(self.id)
        return True
