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

# Import smtplib for the actual sending function
import json
import smtplib
# Import the email modules we'll need
from email.mime.text import MIMEText

import web
from datetime import timedelta, datetime
from sqlobject import SQLObjectNotFound, SQLObjectIntegrityError
from sqlobject.dberrors import DuplicateEntryError
import logging

from ictv.models.channel import Channel, ChannelBundle, PluginChannel
from ictv.models.role import UserPermissions
from ictv.models.screen import Screen
from ictv.models.user import User
from ictv.app import sidebar
from ictv.pages.utils import ICTVAuthPage, PermissionGate
from ictv.common.feedbacks import ImmediateFeedback, add_feedback, store_form
from ictv.plugin_manager.plugin_utils import ChannelGate
from ictv.renderer.renderer import Templates

logger = logging.getLogger('pages')


class DetailPage(ICTVAuthPage):
    def GET(self, channel_id):
        channel = Channel.get(int(channel_id))
        current_user = User.get(self.session['user']['id'])
        if channel in Channel.get_visible_channels_of(current_user):
            return self.render_page(channel)
        raise web.forbidden()

    @PermissionGate.administrator
    def POST(self, channel_id):
        channel = Channel.get(int(channel_id))
        form = web.input()
        try:
            if form.action == 'add-channel-to-bundles':
                bundles_diff = json.loads(form.pop('diff', '{}'))
                for bundle_id, part_of in bundles_diff.items():
                    bundle = ChannelBundle.get(int(bundle_id))
                    if part_of:
                        try:
                            bundle.add_channel(channel)
                        except ValueError:
                            raise ImmediateFeedback(form.action, 'bundle_cycle', bundle.name)
                    else:
                        bundle.remove_channel(channel)
                add_feedback(form.action, 'ok')
        except ImmediateFeedback:
            pass
        form.was_bundle = type(channel) == ChannelBundle  # Hack to display the bundles tab instead
        form.data_edit = json.dumps([b.id for b in channel.bundles])
        form.channel_id = channel_id
        form.name = channel.name
        store_form(form)
        raise web.seeother('/channels')

    @sidebar
    def render_page(self, channel):
        current_user = User.get(self.session['user']['id'])

        now = datetime.now()
        last_update = self.plugin_manager.get_last_update(channel.id) or now
        if type(channel) is PluginChannel and last_update + timedelta(minutes=channel.cache_validity) < now:
            last_update = now
        try:
            if type(channel) is ChannelBundle:
                vertical = channel.is_vertical_bundle()
            elif type(channel) is PluginChannel:
                vertical = channel.get_config_param('vertical')
            else:
                vertical = False
        except KeyError:
            vertical = False
        return self.renderer.channeld(channel=channel, channel_type=type(channel).__name__, current_user=current_user,
                                      bundles=ChannelBundle.select().filter(ChannelBundle.q.id != channel.id),
                                      can_force_update=UserPermissions.administrator in current_user.highest_permission_level
                                                       or (type(channel) is PluginChannel and channel.has_contrib(current_user)),
                                      last_update=last_update,vertical= vertical)

class SubscribeScreensPage(ICTVAuthPage):

    @sidebar
    def GET(self, channel_id):
        channel = Channel.get(channel_id)
        current_user = User.get(self.session['user']['id'])
        screens_of_current_user = Screen.get_visible_screens_of(current_user)
        return self.renderer.channel_subscriptions(channel = channel, possible_screens= screens_of_current_user,user = current_user, subscriptions = current_user.get_subscriptions_of_owned_screens())

    @PermissionGate.administrator
    def POST(self,channel_id):
        form = web.input()
        u = User.get(self.session['user']['id'])
        subscribed = []
        unsubscribed = []
        if form.diff == 'diff':
            raise ImmediateFeedback(form.action, 'nothing_changed')
        try:
            diff = json.loads(form.diff)
        except (json.JSONDecodeError, ValueError):
            raise ImmediateFeedback(form.action, 'inconsistent_diff')
        try:
            channelid = int(channel_id)
        except ValueError:
            raise ImmediateFeedback(form.action, 'invalid_channel/screen_id')
        for k, v in diff.items():
            try:
                sub = bool(v)
            except ValueError:
                raise ImmediateFeedback(form.action, 'invalid_channel/screen_id')
            try:
                screenid = int(k)
            except ValueError:
                raise ImmediateFeedback(form.action, 'invalid_channel/screen_id')
            try:
                channel = Channel.get(channelid)
                if not channel.can_subscribe(u):
                    raise web.forbidden(message="You're not allow to do that")
                screen = Screen.get(screenid)
                if not u in screen.owners:
                    raise web.forbidden(message="You're not allow to do that")
                #sub true -> New subscription
                #sub false -> Remove subscription
                if sub:
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
                raise ImmediateFeedback(form.action, 'invalid_channel/screen_id')
            except DuplicateEntryError:
                # if the user has checked + unchecked the same checkbox, it will appear on the diff,
                # we just need to do nothing.
                pass
            except SQLObjectIntegrityError:
                # when there id more than one subscription matching the pair channel/screen
                pass
        raise web.seeother("/channels/%s/subscriptions" % channel_id)


class ForceUpdateChannelPage(ICTVAuthPage):
    @ChannelGate.contributor
    def GET(self, channel_id, channel):
        self.plugin_manager.invalidate_cache(channel.plugin.name, channel.id)
        raise web.seeother('/channel/%d' % channel.id)


class RequestPage(ICTVAuthPage):
    def GET(self, id, user_id):
        channel_id = int(id)
        chan = Channel.get(channel_id)
        user_id = int(user_id)
        user = User.get(user_id)

        st = "You just receive a request of subscription for channel " + chan.name + ". Could you please subscribe " + str(user.fullname) + " (" + user.email + ") to this channel."
        for admin in chan.get_admins():
            web.sendmail(web.config.smtp_sendername, admin.email, 'Request for subscription to a channel', st, headers={'Content-Type': 'text/html;charset=utf-8'})
        return web.seeother('/channels')


class ChannelPage(ICTVAuthPage):
    @ChannelGate.contributor
    def GET(self, channel_id, channel):
        return self.render_page(channel)

    @ChannelGate.contributor
    def POST(self, channel_id, channel):
        """ Handles channel creation, editing, deletion, configuration and user permissions. """
        form = web.input()
        current_user = User.get(self.session['user']['id'])
        try:
            if form.action == 'reset-config':
                if form.all == "true":
                    for param_id, param_attrs in channel.plugin.channels_params.items():
                        read, write = channel.get_access_rights_for(param_id, current_user)
                        if read and write:
                            channel.plugin_config.pop(param_id, None)
                            # Force SQLObject update
                            channel.plugin_config = channel.plugin_config
                else:
                    param_id = form["reset-param-id"]
                    if param_id not in channel.plugin.channels_params.keys():
                        raise ImmediateFeedback(form.action, "invalid_param_id")
                    read, write = channel.get_access_rights_for(param_id, current_user)
                    if read and write:
                        channel.plugin_config.pop(param_id, None)
                    else:
                        raise web.forbidden()
                    # Force SQLObject update
                    channel.plugin_config = channel.plugin_config
                    channel.syncUpdate()
                logger.info('params of channel ' + channel.name + ' reset by ' + current_user.log_name)
            elif form.action == 'reset-cache-config':
                if not current_user.super_admin:
                    raise web.forbidden()
                form.name = channel.name
                channel.cache_activated = None
                channel.cache_validity = None
                add_feedback('general', 'channel_cache_reset')
                logger.info('the cache configuration of channel %s has been reset by user %s', channel.name,
                            current_user.log_name)
            elif form.action == 'reset-filtering-config':
                if not current_user.super_admin:
                    raise web.forbidden()
                form.name = channel.name
                channel.keep_noncomplying_capsules = None
                add_feedback('general', 'channel_filtering_reset')
                logger.info('the capsule filtering configuration of channel %s has been reset by user %s',
                            channel.name,
                            current_user.log_name)
            add_feedback('general', 'channel_edited')
            add_feedback(form.action, 'ok')
            form.name = channel.name
        except ImmediateFeedback:
            if channel is not None and channel.enabled:
                form.enabled = 'on'
        store_form(form)
        raise web.seeother('/channels/%d' % channel.id)

    @sidebar
    def render_page(self, channel):
        """ Render this page. """
        templates = sorted([(template, Templates[template]['name']) for template in Templates])
        readable_params = []
        writable_params = []
        current_user = User.get(self.session['user']['id'])
        for param_id, param_attrs in sorted(channel.plugin.channels_params.items(), key=lambda x: x[1]['order']):
            read, write = channel.get_access_rights_for(param_id, current_user)
            if not write and read:
                readable_params.append((param_id, param_attrs))
            elif read and write:
                writable_params.append((param_id, param_attrs))
        readable_params, writable_params = self.get_params(channel, current_user)
        is_admin = current_user.super_admin or channel.has_admin(self.session['user']['id'])
        return self.renderer.channel(
            channel=channel,
            templates=templates,
            readable_params=readable_params,
            writable_params=writable_params,
            can_modify_cache=current_user.super_admin,
            can_modify_capsule_filter=current_user.super_admin
        )

    @staticmethod
    def get_params(channel, user):
        readable_params = []
        writable_params = []
        for param_id, param_attrs in sorted(channel.plugin.channels_params.items(), key=lambda x: x[1]['order']):
            read, write = channel.get_access_rights_for(param_id, user)
            if not write and read:
                readable_params.append((param_id, param_attrs))
            elif read and write:
                writable_params.append((param_id, param_attrs))
        return readable_params, writable_params
