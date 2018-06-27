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


def get_feedbacks():
    """ Returns feedbacks available for this request. """
    return Feedbacks(web.ctx.session.get('feedbacks', []))


def get_next_feedbacks():
    """
        Returns feedbacks available for the next request.
        This is implemented for compatibility reasons until all pages implement a Post/Redirect/Get pattern.
    """
    return Feedbacks(web.ctx.session.get('next_request_feedbacks', []))


def add_feedback(type, message, value=None):
    feedbacks = web.ctx.session.get('next_request_feedbacks', [])
    feedbacks.append({'type': type, 'message': message, 'value': value})
    web.ctx.session.next_request_feedbacks = feedbacks


def rotate_feedbacks():
    web.ctx.session.feedbacks = web.ctx.session.get('next_request_feedbacks', [])
    web.ctx.session.next_request_feedbacks = []


class Feedbacks(list):
    """
        A class that extends list from which instances can remember which feedback was checked to be in last.
        This is useful to shorten calls of feedback_value after checking for a certain feedback to be in.
    """
    def has(self, type, message):
        self._last_item_checked = (type, message)
        for t, m, in [(d['type'], d['message']) for d in self]:
            if t == type and m == message:
                return True
        return False

    def feedback_value(self, type=None, message=None):
        if type is None and message is None and self._last_item_checked:
            type, message = self._last_item_checked

        for t, m, v in [(d['type'], d['message'], d['value']) for d in self]:
            if t == type and m == message:
                return v
        return None

    def has_type(self, *types):
        for t in types:
            for f in self:
                if f['type'] == t:
                    return True
        return False


class ImmediateFeedback(Exception):
    """ Utility class to break the flow of execution and add a feedback. """
    def __init__(self, type, message, value=None):
        add_feedback(type, message, value)


def store_form(form):
    web.ctx.session.form = list(form.items())


def pop_previous_form():
    return web.Storage(web.ctx.session.pop('form', {}))

