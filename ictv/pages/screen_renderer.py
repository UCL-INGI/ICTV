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

import logging
import random
from datetime import datetime

import web
from sqlobject import SQLObjectNotFound

from ictv.models.screen import Screen
from ictv.pages.utils import ICTVPage

screens_logger = logging.getLogger('screens')


class ScreenRenderer(ICTVPage):
    def GET(self, screen_id, secret):
        """ Render the channels of this screen. """
        try:
            screen = Screen.get(screen_id)
        except SQLObjectNotFound:
            raise web.notfound()
        if screen.secret != secret:
            raise web.forbidden()
        if web.ctx.env.get('REMOTE_ADDR') is None:
            pass
        else:
            screens_logger.info("Request to the screen " + str(screen_id) + " has been done from:" + web.ctx.env.get('REMOTE_ADDR'))
        if web.ctx.env.get('HTTP_USER_AGENT') == 'cache_daemon.py':
            screen.last_ip = web.ctx.ip
            screen.last_access = datetime.now()
        return render_screen(screen, self.app)


def render_screen(screen, app):
    try:
        screen_capsules = screen.get_channels_content(app)
        return app.ictv_renderer.render_screen(screen_capsules, show_number=screen.show_slide_number)
    except Exception:
        screens_logger.error('An Exception occured while rendering screen %s (%d)', screen.name, screen.id, exc_info=True)
        raise
