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

from ictv.models import building
from ictv.models.building import Building
from ictv.models.channel import Channel, PluginChannel, ChannelBundle
from ictv.models.plugin import Plugin
from ictv.models.role import UserPermissions
from ictv.models.screen import Screen
from ictv.models.user import User
from ictv.tests import FakePluginTestCase


class ChannelsPageTestCase(FakePluginTestCase):
    def setUp(self):
        super(ChannelsPageTestCase, self).setUp()
        Channel.deleteMany(None)
        self.fake_plugin = Plugin.byName('fake_plugin')
        self.pc1 = PluginChannel(plugin=self.fake_plugin, name='PC 1', subscription_right='public')
        self.pc2 = PluginChannel(plugin=self.fake_plugin, name='PC 2', subscription_right='public')
        self.pc3 = PluginChannel(plugin=self.fake_plugin, name='PC 3', subscription_right='public')
        self.bundle = ChannelBundle(name='Bundle', subscription_right='public')
        self.building = Building(name='Building')
        self.screen = Screen(name='Screen', building=self.building)
        self.user_nothing = User(email='nothing@localhost', disabled=False)
        self.user_contrib = User(email='contrib@localhost', disabled=False)
        self.pc1.give_permission_to_user(self.user_contrib, UserPermissions.channel_contributor)
        self.user_chan_admin = User(email='chan_admin@localhost', disabled=False)
        self.user_chan_admin2 = User(email='chan_admin2@localhost', disabled=False)
        self.pc1.give_permission_to_user(self.user_chan_admin, UserPermissions.channel_administrator)
        self.pc2.give_permission_to_user(self.user_chan_admin2, UserPermissions.channel_administrator)
        self.user_screen_admin = User(email='screen_admin@locahost', disabled=False)
        self.screen.safe_add_user(self.user_screen_admin)
        self.user_admin = User(email='admin@localhost', disabled=False, admin=True)
        self.user_super_admin = User(email='super_admin@localhost', disabled=False, admin=True, super_admin=True)
        self.users = [self.user_nothing, self.user_contrib, self.user_chan_admin, self.user_chan_admin2, self.user_screen_admin, self.user_admin, self.user_super_admin]


class ChannelsPageGetTest(ChannelsPageTestCase):
    def runTest(self):
        """ Tests that every user has access to the page. """
        for u in self.users:
            self.ictv_app.test_user = {'email': u.email}
            assert self.testApp.get('/channels', status=200).body is not None


class ChannelCreationTest(ChannelsPageTestCase):
    def runTest(self):
        """ Tests channels creation via the Channels page """
        channel_params = {'action': 'create-channel', 'name': 'Plugin Channel test creation', 'description': 'Descr.', 'enabled': 'on',
                          'subscription_right': 'public', 'plugin': self.fake_plugin.id}
        bundle_params = dict(**channel_params)
        bundle_params.update({'action': 'create-bundle', 'name': 'Channel Bundle test creation'})

        def assert_creation(status=200):
            assert PluginChannel.selectBy(name=channel_params['name']).getOne(None) is None
            assert self.testApp.post('/channels', params=channel_params, status=status).body is not None
            chan = PluginChannel.selectBy(name=channel_params['name']).getOne(None)
            assert chan is not None
            chan.destroySelf()

            assert ChannelBundle.selectBy(name=bundle_params['name']).getOne(None) is None
            assert self.testApp.post('/channels', params=bundle_params, status=status).body is not None
            chan = ChannelBundle.selectBy(name=bundle_params['name']).getOne(None)
            assert chan is not None
            chan.destroySelf()

        def assert_no_creation(status=200):
            assert PluginChannel.selectBy(name=channel_params['name']).getOne(None) is None
            assert self.testApp.post('/channels', params=channel_params, status=status).body is not None
            assert PluginChannel.selectBy(name=channel_params['name']).getOne(None) is None
            assert ChannelBundle.selectBy(name=bundle_params['name']).getOne(None) is None
            assert self.testApp.post('/channels', params=bundle_params, status=status).body is not None
            assert ChannelBundle.selectBy(name=bundle_params['name']).getOne(None) is None

        # Test basic creation
        assert_creation()

        # Test name less than 3 chars
        channel_params['name'] = bundle_params['name'] = 'aa'
        assert_no_creation()
        channel_params['name'] = 'Proper channel name'
        bundle_params['name'] = 'Proper bundle name'

        # Test invalid subscription right
        channel_params['subscription_right'] = bundle_params['subscription_right'] = 'invalid'
        assert_no_creation()
        channel_params['subscription_right'] = bundle_params['subscription_right'] = 'public'

        # Test insufficient permissions for channel creation
        for u in [self.user_nothing, self.user_contrib, self.user_chan_admin, self.user_screen_admin]:
            self.ictv_app.test_user = {'email': u.email}
            assert_no_creation(403)

        # Test sufficient permissions for channel creation
        for u in [self.user_admin, self.user_super_admin]:
            self.ictv_app.test_user = {'email': u.email}
            assert_creation()

        # Test invalid plugin
        channel_params['plugin'] = self.fake_plugin.id + 42
        assert PluginChannel.selectBy(name=channel_params['name']).getOne(None) is None
        assert self.testApp.post('/channels', params=channel_params, status=200).body is not None
        assert PluginChannel.selectBy(name=channel_params['name']).getOne(None) is None
        channel_params['plugin'] = 'invalid'
        assert PluginChannel.selectBy(name=channel_params['name']).getOne(None) is None
        assert self.testApp.post('/channels', params=channel_params, status=200).body is not None
        assert PluginChannel.selectBy(name=channel_params['name']).getOne(None) is None
        channel_params['plugin'] = self.fake_plugin.id

        # Test invalid action
        channel_params['action'] = bundle_params['action'] = 'create-invalid'
        assert_no_creation(400)
        channel_params['action'] = 'create-channel'
        bundle_params['action'] = 'create-bundle'

        # Test duplicate name
        Channel(name='already taken', subscription_right='public')
        channel_params['name'] = bundle_params['name'] = 'already taken'
        assert_no_creation()


class ChannelEditionTest(ChannelsPageTestCase):
    def runTest(self):
        """ Tests the channels edition through the Channels page """
        channel_params = {'action': 'edit-channel', 'name': 'Plugin Channel test edition', 'description': 'Descr.',
                          'subscription_right': 'public', 'plugin': self.fake_plugin.id, 'id': self.pc1.id}
        bundle_params = dict(**channel_params)
        bundle_params.update({'action': 'edit-bundle', 'name': 'Channel Bundle test edition', 'id': self.bundle.id})
        bundle_params.pop('plugin')

        def get_attr(o, a):
            if a == 'plugin':
                return o.plugin.id
            if a == 'enabled':
                return 'on' if o.enabled else ''
            return getattr(o, a)

        def assert_edition(attrs=None, channel_params=channel_params, bundle_params=bundle_params, status=200):
            if attrs is None:
                attrs = ['name', 'description', 'enabled', 'subscription_right', 'plugin']
            assert self.testApp.post('/channels', params=channel_params, status=status).body is not None
            pc = PluginChannel.get(self.pc1.id)
            for attr in attrs:
                if attr in channel_params:
                    assert get_attr(pc, attr) == channel_params[attr]
            assert self.testApp.post('/channels', params=bundle_params, status=status).body is not None
            bc = ChannelBundle.get(self.bundle.id)
            for attr in attrs:
                if attr in bundle_params:
                    assert get_attr(bc, attr) == bundle_params[attr]
            if channel_params is not orig_plugin_channel_params and bundle_params is not orig_bundle_params:
                assert_edition(channel_params=orig_plugin_channel_params, bundle_params=orig_bundle_params)  # Revert

        def assert_no_edition(status=200):
            assert self.testApp.post('/channels', params=channel_params, status=status).body is not None
            assert orig_plugin_channel == repr(PluginChannel.get(self.pc1.id))
            assert self.testApp.post('/channels', params=bundle_params, status=status).body is not None
            assert orig_bundle_channel == repr(ChannelBundle.get(self.bundle.id))

        orig_plugin_channel_params = {'action': 'edit-channel', 'name': 'Plugin Channel',
                                      'description': 'Original descr.', 'subscription_right': 'public',
                                      'plugin': self.fake_plugin.id, 'id': self.pc1.id}
        orig_bundle_params = dict(**orig_plugin_channel_params)
        orig_bundle_params.update({'action': 'edit-bundle', 'name': 'Channel Bundle test edition', 'id': self.bundle.id})
        orig_bundle_params.pop('plugin')
        assert_edition(channel_params=orig_plugin_channel_params, bundle_params=orig_bundle_params)

        orig_plugin_channel = repr(PluginChannel.get(self.pc1.id))
        orig_bundle_channel = repr(ChannelBundle.get(self.bundle.id))

        # Test basic functionality
        assert_edition()

        # Test insufficient permissions for channel edition
        for u in [self.user_nothing, self.user_contrib, self.user_chan_admin, self.user_screen_admin]:
            self.ictv_app.test_user = {'email': u.email}
            assert_no_edition(403)

        # Test sufficient permissions for channel edition
        for u in [self.user_admin, self.user_super_admin]:
            self.ictv_app.test_user = {'email': u.email}
            assert_edition()

        # Test invalid id
        channel_params['id'] = bundle_params['id'] = -1
        assert_no_edition()
        channel_params['id'] = bundle_params['id'] = 'invalid'
        assert_no_edition()
        channel_params['id'] = self.pc1.id
        bundle_params['id'] = self.bundle.id

        # Test invalid plugin
        channel_params['plugin'] = -1
        assert self.testApp.post('/channels', params=channel_params, status=200).body is not None
        assert orig_plugin_channel == repr(PluginChannel.get(self.pc1.id))
        channel_params['plugin'] = 'invalid'
        assert self.testApp.post('/channels', params=channel_params, status=200).body is not None
        assert orig_plugin_channel == repr(PluginChannel.get(self.pc1.id))
        channel_params['plugin'] = self.fake_plugin.id

        # Test invalid action
        channel_params['action'] = bundle_params['action'] = 'edit-invalid'
        assert_no_edition(400)
        channel_params['action'] = 'edit-channel'
        bundle_params['action'] = 'edit-bundle'

        # Test duplicate name
        Channel(name='already taken', subscription_right='public')
        channel_params['name'] = bundle_params['name'] = 'already taken'
        assert_no_edition()


class ChannelDeletionTest(ChannelsPageTestCase):
    def runTest(self):
        """ Tests the channels deletion through the Channels page """
        pc1_id = self.pc1.id
        bundle_id = self.bundle.id

        channel_params = {'action': 'delete-channel', 'id': pc1_id}
        bundle_params = {'action': 'delete-bundle', 'id': bundle_id}

        def assert_deletion(channel_params=channel_params, bundle_params=bundle_params, status=200):
            assert self.testApp.post('/channels', params=channel_params, status=status).body is not None
            assert PluginChannel.selectBy(id=pc1_id).getOne(None) is None
            assert self.testApp.post('/channels', params=bundle_params, status=status).body is not None
            assert ChannelBundle.selectBy(id=bundle_id).getOne(None) is None
            return (PluginChannel(plugin=self.fake_plugin, name='PC 1', subscription_right='public').id,
                    ChannelBundle(name='Bundle', subscription_right='public').id)

        def assert_no_deletion(channel_params=channel_params, bundle_params=bundle_params, status=200):
            assert self.testApp.post('/channels', params=channel_params, status=status).body is not None
            assert PluginChannel.selectBy(id=pc1_id).getOne(None) is not None
            assert self.testApp.post('/channels', params=bundle_params, status=status).body is not None
            assert ChannelBundle.selectBy(id=bundle_id).getOne(None) is not None

        # Test basic functionality
        pc1_id, bundle_id = assert_deletion()
        channel_params['id'] = pc1_id
        bundle_params['id'] = bundle_id

        # Test insufficient permissions for channel edition
        for u in [self.user_nothing, self.user_contrib, self.user_chan_admin, self.user_screen_admin, self.user_admin]:
            self.ictv_app.test_user = {'email': u.email}
            assert_no_deletion(status=403)

        # Test sufficient permissions for channel edition
        for u in [self.user_super_admin]:
            self.ictv_app.test_user = {'email': u.email}
            pc1_id, bundle_id = assert_deletion()
            channel_params['id'] = pc1_id
            bundle_params['id'] = bundle_id

            # Test invalid id
            channel_params['id'] = bundle_params['id'] = -1
            assert_no_deletion()
            channel_params['id'] = bundle_params['id'] = 'invalid'
            assert_no_deletion()
            channel_params['id'] = pc1_id
            bundle_params['id'] = bundle_id

        # Test subscriptions
        pc1_id, bundle_id = assert_deletion()
        channel_params['id'] = pc1_id
        bundle_params['id'] = bundle_id
        self.pc1 = PluginChannel.get(pc1_id)
        self.bundle = ChannelBundle.get(bundle_id)
        self.screen.subscribe_to(self.user_super_admin, self.pc1)
        assert self.testApp.post('/channels', params=channel_params, status=200).body is not None
        assert PluginChannel.selectBy(id=pc1_id).getOne(None) is not None
        self.screen.subscribe_to(self.user_super_admin, self.bundle)
        assert self.testApp.post('/channels', params=bundle_params, status=200).body is not None
        assert ChannelBundle.selectBy(id=bundle_id).getOne(None) is not None
        self.screen.unsubscribe_from(self.user_super_admin, self.pc1)
        assert self.testApp.post('/channels', params=channel_params, status=200).body is not None
        assert PluginChannel.selectBy(id=pc1_id).getOne(None) is None
        self.screen.unsubscribe_from(self.user_super_admin, self.bundle)
        assert self.testApp.post('/channels', params=bundle_params, status=200).body is not None
        assert ChannelBundle.selectBy(id=bundle_id).getOne(None) is None


class ChannelUsersTest(ChannelsPageTestCase):
    def runTest(self):
        """ Tests the users management through the Channels page """
        diff = {self.user_nothing.id: {'permission': UserPermissions.channel_contributor.value}}
        channel_params = {'action': 'add-users-channel', 'id': self.pc1.id, 'users': json.dumps(diff)}

        def assert_user_no_permission():
            self.pc1.expire()
            assert self.pc1.get_channel_permissions_of(self.user_nothing) == UserPermissions.no_permission
            assert not self.pc1.has_contrib(self.user_nothing) and not self.pc1.has_admin(self.user_nothing)

        def assert_users_change():
            assert_user_no_permission()
            diff[self.user_nothing.id]['permission'] = UserPermissions.channel_contributor.value
            channel_params['users'] = json.dumps(diff)
            assert self.testApp.post('/channels', params=channel_params, status=200).body is not None
            assert self.pc1.get_channel_permissions_of(self.user_nothing) == UserPermissions.channel_contributor
            assert self.pc1.has_contrib(self.user_nothing) and not self.pc1.has_admin(self.user_nothing)

            diff[self.user_nothing.id]['permission'] = UserPermissions.no_permission.value
            channel_params['users'] = json.dumps(diff)
            assert self.testApp.post('/channels', params=channel_params, status=200).body is not None
            assert not self.pc1.has_contrib(self.user_nothing) and not self.pc1.has_admin(self.user_nothing)

            diff[self.user_nothing.id]['permission'] = UserPermissions.channel_administrator.value
            channel_params['users'] = json.dumps(diff)
            assert self.testApp.post('/channels', params=channel_params, status=200).body is not None
            assert self.pc1.get_channel_permissions_of(self.user_nothing) == UserPermissions.channel_administrator
            assert self.pc1.has_contrib(self.user_nothing) and self.pc1.has_admin(self.user_nothing)

            diff[self.user_nothing.id]['permission'] = UserPermissions.no_permission.value
            channel_params['users'] = json.dumps(diff)
            assert self.testApp.post('/channels', params=channel_params, status=200).body is not None
            assert_user_no_permission()

            diff[self.user_nothing.id]['authorized_subscriber'] = True
            channel_params['users'] = json.dumps(diff)
            assert self.testApp.post('/channels', params=channel_params, status=200).body is not None
            assert_user_no_permission()
            assert self.user_nothing in self.pc1.authorized_subscribers

            diff[self.user_nothing.id]['authorized_subscriber'] = False
            channel_params['users'] = json.dumps(diff)
            assert self.testApp.post('/channels', params=channel_params, status=200).body is not None
            assert_user_no_permission()
            assert self.user_nothing not in self.pc1.authorized_subscribers

        def assert_no_users_change(status=200):
            assert_user_no_permission()
            assert self.testApp.post('/channels', params=channel_params, status=status).body is not None
            assert_user_no_permission()

            diff[self.user_nothing.id]['permission'] = UserPermissions.channel_administrator.value
            channel_params['users'] = json.dumps(diff)
            assert self.testApp.post('/channels', params=channel_params, status=status).body is not None
            assert_user_no_permission()

            diff[self.user_nothing.id]['authorized_subscriber'] = True
            channel_params['users'] = json.dumps(diff)
            assert self.testApp.post('/channels', params=channel_params, status=status).body is not None
            assert_user_no_permission()
            assert self.user_nothing not in self.pc1.authorized_subscribers

            diff[self.user_nothing.id]['authorized_subscriber'] = False
            channel_params['users'] = json.dumps(diff)
            assert self.testApp.post('/channels', params=channel_params, status=status).body is not None
            assert_user_no_permission()
            assert self.user_nothing not in self.pc1.authorized_subscribers

        # Test basic functionality
        assert_users_change()

        # Test admin and super admin cannot be set through plugin channels
        diff[self.user_nothing.id]['permission'] = UserPermissions.administrator.value
        channel_params['users'] = json.dumps(diff)
        assert self.testApp.post('/channels', params=channel_params, status=200).body is not None
        assert self.pc1.get_channel_permissions_of(self.user_nothing) == UserPermissions.no_permission
        assert not self.pc1.has_contrib(self.user_nothing) and not self.pc1.has_admin(self.user_nothing)

        diff[self.user_nothing.id]['permission'] = UserPermissions.super_administrator.value
        channel_params['users'] = json.dumps(diff)
        assert self.testApp.post('/channels', params=channel_params, status=200).body is not None
        assert self.pc1.get_channel_permissions_of(self.user_nothing) == UserPermissions.no_permission
        assert not self.pc1.has_contrib(self.user_nothing) and not self.pc1.has_admin(self.user_nothing)

        # Test insufficient permissions for users change
        for u in [self.user_nothing, self.user_contrib, self.user_screen_admin]:
            self.ictv_app.test_user = {'email': u.email}
            assert_no_users_change(403)

        # Test chan admin can only change contrib or auth sub
        self.ictv_app.test_user = {'email': self.user_chan_admin.email}
        assert_user_no_permission()
        diff[self.user_nothing.id]['permission'] = UserPermissions.channel_contributor.value
        channel_params['users'] = json.dumps(diff)
        assert self.testApp.post('/channels', params=channel_params, status=200).body is not None
        assert self.pc1.get_channel_permissions_of(self.user_nothing) == UserPermissions.channel_contributor
        assert self.pc1.has_contrib(self.user_nothing) and not self.pc1.has_admin(self.user_nothing)

        diff[self.user_nothing.id]['permission'] = UserPermissions.no_permission.value
        channel_params['users'] = json.dumps(diff)
        assert self.testApp.post('/channels', params=channel_params, status=200).body is not None
        assert not self.pc1.has_contrib(self.user_nothing) and not self.pc1.has_admin(self.user_nothing)

        diff[self.user_nothing.id]['permission'] = UserPermissions.channel_administrator.value
        channel_params['users'] = json.dumps(diff)
        assert self.testApp.post('/channels', params=channel_params, status=200).body is not None
        assert_user_no_permission()

        diff[self.user_nothing.id]['authorized_subscriber'] = True
        channel_params['users'] = json.dumps(diff)
        assert self.testApp.post('/channels', params=channel_params, status=200).body is not None
        assert_user_no_permission()
        assert self.user_nothing in self.pc1.authorized_subscribers

        diff[self.user_nothing.id]['authorized_subscriber'] = False
        channel_params['users'] = json.dumps(diff)
        assert self.testApp.post('/channels', params=channel_params, status=200).body is not None
        assert_user_no_permission()
        assert self.user_nothing not in self.pc1.authorized_subscribers

        # Test sufficient permissions for users change
        for u in [self.user_admin, self.user_super_admin]:
            self.ictv_app.test_user = {'email': u.email}
            assert_users_change()

        # Test an admin from another channel cannot change users in this channel
        self.ictv_app.test_user = {'email': self.user_chan_admin2.email}
        assert_no_users_change(403)
        del self.ictv_app.test_user

        # Test invalid channel
        channel_params['id'] = self.bundle.id
        assert_no_users_change()
        channel_params['id'] = -1
        assert_no_users_change()
        channel_params['id'] = 'invalid'
        assert_no_users_change()
        channel_params['id'] = self.pc1.id

        # Test no users dict
        channel_params.pop('users')
        assert_user_no_permission()
        assert self.testApp.post('/channels', params=channel_params, status=400).body is not None
        assert_user_no_permission()
