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

import web
from sqlobject import SQLObjectNotFound
from sqlobject.dberrors import DuplicateEntryError

import logging

from ictv.common.feedbacks import add_feedback, ImmediateFeedback, store_form
from ictv.models.screen import Screen
from ictv.models.building import Building
from ictv.models.user import User
from ictv.app import sidebar
from ictv.pages.utils import PermissionGate, ICTVAuthPage

logger = logging.getLogger('pages')


class BuildingsPage(ICTVAuthPage):

    @sidebar
    def render_page(self):
        current_user = User.get(self.session['user']['id'])
        return self.renderer.buildings(buildings=Building.select(), current_user=current_user)

    @PermissionGate.administrator
    def GET(self):
        return self.render_page()

    @PermissionGate.administrator
    def POST(self):
        """ Handles building creation, editing and deletion. """
        current_user = User.get(self.session['user']['id'])
        form = web.input()
        try:
            if form.action == 'delete':
                if not current_user.super_admin:
                    raise web.forbidden()
                try:
                    id = int(form.id)
                except ValueError:
                    logger.warning('user %s tries to delete a building with invalid id (id = %s)', current_user.log_name, str(form.id))
                    raise ImmediateFeedback(form.action, 'invalid_id')
                try:
                    screens = Screen.selectBy(building=id)
                    if screens.count() > 0:
                        logger.warning('user %s tries to delete a building with screens still present in this building (id = %s)', current_user.log_name, str(id))
                        raise ImmediateFeedback(form.action, 'delete_building_but_screens_present', [(s.id, s.name) for s in screens])
                    Building.delete(id)
                    logger.info("building %s has been deleted by user %s", str(id), current_user.log_name)
                except SQLObjectNotFound as e:
                    logger.warning("user %s tries to delete a building with an id that doesn't exist (id = %s)", current_user.log_name, str(form.id))
                    raise ImmediateFeedback(form.action, 'no_id_matching')
            else:
                name = form.name.strip()
                if name == "":
                    raise ImmediateFeedback(form.action, 'empty_name')
                if len(form.name) > Building.sqlmeta.columns['name'].length:
                    raise ImmediateFeedback(form.action, 'too_long_name')
                if form.action == 'create':
                    try:
                        Building(name=form.name, city=form.city)
                        logger.info("building %s has been created by user %s", form.name, current_user.log_name)
                    except DuplicateEntryError:
                        logger.warning("user %s tries to create a building with a name that already exists (name = %s)", current_user.log_name, form.name)
                        raise ImmediateFeedback(form.action, 'name_already_exists')
                elif form.action == 'edit':
                    try:
                        id = int(form.id)
                    except ValueError:
                        logger.warning('user %s tries to edit a building with invalid id (id = %s)', current_user.log_name, str(form.id))
                        raise ImmediateFeedback(form.action, 'invalid_building_id')
                    try:
                        building = Building.get(id)
                    except SQLObjectNotFound as e:
                        logger.warning("user %s tries to edit a building with an id that doesn't exist (id = %s)", current_user.log_name, str(form.id))
                        raise ImmediateFeedback(form.action, 'no_id_matching')
                    try:
                        building.name = form.name
                        building.city = form.city
                    except DuplicateEntryError:
                        logger.warning("user %s tries to edit the building %s with a name already present (name = %d)", current_user.log_name, str(form.id), form.name)
                        raise ImmediateFeedback(form.action, 'name_already_exists')

                    logger.info("building %s has been edited by user %s (new name = %s)", str(id), current_user.log_name, form.name)
            add_feedback(form.action, 'ok')
        except ImmediateFeedback:
            store_form(form)
        return self.render_page()
