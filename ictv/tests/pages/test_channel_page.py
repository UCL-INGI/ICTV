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

from ictv.models.building import Building
from ictv.models.channel import PluginChannel, ChannelBundle, Channel
from ictv.models.plugin import Plugin
from ictv.models.role import UserPermissions
from ictv.models.screen import Screen
from ictv.models.user import User
from ictv.tests import ICTVTestCase, FakePluginTestCase


class ChannelTestCase(FakePluginTestCase):
    n_elements = 5  # must be >= 3
    plugin_channel_name = "test_channel"
    bundle_channel_name = "test_bundle"
    plugin_name = "test_plugin"
    user_nothing_email = "nothing@email.mail"
    user_screen_owner_email = "screenowner@email.mail"
    user_contributor_email = "contributor@email.mail"
    user_contributor_of_other_channel_email = "contributorofotherchannel@email.mail"
    user_administrator_of_other_channel_email = "administratorofotherchannel@email.mail"
    user_channel_admin_email = "channeladmin@email.mail"
    user_administrator_email = "administartor@email.startor"
    user_super_administrator_email = "superadministartor@email.startor"

    def setUp(self, fake_plugin_middleware=lambda: None, ictv_middleware=lambda: None):
        super().setUp(fake_plugin_middleware, ictv_middleware)
        building = Building(name="mytestbuilding")
        screen = Screen(name="mytestscreen", building=building, secret="secret")
        self.plugins = [Plugin(name="%s%d" % (self.plugin_name, i), activated="notfound") for i in
                         range(self.n_elements - 1)]
        self.plugins.append(Plugin.selectBy(name="fake_plugin").getOne())

        self.plugin_channels = [PluginChannel(name="%s%d" % (self.plugin_channel_name, i), plugin=self.plugins[i],
                                              subscription_right="public") for i in range(self.n_elements)]
        self.bundle_channels = [ChannelBundle(name="%s%d" % (self.bundle_channel_name, i), subscription_right="public")
                                for i in range(self.n_elements)]
        other_channel = PluginChannel(name="other_channel",plugin=self.plugins[0], subscription_right="public")
        User(email=self.user_nothing_email, disabled=False)
        User(email=self.user_administrator_email, disabled=False, admin=True)
        User(email=self.user_super_administrator_email, disabled=False, admin=True, super_admin=True)
        screen_owner = User(email=self.user_screen_owner_email, disabled=False)
        screen.safe_add_user(screen_owner)
        contributor = User(email=self.user_contributor_email, disabled=False)
        [plugin_channel.give_permission_to_user(contributor) for plugin_channel in self.plugin_channels]
        contributor_other_channel = User(email=self.user_contributor_of_other_channel_email, disabled=False)
        other_channel.give_permission_to_user(contributor_other_channel)
        administrator_other_channel = User(email=self.user_administrator_of_other_channel_email, disabled=False)
        other_channel.give_permission_to_user(administrator_other_channel, UserPermissions.channel_administrator)
        channel_admin = User(email=self.user_channel_admin_email, disabled=False)
        [plugin_channel.give_permission_to_user(channel_admin, UserPermissions.channel_administrator) for plugin_channel in self.plugin_channels]

    def tearDown(self):
        [plugin_channel.destroySelf() for plugin_channel in self.plugin_channels]
        [bundle_channel.destroySelf() for bundle_channel in self.bundle_channels]
        for email in [self.user_nothing_email, self.user_contributor_email, self.user_channel_admin_email,
                      self.user_administrator_email, self.user_super_administrator_email]:
            User.deleteBy(email=email)
        Plugin.deleteBy(name=self.plugin_name)
        super().tearDown()


class TestAddAndRemoveChannelToBundle(ChannelTestCase):
    def runTest(self):
        """ Checks that a user can successfully add a channel to a bundle """
        # Do the test for a plugin_channel and a bundle_channel
        for channel in [self.plugin_channels[0], self.bundle_channels[1]]:
            # Create the diffs
            # add a channel to some bundles
            diff = {self.bundle_channels[i].id: True for i in range(self.n_elements) if i % 2 == 0}
            # remove from the first bundle
            diff2 = {self.bundle_channels[0].id: False}

            # Test with the first diff (adding a channel to some bundles)
            post_params = {"action": "add-channel-to-bundles", "diff": json.dumps(diff)}
            # add to the bundles
            r = self.testApp.post('/channel/%d' % channel.id, params=post_params, status=303)
            assert r.body is not None
            # verify that everything has been successfully added
            verify_diff(diff, channel)
            # verify that no channel has been added by mistake
            for bundle in filter(lambda b: b.id not in diff.keys(), self.bundle_channels):
                assert channel not in bundle.bundled_channels
            # remove the channel from the first bundle

            # Test with the second diff (removing a channel to one bundle)
            post_params = {"action": "add-channel-to-bundles", "diff": json.dumps(diff2)}
            r = self.testApp.post('/channel/%d' % channel.id, params=post_params, status=303)
            assert r.body is not None
            # verify that it has been removed
            assert channel not in self.bundle_channels[0].bundled_channels
            diff.pop(self.bundle_channels[0].id)
            # verify that no channel has been removed by mistake
            verify_diff(diff, channel)


class TestPermissionsGet(ChannelTestCase):
    def runTest(self):
        """ Verify the access rights for the DetailPage """
        plugin_channel = self.plugin_channels[0]
        bundle_channel = self.bundle_channels[0]

        for channel in [plugin_channel, bundle_channel]:
            self.ictv_app.test_user = {"email": self.user_nothing_email}
            self.testApp.get('/channel/%d' % channel.id, status=403)

            if type(channel) is PluginChannel:
                self.ictv_app.test_user = {"email": self.user_contributor_email}
                self.testApp.get('/channel/%d' % channel.id, status=200)

                self.ictv_app.test_user = {"email": self.user_channel_admin_email}
                self.testApp.get('/channel/%d' % channel.id, status=200)

            self.ictv_app.test_user = {"email": self.user_screen_owner_email}
            self.testApp.get('/channel/%d' % channel.id, status=200)

            self.ictv_app.test_user = {"email": self.user_administrator_email}
            self.testApp.get('/channel/%d' % channel.id, status=200)

            self.ictv_app.test_user = {"email": self.user_super_administrator_email}
            self.testApp.get('/channel/%d' % channel.id, status=200)

            # now test that a screen owner cannot access to a private channel's details
            channel.subscription_right = "private"
            self.ictv_app.test_user = {"email": self.user_screen_owner_email}
            self.testApp.get('/channel/%d' % channel.id, status=403)

            # test that the super_admin, admin, contributor and administrator can access to the page

            self.ictv_app.test_user = {"email": self.user_administrator_email}
            self.testApp.get('/channel/%d' % channel.id, status=200)

            self.ictv_app.test_user = {"email": self.user_super_administrator_email}
            self.testApp.get('/channel/%d' % channel.id, status=200)

            if type(channel) is PluginChannel:
                self.ictv_app.test_user = {"email": self.user_contributor_email}
                self.testApp.get('/channel/%d' % channel.id, status=200)

                self.ictv_app.test_user = {"email": self.user_channel_admin_email}
                self.testApp.get('/channel/%d' % channel.id, status=200)

                # test that the contributor and administrator of another channel cannot have access

                self.ictv_app.test_user = {"email": self.user_contributor_of_other_channel_email}
                self.testApp.get('/channel/%d' % channel.id, status=403)

                self.ictv_app.test_user = {"email": self.user_administrator_of_other_channel_email}
                self.testApp.get('/channel/%d' % channel.id, status=403)

            # now test that a screen owner cannot access to a restricted channel's details without being authorized
            channel.subscription_right = "restricted"
            self.ictv_app.test_user = {"email": self.user_screen_owner_email}
            r = self.testApp.get('/channel/%d' % channel.id, status=403)

            # now test that a screen owner can access to a restricted channel's details after being authorized
            channel.subscription_right = "restricted"
            screen_owner = User.selectBy(email=self.user_screen_owner_email).getOne()
            channel.safe_add_user(screen_owner)
            assert channel in Channel.get_visible_channels_of(screen_owner)
            self.ictv_app.test_user = {"email": self.user_screen_owner_email}
            r = self.testApp.get('/channel/%d' % channel.id, status=200)


class TestBundleCycle(ChannelTestCase):
    def runTest(self):
        """ Tests that we cannot add a direct or indirect cycle of bundles """
        diff = {self.bundle_channels[0].id: True}
        post_params = {"action": "add-channel-to-bundles", "diff": json.dumps(diff)}

        # Try to have a direct cycling bundle
        r = self.testApp.post('/channel/%d' % self.bundle_channels[0].id, params=post_params, status=303)
        assert r.body is not None
        # Verify that nothing has happened
        for bundle in self.bundle_channels:
            assert bundle.bundled_channels.count() == 0

        # Try to have an indirect cycling bundle
        # First let's add the second bundle to the first one
        r = self.testApp.post('/channel/%d' % self.bundle_channels[1].id, params=post_params, status=303)

        # Then let's add the third bundle to the second one
        post_params["diff"] = json.dumps({self.bundle_channels[1].id: True})
        r = self.testApp.post('/channel/%d' % self.bundle_channels[2].id, params=post_params, status=303)

        # Now, let's try to create a cycle by adding the first bundle to the third one
        post_params["diff"] = json.dumps({self.bundle_channels[2].id: True})
        r = self.testApp.post('/channel/%d' % self.bundle_channels[0].id, params=post_params, status=303)

        # The third bundle must be empty
        assert len(list(self.bundle_channels[2].bundled_channels)) == 0

        assert list(self.bundle_channels[0].bundled_channels) == [self.bundle_channels[1]]
        assert list(self.bundle_channels[1].bundled_channels) == [self.bundle_channels[2]]


class TestForceUpdateChannelPage(ChannelTestCase):
    def runTest(self):
        """ Tests that ForceUpdateChannelPage behaves correctly """
        r = self.testApp.get('/channel/%d/force_update' % self.plugin_channels[-1].id, status=303)
        assert r.body is not None


class TestRequestPage(ChannelTestCase):
    # TODO
    pass


class TestResetConfig(ChannelTestCase):
    def runTest(self):
        """ Tests that the config reset works correctly """

        channel = self.plugin_channels[-1]
        config = {
            "string_param": "test",
            "int_param": -1,
            "float_param": 0.5
        }

        def reset_all():
            channel.plugin_config = config
            channel.sync()
            channel.expire()
            # first try to reset every parameter"
            post_params = {"action": "reset-config", "all": "true"}
            r = self.testApp.post('/channels/%d' % channel.id, params=post_params, status=303)
            assert r.body is not None
            assert channel.plugin_config == {}

        def reset_all_forbidden():
            channel.plugin_config = config
            channel.sync()
            channel.expire()
            # first try to reset every parameter"
            post_params = {"action": "reset-config", "all": "true"}
            r = self.testApp.post('/channels/%d' % channel.id, params=post_params, status=403)
            assert r.body is not None
            assert channel.plugin_config == config

        def reset_some():
            # try to reset one of the three set parameters
            channel.plugin_config = config
            channel.sync()
            channel.expire()
            post_params = {"action": "reset-config", "all": "false", "reset-param-id": "int_param"}
            r = self.testApp.post('/channels/%d' % channel.id, params=post_params, status=303)
            assert r.body is not None
            # re-execute the query to update the state and check
            assert channel.plugin_config == {"string_param": "test", "float_param": 0.5}

            # then try to reset a parameter which is not already set
            channel.plugin_config = config
            channel.sync()
            channel.expire()
            post_params = {"action": "reset-config", "all": "false", "reset-param-id": "boolean_param"}
            r = self.testApp.post('/channels/%d' % channel.id, params=post_params, status=303)

            # finally try to reset a parameter which is has an invalid id
            channel.plugin_config = config
            channel.sync()
            channel.expire()
            post_params = {"action": "reset-config", "all": "false", "reset-param-id": "complex_param"}
            assert self.testApp.post('/channels/%d' % channel.id, params=post_params, status=303).body is not None
            assert channel.plugin_config == config

        def reset_some_forbidden():
            # try to reset one of the three set parameters
            channel.plugin_config = config
            channel.sync()
            channel.expire()
            post_params = {"action": "reset-config", "all": "false", "reset-param-id": "int_param"}
            assert self.testApp.post('/channels/%d' % channel.id, params=post_params, status=403).body is not None
            assert channel.plugin_config == config

        self.run_as([self.user_administrator_email, self.user_super_administrator_email],
                    reset_all)
        self.run_as([self.user_administrator_email, self.user_super_administrator_email], reset_some)
        self.run_as([self.user_nothing_email, self.user_contributor_email, self.user_channel_admin_email,
                     self.user_contributor_of_other_channel_email, self.user_administrator_of_other_channel_email],
                    reset_some_forbidden)
        self.run_as([self.user_nothing_email, self.user_contributor_of_other_channel_email,
                     self.user_administrator_of_other_channel_email],
                    reset_all_forbidden)


class TestResetCacheAndFilteringConfig(ChannelTestCase):
    def runTest(self):
        """ Test the reset of the cache config """
        channel = self.plugin_channels[-1]
        channel.cache_activated = not channel.plugin.cache_activated_default
        channel.cache_validity = channel.plugin.cache_validity_default + 1
        channel.keep_noncomplying_capsules = not channel.plugin.keep_noncomplying_capsules_default
        post_params = {"action": "reset-cache-config", "id": channel.id}
        r = self.testApp.post('/channels/%d' % channel.id, params=post_params, status=303)
        assert r.body is not None
        # refresh state
        channel = Channel.get(channel.id)
        assert channel.cache_activated == channel.plugin.cache_activated_default
        assert channel.cache_validity == channel.plugin.cache_validity_default

        post_params = {"action": "reset-filtering-config", "id": channel.id}
        assert self.testApp.post('/channels/%d' % channel.id, params=post_params, status=303).body is not None
        assert channel.keep_noncomplying_capsules == channel.plugin.keep_noncomplying_capsules_default

        def reset_cache_and_filtering_config_forbidden():
            """ Checks that the non-super_admin users cannot reset the cache and filtering configs """
            post_params = {"action": "reset-cache-config", "id": channel.id}
            assert self.testApp.post('/channels/%d' % channel.id, params=post_params, status=403).body is not None
            post_params = {"action": "reset-filtering-config", "id": channel.id}
            assert self.testApp.post('/channels/%d' % channel.id, params=post_params, status=403).body is not None

        self.run_as([self.user_nothing_email, self.user_contributor_email, self.user_channel_admin_email,
                     self.user_administrator_email, self.user_contributor_of_other_channel_email,
                     self.user_administrator_of_other_channel_email], reset_cache_and_filtering_config_forbidden)


class TestChannelPageSimpleGet(ChannelTestCase):
    def runTest(self):
        """ Test get on the page and check that only the authorized users can access the page """
        channel = self.plugin_channels[-1]
        for user in [self.user_contributor_email, self.user_channel_admin_email, self.user_administrator_email,
                     self.user_super_administrator_email]:
            self.ictv_app.test_user = {"email": user}
            assert self.testApp.get('/channels/%d' % channel.id, status=200).body is not None
        for user in [self.user_nothing_email, self.user_contributor_of_other_channel_email,
                     self.user_administrator_of_other_channel_email]:
            self.ictv_app.test_user = {"email": user}
            assert self.testApp.get('/channels/%d' % channel.id, status=403).body is not None


def verify_diff(diff, channel):
    for (bundle_id, subscribed) in diff.items():
        if subscribed:
            assert channel in ChannelBundle.get(bundle_id).bundled_channels
        else:
            assert channel not in ChannelBundle.get(bundle_id).bundled_channels
