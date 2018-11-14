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

import hashlib
from logging import getLogger
import datetime
import web
from ictv.common import utils

from ictv.models.user import User
from ictv.common.feedbacks import ImmediateFeedback, add_feedback, store_form
from ictv.pages.utils import ICTVPage, PermissionGate, ICTVAuthPage

logger = getLogger('local_login')


class LoginPage(ICTVPage):
    def GET(self):
        if 'user' in self.session:
            raise web.seeother('/')
        return self.render_page()

    def POST(self):
        if 'user' in self.session:
            raise web.seeother('/')
        form = web.input()
        try:
            user = User.selectBy(email=form.email, password=hash_password(form.password)).getOne(None)
            if not user:
                raise ImmediateFeedback('login', 'invalid_credentials')
            user.last_connection = datetime.datetime.now()
            self.session['user'] = user.to_dictionary(['id', 'fullname', 'username', 'email'])
        except ImmediateFeedback:
            store_form(form)
            return self.render_page()

        return web.seeother('/')

    def render_page(self):
        return self.standalone_renderer.login(self.config['authentication'], self.config['saml2']['display_name'])


class GetResetLink(ICTVAuthPage):
    def GET(self):  # TODO: Redirect if not using local authentication
        user = User.get(self.session['user']['id'])
        user.reset_secret = utils.generate_secret()
        logger.info('User %s requested a new password reset link', user.log_name)
        raise web.seeother(self.url_for(ResetPage, user.reset_secret))


class ResetPage(ICTVPage):
    def GET(self, secret):
        user = User.selectBy(reset_secret=secret).getOne(None)
        if not user:
            logger.warning('IP %s tried to access password reset page with invalid secret', web.ctx.ip)
            if 'user' in self.session:
                logger.warning('User %s is currently connected', User.get(self.session['user']['id']).log_name)
            raise web.redirect('/')
        return self.standalone_renderer.reset(user=user)

    def POST(self, secret):
        user = User.selectBy(reset_secret=secret).getOne(None)
        form = web.input()
        try:
            if form.get('password1') != form.get('password2'):
                raise ImmediateFeedback('reset', 'passwords_do_not_match')
            password = form.password1.strip()
            if len(password) <= 3:
                raise ImmediateFeedback('reset', 'password_insufficient')
            user.password = hash_password(form.password1)
            user.reset_secret = utils.generate_secret()  # Make this token one time use
            logger.info('User %s has reset its password from IP %s', user.log_name, web.ctx.ip)
        except ImmediateFeedback:
            return self.standalone_renderer.reset(user=user)
        add_feedback('reset', 'ok')
        raise web.seeother(self.url_for(LoginPage))


def hash_password(password):
    return hashlib.sha512(password.encode('utf-8')).hexdigest()
