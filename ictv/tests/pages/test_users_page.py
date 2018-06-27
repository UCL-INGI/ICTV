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

from ictv.models.building import Building
from ictv.models.channel import PluginChannel, ChannelBundle
from ictv.models.plugin import Plugin
from ictv.models.role import UserPermissions
from ictv.models.screen import Screen
from ictv.models.user import User
from ictv.tests import FakePluginTestCase


class UsersPageTestCase(FakePluginTestCase):
    n_elements = 5  # must be >= 3
    plugin_channel_name = "test_channel"
    bundle_channel_name = "test_bundle"
    plugin_name = "test_plugin"
    user_nothing_email = "nothing@email.mail"
    user_nothing_username = "nothing"
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
        User(email=self.user_nothing_email, username=self.user_nothing_username, disabled=False)
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


class TestCreateUser(UsersPageTestCase):
    def runTest(self):
        username = "test_username"
        fullname = "Test FullName"
        email = "user@localhost"
        email2 = "2" + email
        post_params = {"action": "create", "admin": "", "super_admin": "", "username": username, "fullname": fullname,
                       "email": email}
        assert self.testApp.post("/users", post_params, status=303).body is not None
        u = User.selectBy(email=email).getOne(None)
        assert u is not None
        assert u.username == username
        assert u.email == email
        assert u.fullname == fullname
        for username in ["", " ", "  ", "     ", " \t "]:
            post_params = {"action": "create", "admin": "", "super_admin": "", "username": username, "fullname": "",
                           "email": email2}
            assert self.testApp.post("/users", post_params, status=303).body is not None
            u = User.selectBy(email=email2).getOne(None)
            assert u is not None
            assert u.username is None
            assert u.fullname == ""
            assert u.email == email2


class TestCreateDuplicateUser(UsersPageTestCase):
    def runTest(self):
        """ Tries to create duplicate users and checks that no duplication occurs and that it is handled properly
            for the user """
        username = "test_username"
        fullname = "Test FullName"
        # test with duplicate email
        post_params = {"action": "create", "admin": "", "super_admin": "", "username": username, "fullname": fullname,
                       "email": self.user_nothing_email}
        user_before = repr(User.selectBy(email=self.user_nothing_email).getOne(None))
        assert self.testApp.post("/users", post_params, status=303).body is not None
        u = User.selectBy(email=self.user_nothing_email).getOne(None)
        assert u is not None
        user_after = repr(u)
        assert user_after == user_before

        # test with duplicate username
        post_params = {"action": "create", "admin": "", "super_admin": "", "username": self.user_nothing_username,
                       "fullname": fullname, "email": "test_user_mail@mail.test"}
        user_before = repr(User.selectBy(username=self.user_nothing_username).getOne(None))
        assert self.testApp.post("/users", post_params, status=303).body is not None
        u = User.selectBy(username=self.user_nothing_username).getOne(None)
        assert u is not None
        user_after = repr(u)
        assert user_after == user_before


class TestInvalidUserAndEmail(UsersPageTestCase):
    def runTest(self):
        """ Tries to create duplicate users and checks that no duplication occurs and that it is handled properly
            for the user """
        username = "test_username1"
        fullname = "Test FullName"
        correct_email = "test_email@test.email"
        wrong_emails = ["wrongemail", "wrong?mail@mail.com", "vivelété@mail.com", "vivel'ete@mail.com", "@"]
        users_before = {repr(user) for user in User.select()}
        # test some wrong email addresses
        for email in wrong_emails:
            post_params = {"action": "create", "admin": "", "super_admin": "", "username": username,
                           "fullname": fullname, "email": email}
            assert self.testApp.post("/users", post_params, status=303).body is not None
            users_after = {repr(user) for user in User.select()}
            assert users_after == users_before

        # test with wrong usernames
        for username in ["a", "ab"]:
            post_params = {"action": "create", "admin": "", "super_admin": "", "username": username,
                           "fullname": fullname, "email": correct_email}
            assert self.testApp.post("/users", post_params, status=303).body is not None
            users_after = {repr(user) for user in User.select()}
            assert users_after == users_before
