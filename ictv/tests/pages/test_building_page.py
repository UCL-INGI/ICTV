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

from sqlobject import SQLObjectNotFound

from ictv.models.building import Building
from ictv.models.channel import PluginChannel
from ictv.models.plugin import Plugin
from ictv.models.role import UserPermissions
from ictv.models.screen import Screen
from ictv.models.user import User
from ictv.tests import ICTVTestCase


class BuildingTestCase(ICTVTestCase):
    building_name = "AlreadyThereBuilding"
    second_building_name = "AlreadyThereBuilding2"
    user_nothing_email = "nothing@email.mail"
    user_contributor_email = "contributor@email.mail"
    user_channel_admin_email = "channeladmin@email.mail"
    user_administrator_email = "administartor@email.startor"
    user_super_administrator_email = "superadministartor@email.startor"
    channel_name = "mytestchannel"

    def setUp(self):
        super().setUp()
        self.building_id = Building(name=self.building_name).id
        self.building2_id = Building(name=self.second_building_name).id
        self.channel = PluginChannel(name=self.channel_name, plugin=Plugin(name="dummy", activated="notfound"),
                                     subscription_right="public")
        User(email=self.user_nothing_email, disabled=False)
        User(email=self.user_administrator_email, disabled=False, admin=True)
        User(email=self.user_super_administrator_email, disabled=False, admin=True, super_admin=True)
        contributor = User(email=self.user_contributor_email, disabled=False)
        self.channel.give_permission_to_user(contributor)
        channel_admin = User(email=self.user_channel_admin_email, disabled=False)
        self.channel.give_permission_to_user(channel_admin, UserPermissions.channel_administrator)

    def tearDown(self):
        try:
            Building.delete(self.building_id)
            Building.delete(self.building2_id)
        except SQLObjectNotFound:
            pass
        for email in [self.user_nothing_email, self.user_contributor_email, self.user_channel_admin_email,
                      self.user_administrator_email, self.user_super_administrator_email]:
            User.deleteBy(email=email)
        self.channel.destroySelf()
        Plugin.deleteBy(name="dummy")
        super().tearDown()


class SimpleGet(BuildingTestCase):
    def runTest(self):
        """ Checks that every authorized user can get the page and the other receive a 403 error """
        for status_code, emails in [(403, [self.user_nothing_email, self.user_contributor_email,
                                    self.user_channel_admin_email]), (200, [self.user_administrator_email,
                                                                            self.user_super_administrator_email])]:
            for email in emails:
                self.ictv_app.test_user = {"email": email}
                r = self.testApp.get('/buildings', status=status_code)
                assert r.body is not None


class CreateBuildingTest(BuildingTestCase):
    new_building_name = "MyTestBuilding123"
    new_building_city = "BuildingTown"
    post_params = {"action": "create", "name": new_building_name, "city": new_building_city}

    def runTest(self):
        """ Tests that we can successfully create a building via the Building page """
        # Verify that there is no building with this name in db
        assert Building.selectBy(name=self.new_building_name).getOne(default=None) is None
        # Do the post request to create the building
        r = self.testApp.post('/buildings', params=self.post_params, status=200)
        select_result = Building.selectBy(name=self.new_building_name)
        # verify that the building has been created (exactly one), with the correct name and that there is no empty body
        assert select_result.getOne().name == self.new_building_name
        assert select_result.getOne().city == self.new_building_city
        assert r.body is not None
        Building.deleteBy(name=self.new_building_name)


class DeleteBuildingTest(BuildingTestCase):
    def runTest(self):
        """ Tests that we can successfully delete a building via the Building page """
        # Test the deletion of the building
        my_building = Building.selectBy(name=self.building_name).getOne()
        building_id = my_building.id
        post_params = {"action": "delete", "id": str(building_id)}
        # Do the request and verify that it has been deleted and that there is no empty body
        r = self.testApp.post('/buildings', params=post_params, status=200)
        assert Building.selectBy(id=building_id).getOne(default=None) is None
        assert r.body is not None


class EditBuildingTest(BuildingTestCase):
    def runTest(self):
        """ Tests that we can successfully delete a building via the Building page """
        new_name = "BuildingNewName"
        new_city = "BuildingNewCity"
        post_params = {"action": "edit", "id": str(self.building_id), "name": new_name, "city": new_city}
        # Do the request
        r = self.testApp.post('/buildings', params=post_params, status=200)
        # check that the old name is not there anymore
        assert Building.selectBy(name=self.building_name).getOne(default=None) is None
        # check that the building still has the same id but the new name
        assert Building.get(self.building_id).name == new_name
        assert Building.get(self.building_id).city == new_city
        assert r.body is not None


class CreateEditAndDeleteWithoutPermission(BuildingTestCase):
    """ Tests that a non-administrator cannot modify the buildings """

    def runTest(self):
        def try_operations():
            self.testApp.post('/buildings', params=CreateBuildingTest.post_params, status=403)
            for action in ["edit", "delete"]:
                post_params = {"action": action, id: self.building_id}
                self.testApp.post('/buildings', params=post_params, status=403)

        # try to delete, add and create for every type of user
        for email in [self.user_nothing_email, self.user_contributor_email, self.user_channel_admin_email]:
            self.ictv_app.test_user = {"email": email}
            try_operations()
        self.ictv_app.test_user = {"email": self.user_administrator_email}
        self.testApp.post('/buildings', params={"action": "delete", "id": self.building_id},
                          status=403)


class CreateDuplicateBuilding(BuildingTestCase):
    post_params = {"action": "create", "name": BuildingTestCase.building_name, "city": ""}

    def runTest(self):
        results_before = set(Building.select())
        # Create a duplicated building and verify that the error is handled properly for the user
        r = self.testApp.post('/buildings', params=self.post_params, status=200)
        results_after = set(Building.select())
        # Verify that the building table has not changed
        assert results_after == results_before
        assert r.body is not None


class EditToMakeDuplicateBuilding(BuildingTestCase):
    def runTest(self):
        """ Tests that we cannot edit by making duplicated buildings and that no error occurs """
        def f():
            post_params = {"action": "edit", "name": BuildingTestCase.building_name, "id": self.building2_id, "city": ""}
            # Edit to make a duplicated building and verify that the error is handled properly for the user
            r = self.testApp.post('/buildings', params=post_params, status=200)
            assert r.body is not None

        check_table_did_not_change(f)


class CheckOperationsWithWringIDs(BuildingTestCase):

    def runTest(self):
        """ Does operations with wrong database ID and check that the database did not change and that the error has been
         handled properly"""
        not_existing_id = -3
        not_int_id = "minusthree"
        for action in ["edit", "delete"]:
            def f():
                for current_id in [not_existing_id, not_int_id]:
                    post_params = {"action": action, "name": "placeholder", "id": current_id}
                    # Use a wrong ID and see if nothing changed and the error has been handled properly for the user
                    r = self.testApp.post('/buildings', params=post_params, status=200)
                    assert r.body is not None

            check_table_did_not_change(f)


class DeleteBuildingWithAttachedScreens(BuildingTestCase):
    def runTest(self):
        """ Checks that we cannot delete a building with screens attached to it, and checks that the
        error is correctly handler for the user """
        building_to_test = Building.get(self.building2_id)
        s = Screen(name="mytestscreen", building=building_to_test, secret="secret")

        def f():
            post_params = {"action": "delete", "id": building_to_test.id}
            # Use a wrong ID and see if nothing changed and the error has been handled properly for the user
            r = self.testApp.post('/buildings', params=post_params, status=200)
            assert r.body is not None

        check_table_did_not_change(f)
        s.destroySelf()


class CreateAndDeleteScreenWithEmptyName(BuildingTestCase):
    def runTest(self):
        """ Checks that a user cannot add a building with a name composed by only spaces and tabs"""
        for action in ["create", "edit"]:
            for name in ["", " ", "  ", "\t", " \t "]:
                post_params = {"action": action, "id": self.building_id, "name": name}
                # Use a wrong name and see if nothing changed and the error has been handled properly for the user
                r = self.testApp.post('/buildings', params=post_params, status=200)
                assert r.body is not None
                # check that the name did not change
                assert Building.get(self.building_id).name == self.building_name


def check_table_did_not_change(f):
    """ verifies that the table has not changes after executing f """
    before = set(Building.select())
    f()
    after = set(Building.select())
    assert after == before
