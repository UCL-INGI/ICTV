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


class ScreenSubscriptionsTestCase(FakePluginTestCase):
    n_elements = 5  # must be >= 3
    plugin_channel_name = "test_channel"
    bundle_channel_name = "test_bundle"
    plugin_name = "test_plugin"
    user_nothing_email = "nothing@email.mail"
    user_screen_owner_email = "screenowner@email.mail"
    user_other_screen_owner_email = "otherscreenowner@email.mail"
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
        self.screen = Screen(name="mytestscreen", building=building, secret="secret")
        self.other_screen = Screen(name="myothertestscreen", building=building, secret="secret")
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
        self.screen.safe_add_user(screen_owner)
        other_screen_owner = User(email=self.user_other_screen_owner_email, disabled=False)
        self.other_screen.safe_add_user(other_screen_owner)
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


class TestSubmitEmptyDiff(ScreenSubscriptionsTestCase):
    def runTest(self):
        """ Submits an empty diff to the page and ensures that nothing has changed """
        screen = self.screen
        before = {repr(s) for s in screen.subscribed_channels}
        post_params = {"diff": json.dumps({})}
        assert self.testApp.post("/screens/%s/subscriptions" % screen.id, post_params, status=303).body is not None
        after = {repr(s) for s in Screen.get(screen.id).subscribed_channels}
        assert after == before


# TODO: tester de s'abonner à des channel restricted
class TestSubscribeAndUnSubscribeToSomeChannels(ScreenSubscriptionsTestCase):
    def runTest(self):
        """ Subscribes and unsubscribes a screen from some channels and checks that it has been successfully
            subscribed/unsubscribed """
        screen = self.screen
        # subscribe to some plugin_channels
        diff = {self.plugin_channels[i].id: True for i in range(len(self.plugin_channels)) if i % 2 == 0}
        # also subscribe to a bundle
        diff[self.bundle_channels[1].id] = True
        post_params = {"diff": json.dumps(diff)}
        assert self.testApp.post("/screens/%s/subscriptions" % screen.id, post_params, status=303).body is not None
        verify_diff(diff, screen)
        # Now, remove one channel and the added bundle, then, subscribe to another new channel
        diff = {self.plugin_channels[0].id: False, self.bundle_channels[1].id: False, self.plugin_channels[1].id: True}
        post_params = {"diff": json.dumps(diff)}
        assert self.testApp.post("/screens/%s/subscriptions" % screen.id, post_params, status=303).body is not None
        verify_diff(diff, screen)
        # Now, re-subscribe to and un-subscribe from the first plugin_channel and bundle_channel when they are
        # restricted channels and we are in its authorized subscribers
        channel = self.plugin_channels[0]
        bundle = self.bundle_channels[0]
        channel.subscription_right = "restricted"
        bundle.subscription_right = "restricted"
        user = User.selectBy(email=self.user_screen_owner_email).getOne()
        self.ictv_app.test_user = {"email": user.email}
        channel.safe_add_user(user)
        bundle.safe_add_user(user)
        diff = {channel.id: True, bundle.id: True}
        post_params = {"diff": json.dumps(diff)}
        assert self.testApp.post("/screens/%s/subscriptions" % screen.id, post_params, status=303).body is not None
        verify_diff(diff, screen)
        diff = {channel.id: False, bundle.id: False}
        post_params = {"diff": json.dumps(diff)}
        assert self.testApp.post("/screens/%s/subscriptions" % screen.id, post_params, status=303).body is not None


class TestSubscribeToWrongChannel(ScreenSubscriptionsTestCase):
    def runTest(self):
        """ Tries to subscribe to a PluginChannel with a non-activated plugin and to restricted/private channel
            without being in the authorized subscribers and verifies that the subscription has not been done"""
        screen = self.screen
        plugin_channel = self.plugin_channels[0]
        plugin_channel.plugin.activated = "no"
        diff = {plugin_channel.id: True}
        post_params = {"diff": json.dumps(diff)}
        before = {repr(s) for s in screen.subscribed_channels}
        assert self.testApp.post("/screens/%s/subscriptions" % screen.id, post_params, status=303).body is not None
        after = {repr(s) for s in Screen.get(screen.id).subscribed_channels}
        assert after == before

        # Now try to subscribe to restricted channel without having the right to do this
        plugin_channel.plugin.activated = "yes"

        def try_sub_fail():
            for right in "restricted", "private":
                plugin_channel.subscription_right = right
                diff = {plugin_channel.id: True}
                post_params = {"diff": json.dumps(diff)}
                before = {repr(s) for s in screen.subscribed_channels}
                assert self.testApp.post("/screens/%s/subscriptions" % screen.id, post_params, status=403).body is not None
                after = {repr(s) for s in Screen.get(screen.id).subscribed_channels}
                assert after == before
        # Nobody (excepted the admin and super_admin) can succeed to do this, even the owner of the screen
        self.run_as([self.user_nothing_email, self.user_contributor_email, self.user_channel_admin_email,
                     self.user_contributor_of_other_channel_email, self.user_administrator_of_other_channel_email,
                     self.user_screen_owner_email, self.user_other_screen_owner_email], try_sub_fail)


class TestSubscribeToNonExistingChannel(ScreenSubscriptionsTestCase):
    def runTest(self):
        """ Tries to subscribe the screen to a non-existing channel and verifies that it is forbidden by the app and
            nothing has been done """
        screen = self.screen
        plugin_channel = self.plugin_channels[0]
        plugin_channel.plugin.activated = "no"
        diff = {plugin_channel.id: True, -1: True}
        post_params = {"diff": json.dumps(diff)}
        before = {repr(s) for s in screen.subscribed_channels}
        assert self.testApp.post("/screens/%s/subscriptions" % screen.id, post_params, status=403).body is not None
        after = {repr(s) for s in Screen.get(screen.id).subscribed_channels}
        assert after == before


class TestAccessPermissions(ScreenSubscriptionsTestCase):
    def runTest(self):
        """ Verifies that only the owner of the screen and an administrator can access tp the page of the screen """
        screen = self.screen

        def try_post(status):
            def f():
                post_params = {"diff": json.dumps({})}
                assert self.testApp.post("/screens/%s/subscriptions" % screen.id, post_params,
                                         status=status).body is not None
            return f

        def try_get(status):
            def f():
                assert self.testApp.get("/screens/%s/subscriptions" % screen.id,
                                         status=status).body is not None
            return f
        self.run_as([self.user_nothing_email, self.user_contributor_email, self.user_channel_admin_email,
                     self.user_other_screen_owner_email], try_get(403))
        self.run_as([self.user_nothing_email, self.user_contributor_email, self.user_channel_admin_email,
                     self.user_other_screen_owner_email], try_post(403))

        self.run_as([self.user_screen_owner_email, self.user_administrator_email, self.user_super_administrator_email],
                    try_get(200))
        self.run_as([self.user_screen_owner_email, self.user_administrator_email, self.user_super_administrator_email],
                    try_post(303))


class TestAccessNonExistingScreen(ScreenSubscriptionsTestCase):
    def runTest(self):
        """ Tries to access the page for non existing screens and checks that it is correctly handled (404) """
        assert self.testApp.post("/screens/%s/subscriptions" % 100000, {"diff": "{}"}, status=404)
        assert self.testApp.get("/screens/%s/subscriptions" % 100000, status=404)


def verify_diff(diff, screen):
    """ Verifies that all the channels in the diff have been correctly added to/removed from the bundle"""
    for (channel_id, subscribed) in diff.items():
        if subscribed:
            assert Channel.get(channel_id) in screen.subscribed_channels
        else:
            assert Channel.get(channel_id) not in screen.subscribed_channels
