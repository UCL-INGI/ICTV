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

import web
from sqlobject import SQLObjectNotFound

from ictv.models.channel import PluginChannel, Channel
from ictv.models.channel import ChannelBundle
from ictv.models.role import UserPermissions
from ictv.models.screen import Screen
from ictv.models.user import User
from ictv.app import sidebar
import logging
from ictv.common.feedbacks import ImmediateFeedback, add_feedback, store_form
from ictv.pages.utils import ICTVAuthPage, PermissionGate

logger = logging.getLogger('pages')


class ScreenSubscriptionsPage(ICTVAuthPage):
    @sidebar
    def render_page(self, screen, user):
        channels = Channel.get_visible_channels_of(user)
        plugin_channels = [c for c in channels if type(c) == PluginChannel]
        bundle_channels = [c for c in channels if type(c) == ChannelBundle]
        """Let admins select channels with the same orientation as the screen orientation """
        plugin_channels = [c for c in plugin_channels if (c.plugin.name == "editor" and c.get_config_param(
            'vertical') and "Portrait" == screen.orientation) or (c.plugin.name == "editor" and not c.get_config_param(
            'vertical') and "Landscape" == screen.orientation) or (c.plugin.name != "editor")]

        subscriptions=user.get_subscriptions_of_owned_screens()
        last_by =   {sub.channel.id:
                    {
                        'user': sub.created_by.readable_name,
                        'channel_name': sub.channel.name,
                        'plugin_channel': hasattr(sub.channel, 'plugin')
                    }
                    for sub in subscriptions if sub.screen.id == screen.id
                }

        return self.renderer.screen_subscriptions(
            screen=screen,
            user=user,
            users=User.select(),
            screen_channels=Channel.get_screens_channels_from(user=user),
            plugin_channels=plugin_channels,
            bundle_channels=bundle_channels,
            subscriptions=subscriptions,
            last_by = last_by,
            plugin_channels_names = {c.id: c.name for c in plugin_channels},
            bundle_channels_names = {c.id: c.name for c in bundle_channels}
        )

    @PermissionGate.screen_administrator
    def GET(self, screen_id):
        try:
            screen = Screen.get(screen_id)
            u = User.get(self.session['user']['id'])
            if not (UserPermissions.administrator in u.highest_permission_level or screen in u.screens):
                raise web.forbidden()
        except SQLObjectNotFound:
            raise web.notfound()
        return self.render_page(screen, u)

    @PermissionGate.screen_administrator
    def POST(self, screen_id):
        def wrong_channel(channel, subscribe, user):
            """ returns True if the the user wants to subscribe to the channel while its plugin is not activated or if
                the user tries to subscribe to the channel without being in its authorized subscribers"""
            return subscribe and (type(channel) is PluginChannel and channel.plugin.activated != "yes" or (subscribe and not channel.can_subscribe(user)))
        form = web.input()
        try:
            screen = Screen.get(screen_id)
            u = User.get(self.session['user']['id'])
            # Forbid if not admin or does not own this screen
            if not (UserPermissions.administrator in u.highest_permission_level or screen in u.screens):
                logger.warning('user %s tried change subscriptions of screen %d without having the rights to do this',
                               u.log_name, screen.id)
                raise web.forbidden()
            diff = json.loads(form.diff)
            if diff == {}:
                logger.info('user %s submitted empty diff for subscriptions of screen %s', u.log_name, screen.name)
                raise ImmediateFeedback("subscription", 'nothing_changed')
            # Do the subscription/unsubscription for every channel in the diff
            subscribed = []
            unsubscribed = []
            try:
                changes = [(Channel.get(channel_id), subscribe) for channel_id, subscribe in diff.items()]
            except SQLObjectNotFound:
                logger.warning('user %s tried to subscribe/unsubscribe screen %d to a channel which does not exist',
                               u.log_name, screen.id)
                raise web.forbidden()
            # if somebody tries to subscribe to a channel with a disabled plugin
            wrong_channels = [(channel, subscribe) for channel, subscribe in changes if wrong_channel(channel, subscribe, u)]
            if wrong_channels:
                channel, subscribe = wrong_channels[0]
                if channel.plugin.activated != "yes":
                    logger.warning('user %s tried to %s screen %d to channel %d with disabled plugin',
                                   u.log_name, 'subscribe' if subscribe else "unsubscribe", screen.id, channel.id)
                    raise ImmediateFeedback("subscription", "disabled_plugin")
                else:
                    logger.warning('user %s tried to subscribe screen %d to channel %d without having the right to do this',
                                   u.log_name, screen.id, channel.id)
                    raise web.forbidden()
            for channel, subscribe in changes:
                if subscribe:
                    screen.subscribe_to(u, channel)
                    subscribed.append(str(channel.id))
                else:
                    screen.unsubscribe_from(u, channel)
                    unsubscribed.append(str(channel.id))
            if subscribed and unsubscribed:
                message = "user %s has subscribed screen %d to channel(s) %s and unsubscribed from channel(s) %s" % \
                          (u.log_name, screen.id, ', '.join(subscribed), ', '.join(unsubscribed))
            else:
                message = "user %s has %s screen %d to channel(s) %s" % \
                          (u.log_name, "subscribed" if subscribed else "unsubscribed", screen.id,
                           ', '.join(subscribed if subscribed else unsubscribed))
            logger.info(message)
            add_feedback("subscription", 'ok')
        except SQLObjectNotFound:
            raise web.notfound()
        except ImmediateFeedback:
            pass
        store_form(form)
        raise web.seeother("/screens/%s/subscriptions" % screen.id)
