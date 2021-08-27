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

import smtplib

from sqlobject import SQLObjectNotFound
from sqlobject.dberrors import DuplicateEntryError

import logging

from ictv.models.channel import Channel, PluginChannel
from ictv.common.feedbacks import add_feedback, ImmediateFeedback, store_form
from ictv.models.screen import Screen
from ictv.models.building import Building
from ictv.models.user import User
from ictv.app import sidebar
from ictv.pages.utils import PermissionGate, ICTVAuthPage

import ictv.flask.response as resp
from flask_mail import Mail, Message


logger = logging.getLogger('pages')


class EmailPage(ICTVAuthPage):
    @sidebar
    def get(self):
        u = User.get(self.session['user']['id'])
        channels = Channel.select()
        return self.renderer.emails(user=u, channels=channels)

    def post(self):
        form = self.form
        subject = form['subject']
        email_body = form['body']
        to = form['to']
        receivers = []
        if to=="admins":
            receivers =[u for u in User.selectBy(admin=True, disabled=False)]
        elif to=="supadmins":
            receivers=[u for u in User.selectBy(super_admin=True).distinct()]
        elif to == 'contrib':
            id_channel=form['select_channel']
            c = PluginChannel.get(id_channel)
            receivers = [u for u in c.get_contribs()]
        elif to=="channel_editor_users":
            pc = PluginChannel.select()
            for elem in pc:
                if elem.plugin.name=="editor":
                    l1=[u1 for u1 in elem.get_admins()]
                    l2=[u2 for u2 in elem.get_contribs()]
                    list_users = l1+l2
                    receivers=[u for u in list_users]
        else:
          for s in Screen.select():
              receivers=[u for u in s.owners]
        try:
            mail = Mail(self.app)
            msg = Message(recipients=[u.email for u in receivers],
                subject=subject,
                body=email_body,
                extra_headers={'Content-Type': 'text/html;charset=utf-8'}
            )
            mail.send(msg)
        except smtplib.SMTPException:
            logger.error('An error occured when sending email ', exc_info=True)
        resp.seeother("/")
