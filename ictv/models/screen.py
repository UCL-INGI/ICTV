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

import itertools
import random

from sqlobject import StringCol, DatabaseIndex, SQLRelatedJoin, ForeignKey, SQLMultipleJoin, DateTimeCol, BoolCol, \
    SQLMultipleJoin, EnumCol

import ictv.common.utils as utils
from ictv.models.channel import PluginChannel, ChannelBundle
from ictv.models.role import UserPermissions
from ictv.models.ictv_object import ICTVObject
from ictv.models.subscription import Subscription


class Screen(ICTVObject):
    name = StringCol(notNone=True, length =100)
    building = ForeignKey('Building', notNone=True, cascade=False)
    location = StringCol(default=None)  # A free text field to precise the screen location
    screen_id = DatabaseIndex('name', 'building', unique=True)
    owners = SQLRelatedJoin('User')
    subscriptions = SQLMultipleJoin('Subscription')
    secret = StringCol(notNone=True, default=utils.generate_secret)
    macs = SQLMultipleJoin('ScreenMac')
    last_ip = StringCol(default=None)
    last_access = DateTimeCol(default=None)
    shuffle = BoolCol(default=False)
    comment = StringCol(default=None)
    show_postit = BoolCol(default=False)
    show_slide_number = BoolCol(default=False)
    orientation = EnumCol(enumValues=['Landscape','Portrait'],default='Landscape')

    @property
    def subscribed_channels(self):
        return self.subscriptions.throughTo.channel

    def subscribe_to(self, user, channel, weight=1):
        """
        Subscribes this screen to the channel. If this screen is already subscribed to the channel by the user, it changes the weight if needed.

        :param user: The user requesting the subscription.
        :param channel: The channel to subscribe this screen to.
        :param weight: The optional positive non null weight to give to the channel by this screen.
        :return: None
        """
        if weight > 0:
            sub = Subscription.selectBy(screen=self, channel=channel).getOne(None)
            if sub is not None:
                if sub.weight != weight:
                    sub.weight = weight
                if sub.created_by != user:
                    sub.created_by = user
            else:
                Subscription(screen=self, channel=channel, weight=weight, created_by=user)

    def unsubscribe_from(self, user, channel):
        """
        Deletes the user's subscription from this screen to the channel if one exists, otherwise do nothing.

        :param user: The user requesting the subscription deletion.
        :param channel: The channel to unsubscribe this screen from.
        :return: None
        """
        sub = Subscription.selectBy(screen=self, channel=channel).getOne(None)
        # TODO: Commit this to user history
        if sub is not None:
            sub.destroySelf()

    def is_subscribed_to(self, channel):
        return channel in self.subscriptions.throughTo.channel

    @classmethod
    def get_visible_screens_of(cls, user):
        """
        Returns the screens that are managed by the user (or all screens for the superadmin)

        :param user: The user to retrieve the managed screens.
        :return: A iterable with the managed screens (iterable of sqlobjects)
        """
        if UserPermissions.administrator in user.highest_permission_level:
            return Screen.select()
        return user.screens

    def safe_add_user(self, user):
        """ Avoid user duplication in screen owners. """
        if user not in self.owners:
            self.addUser(user)

    def get_view_link(self):
        """ Returns a relative URL to the screen rendered view. """
        return '/screens/%d/view/%s' % (self.id, self.secret)

    def get_client_link(self):
        """ Returns a relative URL to web-based client for this screen. """
        return '/screens/%d/client/%s' % (self.id, self.secret)

    def get_macs_string(self):
        return ';'.join(mac.get_pretty_mac() for mac in self.macs)

    def get_channels_content(self, app):
        """ 
            Returns all the capsules provided by the channels of this screen as an Iterable[PluginCapsule] 
            ignoring channel duplicates
        """
        screen_capsules_iterables = []
        already_added_channels = set()
        plugin_manager = app.plugin_manager

        def add_content(channel):
            for c in channel.flatten():
                # do not add duplicates
                if c.id not in already_added_channels:
                    screen_capsules_iterables.append(plugin_manager.get_plugin_content(c))
                    already_added_channels.add(c.id)
        for sub in self.subscriptions:
            add_content(sub.channel)
        screen_capsules = list(itertools.chain.from_iterable(screen_capsules_iterables))
        if self.shuffle:
            random.shuffle(screen_capsules)
        return screen_capsules


class ScreenMac(ICTVObject):
    """ A simple class to associate multiple MACs to a screen. """
    screen = ForeignKey('Screen', cascade=True)
    mac = StringCol(unique=True,length=50)

    def get_pretty_mac(self):
        """ Returns the prettyfied version of the mac. """
        return "".join(c + ":" if i % 2 else c for i, c in enumerate(self.mac.zfill(12)))[:-1]
