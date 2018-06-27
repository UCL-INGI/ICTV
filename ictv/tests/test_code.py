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

from ictv import get_root_path
from ictv.models.asset import Asset
from ictv.models.building import Building
from ictv.models.channel import PluginChannel, ChannelBundle
from ictv.models.plugin import Plugin
from ictv.models.plugin_param_access_rights import PluginParamAccessRights
from ictv.models.role import UserPermissions, Role
from ictv.models.screen import Screen, ScreenMac
from ictv.models.user import User
from ictv.common.diskstore import PessimisticThreadSafeDiskStore
from ictv.common.enum import EnumMask
from ictv.common.feedbacks import get_feedbacks, add_feedback, get_next_feedbacks, ImmediateFeedback
from ictv.common.json_datetime import DateTimeDecoder, DateTimeEncoder
from ictv.plugin_manager import plugin_manager
from ictv.plugins.birthday import birthday
from ictv.plugins.cal import cal
from ictv.plugins.cal.cal_capsule import CalendarPlugin
from ictv.plugins.embed import embed
from ictv.plugins.rss_legacy import rss_legacy as rss
from ictv.plugins.rss_legacy.rss_capsule import Rss_capsule
from ictv.tests import ICTVTestCase


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


class PluginConfigPageTest(ICTVTestCase):
    def runTest(self):
        """ Tests the plugin config page. """
        r = self.testApp.get('/plugins/1/config', status=200)
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
        PluginChannel(name='testasset2', plugin=Plugin.selectBy(name="editor").getOne(),
                      subscription_right='restricted')
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
            PluginChannel(name='test', plugin=Plugin.selectBy(name="editor").getOne(), subscription_right='restricted')
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


class PluginTest(ICTVTestCase):
    def runTest(self):
        """ Tests the Plugin object. """
        try:
            Plugin(name='testP', activated='yes')
        except DuplicateEntryError:
            assert_true(False)
        p = Plugin.selectBy(name='testP').getOne()
        try:
            p.set(name='testNew')
        except DuplicateEntryError:
            assert_true(False)
        assert_equal(p.name, 'testNew')
        p1 = Plugin.selectBy(name="cal").getOne()
        p1.set(activated="no")
        assert_equal(p1.activated, "no")
        # TODO there is a problem when I disable a plugin that is used. (disable without interface)
        p.set(cache_validity_default=-10)
        assert_true(p.cache_validity_default < 0)
        # TODO cache negative... works here.
        t = Plugin.delete(p.id)
        assert_equal(t, None)


class ChannelTest(ICTVTestCase):
    def runTest(self):
        """ Tests the Channel object. """
        try:
            PluginChannel(name='test', plugin=Plugin.selectBy(name="editor").getOne(), subscription_right='restricted')
            PluginChannel(name='test2', plugin=Plugin.selectBy(name="editor").getOne(), subscription_right='restricted')
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


class PluginManagerTest(ICTVTestCase):
    def runTest(self):
        """ Tests the PluginManager. """
        pm = self.ictv_app.plugin_manager
        PluginChannel(name='testPlugin', plugin=Plugin.selectBy(name="cal").getOne(), subscription_right='public')
        c = PluginChannel.selectBy(name="testPlugin").getOne()
        chanContent = pm.get_plugin_content(c)
        assert_true(None != chanContent)
        pluginCount = len(pm.list_plugins())
        assert_true(pluginCount > 0)
        plugName = "cal"
        pl = pm.get_plugin(plugName)
        assert_true(None != pl)
        try:
            assert_true(None == pm.get_plugin_webapp(plugName))
        except ImportError:
            assert_true(True)
        plugName = 'editor'
        assert_true(None != pm.get_plugin_webapp(plugName))

        pm.get_plugin_content(PluginChannel.get(1))
        ret = pm.get_last_update(1)
        assert_true(ret != None)
        assert_true(pm.get_last_update(0) == None)
        PluginChannel(name='testBirthday', plugin=Plugin.selectBy(name="birthday").getOne(),
                      subscription_right='public')
        c = PluginChannel.selectBy(name="testBirthday").getOne()
        cache_file = os.path.join(get_root_path(), 'plugins/birthday/cache/birthday_%d.json' % c.id)
        pm.invalidate_cache('birthday', c.id)

        if os.path.exists(cache_file):
            birthday.invalidate_cache(c.id)
            assert_false(os.path.exists(cache_file))
        pm.invalidate_cache('birthday', c.id)
        assert_false(os.path.exists(cache_file))
        list = pm.get_plugin_missing_dependencies('birthday')
        assert_true(len(list) == 0)
        PluginChannel.delete(c.id)
        c = PluginChannel.selectBy(name="testPlugin").getOne()
        PluginChannel.delete(c.id)
        assert_true(pm.get_plugins_modules() != None)
        log = plugin_manager.get_logger('editor', PluginChannel.get(1))
        assert_true(log != None)
        log = plugin_manager.get_logger('editor', None)
        assert_true(log != None)
        return


class BirthdayPluginTest(ICTVTestCase):
    def runTest(self):
        """ Tests the birthday plugin. """
        c = PluginChannel(name='testBirthday2', plugin=Plugin.selectBy(name="birthday").getOne(),
                          subscription_right='public')
        ret = birthday.get_content(c.id)
        for elem in ret:
            assert_false(elem.is_empty())
            assert_true(elem.get_slides() != None)
            for slide in elem.get_slides():
                assert_equal(slide.get_template(), 'template-background-text-center')
                assert_true(None != slide.get_content())
                assert_true(None != slide.get_duration())
                slide.duration = -10
                assert_true(slide.get_duration() > 0)
        assert_true(len(ret) > 0)
        cache_file = os.path.join(get_root_path(), 'plugins/birthday/cache/birthday_%d.json' % c.id)
        if os.path.exists(cache_file):
            birthday.invalidate_cache(c.id)
            assert_false(os.path.exists(cache_file))
        t = birthday.str_day_with_suffix(1)
        assert_true(t != None)
        dm = birthday.str_date_without_year(1, 1)
        assert_true(dm != None)
        people = [{"day": 1, "month": 1, "name": "test", "first_name": "test"},
                  {"day": 30, "month": 1, "name": "test2", "first_name": "test2"}]
        ul = birthday.create_ul(people, "month")
        assert_true(ul != None)
        today_list = []
        months_dict = {}
        future_list = []
        past_list = []
        channel = c
        now = date.today()
        birthday.get_informations(today_list, months_dict, past_list, future_list, channel, now)
        assert_true(len(today_list) >= 0)
        assert_true(len(future_list) >= 0)
        assert_true(len(past_list) >= 0)
        past_list, futur_list = birthday.get_past_future(True, True, 10, 10, now, months_dict)
        assert_true(len(past_list) >= 0)
        assert_true(len(future_list) >= 0)
        # TODO - strange here
        past_list, futur_list = birthday.get_past_future(True, True, -10, -10, now, months_dict)
        assert_true(len(past_list) >= 0)
        assert_true(len(future_list) >= 0)
        PluginChannel.delete(c.id)


class CalPluginTest(ICTVTestCase):
    def runTest(self):
        """ Tests the cal plugin. """
        return
        chan = PluginChannel(name='testCal', plugin=Plugin.selectBy(name="cal").getOne(), subscription_right='public')
        c = cal.get_content(chan.id)
        assert_true(c != None)
        fields = cal.give_fields(chan.id)
        assert_true(fields != None)
        conf = cal.get_configuration()
        assert_true(conf != None)
        test = CalendarPlugin(
            url="https://calendar.google.com/calendar/ical/n2v8mp6tql02ss05ve1slju258%40group.calendar.google.com/public/basic.ics",
            after=10, before=10, duration=5000, type='seminar ICTEAM')
        assert_true(test != None)
        assert_true(test.get_slides() != None)
        assert_true(len(test.get_slides()) >= 0)
        assert_true(test.get_theme() == None)
        PluginChannel.delete(chan.id)


class EmbedPluginTest(ICTVTestCase):
    def runTest(self):
        """ Tests the embed plugin. """
        c = PluginChannel(name='testEmbed', plugin=Plugin.selectBy(name="embed").getOne(), subscription_right='public')
        l = embed.get_content(c.id)
        assert_true(l != None)
        hash = embed.get_file_hash(c.id, "http://0.0.0.0:8080")
        assert_true(hash != None)
        PluginChannel.delete(c.id)


class RSSPluginTest(ICTVTestCase):
    def runTest(self):
        """ Tests the RSS plugin. """
        return
        c = PluginChannel(name='testrss', plugin=Plugin.selectBy(name="rss").getOne(), subscription_right='public')
        l = rss.get_content(c.id)
        assert_true(l != None)
        assert_true(rss.get_configuration() != None)
        assert_true(rss.give_fields() != None)
        assert_true(rss.is_json_present() != False)
        cap = Rss_capsule()
        dir_path = os.path.dirname(os.path.realpath(__file__))

        cap.treat_and_format_data("https://www.uclouvain.be/ingi.rss", "title;<h1 .*>(?P<this>.+)<\/h1>", 'base', 5000,
                                  100, date.today(), c.id, dir_path + '/config.yaml', qrcode=False, white_background=False)
        ls = cap.get_slides()
        assert_true(len(ls) >= 0)
        assert_true(cap.get_theme() != None)
        for l in ls:
            assert_true(l.get_content() != None)
            assert_true(l.get_duration() > 0)
            assert_true(l.get_template() != None)

        cap2 = Rss_capsule()
        cap2.treat_and_format_data("https://xkcd.com/rss.xml",
                                   "background;<div id=\"comic\">\n<img src=\"\/\/(?P<this>(.*))\" title=.*",
                                   'template-image-bg', 5000,
                                   10, date.today(), c.id, get_root_path() + '/plugins/rss/static/store.json',
                                   qrcode=False, white_background=False)
        ls = cap2.get_slides()
        assert_true(len(ls) >= 0)
        assert_true(cap2.get_theme() != None)
        for l in ls:
            assert_true(l.get_content() != None)
            assert_true(l.get_duration() > 0)
            assert_true(l.get_template() != None)
        PluginChannel.delete(c.id)


class CommonTests(ICTVTestCase):
    def runTest(self):
        """ Tests the common module. """
        self.common_diskstore()
        self.common_enum()
        self.common_datetimedecoder()
        self.common_utils()

    def common_diskstore(self):
        def randomword(length):
            return ''.join(random.choice(string.ascii_lowercase) for i in range(length))

        pds = PessimisticThreadSafeDiskStore('sessions')
        pds.__setitem__('test', 'test')
        a = pds.__getitem__('test')
        assert_equal(a, 'test')
        pds.__setitem__('test', 'retest')
        a = pds.__getitem__('test')
        assert_equal(a, 'retest')
        s = randomword(10)
        pds.__setitem__(s, 'test')
        a = pds.__getitem__(s)
        assert_equal(a, 'test')
        try:
            assert_raises(KeyError, pds.__getitem__('testthatnotexist'))
        except KeyError:
            assert_true(True)

    def common_enum(self):
        up = UserPermissions(value=UserPermissions.administrator)
        up2 = UserPermissions(value=UserPermissions.channel_contributor)
        up3 = EnumMask(up2.value)
        assert_not_equal(up3.__repr__(), "")
        assert_is_not_none(up3.__contains__(up))
        assert_is_not_none(up3.__eq__(up))
        assert_is_not_none(up3.__eq__(1))
        a = up.__and__(up2)
        assert_is_not_none(a)
        a = up.__and__(up3)
        assert_is_not_none(a)
        a = up.__or__(up2)
        assert_is_not_none(a)
        a = up.__or__(up3)
        assert_is_not_none(a)
        a = up.__contains__(up2)
        assert_is_not_none(a)
        a = up.__contains__(up3)
        assert_is_not_none(a)
        a = up.__eq__(up2)
        assert_is_not_none(a)
        a = up.__eq__(up3)
        assert_is_not_none(a)

    def common_feedback(self):
        web.ctx.session = self.ictv_app.session
        l = get_feedbacks()
        val = "test"
        assert_false(l.has(type="TESTINGFEEDBACK", message="This is a test feedback from the unit test"))
        add_feedback(type="TESTINGFEEDBACK", message="This is a test feedback from the unit test", value=val)
        l = get_next_feedbacks()
        assert_true(l.has(type="TESTINGFEEDBACK", message="This is a test feedback from the unit test"))
        assert_is_not_none(
            l.feedback_value(type="TESTINGFEEDBACK", message="This is a test feedback from the unit test"))
        assert_is_none(
            l.feedback_value(type="TESTINGFEEDBACK2", message="This is a test feedback from the unit test again"))
        assert_is_not_none(
            l.feedback_value(type=None, message=None))
        assert_true(l.has_type(type="TESTINGFEEDBACK"))

        i = ImmediateFeedback(type="TESTINGFEEDBACK", message="This is a test feedback from the unit test",
                              value=val)

    def common_datetimedecoder(self):
        d = DateTimeDecoder()
        dico = {}
        assert_is_not_none(d.dict_to_object(dico))
        dico['__type__'] = 'timedelta'
        assert_is_not_none(d.dict_to_object(dico))
        dico['__type__'] = 'datetime'
        dico['year'] = 2017
        dico['month'] = 1
        dico['day'] = 1
        assert_is_not_none(d.dict_to_object(dico))
        dico['__type__'] = 'int'
        assert_is_not_none(d.dict_to_object(dico))
        d = DateTimeEncoder()
        assert_is_not_none(d.default(datetime.today()))
        a = "coucou"
        assert_is_not_none(d.encode(a))

    def common_utils(self):
        web.ctx.session = self.ictv_app.session
        from ictv.common.utils import make_alert, make_qrcode, get_feedback, feedbacks_has_type
        assert_not_equal("", make_alert("title test", "test body", icon=True))
        assert_is_not_none(make_qrcode("test qr code"))
        assert_is_not_none(get_feedback("test", "testm"))
        add_feedback(type=1, message="This is a test feedback from the unit test")
        assert_true(feedbacks_has_type(type=1, feedbacks=get_next_feedbacks()))
        assert_false(feedbacks_has_type(type="NOTESTINGFEEDBACK", feedbacks=get_next_feedbacks()))
