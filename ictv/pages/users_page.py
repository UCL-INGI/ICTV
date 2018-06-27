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

import re

import web
from sqlobject import SQLObjectNotFound
from sqlobject.dberrors import DuplicateEntryError

from ictv.models.role import UserPermissions
from ictv.models.user import User
from ictv.app import sidebar
from ictv.common.feedbacks import add_feedback, ImmediateFeedback, store_form
from ictv.pages.utils import ICTVAuthPage, PermissionGate


class UserDetailPage(ICTVAuthPage):
    def GET(self, id):
        try:
            id = int(id)
            u = User.get(id)
            if id != self.session['user']['id'] and UserPermissions.administrator not in User.get(self.session['user']['id']).highest_permission_level:
                raise web.forbidden()
            return self.render_page(u)
        except (SQLObjectNotFound, ValueError):
            raise web.seeother('/users')

    @sidebar
    def render_page(self, user):
        return self.renderer.user(user=user)


class UsersPage(ICTVAuthPage):
    pattern = re.compile(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(\.[a-zA-Z0-9-.]+$)?)")

    @PermissionGate.administrator
    def GET(self):
        return self.render_page()

    @PermissionGate.administrator
    def POST(self):
        """ Handles user creation, editing and deletion. """
        form = web.input()
        super_admin = form.get('super_admin', False) == 'on'
        admin = form.get('admin', False) == 'on'
        if super_admin:
            admin = False
        current_user = User.get(self.session['user']['id'])
        try:
            if form.action == 'create':
                username = form.username.strip()
                fullname = form.fullname.strip()
                form.email = form.email.strip()
                email = None if len(form.email) == 0 or not self.pattern.match(form.email) else form.email

                if email is None and len(form.email) != 0:
                    raise ImmediateFeedback(form.action, 'invalid_email')

                if not username:
                    username = None
                elif len(username) < 3:
                    raise ImmediateFeedback(form.action, 'invalid_username')

                try:
                    User(username=username, fullname=fullname, email=email, super_admin=super_admin, disabled=False)
                except DuplicateEntryError:
                    u = User.selectBy(email=form.email).getOne(None)
                    if u is not None:
                        raise ImmediateFeedback(form.action, 'email_already_exists')
                    u = User.selectBy(username=username).getOne(None)
                    if u is not None:
                        raise ImmediateFeedback(form.action, 'username_already_exists')
            elif form.action == 'edit':
                try:
                    form.id = int(form.id)
                    u = User.get(form.id)
                    form.email = form.email.strip()
                    email = None if len(form.email) == 0 or not self.pattern.match(form.email) else form.email
                    form.username = u.username
                    form.fullname = u.fullname

                    if email is None and len(form.email) != 0:
                        raise ImmediateFeedback(form.action, 'invalid_email')

                    if email:
                        try:
                            u.email = email
                        except DuplicateEntryError:
                            raise ImmediateFeedback(form.action, 'email_already_exists')
                    form.email = u.email

                    if not current_user.super_admin:
                        if u.super_admin:
                            raise web.forbidden()
                    else:
                        if self.session['user']['id'] != form.id:
                            u.set(super_admin=super_admin, admin=admin)
                except (SQLObjectNotFound, ValueError):
                    raise ImmediateFeedback(form.action, 'invalid_id')
            elif form.action == 'toggle-activation':
                if not current_user.super_admin:
                    raise web.forbidden()
                try:
                    form.id = int(form.id)
                    u = User.get(form.id)
                    form.email = u.email
                    u.disabled = not u.disabled
                    add_feedback(form.action, 'activated' if not u.disabled else 'deactivated')
                except (SQLObjectNotFound, ValueError):
                    raise ImmediateFeedback(form.action, 'invalid_id')
            add_feedback(form.action, 'ok')
        except ImmediateFeedback:
            pass
        store_form(form)
        raise web.seeother('/users')

    @sidebar
    def render_page(self):
        current_user = User.get(self.session['user']['id'])
        return self.renderer.users(users=User.select(), current_user=current_user, show_reset_button='local' in self.config['authentication'])
