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
import logging
import re

import web
from sqlobject import NOT
from sqlobject import SQLObjectNotFound
from sqlobject.dberrors import DuplicateEntryError

from ictv.models.channel import Channel, PluginChannel, ChannelBundle
from ictv.models.plugin import Plugin
from ictv.models.role import UserPermissions
from ictv.models.user import User
from ictv.app import sidebar
from ictv.common.feedbacks import add_feedback, ImmediateFeedback, store_form
from ictv.pages.utils import ICTVAuthPage, PermissionGate
from ictv.plugin_manager.plugin_utils import MisconfiguredParameters

logger = logging.getLogger('pages')


class ChannelsPage(ICTVAuthPage):
    def GET(self):
        return self.render_page()

    @PermissionGate.channel_administrator
    def POST(self):
        """ Handles channel creation, editing, deletion, configuration and user permissions. """
        form = web.input()
        current_user = User.get(self.session['user']['id'])
        channel = None
        try:
            if form.action.startswith('create') or form.action.startswith('edit'):
                # Prepare creation or edition of channels/bundles
                name = form.name.strip()
                description = form.description if form.description and form.description.strip() else None
                enabled = form.get('enabled') == 'on'
                if form.subscription_right not in ['public', 'restricted', 'private']:
                    raise ImmediateFeedback(form.action, 'invalid_subscription_right')
                if len(name) < 3:
                    raise ImmediateFeedback(form.action, 'invalid_name')
                if len(name)> Channel.sqlmeta.columns['name'].length:
                    raise ImmediateFeedback(form.action,'too_long_name')


            if form.action.startswith('create'):
                if UserPermissions.administrator not in current_user.highest_permission_level:
                    logger.warning('user %s tried to create a channel without being admin', current_user.log_name)
                    raise web.forbidden()

                try:
                    if form.action == 'create-channel':
                        try:
                            plugin_id = int(form.plugin)
                        except ValueError:
                            raise ImmediateFeedback(form.action, 'invalid_plugin')
                        p = Plugin.get(plugin_id)
                        channel = PluginChannel(name=name, plugin=p, subscription_right=form.subscription_right, description=description,
                                                enabled=enabled, drop_silently_non_complying_slides=p.drop_silently_non_complying_slides_default)
                        if p.webapp:
                            self.plugin_manager.add_mapping(self.app, channel)

                    elif form.action == 'create-bundle':
                        channel = ChannelBundle(name=name, description=description, subscription_right=form.subscription_right,
                                          enabled=enabled)
                    else:
                        raise web.badrequest()
                except SQLObjectNotFound:
                    raise ImmediateFeedback(form.action, 'invalid_plugin')
                except DuplicateEntryError:
                    raise ImmediateFeedback(form.action, 'name_already_exists')
                logger.info('channel ' + channel.name + ' created by ' + current_user.log_name)
            elif form.action.startswith('edit'):
                if UserPermissions.administrator not in current_user.highest_permission_level:
                    raise web.forbidden()
                try:
                    form.id = int(form.id)
                    channel = (PluginChannel if form.action == 'edit-channel' else Channel).get(form.id)
                except (SQLObjectNotFound, ValueError):
                    raise ImmediateFeedback(form.action, 'invalid_id')

                previous_state = {'name': channel.name, 'description': channel.description,
                                  'subscription_right': channel.subscription_right, 'enabled': channel.enabled}
                new_state = {'name': name, 'description': description, 'subscription_right': form.subscription_right,
                             'enabled': enabled}
                state_diff = dict(set(new_state.items()) - set(previous_state.items()))

                if form.action == 'edit-channel':
                    try:
                        plugin_id = int(form.plugin)
                        p = Plugin.get(plugin_id)
                        add_mapping = p.webapp and channel.plugin != p
                        previous_state['plugin'] = channel.plugin
                        new_state['plugin'] = p
                    except (SQLObjectNotFound, ValueError):
                        raise ImmediateFeedback(form.action, 'invalid_plugin')
                elif form.action == 'edit-bundle':
                    pass  # There is nothing more to edit for a bundle than a channel
                else:
                    raise web.badrequest()

                try:
                    channel.set(**new_state)
                except DuplicateEntryError:
                    channel.set(**previous_state)  # Rollback
                    raise ImmediateFeedback(form.action, 'name_already_exists')

                logger.info('[Channel %s (%d)] ' % (channel.name, channel.id) + current_user.log_name + ' edited the channel.\n'
                            'Previous state: %s\n' % str({k: v for k, v in previous_state.items() if k in state_diff}) +
                            'New state: %s' % str(state_diff))

                if form.action == 'edit-channel' and add_mapping:
                    self.plugin_manager.add_mapping(self.app, channel)
            elif form.action.startswith('delete'):
                if not current_user.super_admin:
                    logger.warning('the user %s tried to delete a channel without having the rights to do it',
                                   current_user.log_name)
                    raise web.forbidden()
                try:
                    form.id = int(form.id)
                    channel = Channel.get(form.id)
                    if channel.subscriptions.count() > 0 and 'confirm-delete' not in form:
                        raise ImmediateFeedback(form.action, 'channel_has_subscriptions',
                                                {'channel': {'name': channel.name, 'id': channel.id, 'description': channel.description, 'subscription_right': channel.subscription_right},
                                                 'plugin_id': channel.plugin.id if form.action == 'delete-channel' else None,
                                                 'subscriptions': [(s.screen.id, s.screen.name, s.screen.building.name) for s in channel.subscriptions]
                                                 })
                    form.name = channel.name
                    channel_name = channel.name
                    channel.destroySelf()
                    logger.info('the channel %s has been deleted by user %s', channel_name, current_user.log_name)
                except (SQLObjectNotFound, ValueError) as e:
                    print(e)
                    raise ImmediateFeedback(form.action, 'invalid_id')
            elif form.action == 'add-users-channel':
                try:
                    if 'users' not in form:
                        raise web.badrequest()
                    form.users = json.loads(form.users)
                    form.id = int(form.id)
                    channel = PluginChannel.get(form.id)
                    if not channel.has_admin(current_user) and UserPermissions.administrator not in current_user.highest_permission_level:
                        raise web.forbidden()
                    form.name = channel.name
                    for user_id, diff in form.users.items():
                        user_id = int(user_id)
                        user = User.get(user_id)
                        if 'permission' in diff:
                            permission_level = diff['permission']
                            new_permission_level = UserPermissions(permission_level)
                            old_permission_level = channel.get_channel_permissions_of(user)
                            if new_permission_level == UserPermissions.no_permission \
                                    and (UserPermissions.administrator in current_user.highest_permission_level or old_permission_level == UserPermissions.channel_contributor):
                                channel.remove_permission_to_user(user)
                                logger.info('permissions of user %s concerning channel %s have been removed by user %s',
                                            user.log_name, channel.name, current_user.log_name)
                            elif (new_permission_level == UserPermissions.channel_contributor and channel.has_admin(
                                    current_user) and old_permission_level == UserPermissions.no_permission) \
                                    or (new_permission_level in UserPermissions.channel_administrator and UserPermissions.administrator in current_user.highest_permission_level):
                                channel.give_permission_to_user(user, new_permission_level)
                                logger.info(
                                    'permissions of user %s concerning channel %s have been set to %s by user %s',
                                    user.log_name, channel.name,
                                    UserPermissions.get_permission_string(new_permission_level),
                                    current_user.log_name)
                        if 'authorized_subscriber' in diff:
                            authorized_subscriber = diff['authorized_subscriber']
                            if authorized_subscriber and (user not in channel.authorized_subscribers):
                                channel.addUser(user)
                                logger.info(
                                    'the user %s has been added to channel %s as authorized subscriber by user %s',
                                    user.log_name, channel.name, current_user.log_name)
                            elif not authorized_subscriber and (user in channel.authorized_subscribers):
                                channel.removeUser(user)
                                logger.info(
                                    'the user %s has been removed from channel %s as authorized subscriber by user %s',
                                    user.log_name, channel.name, current_user.log_name)
                except (SQLObjectNotFound, ValueError):
                    raise ImmediateFeedback(form.action, 'invalid_id')
                except (KeyError, json.JSONDecodeError):
                    raise ImmediateFeedback(form.action, 'invalid_users')
            elif form.action == 'configure':
                try:
                    form.id = int(form.id)
                    channel = PluginChannel.get(form.id)
                    pattern = re.compile(r'list\[.*\]')
                    if UserPermissions.administrator in current_user.highest_permission_level or UserPermissions.channel_administrator in channel.get_channel_permissions_of(
                            current_user) or channel.has_contrib(current_user):
                        for k, v in [(k, v) for k, v in channel.plugin.channels_params.items() if
                                     channel.get_access_rights_for(k, current_user)[1]]:
                            # Iterates on the parameters the current user can write to
                            if v['type'] == 'bool':
                                value = k in form and form[k] == 'on'
                            elif v['type'] == 'int':
                                value = int(form[k])
                                if not (v.get('min', float('-inf')) <= value <= v.get('max', float('inf'))):
                                    continue
                            elif pattern.match(v['type']):
                                inner_type = v['type'][5:-1]
                                if inner_type == 'string':
                                    value = web.input(**{k: ['']})[k]
                                elif pattern.match(inner_type):
                                    inner_type = inner_type[5:-1]
                                    if inner_type == 'string':
                                        delimiter = form[k + '-delimiter']
                                        values = web.input(**{k: ['']})[k]
                                        lists = []
                                        l = []
                                        for v in values:
                                            if v == delimiter:
                                                lists.append(l)
                                                l = []
                                            else:
                                                l.append(v)
                                        value = lists

                            elif k in form:
                                if v['type'] == 'template' and form[k] == '~':
                                    value = None
                                else:
                                    value = form[k]
                            else:
                                continue

                            if channel.get_config_param(k) != value:
                                channel.plugin_config[k] = value
                                logger.info('the %s parameter of channel %s has been changed to %s by user %s',
                                            k, channel.name, value, current_user.log_name)

                        if current_user.super_admin:
                            channel.cache_activated = 'cache-activated' in form and form['cache-activated'] == 'on'
                            channel.cache_validity = int(form['cache-validity']) if 'cache-validity' in form and form[
                                'cache-validity'] else channel.cache_validity
                            channel.keep_noncomplying_capsules = 'keep-capsules' in form and form['keep-capsules'] == 'on'
                            channel.drop_silently_non_complying_slides = 'drop_silently_non_complying_slides' in form and form['drop_silently_non_complying_slides'] == 'on'

                        channel.plugin_config = channel.plugin_config  # Force SQLObject update
                        try:
                            self.plugin_manager.invalidate_cache(channel.plugin.name, channel.id)
                            self.plugin_manager.get_plugin(channel.plugin.name).get_content(channel.id)
                        except MisconfiguredParameters as e:
                            for faulty_param in e:
                                add_feedback(form.action, faulty_param[0], faulty_param)
                            raise web.seeother('/channels/%d' % channel.id)
                        except Exception as e:
                            add_feedback(form.action, 'general_error', str(e))
                            raise web.seeother('/channels/%d' % channel.id)
                    else:
                        raise web.forbidden()
                    form.name = channel.name
                except (SQLObjectNotFound, ValueError):
                    raise ImmediateFeedback(form.action, 'invalid_id')
            if channel:
                form.name = channel.name
            add_feedback(form.action, 'ok')

        except ImmediateFeedback:
            if channel is not None and channel.enabled:
                form.enabled = 'on'
        store_form(form)
        return self.render_page(current_user)

    @sidebar
    def render_page(self, current_user=None, users=None):
        if current_user is None:
            current_user = User.get(self.session['user']['id'])
        if UserPermissions.channel_administrator in current_user.highest_permission_level:
            users = User.select()

        channels = list(Channel.get_visible_channels_of(current_user))

        plugin_channels = []
        bundles = []

        for channel in channels:
            if type(channel) is PluginChannel:
                plugin_channels.append(channel)
            elif type(channel) is ChannelBundle:
                bundles.append(channel)

        return self.renderer.channels(plugin_channels=plugin_channels, bundles=bundles, current_user=current_user,
                                      users=users, activated_plugins=Plugin.selectBy(activated='yes'),
                                      found_plugins=Plugin.select(NOT(Plugin.q.activated == 'notfound')))
