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


class ManageBundlePage(ICTVAuthPage):
    @sidebar
    def render_page(self, bundle, user):
        channels = Channel.select()
        plugin_channels = [c for c in channels if type(c) == PluginChannel]
        bundle_channels = [c for c in channels if type(c) == ChannelBundle]
        return self.renderer.manage_bundle(
            bundle=bundle,
            user=user,
            subscribed_channels=bundle.bundled_channels,
            plugin_channels=plugin_channels,
            bundle_channels=bundle_channels,
        )

    @PermissionGate.administrator
    def GET(self, bundle_id):
        try:
            bundle = ChannelBundle.get(bundle_id)
            u = User.get(self.session['user']['id'])
        except SQLObjectNotFound:
            raise web.notfound()
        return self.render_page(bundle, u)

    @PermissionGate.administrator
    def POST(self, bundle_id):
        def wrong_channel(channel, bundle, add):
            """ returns True if the channel to add is the bundle itself
                or if the channel is a PluginChannel with disabled plugin """
            return bundle.id == channel.id or add and type(channel) is PluginChannel and channel.plugin.activated != "yes"
        form = web.input()
        try:
            bundle = ChannelBundle.get(bundle_id)
            u = User.get(self.session['user']['id'])
            diff = json.loads(form.diff)
            if diff == {}:
                logger.info('user %s submitted empty diff for bundle management %s', u.log_name, bundle.name)
                raise ImmediateFeedback("manage_channels", 'nothing_changed')
            # Do the subscription/unsubscription for every channel in the diff
            contained = []
            not_contained = []
            try:
                changes = [(Channel.get(channel_id), add) for channel_id, add in diff.items()]
            except SQLObjectNotFound:
                logger.warning('user %s tried to add a channel which does not exist to bundle %d',
                               u.log_name, bundle.id)
                raise web.forbidden()
            # if somebody tries to add a channel with a disabled plugin or to add a bundle to itself
            wrong_channels = [(channel, add) for channel, add in changes if wrong_channel(channel, bundle, add)]
            if wrong_channels:
                channel, add = wrong_channels[0]
                if channel.id == bundle.id:
                    logger.warning('user %s tried to %s bundle %d to itself',
                                   u.log_name, 'add' if add else "remove", bundle.id)
                    raise ImmediateFeedback("manage_channels", "added_to_itself")
                else:
                    logger.warning('user %s tried to %s channel %d with disabled plugin to bundle %d',
                                   u.log_name, 'add' if add else "remove", channel.id, bundle.id)
                    raise ImmediateFeedback("manage_channels", "disabled_plugin")
            for channel, add in changes:
                if add:
                    try:
                        bundle.add_channel(channel)
                    except ValueError:
                        logger.warning("user %s has made changes in channels management of bundle %d that created a "
                                       "cycle of bundles by adding channel %d (%s)", u.log_name, bundle.id, channel.id,
                                       channel.name)
                        form.channel_name = channel.name
                        raise ImmediateFeedback("manage_channels", "bundle_cycle")

                    contained.append(str(channel.id))
                else:
                    bundle.remove_channel(channel)
                    not_contained.append(str(channel.id))
            if contained and not_contained:
                message = "user %s has added to channel(s) %s and removed channel(s) %s to bundle %d" % \
                          (u.log_name, ', '.join(contained), ', '.join(not_contained), bundle.id)
            else:
                message = "user %s has %s channel(s) %s to bundle %d" % \
                          (u.log_name, "added" if contained else "removed",
                           ', '.join(contained if contained else not_contained), bundle.id)
            logger.info(message)
            add_feedback("manage_channels", 'ok')
        except SQLObjectNotFound:
            raise web.notfound()
        except ImmediateFeedback:
            pass
        store_form(form)
        raise web.seeother("/channels/%s/manage_bundle" % bundle.id)
