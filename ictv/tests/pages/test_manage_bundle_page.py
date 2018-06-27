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
from ictv.tests import FakePluginTestCase


class ManageBundleTestCase(FakePluginTestCase):
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

    def run_as(self, users, f):
        """ Runs f as each user in the users list """
        for user in users:
            self.ictv_app.test_user = {"email": user}
            f()

    def setUp(self, fake_plugin_middleware=lambda: None, ictv_middleware=lambda: None):
        super().setUp(fake_plugin_middleware, ictv_middleware)
        building = Building(name="mytestbuilding")
        screen = Screen(name="mytestscreen", building=building, secret="secret")
        self.plugins = [Plugin(name="%s%d" % (self.plugin_name, i), activated="yes") for i in
                        range(self.n_elements - 1)]
        self.plugins.append(Plugin.selectBy(name="fake_plugin").getOne())

        self.plugin_channels = [PluginChannel(name="%s%d" % (self.plugin_channel_name, i), plugin=self.plugins[i],
                                              subscription_right="public") for i in range(self.n_elements)]
        self.bundle_channels = [ChannelBundle(name="%s%d" % (self.bundle_channel_name, i), subscription_right="public")
                                for i in range(self.n_elements)]
        other_channel = PluginChannel(name="other_channel", plugin=self.plugins[0], subscription_right="public")
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
        [plugin_channel.give_permission_to_user(channel_admin, UserPermissions.channel_administrator) for plugin_channel
         in self.plugin_channels]

    def tearDown(self):
        [plugin_channel.destroySelf() for plugin_channel in self.plugin_channels]
        [bundle_channel.destroySelf() for bundle_channel in self.bundle_channels]
        for email in [self.user_nothing_email, self.user_contributor_email, self.user_channel_admin_email,
                      self.user_administrator_email, self.user_super_administrator_email]:
            User.deleteBy(email=email)
        Plugin.deleteBy(name=self.plugin_name)
        super().tearDown()


class TestSubmitEmptyDiff(ManageBundleTestCase):
    def runTest(self):
        """ Submits an empty diff to the page and ensures that nothing has changed """
        bundle = self.bundle_channels[0]
        before = {repr(b) for b in ChannelBundle.select()}
        post_params = {"diff": json.dumps({})}
        assert self.testApp.post("/channels/%d/manage_bundle" % bundle.id, post_params, status=303).body is not None
        after = {repr(b) for b in ChannelBundle.select()}
        assert after == before


class TestAddAndRemoveSomeChannels(ManageBundleTestCase):
    def runTest(self):
        """ Adds and removes some channel to the bundle and checks that it has been successfully added/removed """
        bundle = self.bundle_channels[0]
        # subscribe to some plugin_channels
        diff = {self.plugin_channels[i].id: True for i in range(len(self.plugin_channels)) if i % 2 == 0}
        # also subscribe to a bundle
        diff[self.bundle_channels[1].id] = True
        post_params = {"diff": json.dumps(diff)}
        assert self.testApp.post("/channels/%d/manage_bundle" % bundle.id, post_params, status=303).body is not None
        verify_diff(diff, bundle)
        # Now, remove one channel, and the added bundle, then, subscribe to another new channel
        diff = {self.plugin_channels[0].id: False, self.bundle_channels[1].id: False, self.plugin_channels[1].id: True}
        post_params = {"diff": json.dumps(diff)}
        assert self.testApp.post("/channels/%d/manage_bundle" % bundle.id, post_params, status=303).body is not None
        verify_diff(diff, bundle)


class TestAddWringChannels(ManageBundleTestCase):
    def runTest(self):
        """ Tries to add a bundle to itself and plugin_channels with disabled plugins to the bundle and checks that
            nothing has been added """
        bundle = self.bundle_channels[0]
        before = {dump_bundle(b) for b in ChannelBundle.select()}
        diff = {bundle.id: True}
        post_params = {"diff": json.dumps(diff)}
        assert self.testApp.post("/channels/%d/manage_bundle" % bundle.id, post_params, status=303).body is not None
        after = {dump_bundle(b) for b in ChannelBundle.select()}
        assert after == before
        channel = self.plugin_channels[0]
        channel.plugin.activated = "no"
        diff = {channel.id: True}
        post_params = {"diff": json.dumps(diff)}
        assert self.testApp.post("/channels/%d/manage_bundle" % bundle.id, post_params, status=303).body is not None
        assert after == before


class TestAddNonExistingChannel(ManageBundleTestCase):
    def runTest(self):
        """ Tries to add to the bundle a channel that does not exist and
            verifies that it is handled correctly for the user """
        bundle = self.bundle_channels[0]
        before = {dump_bundle(b) for b in ChannelBundle.select()}
        diff = {-1: True}
        post_params = {"diff": json.dumps(diff)}
        assert self.testApp.post("/channels/%d/manage_bundle" % bundle.id, post_params, status=403).body is not None
        after = {dump_bundle(b) for b in ChannelBundle.select()}
        assert after == before


class TestCreateBundleCycles(ManageBundleTestCase):
    def runTest(self):
        """ Tries to create a cycle of bundles and checks that it is handled properly (no bundle created) """
        # Try to have an indirect cycling bundle
        # First let's add the second bundle to the first one
        diff = {self.bundle_channels[1].id: True}
        post_params = {"diff": json.dumps(diff)}
        assert self.testApp.post('/channels/%d/manage_bundle' % self.bundle_channels[0].id, params=post_params,
                                 status=303).body is not None

        # Then let's add the third bundle to the second one
        post_params["diff"] = json.dumps({self.bundle_channels[2].id: True})
        assert self.testApp.post('/channels/%d/manage_bundle' % self.bundle_channels[1].id, params=post_params,
                                 status=303).body is not None

        # Now, let's try to create a cycle by adding the first bundle to the third one
        post_params["diff"] = json.dumps({self.bundle_channels[0].id: True})
        assert self.testApp.post('/channels/%d/manage_bundle' % self.bundle_channels[2].id, params=post_params,
                                 status=303).body is not None

        # The third bundle must be empty
        assert len(list(self.bundle_channels[2].bundled_channels)) == 0

        assert list(self.bundle_channels[0].bundled_channels) == [self.bundle_channels[1]]
        assert list(self.bundle_channels[1].bundled_channels) == [self.bundle_channels[2]]


class TestAccessForNonExistingBundle(ManageBundleTestCase):
    def runTest(self):
        """ Tries to access to the page for a non existing bundle, and checks that it does not throw a 500 """
        diff = json.dumps({})
        assert self.testApp.post('/channels/%d/manage_bundle' % 100000, params={"diff": diff},
                                 status=404).body is not None
        assert self.testApp.get('/channels/%d/manage_bundle' % 100000, status=404).body is not None


class TestPermissions(ManageBundleTestCase):
    def runTest(self):
        """ Verifies that only administrators can access to this page """
        post_params = {"diff": json.dumps({})}
        bundle = self.bundle_channels[0]

        def try_post(status):
            def f():
                assert self.testApp.post("/channels/%d/manage_bundle" % bundle.id, post_params,
                                         status=status).body is not None
            return f

        def try_get(status):
            def f():
                assert self.testApp.get("/channels/%d/manage_bundle" % bundle.id, status=status).body is not None
            return f

        # Non administrator users should not be allowed to access the page
        self.run_as([self.user_nothing_email, self.user_contributor_email, self.user_channel_admin_email,
                     self.user_contributor_of_other_channel_email, self.user_administrator_of_other_channel_email],
                    try_post(403))
        self.run_as([self.user_nothing_email, self.user_contributor_email, self.user_channel_admin_email,
                     self.user_contributor_of_other_channel_email, self.user_administrator_of_other_channel_email],
                    try_get(403))

        # Administrator users should be allowed to access the page
        self.run_as([self.user_administrator_email, self.user_super_administrator_email], try_post(303))
        self.run_as([self.user_administrator_email, self.user_super_administrator_email], try_get(200))


def verify_diff(diff, bundle):
    """ Verifies that all the channels in the diff have been correctly added to/removed from the bundle"""
    for (channel_id, subscribed) in diff.items():
        if subscribed:
            assert Channel.get(channel_id) in bundle.bundled_channels
        else:
            assert Channel.get(channel_id) not in bundle.bundled_channels


def dump_bundle(bundle):
    return str(repr(bundle) + str({repr(bc) for bc in bundle.bundled_channels}))
