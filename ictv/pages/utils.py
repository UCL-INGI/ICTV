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
from functools import wraps
from logging import getLogger

import flask
from flask.views import MethodView

from ictv.flask.migration_adapter import Storage
from ictv.models.role import UserPermissions
from ictv.models.user import User
from ictv.plugin_manager.plugin_manager import PluginManager
from ictv.plugin_manager.plugin_utils import ChannelGate
from ictv.renderer.renderer import ICTVRenderer
from ictv.storage.cache_manager import CleanupScheduler
from ictv.storage.download_manager import DownloadManager
from ictv.storage.transcoding_queue import TranscodingQueue

import ictv.flask.response as resp


class ICTVPage(MethodView):
    """
        A base for all the pages of the ICTV webapp.
        Contains references to the PluginManager, web.py renderer & session, ICTVRenderer,
        DownloadManager, CleanupScheduler and ICTV config.
    """

    @property
    def app(self):
        """ Returns the web.py application singleton of ICTV Core. """
        return flask.current_app

    @property
    def plugin_manager(self) -> PluginManager:
        """ Returns the PluginManager singleton. """
        return self.app.plugin_manager

    @property
    def ictv_renderer(self) -> ICTVRenderer:
        """ Returns the ICTVRenderer singleton. """
        return self.app.ictv_renderer

    @property
    def session(self) -> flask.session:
        """ Returns the webapp session. """
        return flask.session

    @property
    def renderer(self):
        """ Returns the webapp renderer. """
        return self.app.renderer

    @property
    def standalone_renderer(self):
        """ Returns the webapp renderer without any base template. """
        return self.app.standalone_renderer

    @property
    def download_manager(self) -> DownloadManager:
        """ Returns the DownloadManager singleton. """
        return self.app.download_manager

    @property
    def cleanup_scheduler(self) -> CleanupScheduler:
        """ Returns the CleanupScheduler singleton. """
        return self.app.cleanup_scheduler

    @property
    def transcoding_queue(self) -> TranscodingQueue:
        """ Returns the TranscodingQueue singleton. """
        return self.app.transcoding_queue

    @property
    def config(self) -> dict:
        """ Returns the ICTV config. """
        return self.app.config

    @property
    def version(self):
        """ Returns the ICTV version. """
        return self.app.version

    @property
    def form(self) -> Storage:
        """ Returns the request form. """

        # ImmutableMultiDict.to_dict() is not sufficient as it
        # as it ignores multiple keys (form arrays)
        # Manually adding the lists as lists int the Storage object
        form_aslists = flask.request.form.lists()
        finaldict = flask.request.form.to_dict()
        for key,value in form_aslists:
            if len(value)>1:
                finaldict[key]=value
        finaldict.update(flask.request.files)
        return Storage(finaldict)

    def input(self, **defaults) -> Storage:
        """ Returns the request form. """
        original_form = defaults.copy()

        form_aslists = flask.request.form.lists()
        finaldict = flask.request.form.to_dict()
        for key,value in form_aslists:
            if len(value)>1:
                finaldict[key]=value

        original_form.update(finaldict)

        # Replicating the web.input() strange behaviour
        # when called with an expectation of multiple arguments
        # see https://webpy.org/cookbook/input
        for key,value in defaults.items():
            if type(value)==type([]) and type(original_form[key])!=type([]):
                original_form[key]=[original_form[key]]


        return Storage(original_form)

    def url_for(self, page_class, *args):
        """ Returns an URL filled with the given arguments to the given page. """
        page_path = page_class.__module__ + '.' + page_class.__qualname__
        page_url = None
        for url, page in self.app.mapping:
            if page_path == page:
                page_url = url
                break
        if not page_url:
            raise KeyError('% is not a page mapped in the application' % page_path)

        if args:
            regex = r"(\([^\/]*\))"
            for match, arg in zip(re.finditer(regex, page_url), args):
                page_url = page_url.replace(match.group(), str(arg))

        return page_url



class ICTVAuthPage(ICTVPage):
    """ A simple subclass to indicate that a subclassing page cannot be accessed without being authenticated. """
    pass


class DummyLogin(ICTVPage):
    def get(self, email):
        u = User.selectBy(email=email).getOne(None)
        if u is not None:
            self.session['user'] = u.to_dictionary(['id', 'fullname', 'email'])
            if 'sidebar' in self.session:
                self.session.pop('sidebar')
        resp.seeother('/')


class DummyRenderer(ICTVAuthPage):
    @ChannelGate.contributor
    def get(self, channelid, channel):
        return self.ictv_renderer.preview_capsules(self.plugin_manager.get_plugin_content(channel))


class LogAs(ICTVAuthPage):
    """
    Logs the super_administrator as another user, by inserting the "logged_as" field in the session.
    'logged_as': {'id': [[target_user_id]], 'email': [[target_user_email]], 'full_name': target_user_fullname}
    """
    logger = getLogger('pages')

    def get(self, target_user):
        @PermissionGate.administrator
        def log_as():
            u = User.selectBy(email=target_user).getOne()
            real_user_dict = self.session['user'] if 'real_user' not in self.session else self.session['real_user']
            real_user = User.selectBy(email=real_user_dict['email']).getOne()
            if u is not None:
                if u.highest_permission_level in real_user.highest_permission_level:
                    self.session['real_user'] = self.session['user'] if 'real_user' not in self.session else self.session['real_user']
                    self.session['user'] = u.to_dictionary(['id', 'fullname', 'email'])
                    self.logger.info('the super_administrator %s has been logged as %s',
                                     real_user.log_name, u.log_name)
                    resp.seeother('/')
                else:
                    resp.forbidden()

        if target_user == 'nobody':
            if 'real_user' in self.session:
                self.session['user'] = self.session['real_user']
                self.session.pop('real_user')
            resp.seeother('/')
        log_as()

        return "the user " + target_user + " does not exist"


class DummyCapsuleRenderer(ICTVAuthPage):  # TODO: Move this to editor/app.py
    @ChannelGate.contributor
    def get(self, channelid, capsuleid, channel):
        plugin = self.plugin_manager.get_plugin(channel.plugin.name)
        capsules = plugin.get_content(channelid=int(channelid), capsuleid=int(capsuleid))
        PluginManager.dereference_assets(capsules)
        return self.ictv_renderer.preview_capsules(capsules=capsules)


class LogoutPage(ICTVAuthPage):
    def post(self):
        self.session.clear()
        resp.seeother('/')


class TourPage(ICTVAuthPage):
    def post(self, status):
        User.get(self.session['user']['id']).has_toured = status == 'ended'
        resp.seeother(flask.request.environ.get('HTTP_REFERER', '/'))


class PermissionGateMeta(type):
    """
        Utility class that constructs dynamically decorators to protect methods from being invoked by user with unsufficient permissions.
        For each permission level in UserPermissions, a decorator with the same name is created in this class.
    """
    def __init__(self, *args, **kwargs):
        """ Iterates over the attributes of UserPermissions and creates a corresponding decorator. """
        for permission_level in UserPermissions:
            setattr(self, permission_level.name,
                    PermissionGateMeta._make_permission_level_decorator(self, permission_level))
        super().__init__(self)

    def _make_permission_level_decorator(cls, permission_level):
        """
            Returns a class method that verify that the current user in web.py session has sufficient permission rights
            corresponding to the given permission level.
        """
        def decorator(cls, f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                app = flask.current_app
                if 'user' in app.session:
                    u = User.get(app.session['user']['id'])
                    if 'real_user' in app.session:
                        real_user = User.get(app.session['real_user']['id'])
                        # if the real user has at least the same right as the "logged as" user
                        if u.highest_permission_level not in real_user.highest_permission_level:
                            resp.seeother('/logas/nobody')
                    if permission_level in u.highest_permission_level:
                        return f(*args, **kwargs)
                    resp.forbidden()

            return decorated_function

        return classmethod(decorator)


class PermissionGate(object, metaclass=PermissionGateMeta):
    """ Utility class automatically filled by PermissionGateMeta. """
    pass

class DebugEnv(ICTVAuthPage):
    @PermissionGate.super_administrator
    def get(self):
        from pprint import pformat
        return pformat(flask.request.__dict__) + '\n' + pformat(self.config)
