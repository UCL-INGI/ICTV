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
from abc import ABCMeta
from functools import wraps

import web
from pymediainfo import MediaInfo
from sqlobject import declarative

from ictv.models.asset import Asset
from ictv.models.channel import PluginChannel
from ictv.models.role import UserPermissions
from ictv.models.user import User
from ictv.plugin_manager.plugin_slide import PluginSlide
from ictv.renderer.renderer import Templates


class ChannelGate(object):
    """
        Utility class allowing to protect channels HTTP methods from being invoked by users
        with unsufficient permission level on the channel. See :func:`~plugin_utils.webapp_decorator`
    """
    @staticmethod
    def contributor(f):
        return webapp_decorator(f, UserPermissions.channel_contributor)

    @staticmethod
    def administrator(f):
        return webapp_decorator(f, UserPermissions.channel_administrator)


class SQLObjectAndABCMeta(declarative.DeclarativeMeta, ABCMeta):
    pass


def webapp_decorator(func, permission_level):
    """
    This decorator wraps a web.py page function and verify that the current user has sufficient permissions to access
    the PluginChannel web application. The channel object is passed to the page as the ``channel`` parameter.
    If no sufficient permission are found, web.forbidden() is raised.
    
    :param func: the web.py page function
    :param permission_level: the minimum permission level needed
    :return: the wrapper
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        app = web.ctx.app_stack[0]
        if len(web.ctx.homepath) > 0:  # We are in a sub-app
            channelid = re.findall(r'\d+', web.ctx.homepath)[0]
        else:  # We are in the core app
            channelid = re.findall(r'\d+', web.ctx.path)[0]
        channel = PluginChannel.get(channelid)
        u = User.get(app.session['user']['id'])
        if 'real_user' in app.session:
            real_user = User.get(app.session['real_user']['id'])
            # if the real user has at least the same right as the "logged as" user
            if u.highest_permission_level not in real_user.highest_permission_level:
                raise web.seeother('/logas/nobody')
        if UserPermissions.administrator in u.highest_permission_level or permission_level in channel.get_channel_permissions_of(u):
            kwargs['channel'] = channel
            return func(*args, **kwargs)
        else:
            raise web.forbidden()

    return wrapper


def seeother(channel_id, plugin_absolute_url):
    """ Returns a 303 See Other redirect in an absolute way. """
    headers = {
        'Content-Type': 'text/html',
        'Location': '/channels/%d%s' % (int(channel_id), plugin_absolute_url)
    }
    return web.HTTPError(status='303 See Other', headers=headers)


class MisconfiguredParameters(BaseException):
    """ An utility class for a plugin to report one or more faulty parameters to ICTV. """
    def __init__(self, param_id, value, message=None):
        self.parameters = []
        self._str = None
        self.add_faulty_parameter(param_id, value, message)

    def add_faulty_parameter(self, param_id, value, message):
        self.parameters.append((param_id, value, message))
        self._str = (self._str + '\n' if self._str else '') + \
                    ('Parameter %s with value %s was reported as faulty.' % (param_id, str(value)))
        if message:
            self._str += ' Additional message: ' + message
        return self

    def __str__(self):
        return self._str

    def __iter__(self):
        return iter(self.parameters)

    def __len__(self):
        return len(self.parameters)


class VideoSlide(PluginSlide):
    """ A convenient class to instantiate slides that contain fullscreen videos. """
    def __init__(self, slide_input, template):
        if 'video' not in slide_input and 'file' not in slide_input:
            raise ValueError('No video was specified in either video or file slide input type')
        self.content = {'background-1': slide_input}
        if 'background-1' not in Templates[template]:
            raise KeyError('The template %s has no background to put the video' % template)
        video_path = slide_input['video'] if 'video' in slide_input else Asset.get(slide_input['file']).path
        video_info = MediaInfo.parse(video_path)
        self.duration = video_info.tracks[0].duration + 1000
        self.template = template

    def get_content(self):
        return self.content

    def get_template(self) -> str:
        return self.template

    def get_duration(self):
        return self.duration
