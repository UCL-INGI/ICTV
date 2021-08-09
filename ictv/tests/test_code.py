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

import os
import random
import string
from datetime import date, datetime

import web
from nose.tools import *
from sqlobject import SQLObjectNotFound
from sqlobject.dberrors import DuplicateEntryError

from ictv.common import get_root_path
from ictv.models.asset import Asset
from ictv.models.building import Building
from ictv.models.channel import PluginChannel, ChannelBundle
from ictv.models.plugin import Plugin
from ictv.models.plugin_param_access_rights import PluginParamAccessRights
from ictv.models.role import UserPermissions, Role
from ictv.models.screen import Screen, ScreenMac
from ictv.models.user import User
from ictv.common.enum import EnumMask
from ictv.common.feedbacks import get_feedbacks, add_feedback, get_next_feedbacks, ImmediateFeedback
from ictv.common.json_datetime import DateTimeDecoder, DateTimeEncoder
from ictv.plugin_manager import plugin_manager
from ictv.tests import ICTVTestCase, FakePluginTestCase


class SetUpTearDownAccess(ICTVTestCase):
    def runTest(self):
        """ Tests the setup and tear down of the app in a process life. """
        t = BasicPageAccess()
        t.testApp = self.testApp
        t.ictv_app = self.ictv_app
        t.runTest()
        self.tearDown()
        self.setUp()
        t.runTest()


class BasicPageAccess(ICTVTestCase):
    def runTest(self):
        """ Tests all main pages returns 200. """
        urls = ['/', '/buildings', '/channels', '/logs', '/plugins', '/screens', '/storage', '/users']
        for url in urls:
            r = self.testApp.get(url, status=200)
            assert_not_equal(r.body, None)


class UsersPageTest(ICTVTestCase):
    def runTest(self):
        """ Tests the users page. """
        self.users()
        self.users_1()
        self.users_2()

    def users(self):
        pass
        # basic test
        # form = r.form[0]
        # username = 'test'
        # fullname = 'test test'
        # email = 'test@test.com'
        # super_admin = False
        # form['username'] = username
        # form['fullname'] = fullname
        # form['email'] = email
        # form['super_admin'] = super_admin
        # form.action = "create"
        # res = form.submit()
        # newUser = User.selectBy(email='test@test.com').getOne()
        # assert_equal(newUser.username,username)
        # assert_equal(newUser.fullname, fullname)
        # assert_equal(newUser.email, email)
        # assert_equal(newUser.super_admin, False)
        # assert_equal(newUser.disabled, False)
        # assert_equal(res.status,200)

    def users_1(self):
        # basic test
        self.testApp.get('/users/1', status=200)

    def users_2(self):
        # test a wrong id
        self.testApp.get('/users/1000', status=303)


class ScreensPageTest(ICTVTestCase):
    def runTest(self):
        """ Tests the screens page. """
        self.screens_1()
        self.screens_2()

    def screens_1(self):
        # basic test
        Screen(name='A', building=Building(name='A'))
        r = self.testApp.get('/screens/1', status=200)
        assert_not_equal(r.body, None)

    def screens_2(self):
        # test a wrong id
        self.testApp.get('/screens/1000', status=303)


class ScreenConfigTest(ICTVTestCase):
    def runTest(self):
        """ Tests the screen config page. """
        self.screens_config_1()
        self.screens_config_2()

    def screens_config_1(self):
        # basic test
        Screen(name='A', building=Building(name='A'))
        r = self.testApp.get('/screens/1/config')
        print(r.body, r.headers)
        assert_equal(r.status, 200)
        assert_not_equal(r.body, None)

    def screens_config_2(self):
        # test a wrong id
        r = self.testApp.get('/screens/1000/config')
        print(r.body, r.headers)
        assert_equal(r.status, 303)
        assert_not_equal(r.body, None)


class ScreenViewTest(ICTVTestCase):
    def runTest(self):
        """ Tests the screen view pages. """
        self.screen_view_1()
        self.screen_client_1()

    def screen_view_1(self):
        sc = Screen(name='A', building=Building(name='A'))
        r = self.testApp.get('/screens/1/view/' + sc.secret, status=200)
        assert_not_equal(r.body, None)

    def screen_client_1(self):
        sc = Screen.get(1)
        r = self.testApp.get('/screens/1/client/' + sc.secret, status=200)
        assert_not_equal(r.body, None)


class ScreenRoutingTest(ICTVTestCase):
    def runTest(self):
        """ Tests the screen routing based on encoded MAC addresses. """
        sc = Screen(name='A', building=Building(name='A'))
        sm = ScreenMac(screen=sc, mac='000000000000')
        self.testApp.get('/screens/redirect/' + sm.mac, status=303)


class ChannelDetailsPageTest(ICTVTestCase):
    def runTest(self):
        """ Tests the channel details page. """
        PluginChannel(name='A', plugin=Plugin(name='fake_plugin', activated='notfound'), subscription_right='public')
        self.channels_1()
        self.channels_1_request()

    def channels_1(self):
        # basic test
        r = self.testApp.get('/channels/1', status=200)
        assert_not_equal(r.body, None)

    def channels_1_request(self):
        # basic test
        self.testApp.get('/channels/1/request/1', status=303)
        u = User(username='testchanrequest', email='testchganrequ.test123456789@uclouvain.be', super_admin=True,
                 disabled=False)
        self.testApp.get('/channels/1/request/' + str(u.id), status=303)
        User.delete(u.id)

    def channel_1_fu(self):
        # basic test
        self.testApp.get('/channel/1/force_update', status=303)


class ChannelPreviewTest(ICTVTestCase):
    def runTest(self):
        """ Tests the preview of a channel. """
        self.preview_channel()

    def preview_channel(self):
        c = ChannelBundle(name='A', subscription_right='public')
        r = self.testApp.get('/preview/channels/1/' + c.secret)
        assert_equal(r.status, 200)


class PluginConfigPageTest(FakePluginTestCase):
    def runTest(self):
        """ Tests the plugin config page. """
        r = self.testApp.get('/plugins/%d/config' % Plugin.selectBy(name='fake_plugin').getOne().id, status=200)
        assert_not_equal(r.body, None)


class LocalLoginTest(ICTVTestCase):
    def runTest(self):
        """ Tests the local login. """
        self.local_login()

    def local_login(self):
        self.testApp.get('/login')
        self.testApp.get('/reset', status=303)
        u = User.get(1)
        r = self.testApp.get('/reset/' + u.reset_secret, status=200)
        assert_not_equal(r.body, None)


class LogAsTest(ICTVTestCase):  # TODO: Update this test
    def runTest(self):
        """ Tests the log as functionality. """
        # self.testApp.get('/logas/ludovic.taffin@uclouvain.be', status=303)


class CacheTest(ICTVTestCase):
    def runTest(self):
        """ Tests the cache mecanism. """
        u = User(username='testasset', fullname='testasset test', email='testasset.test@uclouvain.be',
                 super_admin=True,
                 disabled=False)
        PluginChannel(name='testasset2', plugin=Plugin(name='cache_plugin', activated='no'), subscription_right='restricted')
        c = PluginChannel.selectBy(name="testasset2").getOne()
        a = Asset(plugin_channel=c, user=u)
        self.testApp.get('/cache/' + str(a.id), status=303)
        try:
            Asset.delete(a.id)
        except SQLObjectNotFound:
            pass
        finally:
            User.delete(u.id)
            PluginChannel.delete(c.id)


class BuildingTest(ICTVTestCase):
    def runTest(self):
        """ Tests the Building object. """
        try:
            Building(name="test")
        except DuplicateEntryError:
            assert_true(False)
        b = Building.selectBy(name="test").getOne()

        assert_not_equal(b, None)
        assert_equal(b.name, "test")
        try:
            b.set(name="newName")
        except DuplicateEntryError:
            assert_true(False)
        assert_equal(b.name, "newName")
        b.set(name="test")

        t = Building.delete(b.id)
        assert_equal(t, None)
        t = Building.selectBy(name="test").getOne(None)
        assert_equal(t, None)


class UserTest(ICTVTestCase):
    def runTest(self):
        """ Tests the User object """
        try:
            User(username='test', fullname='test test', email='test.test@uclouvain.be', super_admin=True,
                 disabled=False)
        except DuplicateEntryError:
            assert_true(False)
        b = User.selectBy(username="test").getOne()

        assert_not_equal(b, None)
        assert_equal(b.username, "test")
        try:
            b.set(username="newName")
        except DuplicateEntryError:
            assert_true(False)
        assert_equal(b.username, "newName")
        b.set(username="test")
        l = b.get_subscriptions_of_owned_screens()
        assert_true(l.count() >= 0)
        una = User(username='testnoadmin', fullname='testnoadmin test', email='testnoadmin.test@uclouvain.be',
                   super_admin=False,
                   disabled=False)
        l = una.get_subscriptions_of_owned_screens()
        assert_true(l.count() >= 0)
        User.delete(una.id)
        b.set(disabled=True)
        assert_equal(b.disabled, True)
        t = b.owns_screen()
        assert_equal(t, False)
        b = User.selectBy(username="admin").getOne()
        b.addScreen(Screen(name='A', building=Building(name='A')))
        t = b.owns_screen()
        assert_equal(t, True)
        b = User.selectBy(username="test").getOne()
        t = User.delete(b.id)
        assert_equal(t, None)
        b = User.selectBy(username="test").getOne(None)
        assert_true(None == b)


class RoleTest(ICTVTestCase):
    def runTest(self):
        """ Tests the Role object. """
        try:
            u = User(username='test', fullname='test test', email='test.test@uclouvain.be', super_admin=True,
                     disabled=False)
            PluginChannel(name='test', plugin=Plugin(name='role_plugin', activated='no'), subscription_right='restricted')
            c = PluginChannel.selectBy(name="test").getOne()
            r = Role(user=u, channel=c, permission_level=UserPermissions.channel_contributor)
            assert_true(r != None)
            assert_true(r.permission_level == UserPermissions.channel_contributor)
            r.permission_level = UserPermissions.channel_administrator
            assert_true(r.permission_level == UserPermissions.channel_administrator)
            Role.delete(r.id)
            role = Role.selectBy(user=u, channel=c).getOne(None)
            assert_true(role == None)
            PluginChannel.delete(c.id)
            User.delete(u.id)
        except DuplicateEntryError:
            assert_true(False)


class ChannelTest(ICTVTestCase):
    def runTest(self):
        """ Tests the Channel object. """
        try:
            PluginChannel(name='test', plugin=Plugin(name='channel_plugin', activated='no'), subscription_right='restricted')
            PluginChannel(name='test2', plugin=Plugin.selectBy(name='channel_plugin').getOne(), subscription_right='restricted')
            c = PluginChannel.selectBy(name="test").getOne()
            assert_not_equal(None, c)
            c.set(name="testNew")
            assert_equal(c.name, "testNew")
            u = User(username='test', fullname='test test', email='test.test@uclouvain.be', super_admin=True,
                     disabled=False)
            up = UserPermissions.channel_contributor
            c.give_permission_to_user(u, up)
            role = Role.selectBy(user=u, channel=c).getOne(None)
            assert_true(role != None)
            c.give_permission_to_user(u, up)
            role = Role.selectBy(user=u, channel=c).getOne(None)
            assert_true(role != None)
            getup = c.get_channel_permissions_of(u)
            assert_equal(getup, up)
            getupnoperm = c.get_channel_permissions_of(User.get(1))
            assert_equal(getupnoperm, UserPermissions.no_permission)
            c.remove_permission_to_user(u)
            role = Role.selectBy(user=u, channel=c).getOne(None)
            assert_true(role == None)
            assert_false(c.has_admin(u))
            up = UserPermissions.channel_administrator
            c.give_permission_to_user(u, up)
            assert_true(c.has_admin(u))
            assert_true(c.has_contrib(u))
            assert_is_not_none(c.get_admins())
            assert_is_not_none(c.get_contribs())
            assert_in(str(u.id), c.get_users_as_json())
            c.remove_permission_to_user(u)
            role = Role.selectBy(user=u, channel=c).getOne(None)
            assert_true(role == None)
            c.give_permission_to_user(None, up)
            role = Role.selectBy(user=u).getOne(None)
            assert_true(role == None)
            tru = c.has_visible_params_for(u)
            assert_true(tru)
            u3 = User(username='test3', fullname='test3 test2', email='test3.test2@uclouvain.be', super_admin=False,
                      disabled=False)
            tru = c.has_visible_params_for(u3)
            assert_false(tru)
            t = PluginChannel.delete(c.id)
            assert_equal(t, None)
            # try to delete a channel used by a screen - Seems to work...
            sc = Screen(name='A', building=Building(name='A'))
            sc.subscribe_to(u, PluginChannel.get(2))
            # t2 = PluginChannel.delete(2)
            c4 = PluginChannel.get(2)
            nbSub = c4.subscriptions.count()
            c4.set(enabled=False)
            assert_equal(nbSub, c4.subscriptions.count())
            c4.set(enabled=True)
            c4.set(subscription_right="private")
            assert_equal(nbSub, c4.subscriptions.count())
            c4.set(subscription_right="public")
            # todo seems working by bypassing the webinterface
            c4.set(cache_validity=-10)
            assert_true(c4.cache_validity < 0)
            sc.unsubscribe_from(u, PluginChannel.get(2))
            u2 = User(username='test2', fullname='test2 test2', email='test2.test2@uclouvain.be', super_admin=False,
                      disabled=False)
            l = PluginChannel.get_screens_channels_from(u2)
            assert_is_not_none(l)
            temp = PluginChannel.get_visible_channels_of(u2)
            assert_is_not_none(temp)
            User.delete(u.id)
            User.delete(u2.id)
            User.delete(u3.id)
        except DuplicateEntryError:
            assert_true(False)

        return


class ScreenTest(ICTVTestCase):
    def runTest(self):
        """ Tests the Screen object. """
        try:
            b = Building(name="test")
            s = Screen(name='News Réaumur', building=b)
            assert_not_equal(None, s)
            s.set(name="testNew")
            assert_equal(s.name, "testNew")
            t = Screen.delete(s.id)
            Building.delete((b.id))
            assert_equal(t, None)
        except DuplicateEntryError:
            assert_true(False)
        return
