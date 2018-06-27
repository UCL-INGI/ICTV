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

import datetime
import json
import os
import time

import pytest

from ictv import get_root_path
from ictv.models.asset import Asset
from ictv.models.building import Building
from ictv.models.channel import PluginChannel, Channel, ChannelBundle
from ictv.models.log_stat import LogStat
from ictv.models.plugin import Plugin
from ictv.models.plugin_param_access_rights import PluginParamAccessRights
from ictv.models.role import UserPermissions, Role
from ictv.models.screen import Screen, ScreenMac
from ictv.models.user import User
from ictv.tests import ICTVTestCase, create_fake_plugin, FakePluginTestCase


class AssetObjectTest(ICTVTestCase):
    def runTest(self):
        """ Tests the Asset SQLObject. """
        fake_plugin = Plugin(name='fake_plugin', activated='notfound')
        asset_channel = PluginChannel(name='Asset Channel', plugin=fake_plugin, subscription_right='public')

        a1 = Asset(plugin_channel=asset_channel, user=None, filename='path_test', extension='.txt')
        last_ref_a1 = a1.last_reference
        time.sleep(1)
        assert a1.path == os.path.join('static', 'storage', str(asset_channel.id), str(a1.id) + '.txt')
        assert a1.last_reference > last_ref_a1

        a2 = Asset(plugin_channel=asset_channel, user=None, filename='path_test')
        assert a2.path == os.path.join('static', 'storage', str(asset_channel.id), str(a2.id))

        a3 = Asset(plugin_channel=asset_channel, user=None, filename='cache_test', in_flight=True)
        a3_path = os.path.join('static', 'storage', str(asset_channel.id), str(a3.id))
        assert a3.path is None
        assert a3._get_path(force=True) == a3_path
        a3.in_flight = False
        assert a3.path == a3_path

        a4 = Asset(plugin_channel=asset_channel, user=None, filename='test_write', extension='.txt')
        a4_path = os.path.join(get_root_path(), 'static', 'storage', str(asset_channel.id), str(a4.id) + '.txt')
        a4_content = 'a4 file content'.encode()
        a4.write_to_asset_file(a4_content)
        with open(a4_path, 'rb') as f:
            assert f.read() == a4_content
        a4.destroySelf()
        assert not os.path.exists(a4_path)


class ChannelObjectTest(ICTVTestCase):
    def runTest(self):
        """ Tests the Channel SQLObject """
        Channel.deleteMany(None)
        fake_plugin = Plugin(name='fake_plugin', activated='notfound')
        channel = Channel(name='Channel', subscription_right='public', secret='abcdef')
        plugin_channel = PluginChannel(name='Channel2', plugin=fake_plugin, subscription_right='public')
        bundle_channel = ChannelBundle(name='Channel3', subscription_right='public')
        building = Building(name='building')
        screen = Screen(name='Screen', building=building)
        user = User(fullname='User', email='test@localhost')
        user2 = User(fullname='User2', email='test2@localhost')

        # Test can_subscribe()
        def test_channel_subscription(c, u):
            def assert_subscription_no_perm():
                assert c.can_subscribe(u)
                c.subscription_right = 'restricted'
                assert not c.can_subscribe(u)
                c.subscription_right = 'private'
                assert not c.can_subscribe(u)
                c.subscription_right = 'public'
                assert c.can_subscribe(u)

            def assert_subscription_admin():
                assert c.can_subscribe(u)
                c.subscription_right = 'restricted'
                assert c.can_subscribe(u)
                c.subscription_right = 'private'
                assert c.can_subscribe(u)
                c.subscription_right = 'public'
                assert c.can_subscribe(u)

            def assert_subscription_super_admin():
                assert c.can_subscribe(u)
                c.subscription_right = 'restricted'
                assert c.can_subscribe(u)
                c.subscription_right = 'private'
                assert c.can_subscribe(u)
                c.subscription_right = 'public'
                assert c.can_subscribe(u)

            assert_subscription_no_perm()
            user.admin = True
            assert_subscription_admin()
            user.admin = False
            user.super_admin = True
            assert_subscription_super_admin()
            user.super_admin = False

        test_channel_subscription(channel, user)
        test_channel_subscription(plugin_channel, user)
        test_channel_subscription(bundle_channel, user)

        # Test get_channels_authorized_subscribers_as_json()
        def test_channel_subscribers(c):
            def assert_no_users():
                assert Channel.get_channels_authorized_subscribers_as_json([c]) == '{"%d": []}' % c.id

            def assert_only_user(u):
                assert Channel.get_channels_authorized_subscribers_as_json([c]) == '{"%d": [%d]}' % (c.id, u.id)

            def assert_users(*users):
                for u in json.loads(Channel.get_channels_authorized_subscribers_as_json([c]))[str(c.id)]:
                    assert u in [u.id for u in users]

            assert_no_users()
            c.safe_add_user(user)
            assert_only_user(user)
            # check that there is no duplicate
            c.safe_add_user(user)
            assert_only_user(user)
            c.removeUser(user)
            c.safe_add_user(user)
            assert_only_user(user)
            c.safe_add_user(user2)
            assert_users(user, user2)
            c.removeUser(user)
            assert_only_user(user2)
            c.removeUser(user2)
            assert_no_users()

        test_channel_subscribers(channel)
        test_channel_subscribers(plugin_channel)
        test_channel_subscribers(bundle_channel)

        # Test get_visible_channels_of()
        def test_visible_channels(u):
            def assert_no_channels():
                assert Channel.get_visible_channels_of(u) == set()

            def assert_channel(c):
                assert Channel.get_visible_channels_of(u) == {c}

            def assert_all_channels():
                assert Channel.get_visible_channels_of(u) == {channel, plugin_channel, bundle_channel}

            def assert_public_channels():
                channel.subscription_right = 'restricted'
                assert Channel.get_visible_channels_of(u) == {plugin_channel, bundle_channel}
                channel.subscription_right = 'private'
                assert Channel.get_visible_channels_of(u) == {plugin_channel, bundle_channel}
                channel.subscription_right = 'public'

            assert_no_channels()
            u.admin = True
            assert_all_channels()
            u.admin = False
            assert_no_channels()
            u.super_admin = True
            assert_all_channels()
            u.super_admin = False
            assert_no_channels()

            screen.addUser(u)
            assert_public_channels()
            screen.removeUser(u)
            assert_no_channels()

            channel.subscription_right = 'restricted'
            assert_no_channels()
            channel.addUser(u)
            assert_channel(channel)
            screen.addUser(u)
            assert_all_channels()
            channel.removeUser(u)
            screen.removeUser(u)
            assert_no_channels()
            channel.subscription_right = 'public'

            plugin_channel.give_permission_to_user(u, UserPermissions.channel_contributor)
            assert_channel(plugin_channel)
            plugin_channel.give_permission_to_user(u, UserPermissions.channel_administrator)
            assert_channel(plugin_channel)
            plugin_channel.remove_permission_to_user(u)
            assert_no_channels()

        test_visible_channels(user)
        test_visible_channels(user2)

        # Test get_screens_channels_from()
        def test_screens_channels(u):
            def assert_no_channels():
                assert set(Channel.get_screens_channels_from(u)) == set()

            def assert_channel(c):
                assert set(Channel.get_screens_channels_from(u)) == {c}

            def assert_channels(*channels):
                assert set(Channel.get_screens_channels_from(u)) == set(channels)

            def assert_all_channels():
                assert set(Channel.get_screens_channels_from(u)) == {channel, plugin_channel, bundle_channel}

            assert_all_channels()
            channel.subscription_right = 'restricted'
            plugin_channel.subscription_right = 'restricted'
            bundle_channel.subscription_right = 'restricted'
            assert_no_channels()
            u.super_admin = True
            assert_all_channels()
            u.super_admin = False
            assert_no_channels()
            channel.addUser(u)
            assert_channel(channel)
            channel.removeUser(u)
            assert_no_channels()
            screen.addUser(user)
            screen.subscribe_to(user, channel)
            assert_channel(channel)
            screen.subscribe_to(user, bundle_channel)
            assert_channels(channel, bundle_channel)

            channel.subscription_right = 'public'
            plugin_channel.subscription_right = 'public'
            bundle_channel.subscription_right = 'public'

        test_screens_channels(user)

        # Test get_preview_link()
        assert channel.get_preview_link() == '/preview/channels/%d/abcdef' % channel.id


class PluginChannelObjectTest(FakePluginTestCase):
    def runTest(self):
        """ Tests the PluginChannel SQLObject """
        Channel.deleteMany(None)
        fake_plugin = Plugin.selectBy(name='fake_plugin').getOne()
        plugin_channel = PluginChannel(name='MyPluginChannel', plugin=fake_plugin, subscription_right='public')
        user = User(fullname='User', email='test@localhost')
        user2 = User(fullname='User2', email='test2@localhost')

        assert plugin_channel.get_type_name() == 'Plugin fake_plugin'

        # Test user permissions
        def assert_no_permission(c, u):
            assert c.get_channel_permissions_of(u) == UserPermissions.no_permission
            assert u not in c.get_admins() and u not in c.get_contribs()

        def has_contrib(u, check_inlist=True):
            return plugin_channel.has_contrib(u) and (not check_inlist or u in plugin_channel.get_contribs())

        def has_admin(u):
            return plugin_channel.has_admin(u) and u in plugin_channel.get_admins()

        assert_no_permission(plugin_channel, user)
        assert_no_permission(plugin_channel, user2)

        plugin_channel.give_permission_to_user(user, UserPermissions.channel_contributor)
        role = Role.selectBy(user=user, channel=plugin_channel).getOne()

        assert has_contrib(user)
        assert not has_admin(user)
        assert not has_contrib(user2)
        assert not has_admin(user2)
        assert role.permission_level == UserPermissions.channel_contributor == plugin_channel.get_channel_permissions_of(
            user)

        assert json.loads(plugin_channel.get_users_as_json()) == {
            str(user.id): UserPermissions.channel_contributor.value}

        plugin_channel.give_permission_to_user(user, UserPermissions.channel_administrator)
        assert has_contrib(user, check_inlist=False)
        assert has_admin(user)
        assert not has_contrib(user2)
        assert not has_admin(user2)
        assert role.permission_level == UserPermissions.channel_administrator == plugin_channel.get_channel_permissions_of(
            user)

        assert json.loads(plugin_channel.get_users_as_json()) == {
            str(user.id): UserPermissions.channel_administrator.value}
        assert json.loads(PluginChannel.get_channels_users_as_json([plugin_channel])) == \
            {str(plugin_channel.id): {str(user.id): UserPermissions.channel_administrator.value}}

        plugin_channel.remove_permission_to_user(user)
        plugin_channel.give_permission_to_user(user2, UserPermissions.channel_administrator)
        assert not has_contrib(user)
        assert not has_admin(user)
        assert has_contrib(user2, check_inlist=False)
        assert has_admin(user2)
        plugin_channel.remove_permission_to_user(user2)
        assert not has_contrib(user2)
        assert not has_admin(user2)

        # Test plugin config parameters
        assert plugin_channel.get_config_param('string_param') == 'default string'
        assert plugin_channel.get_config_param('int_param') == 1
        assert plugin_channel.get_config_param('float_param') == float('-inf')
        assert plugin_channel.get_config_param('boolean_param') is True
        assert plugin_channel.get_config_param('template_param') is None
        with pytest.raises(KeyError):
            assert plugin_channel.get_config_param('this_param_does_not_exists')

        def assert_value_is_set(param, value):
            plugin_channel.plugin_config[param] = value
            plugin_channel.plugin_config = plugin_channel.plugin_config  # Force SQLObject update
            assert plugin_channel.get_config_param(param) == value

        assert_value_is_set('string_param', 'Hello, world!')
        assert_value_is_set('int_param', 42)
        assert_value_is_set('float_param', 42.0)
        assert_value_is_set('boolean_param', False)
        assert_value_is_set('template_param', 'fake-template')

        # Test parameters access rights
        ppar = PluginParamAccessRights.selectBy(plugin=fake_plugin, name='int_param').getOne()
        ppar.channel_contributor_read = False
        ppar.channel_contributor_write = False
        ppar.channel_administrator_read = True
        ppar.channel_administrator_write = False
        ppar.administrator_read = True
        ppar.administrator_write = True

        user.super_admin = True
        assert plugin_channel.has_visible_params_for(user)
        for param in ['string_param', 'int_param', 'float_param', 'boolean_param', 'template_param']:
            assert plugin_channel.get_access_rights_for(param, user) == (True, True)
        user.super_admin = False

        assert not plugin_channel.has_visible_params_for(user)
        plugin_channel.give_permission_to_user(user, UserPermissions.channel_contributor)
        assert not plugin_channel.has_visible_params_for(user)
        assert plugin_channel.get_access_rights_for('int_param', user) == (False, False)
        plugin_channel.give_permission_to_user(user, UserPermissions.channel_administrator)
        assert plugin_channel.has_visible_params_for(user)
        assert plugin_channel.get_access_rights_for('int_param', user) == (True, False)
        user.admin = True
        assert plugin_channel.has_visible_params_for(user)
        assert plugin_channel.get_access_rights_for('int_param', user) == (True, True)
        plugin_channel.remove_permission_to_user(user)
        user.admin = False
        assert not plugin_channel.has_visible_params_for(user)
        assert plugin_channel.get_access_rights_for('int_param', user) == (False, False)

        # Test miscellaneous parameters
        assert plugin_channel.cache_activated is True
        plugin_channel.plugin.cache_activated_default = False
        assert plugin_channel.cache_activated is False
        plugin_channel.cache_activated = True
        assert plugin_channel.cache_activated is True

        assert plugin_channel.cache_validity is 60
        plugin_channel.plugin.cache_validity_default = 120
        assert plugin_channel.cache_validity is 120
        plugin_channel.cache_validity = 42
        assert plugin_channel.cache_validity is 42

        assert plugin_channel.keep_noncomplying_capsules is False
        plugin_channel.plugin.keep_noncomplying_capsules_default = True
        assert plugin_channel.keep_noncomplying_capsules is True
        plugin_channel.keep_noncomplying_capsules = False
        assert plugin_channel.keep_noncomplying_capsules is False

        # Test flatten()
        plugin_channel.enabled = False
        assert plugin_channel.flatten() == []
        assert plugin_channel.flatten(keep_disabled_channels=True) == [plugin_channel]
        plugin_channel.enabled = True
        assert plugin_channel.flatten() == [plugin_channel]


class ChannelBundleObjectTest(FakePluginTestCase):
    def runTest(self):
        """ Tests the ChannelBundle SQLObject """
        fake_plugin = Plugin.byName('fake_plugin')
        fake_plugin.cache_activated_default = False
        pc1 = PluginChannel(name='Channel1', plugin=fake_plugin, subscription_right='public')
        pc2 = PluginChannel(name='Channel2', plugin=fake_plugin, subscription_right='public')
        pc3 = PluginChannel(name='Channel3', plugin=fake_plugin, subscription_right='public')
        channel_bundle = ChannelBundle(name='Channel Bundle', subscription_right='public')
        channel_bundle2 = ChannelBundle(name='Channel Bundle 2', subscription_right='public')
        channel_bundle3 = ChannelBundle(name='Channel Bundle 3', subscription_right='public')

        # Test basic functionality
        channel_bundle.add_channel(pc1)
        channel_bundle.add_channel(pc1)
        channel_bundle.add_channel(pc2)
        channel_bundle.add_channel(pc2)
        channel_bundle.add_channel(pc3)
        channel_bundle.add_channel(pc3)
        assert list(channel_bundle.flatten()) == [pc1, pc2, pc3]

        channel_bundle.remove_channel(pc2)
        assert list(channel_bundle.flatten()) == [pc1, pc3]

        bundle_content = [self.ictv_app.plugin_manager.get_plugin_content(pc) for pc in channel_bundle.flatten()]
        channels_content = [self.ictv_app.plugin_manager.get_plugin_content(pc1),
                            self.ictv_app.plugin_manager.get_plugin_content(pc3)]
        for content1, content2 in zip(bundle_content, channels_content):
            capsule1 = content1[0]
            capsule2 = content2[0]
            assert capsule1 == capsule2

        channel_bundle.remove_channel(pc2)
        channel_bundle.remove_channel(pc3)
        channel_bundle.remove_channel(pc1)
        assert list(channel_bundle.flatten()) == []

        assert channel_bundle.get_type_name() == 'Bundle'

        # Test cycle detection
        channel_bundle.add_channel(channel_bundle2)
        channel_bundle2.add_channel(channel_bundle3)
        with pytest.raises(ValueError):
            channel_bundle3.add_channel(channel_bundle)
        with pytest.raises(ValueError):
            channel_bundle.add_channel(channel_bundle)


class RoleObjectTest(ICTVTestCase):
    def runTest(self):
        """ Tests the Role SQLObject """
        Channel.deleteMany(None)
        fake_plugin = Plugin(name='fake_plugin', activated='notfound')
        plugin_channel = PluginChannel(name='Plugin Channel', plugin=fake_plugin, subscription_right='public')
        user = User(fullname='User', email='test@localhost')

        role = Role(user=user, channel=plugin_channel, permission_level=UserPermissions.channel_administrator)
        assert role._SO_get_permission_level() == 'channel_administrator'
        assert role.permission_level == UserPermissions.channel_administrator
        role.permission_level = UserPermissions.channel_contributor
        assert role._SO_get_permission_level() == 'channel_contributor'
        assert role.permission_level == UserPermissions.channel_contributor


class UserPermissionsTest(ICTVTestCase):
    def runTest(self):
        """ Tests the UserPermissions class """
        assert hash(UserPermissions.super_administrator) == 0b11111
        assert UserPermissions.get_permission_string(UserPermissions.channel_administrator) == 'channel_administrator'
        assert UserPermissions.get_permission_string(UserPermissions.channel_contributor) == 'channel_contributor'
        with pytest.raises(ValueError):
            UserPermissions.get_permission_string(UserPermissions.administrator)
        assert UserPermissions.get_permission_name(UserPermissions.administrator) == 'Administrator'

        assert UserPermissions.channel_contributor in UserPermissions.channel_contributor
        assert UserPermissions.channel_contributor in UserPermissions.channel_administrator
        assert UserPermissions.channel_contributor not in UserPermissions.screen_administrator
        assert UserPermissions.channel_contributor in UserPermissions.administrator
        assert UserPermissions.channel_contributor in UserPermissions.super_administrator

        assert UserPermissions.channel_administrator not in UserPermissions.channel_contributor
        assert UserPermissions.channel_administrator in UserPermissions.channel_administrator
        assert UserPermissions.channel_administrator not in UserPermissions.screen_administrator
        assert UserPermissions.channel_administrator in UserPermissions.administrator
        assert UserPermissions.channel_administrator in UserPermissions.super_administrator

        assert UserPermissions.screen_administrator not in UserPermissions.channel_contributor
        assert UserPermissions.screen_administrator not in UserPermissions.channel_administrator
        assert UserPermissions.screen_administrator in UserPermissions.screen_administrator
        assert UserPermissions.screen_administrator in UserPermissions.administrator
        assert UserPermissions.screen_administrator in UserPermissions.super_administrator

        assert UserPermissions.administrator not in UserPermissions.channel_contributor
        assert UserPermissions.administrator not in UserPermissions.channel_administrator
        assert UserPermissions.administrator not in UserPermissions.screen_administrator
        assert UserPermissions.administrator in UserPermissions.administrator
        assert UserPermissions.administrator in UserPermissions.super_administrator
        assert (UserPermissions.channel_administrator | UserPermissions.screen_administrator) in UserPermissions.administrator

        assert UserPermissions.super_administrator not in UserPermissions.channel_contributor
        assert UserPermissions.super_administrator not in UserPermissions.channel_administrator
        assert UserPermissions.super_administrator not in UserPermissions.screen_administrator
        assert UserPermissions.super_administrator not in UserPermissions.administrator
        assert UserPermissions.super_administrator in UserPermissions.super_administrator
        assert UserPermissions.super_administrator not in (UserPermissions.channel_administrator | UserPermissions.screen_administrator)
        assert UserPermissions.administrator in UserPermissions.super_administrator


class ScreenObjectTest(FakePluginTestCase):
    def runTest(self):
        """ Tests the Screen SQLObject """
        Channel.deleteMany(None)
        Screen.deleteMany(None)
        channel = Channel(name='Channel', subscription_right='public', secret='abcdef')
        plugin_channel = PluginChannel(name='Channel2', plugin=Plugin.byName('fake_plugin'), subscription_right='public')
        plugin_channel2 = PluginChannel(name='Channel3', plugin=Plugin.byName('fake_plugin'), subscription_right='public')
        bundle_channel = ChannelBundle(name='Channel4', subscription_right='public')
        bundle_channel.add_channel(plugin_channel2)
        building = Building(name='building')
        screen = Screen(name='Screen', building=building, secret='abcdef')
        screen2 = Screen(name='Screen2', building=building)
        user = User(fullname='User', email='test@localhost')
        user2 = User(fullname='User2', email='test2@localhost')

        # Miscellaneous test
        assert screen.get_view_link() == '/screens/%d/view/abcdef' % screen.id
        assert screen.get_client_link() == '/screens/%d/client/abcdef' % screen.id
        assert screen.get_macs_string() == ''
        assert screen not in user.screens
        screen.safe_add_user(user)
        assert screen in user.screens
        assert screen not in user2.screens
        screen.removeUser(user)
        assert screen not in user2.screens

        # Test subscription
        assert not screen.is_subscribed_to(channel)
        screen.subscribe_to(user, channel)
        assert screen.is_subscribed_to(channel)
        sub = screen.subscriptions[0]
        screen.subscribe_to(user2, channel, weight=42)
        assert sub.created_by == user2
        assert sub.weight == 42
        assert screen.is_subscribed_to(channel)
        assert list(screen.subscribed_channels) == [channel]
        screen.unsubscribe_from(user2, channel)
        assert not screen.is_subscribed_to(channel)

        # Test macs
        ScreenMac(screen=screen, mac='00b16b00b500')
        ScreenMac(screen=screen, mac='00b16b00b501')
        assert screen.get_macs_string() == '00:b1:6b:00:b5:00;00:b1:6b:00:b5:01'

        # Test get_visible_screens_of()
        assert list(Screen.get_visible_screens_of(user)) == list(Screen.get_visible_screens_of(user2)) == []
        user.admin = True
        assert list(Screen.get_visible_screens_of(user)) == [screen, screen2]
        assert list(Screen.get_visible_screens_of(user2)) == []
        user.admin = False
        user2.super_admin = True
        assert list(Screen.get_visible_screens_of(user2)) == [screen, screen2]
        assert list(Screen.get_visible_screens_of(user)) == []
        user2.super_admin = False
        screen.safe_add_user(user)
        screen2.safe_add_user(user2)
        assert list(Screen.get_visible_screens_of(user)) == [screen]
        assert list(Screen.get_visible_screens_of(user2)) == [screen2]

        # Test channel content
        screen.subscribe_to(user, plugin_channel)
        screen.subscribe_to(user, bundle_channel)
        screen_content = screen.get_channels_content(self.ictv_app)
        assert len(screen_content) == 2
        assert len(screen_content[0].get_slides()) == 1
        assert screen_content[0].get_slides()[0].get_content() == {'background-1': {'size': 'contain', 'src': ''},
                                                                   'title-1': {'text': 'Channel2'}, 'text-1': {'text': ''}}
        assert len(screen_content[1].get_slides()) == 1
        assert screen_content[1].get_slides()[0].get_content() == {'background-1': {'size': 'contain', 'src': ''},
                                                                   'title-1': {'text': 'Channel3'}, 'text-1': {'text': ''}}
        screen.shuffle = True
        assert len(screen.get_channels_content(self.ictv_app)) == 2


class ScreenMacObjectTest(ICTVTestCase):
    def runTest(self):
        """ Tests the ScreenMac SQLObject """
        building = Building(name='building')
        screen = Screen(name='Screen', building=building, secret='abcdef')
        mac = ScreenMac(screen=screen, mac='00b16b00b500')
        assert mac.get_pretty_mac() == '00:b1:6b:00:b5:00'


class ICTVObjectTest(ICTVTestCase):
    def runTest(self):
        """ Tests the ICTVObject SQLObject """
        user = User(fullname='User', email='test@localhost')
        assert user.to_dictionary(['fullname', 'email']) == {'fullname': 'User', 'email': 'test@localhost'}


class PluginObjectTestA(FakePluginTestCase):
    def setUp(self):
        super(PluginObjectTestA, self).setUp(
            fake_plugin_middleware=lambda: os.remove(os.path.join(self.fake_plugin_root, 'config' + os.extsep + 'yaml'))
        )

    def runTest(self):
        """ Tests that a missing config.yaml file result in a not found plugin object """
        assert Plugin.byName('fake_plugin').activated == 'notfound'


class PluginObjectTestB(ICTVTestCase):
    def setUp(self):
        super(PluginObjectTestB, self).setUp(
            middleware=lambda: Plugin(name='fake_plugin', activated='yes')
        )

    def runTest(self):
        """ Tests that missing plugin code result in a not found plugin object """
        assert Plugin.byName('fake_plugin').activated == 'notfound'


class PluginObjectTestC(FakePluginTestCase):
    def setUp(self):  # This test duplicates a lot of setUp code, it should be refactored or dropped
        from ictv.app import get_app
        from ictv.database import setup_database, create_database, load_plugins
        from ictv.plugin_manager.plugin_manager import PluginManager
        from paste.fixture import TestApp

        create_fake_plugin(self.fake_plugin_root)

        setup_database()
        create_database()
        load_plugins()
        Plugin.selectBy(name='fake_plugin').getOne().activated = 'notfound'
        Plugin.update_plugins(PluginManager.list_plugins())
        self.ictv_app = get_app("/tmp/config.yaml")
        self.testApp = TestApp(self.ictv_app.wsgifunc())

    def runTest(self):
        """ Tests that a previously not found plugin object is marked as deactivated after being found """
        assert Plugin.byName('fake_plugin').activated == 'no'


class PluginObjectTestD(FakePluginTestCase):
    def setUp(self):
        def f():
            p = Plugin.selectBy(name='fake_plugin').getOne()
            p.activated = 'yes'
            p.channels_params['this_parameter_does_not_exists'] = None
            p.channels_params = p.channels_params  # Force SQLObject update
            PluginParamAccessRights(plugin=p, name='this_parameter_does_not_exists')

        super(PluginObjectTestD, self).setUp(ictv_middleware=f)

    def runTest(self):
        p = Plugin.byName('fake_plugin')
        assert 'this_parameter_does_not_exists' not in p.channels_params
        assert PluginParamAccessRights.selectBy(plugin=p, name='this_parameter_does_not_exists').getOne(None) is None


class PluginObjectTestF(FakePluginTestCase):
    def runTest(self):
        fake_plugin = Plugin.byName('fake_plugin')
        user = User(fullname='User', email='test@localhost')

        assert fake_plugin.channels_number == 0
        pc1 = PluginChannel(plugin=fake_plugin, name='Plugin Channel 1', subscription_right='public')
        assert fake_plugin.channels_number == 1
        pc2 = PluginChannel(plugin=fake_plugin, name='Plugin Channel 2', subscription_right='public')
        assert fake_plugin.channels_number == 2
        pc2.destroySelf()
        assert fake_plugin.channels_number == 1

        pc2 = PluginChannel(plugin=fake_plugin, name='Plugin Channel 2', subscription_right='public')
        pc3 = PluginChannel(plugin=fake_plugin, name='Plugin Channel 3', subscription_right='public')
        bundle_channel = ChannelBundle(name='Bundle', subscription_right='public')
        bundle_channel.add_channel(pc3)
        building = Building(name='building')
        screen1 = Screen(name='Screen1', building=building)
        screen2 = Screen(name='Screen2', building=building)
        screen3 = Screen(name='Screen3', building=building)

        assert fake_plugin.screens_number == 0
        screen1.subscribe_to(user, pc1)
        assert fake_plugin.screens_number == 1
        screen1.subscribe_to(user, pc2)
        assert fake_plugin.screens_number == 1
        screen2.subscribe_to(user, pc3)
        assert fake_plugin.screens_number == 2
        screen2.subscribe_to(user, bundle_channel)
        assert fake_plugin.screens_number == 2
        screen3.subscribe_to(user, bundle_channel)
        assert fake_plugin.screens_number == 3


class PluginParamAccessRightsTest(ICTVTestCase):
    def runTest(self):
        """ Tests the plugin parameter access rights. """
        p = Plugin(name='testPlug', activated='yes')
        par = PluginParamAccessRights(plugin=p, name='testParam')
        assert par.get_access_rights_for(UserPermissions.super_administrator) == (True, True)
        assert par.get_access_rights_for(UserPermissions.administrator) == (True, True)
        assert par.get_access_rights_for(UserPermissions.channel_administrator) == (True, False)
        assert par.get_access_rights_for(UserPermissions.channel_contributor) == (False, False)
        assert par.get_access_rights_for(UserPermissions.no_permission) == (False, False)


class UserObjectTest(ICTVTestCase):
    def runTest(self):
        """ Tests the User SQLObject """
        user = User(username='username', fullname='fullname', email='email')
        fake_plugin = Plugin(name='fake_plugin', activated='notfound')
        plugin_channel = PluginChannel(plugin=fake_plugin, name='Channel', subscription_right='public')
        building = Building(name='building')
        screen = Screen(name='Screen', building=building)
        screen.subscribe_to(user, plugin_channel)

        # Miscellaneous test
        assert user.log_name == 'fullname (%d)' % user.id
        user.fullname = None
        assert user.log_name == 'email (%d)' % user.id
        user.fullname = 'fullname'
        assert user.log_name == 'fullname (%d)' % user.id
        assert user.readable_name == 'fullname'
        user.fullname = None
        assert user.readable_name == 'username'
        user.username = None
        assert user.readable_name == 'email'

        # Test permissions
        assert user.highest_permission_level == UserPermissions.no_permission
        assert list(user.get_subscriptions_of_owned_screens()) == []
        assert list(user.get_channels_with_permission_level(UserPermissions.channel_contributor)) == []
        assert list(user.get_channels_with_permission_level(UserPermissions.channel_administrator)) == []

        plugin_channel.give_permission_to_user(user, UserPermissions.channel_contributor)
        assert user.highest_permission_level == UserPermissions.channel_contributor
        assert list(user.get_channels_with_permission_level(UserPermissions.channel_contributor)) == [plugin_channel]
        assert list(user.get_channels_with_permission_level(UserPermissions.channel_administrator)) == []

        plugin_channel.give_permission_to_user(user, UserPermissions.channel_administrator)
        assert user.highest_permission_level == UserPermissions.channel_administrator
        assert list(user.get_channels_with_permission_level(UserPermissions.channel_contributor)) == []
        assert list(user.get_channels_with_permission_level(UserPermissions.channel_administrator)) == [plugin_channel]

        plugin_channel.remove_permission_to_user(user)
        assert user.highest_permission_level == UserPermissions.no_permission
        assert list(user.get_subscriptions_of_owned_screens()) == []

        user.admin = True
        assert user.highest_permission_level == UserPermissions.administrator
        assert list(user.get_subscriptions_of_owned_screens()) == list(screen.subscriptions)
        user.admin = False
        assert user.highest_permission_level == UserPermissions.no_permission
        assert list(user.get_subscriptions_of_owned_screens()) == []
        user.super_admin = True
        assert user.highest_permission_level == UserPermissions.super_administrator
        assert list(user.get_subscriptions_of_owned_screens()) == list(screen.subscriptions)
        user.super_admin = False
        assert user.highest_permission_level == UserPermissions.no_permission
        assert list(user.get_subscriptions_of_owned_screens()) == []

        screen.safe_add_user(user)
        assert user.highest_permission_level == UserPermissions.screen_administrator
        assert list(user.get_subscriptions_of_owned_screens()) == list(screen.subscriptions)
        screen.removeUser(user)
        assert list(user.get_subscriptions_of_owned_screens()) == []
        assert user.highest_permission_level == UserPermissions.no_permission


class LogStatTestDump(ICTVTestCase):
    def runTest(self):
        """ verifies the dump_log_stats method of LogStat """
        # generate log_stats dict
        my_stats = {
            "test_stat_1": {
                "DEBUG": datetime.datetime.now(),
                "INFO": datetime.datetime.now(),
                "WARNING": datetime.datetime.now(),
                "ERROR": datetime.datetime.now(),
                "n_entries": 3
            },
            "test_stat_2": {
                "INFO": datetime.datetime.now(),
                "WARNING": datetime.datetime.now()
            }
        }
        my_stats["test_stat_1"]["last_activity"] = my_stats["test_stat_1"]["ERROR"]
        my_stats["test_stat_2"]["last_activity"] = my_stats["test_stat_2"]["WARNING"]
        LogStat.dump_log_stats(my_stats)
        test_stat_1 = LogStat.selectBy(logger_name="test_stat_1").getOne(None)
        test_stat_2 = LogStat.selectBy(logger_name="test_stat_2").getOne(None)
        assert test_stat_1 is not None
        assert test_stat_2 is not None
        assert test_stat_1.last_debug == my_stats["test_stat_1"]["DEBUG"]
        assert test_stat_1.last_info == my_stats["test_stat_1"]["INFO"]
        assert test_stat_1.last_warning == my_stats["test_stat_1"]["WARNING"]
        assert test_stat_1.last_error == my_stats["test_stat_1"]["ERROR"]
        assert test_stat_1.last_activity == my_stats["test_stat_1"]["last_activity"]
        assert test_stat_1.n_entries == my_stats["test_stat_1"]["n_entries"]

        assert test_stat_2.last_debug is None
        assert test_stat_2.last_info == my_stats["test_stat_2"]["INFO"]
        assert test_stat_2.last_warning == my_stats["test_stat_2"]["WARNING"]
        assert test_stat_2.last_error is None
        assert test_stat_2.last_activity == my_stats["test_stat_2"]["last_activity"]
        assert test_stat_2.n_entries == 0


class LogStatTestLoad(ICTVTestCase):
    def runTest(self):
        """ verifies the dump_log_stats method of LogStat """
        # first remove everything in the table
        LogStat.deleteMany(None)
        # generate log_stats dict
        my_stats = {
            "test_stat_1": {
                "DEBUG": datetime.datetime.now(),
                "INFO": datetime.datetime.now(),
                "WARNING": datetime.datetime.now(),
                "ERROR": datetime.datetime.now(),
                "n_entries": 3
            },
            "test_stat_2": {
                "INFO": datetime.datetime.now(),
                "WARNING": datetime.datetime.now()
            }
        }
        my_stats["test_stat_1"]["last_activity"] = my_stats["test_stat_1"]["ERROR"]
        my_stats["test_stat_2"]["last_activity"] = my_stats["test_stat_2"]["WARNING"]
        # insert the stats in the database
        LogStat.dump_log_stats(my_stats)

        # add the n_entries attrbute which will be automaticcaly added by dump in its return value
        my_stats["test_stat_2"]["n_entries"] = 0

        # Now load the inserted stats and check that everything has been correctly loaded
        assert LogStat.load_log_stats() == my_stats