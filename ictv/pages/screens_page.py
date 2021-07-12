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
from datetime import datetime,timedelta

import web
from sqlobject import SQLObjectNotFound, SQLObjectIntegrityError
from sqlobject.dberrors import DuplicateEntryError

from ictv.models.building import Building
from ictv.models.channel import Channel, PluginChannel
from ictv.models.role import UserPermissions
from ictv.models.screen import Screen, ScreenMac
from ictv.models.user import User
from ictv.app import sidebar
from ictv.common.feedbacks import add_feedback, ImmediateFeedback, store_form
from ictv.pages.utils import ICTVAuthPage, PermissionGate


class ScreenConfigPage(ICTVAuthPage):

    @PermissionGate.screen_administrator
    def GET(self, id):
        try:
            id = int(id)
            sc = Screen.get(id)
            return self.render_page(sc)
        except (SQLObjectNotFound, ValueError):
            raise web.seeother('/screens')

    @sidebar
    def render_page(self, screen):
        return self.renderer.screen_config(screen=screen)


class DetailPage(ICTVAuthPage):

    @PermissionGate.screen_administrator
    def GET(self,id):
        try:
            id = int(id)
            sc = Screen.get(id)
            return self.render_page(sc)
        except (SQLObjectNotFound, ValueError):
            raise web.seeother('/screens')

    @sidebar
    def render_page(self,screen):
        return self.renderer.screen(screen=screen)


class ScreensPage(ICTVAuthPage):

    @sidebar
    def render_page(self):
        u = User.get(self.session['user']['id'])
        screen_status_validity = datetime.now() - timedelta(hours=1)

        def get_data_edit_object(screen):
            object = screen.to_dictionary(['name', 'comment', 'location'])
            object['screenid'] = screen.id
            object['mac'] = screen.get_macs_string() if screen.macs is not None else ''
            object['building-name'] = screen.building.name
            return json.dumps(object)


        return self.renderer.screens(
            screens=Screen.get_visible_screens_of(u),
            buildings=Building.select(),
            user=u,
            highest_permission_level=u.highest_permission_level,
            users=User.select(),
            channels=Channel.get_screens_channels_from(user=u),
            subscriptions=u.get_subscriptions_of_owned_screens(),
            screen_status_validity=screen_status_validity,
            max_inactivity_period=timedelta(weeks=4),
            get_data_edit_object=get_data_edit_object
        )

    @staticmethod
    def check_mac_address(mac):
        """
        Raise a ValueError if this not a correct format of a MAC address (the separator is ":")
        Is the format is valid, returns the mac address without the separator.
        """
        mac_bytes = mac.split(':')
        if len(mac_bytes) != 6:
            raise ValueError
        # check bytes one by one
        for byte in mac_bytes:
            if len(byte) != 2:
                raise ValueError
            # check that it is in hexadecimal. If this is not, it will raise a ValueError
            i = int(byte, 16)
        return ''.join(mac_bytes)

    @PermissionGate.screen_administrator
    def GET(self):
        return self.render_page()

    @PermissionGate.screen_administrator
    def POST(self):
        """ Handles screen creation, editing, deletion, channel subscriptions. """
        form = web.input()
        u = User.get(self.session['user']['id'])
        try:
            if form.action == 'delete':
                if not u.super_admin:
                    raise web.forbidden()
                try:
                    screenid = int(form.screenid)
                except ValueError:
                    raise ImmediateFeedback(form.action, 'invalid_id')
                try:
                    Screen.delete(screenid)
                    raise ImmediateFeedback(form.action, 'ok')
                except SQLObjectNotFound as e:
                    raise ImmediateFeedback(form.action, 'no_id_matching')
            elif form.action == 'subscribe':
                if form.diff == 'diff':
                    raise ImmediateFeedback(form.action, 'nothing_changed')
                try:
                    diff = json.loads(form.diff)
                except (json.JSONDecodeError, ValueError):
                    raise ImmediateFeedback(form.action, 'inconsistent_diff')
                try:
                    screenid = int(form.screenid)
                except ValueError:
                    raise ImmediateFeedback(form.action, 'invalid_channel/screen_id')
                for k, v in diff.items():
                    try:
                        sub = bool(v)
                    except ValueError:
                        raise ImmediateFeedback(form.action, 'invalid_channel/screen_id')
                    try:
                        channelid = int(k)
                    except ValueError:
                        raise ImmediateFeedback(form.action, 'invalid_channel/screen_id')
                    try:
                        channel = Channel.get(channelid)
                        screen = Screen.get(screenid)
                        if UserPermissions.administrator not in u.highest_permission_level and not (channel.can_subscribe(u) and u in screen.owners):
                            raise web.forbidden()
                        if sub:
                            if hasattr(channel, "plugin") and channel.plugin.activated != 'yes':
                                raise web.forbidden()
                            screen.subscribe_to(user=u, channel=channel)
                        else:
                            screen.unsubscribe_from(user=u, channel=channel)
                    except SQLObjectNotFound:
                        raise ImmediateFeedback(form.action, 'invalid_channel/screen_id')
                    except DuplicateEntryError:
                        # if the user has checked + unchecked the same checkbox, it will appear on the diff,
                        # we just need to do nothing.
                        pass
                    except SQLObjectIntegrityError:
                        # when there id more than one subscription matching the pair channel/screen
                        # TODO: log something
                        pass
            elif form.action == 'chown':
                if form.diff == 'diff':
                    raise ImmediateFeedback(form.action, 'nothing_changed')
                try:
                    diff = json.loads(form.diff)
                except (json.JSONDecodeError, ValueError):
                    raise ImmediateFeedback(form.action, 'inconsistent_diff')
                try:
                    screenid = int(form.screenid)
                except ValueError:
                    raise ImmediateFeedback(form.action, 'screenid')
                for k, v in diff.items():
                    try:
                        own = bool(v)
                    except ValueError:
                        raise ImmediateFeedback(form.action, 'invalid_screen/user_id')
                    try:
                        userid = int(k)
                    except ValueError:
                        raise ImmediateFeedback(form.action, 'invalid_screen/user_id')
                    try:
                        screen = Screen.get(screenid)
                        if UserPermissions.administrator not in u.highest_permission_level and u not in screen.owners:
                            raise web.forbidden()
                        user = User.get(userid)
                        if own:
                            screen.safe_add_user(user)
                        else:
                            screen.removeUser(user)
                    except SQLObjectNotFound:
                        raise ImmediateFeedback(form.action, 'invalid_screen/user_id')
                    except DuplicateEntryError:
                        # if the user has checked + unchecked the same checkbox, it will appear on the diff,
                        # we just need to do nothing.
                        pass
                    except SQLObjectIntegrityError:
                        # when there is more than one subscription mathing the pair channel/screen
                        # TODO: log something
                        pass
            elif form.action == 'configure':
                screen = Screen.get(int(form.id))
                screen.shuffle = form.get('shuffle') == 'on'
                screen.show_postit = form.get('postit') == 'on'
                screen.show_slide_number = form.get('show_slide_number') == 'on'
            else:
                building = Building.get(form.building.strip())
                name = form.name.strip()
                form.building_name = None
                if not building:
                    raise ImmediateFeedback(form.action, 'empty_building')
                form.building_name = building.name
                if not name:
                    raise ImmediateFeedback(form.action, 'empty_name')
                if len(name) > Screen.sqlmeta.columns['name'].length:
                    raise ImmediateFeedback(form.action,'too_long_name')

                try:
                    macs = {self.check_mac_address(mac) for mac in form.mac.strip().lower().split(';') if mac}
                except ValueError:
                    raise ImmediateFeedback(form.action, 'invalid_mac_address')

                if form.action == 'create':
                    if UserPermissions.administrator not in u.highest_permission_level:
                        raise web.forbidden()
                    try:
                        screen = Screen(name=form.name.strip(), building=form.building, location=form.location.strip(), comment= form.comment.strip(), orientation= form.orientation)
                    except DuplicateEntryError:
                        raise ImmediateFeedback(form.action, 'name_already_exists')

                elif form.action == 'edit':
                    if UserPermissions.administrator not in u.highest_permission_level:
                        raise web.forbidden()
                    try:
                        screenid = int(form.screenid)
                    except ValueError:
                        raise ImmediateFeedback(form.action, 'invalid_id')

                    screen = Screen.get(screenid)
                    if screen is None:
                        raise ImmediateFeedback(form.action, 'no_id_matching')

                    try:
                        screen.name = form.name.strip()
                        screen.building = form.building
                        screen.orientation = form.orientation
                    except DuplicateEntryError:
                        raise ImmediateFeedback(form.action, 'name_already_exists')
                    screen.location = form.location.strip()
                    screen.comment = form.comment.strip()
                else:
                    raise NotImplementedError

                try:
                    screen_macs = [screen_mac.mac for screen_mac in screen.macs]
                    for mac in screen_macs:
                        if mac not in macs:
                            ScreenMac.selectBy(mac=mac).getOne().destroySelf()
                    for mac in macs:
                        if mac not in screen_macs:
                            ScreenMac(screen=screen, mac=mac)
                except DuplicateEntryError:
                    raise ImmediateFeedback(form.action, 'mac_already_exists')

            add_feedback(form.action, 'ok')
        except ImmediateFeedback:
            pass
        store_form(form)

        return self.render_page()
