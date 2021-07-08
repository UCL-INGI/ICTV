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

import html
import json
import logging
import os
import re
import sys
from functools import wraps

import builtins
import web
import yaml
from sqlobject import SQLObjectNotFound, sqlhub
from sqlobject.dberrors import DatabaseError
from web.py3helpers import string_types

import ictv
import ictv.common
from ictv import database
from ictv.common import get_root_path
from ictv.models.log_stat import LogStat
from ictv.models.role import UserPermissions
from ictv.models.template import Template
from ictv.models.user import User
from ictv.common.diskstore import OptimisticThreadSafeDisktore
from ictv.common.feedbacks import rotate_feedbacks, get_feedbacks, pop_previous_form, get_next_feedbacks
from ictv.common.logging import init_logger, load_loggers_stats
from ictv.common.utils import make_tooltip, make_alert, generate_secret, pretty_print_size, timesince, is_test
from ictv.database import SQLObjectThreadConnection, close_database
from ictv.pages.utils import ICTVAuthPage, PermissionGate
from ictv.plugin_manager.plugin_manager import PluginManager
from ictv.renderer.renderer import ICTVRenderer
from ictv.storage.cache_manager import CleanupScheduler
from ictv.storage.download_manager import DownloadManager
from ictv.storage.transcoding_queue import TranscodingQueue


from web.contrib.template import render_jinja

urls = (
    '/', 'ictv.app.IndexPage',
    '/users', 'ictv.pages.users_page.UsersPage',
    '/users/(\d+)','ictv.pages.users_page.UserDetailPage',
    '/screens', 'ictv.pages.screens_page.ScreensPage',
    '/screens/(\d+)', 'ictv.pages.screens_page.DetailPage',
    '/screens/(\d+)/config', 'ictv.pages.screens_page.ScreenConfigPage',
    '/screens/(\d+)/view/(.+)', 'ictv.pages.screen_renderer.ScreenRenderer',
    '/screens/(\d+)/client/(.+)', 'ictv.pages.screen_client.ScreenClient',
    '/screens/(\d+)/subscriptions', 'ictv.pages.screen_subscriptions_page.ScreenSubscriptionsPage',
    '/screens/redirect/(.+)', 'ictv.pages.screen_router.ScreenRouter',
    '/buildings', 'ictv.pages.buildings_page.BuildingsPage',
    '/channels', 'ictv.pages.channels_page.ChannelsPage',
    '/channels/(\d+)', 'ictv.pages.channel_page.ChannelPage',
    '/channels/(\d+)/request/(\d+)', 'ictv.pages.channel_page.RequestPage',
    '/channels/(\d+)/manage_bundle', 'ictv.pages.manage_bundle_page.ManageBundlePage',
    '/channels/(\d+)/subscriptions', 'ictv.pages.channel_page.SubscribeScreensPage',
    '/channel/(\d+)','ictv.pages.channel_page.DetailPage',
    '/channel/(\d+)/force_update','ictv.pages.channel_page.ForceUpdateChannelPage',
    '/plugins', 'ictv.pages.plugins_page.PluginsPage',
    '/plugins/(\d+)/config', 'ictv.pages.plugins_page.PluginConfigPage',
    '/preview/channels/(\d+)/(.+)', 'ictv.pages.channel_renderer.ChannelRenderer',
    '/renderer/(\d+)', 'ictv.pages.utils.DummyRenderer',
    '/renderer/(\d+)/capsule/(\d+)', 'ictv.pages.utils.DummyCapsuleRenderer',
    '/cache/(\d+)', 'ictv.storage.cache_page.CachePage',
    '/storage', 'ictv.pages.storage_page.StoragePage',
    '/storage/(\d+)', 'ictv.pages.storage_page.StorageChannel',
    '/logs', 'ictv.pages.logs_page.LogsPage',
    '/logs/(.+)', 'ictv.pages.logs_page.ServeLog',
    '/logas/(.+)', 'ictv.pages.utils.LogAs',
    '/tour/(started|ended)', 'ictv.pages.utils.TourPage',
    '/client/ks/(.+)', 'ictv.client.pages.client_pages.Kickstart',
    '/emails', 'ictv.pages.emails_page.EmailPage',
    '/transcoding/(.+)/progress', 'ictv.storage.transcoding_page.ProgressPage'
)

sidebar_elements = {
    'ictv.pages.plugins_page.PluginsPage': {'name': 'Plugins', 'icon': 'fa-plug',
                                           'rights': UserPermissions.administrator},
    'ictv.pages.users_page.UsersPage': {'name': 'Users', 'icon': 'fa-users',
                                       'rights': UserPermissions.administrator},
    'ictv.pages.buildings_page.BuildingsPage': {'name': 'Buildings', 'icon': 'fa-building-o',
                                         'rights': UserPermissions.administrator},
    'ictv.pages.channels_page.ChannelsPage': {'name': 'Channels', 'icon': 'fa-picture-o',
                                             'rights': UserPermissions.no_permission},
    'ictv.pages.screens_page.ScreensPage': {'name': 'Screens', 'icon': 'fa-television',
                                           'rights': UserPermissions.screen_administrator},
    'ictv.pages.storage_page.StoragePage': {'name': 'Storage', 'icon': 'fa-hdd-o',
                                            'rights': UserPermissions.super_administrator},
    'ictv.pages.logs_page.LogsPage': {'name': 'Logs', 'icon': 'fa-history',
                                      'rights': UserPermissions.super_administrator},
    'ictv.pages.emails_page.EmailPage': {'name': 'Emails', 'icon': 'fa-envelope',
                                         'rights': UserPermissions.super_administrator}
}

# Explicitly set web.py debugging mode to false
web.config.debug = False


def sidebar(f):
    """ Utility method providing a simple way to populate the sidebar in function of the user permissions. """

    def get_classes_from_user(user):
        """ Returns a list as a tuple of the names of classes in the `pages` package accessible to this user. """
        highest_permission_level = user.highest_permission_level
        if user.disabled:
            return ()
        return (name for name, params in sidebar_elements.items() if params['rights'] in highest_permission_level)

    @wraps(f)
    def decorated_function(*args, **kwargs):
        app = web.ctx.app_stack[0]
        if 'user' in app.session and 'sidebar' not in app.session:
            try:
                u = User.get(app.session['user']['id'])
                if 'real_user' in app.session:
                    real_user = User.get(app.session['real_user']['id'])
                    # if the real user has at least the same right as the "logged as" user
                    if u.highest_permission_level not in real_user.highest_permission_level:
                        raise web.seeother('/logas/nobody')
                user_sidebar = {}
                for class_name in get_classes_from_user(u):
                    e = sidebar_elements[class_name]
                    user_sidebar[e['name']] = {'url': urls[urls.index(class_name) - 1], 'icon': e['icon']}
                    app.session['sidebar'] = sorted(user_sidebar.items())
            except SQLObjectNotFound:
                return f(*args, **kwargs)
        return f(*args, **kwargs)

    return decorated_function

# TODO find a workaround -  added for transition to jinja
# cfr screens template for use
def get_data_edit_object(screen):
    object = screen.to_dictionary(['name', 'comment', 'location'])
    object['screenid'] = screen.id
    object['mac'] = screen.get_macs_string() if screen.macs is not None else ''
    object['building-name'] = screen.building.name
    return json.dumps(object)

class IndexPage(ICTVAuthPage):
    @sidebar
    def GET(self):
        return self.renderer.home(homepage_description=self.config['homepage_description'], user_disabled=User.get(self.session['user']['id']).disabled)


def get_request_errors_preprocessor(db_logger, pages_logger):
    def request_errors_preprocessor(query):
        sqlhub.threadConnection = SQLObjectThreadConnection.get_conn()
        try:
            return query()
        except web.HTTPError as e:
            if type(e) is web.webapi._InternalError:
                pages_logger.error('An error occured while executing request %s', web.ctx.path, exc_info=True)
            raise
        except DatabaseError:
            db_logger.error('An error occured while executing queries for request %s', web.ctx.path, exc_info=True)
            raise
    return request_errors_preprocessor


def load_templates_and_themes():
    Template.deleteMany(None)
    for template in next((os.walk(os.path.join(get_root_path(), 'renderer/templates/'))))[2]:
        Template(name=template.replace('.html', ''))


def get_saml_processor(app):
    def saml_processor(handler):
        if 'user' not in app.session:
            raise web.seeother('/shibboleth?sso')
        return handler()
    return saml_processor


def get_local_authentication_processor(app):
    def local_authentication_processor(handler):
        if 'user' not in app.session and not web.ctx.path.startswith('/login') and not web.ctx.path.startswith('/reset'):
            raise web.seeother('/login')
        return handler()
    return local_authentication_processor


def get_authentication_processor(app):
    mode_to_processor = {'saml2': get_saml_processor(app), 'local': get_local_authentication_processor(app)}

    def match(mapping, path):
        """
            Based on web.py application mapping and a path,
            returns the corresponding class which should handle the request.
        """
        for pat, what in mapping:
            if isinstance(what, web.application):
                if path.startswith(pat):
                    return match(what.mapping, path[len(pat):])
                else:
                    continue
            elif isinstance(what, string_types):
                what, result = web.utils.re_subm('^' + pat + '$', what, path)
            else:
                result = web.utils.re_compile('^' + pat + '$').match(path)

            if result:
                return what, [x for x in result.groups()]
        return None, None

    def authentication_processor(handler):
        def post_auth():
            if 'user' in app.session:
                User.get(id=app.session['user']['id'])
                app.session.pop('sidebar', None)
            return handler()

        class_path, _ = match(app.mapping, web.ctx.path)
        if class_path:
            if '.' in class_path:
                mod, cls = class_path.rsplit('.', 1)
                mod = __import__(mod, None, None, [''])
                cls = getattr(mod, cls)
            else:
                cls = app.fvars[class_path]
            if issubclass(cls, ICTVAuthPage):
                if is_test():
                    if hasattr(app, 'test_user'):
                        u = User.selectBy(email=app.test_user['email']).getOne()
                        app.session['user'] = u.to_dictionary(['id', 'fullname', 'username', 'email'])
                        return post_auth()
                    elif 'user' in app.session:
                        del app.session['user']  # This may not be the ideal way of changing users
                if app.config['debug']['autologin']:
                    u = User.selectBy(email='admin@ictv').getOne(None)
                    if u is not None:
                        app.session['user'] = u.to_dictionary(['id', 'fullname', 'username', 'email'])
                        return post_auth()

                mode = app.config['authentication'][0]  # The first mode is the main authentication mode
                if mode not in mode_to_processor:
                    raise Exception('Authentication method "%s" specified in config file is not supported' % app.config[
                        'authentication'])
                return mode_to_processor[mode](post_auth)
        return post_auth()

    return authentication_processor


def proxy_web_ctx_processor(handler):
    web.ctx.host = web.ctx.env.get('HTTP_X_FORWARDED_HOST', web.ctx.host)
    web.ctx.ip = web.ctx.env.get('HTTP_X_FORWARDED_FOR', web.ctx.ip)
    web.ctx.homedomain = '%s://%s' % (web.ctx.protocol, web.ctx.host)

    return handler()


def dump_log_stats():
    from ictv.common.logging import loggers_stats
    LogStat.dump_log_stats(loggers_stats)


class DebugEnv(ICTVAuthPage):
    @PermissionGate.super_administrator
    def GET(self):
        from pprint import pformat
        return pformat(web.ctx.__dict__) + '\n' + pformat(self.config)


if not is_test():  # TODO: Find why this ignores the first SIGINT when placed in ictv-webapp
    from ictv.libs.register_exit_fun import register_exit_fun

    @register_exit_fun
    def exit_fun():
        if database.database_path is not None:
            sqlhub.threadConnection = SQLObjectThreadConnection.get_conn()
            sqlhub.doInTransaction(dump_log_stats)
            close_database()
            os._exit(0)


def get_config(config_path):
    with open(config_path) as f:
        config = yaml.load(f)
    with open(os.path.join(get_root_path(), 'configuration.metadata' + os.extsep + 'yaml')) as f:
        metadata = yaml.load(f)
    with open(os.path.join(get_root_path(), 'configuration.default' + os.extsep + 'yaml')) as f:
        defaults = yaml.load(f)

    def validate_config(config_dict, metadata, defaults, prefix=''):
        """
            Ensures config parameters have valid values.
            Modifies the given configuration with default values when none can be found in the given config.
            Returns a list of parameters that are invalid.
        """
        sentinel = []
        for key, key_metadata in metadata.items():
            key_name = prefix + key
            if key in config_dict:
                value = config_dict[key]
            elif key in defaults:
                value = defaults[key]
            else:
                value = sentinel
                yield key_name, KeyError, None

            if value is not sentinel:
                config_dict[key] = value
                key_type = key_metadata['type']
                if key_type in vars(builtins):
                    if type(value) != vars(builtins)[key_type] and value is not None:
                        yield key_name, TypeError, (key_type, type(value).__name__)
                    elif key_type == 'int':
                        if ('min' in key_metadata and value < key_metadata['min']) \
                                or ('max' in key_metadata and value > key_metadata['max']):
                            yield key_name, ValueError, None
                    elif key_type == 'dict':
                        yield from validate_config(value, key_metadata['items'], defaults.get(key),
                                                   prefix=key_name + '.')
                elif key_type.startswith('list['):
                    if type(value) is not list:
                        yield key_name, TypeError, (key_type, type(value).__name__)
                    else:
                        inner_type = vars(builtins)[key_type[5:-1]]
                        for i, v in enumerate(value):
                            if type(v) is not inner_type and value is not None:
                                yield '%s[%d]' % (key_name, i), TypeError, (key_type[5:-1], type(v).__name__)

    def check_for_unused_keys(config_dict, metadata, prefix=''):
        """ Checks if the given configuration contains parameters that are not used by ICTV and alerts the user. """
        for key, value in config_dict.items():
            key_name = prefix + key
            key_metadata = metadata.get(key)
            if not key_metadata:
                print('Config file specifies parameter %s but this parameter has no influence on ICTV' % key_name,
                      file=sys.stderr)
            if key_metadata['type'] == 'dict':
                check_for_unused_keys(value, key_metadata['items'], prefix=key_name + '.')

    check_for_unused_keys(config, metadata)
    config_errors = list(validate_config(config, metadata, defaults))

    if config_errors:
        for key, error, info in config_errors:
            if error is KeyError:
                print('Parameter %s was not specified in config file and no default value could be found' % key,
                      file=sys.stderr)
            elif error is TypeError:
                print('Parameter %s has an inappropriate type, expected %s but found %s' % (key, *info),
                      file=sys.stderr)
            elif error is ValueError:
                print(
                    'Parameter %s has an inappropriate value, please check the additional constraints on this parameter'
                    % key, file=sys.stderr)
        raise Exception('Config file is incorrect')

    def load_default_slides(config_dict):
        """ Loads the default slides configuration file inside the main configuration dict. Returns the dict. """
        default_slides_path = config_dict.get('default_slides') or os.path.join(get_root_path(), 'default_slides.default' + os.extsep + 'yaml')
        default_slides_path = os.path.join(os.path.dirname(config_path), default_slides_path)

        if not os.path.exists(default_slides_path):
            raise Exception('Default slides config file could not be found in %s' % default_slides_path)
        with open(default_slides_path) as default_slides_file:
            config_dict['default_slides'] = yaml.load(default_slides_file)

        return config_dict

    return load_default_slides(config)

def get_app(config_path, sessions_path=""):
    """
        Returns the web.py main application of ICTV.
        Currently, only one application can be run a time due to how data such as assets, database, config files
        or plugins is stored.
    """
    # Loads ICTV core config file
    config_file = get_config(config_path)
    if database.database_path is None:
        database.database_path = config_file['database_uri']

    app_urls = urls
    if config_file['debug']['dummy_login']:
        app_urls += ('/login/(.+)', 'ictv.pages.utils.DummyLogin')

    if config_file['debug']['debug_env']:
        app_urls += ('/debug_env', 'DebugEnv')

    if 'local' in config_file['authentication']:
        app_urls += ('/login', 'ictv.pages.local_login.LoginPage',
                     '/reset', 'ictv.pages.local_login.GetResetLink',
                     '/reset/(.+)', 'ictv.pages.local_login.ResetPage',
                     '/logout', 'ictv.pages.utils.LogoutPage',)

    if 'saml2' in config_file['authentication']:
        app_urls += ('/shibboleth', 'ictv.pages.shibboleth.Shibboleth',
                     '/shibboleth_metadata', 'ictv.pages.shibboleth.MetadataPage',)

    # Create a base web.py application
    app = web.application(app_urls, globals())
    app.config = config_file

    app.version = ictv.common.__version__

    with open(os.path.join(get_root_path(), 'info' + os.extsep + 'yaml')) as f:
        # Loads ICTV user info texts
        info_texts = yaml.load(f)

    # Load the SMTP config into web.py
    smtp_conf = app.config.get('smtp', None)
    if smtp_conf:
        web.config.smtp_sendername = smtp_conf['sender_name']
        web.config.smtp_server = smtp_conf['host']
        web.config.smtp_port = smtp_conf['port']
        web.config.smtp_username = smtp_conf.get('username', '')
        web.config.smtp_password = smtp_conf.get('password', '')
        web.config.smtp_starttls = smtp_conf.get('starttls', False)

    # Create a persistent HTTP session storage for the app
    app.session = web.session.Session(app, OptimisticThreadSafeDisktore(os.path.join(sessions_path, 'sessions')))

    # Populate the web.py templates globals
    template_globals = {'session': app.session,
                        'get_feedbacks': get_feedbacks, 'get_next_feedbacks': get_next_feedbacks,
                        'pop_previous_form': pop_previous_form,
                        'UserPermissions': UserPermissions, 'json': json,
                        'str': str, 'sorted': sorted, 'hasattr': hasattr, 'sidebar_collapse': False, 'show_header': True,
                        'show_footer': True, 're': re, 'info': info_texts, 'make_tooltip': make_tooltip,
                        'make_alert': make_alert, 'escape': html.escape,
                        'show_reset_password':  'local' in app.config['authentication'],
                        'homedomain': lambda: web.ctx.homedomain, 'generate_secret': generate_secret,
                        'version': lambda: app.version, 'pretty_print_size': pretty_print_size, 'timesince': timesince,
                        'User': User, 'get_user': lambda: User.get(app.session['user']['id']),
                        'get_data_edit_object': get_data_edit_object}
    # Init the web.py renderer used for the admin interface
    template_kwargs = {'loc': os.path.join(get_root_path(), 'templates/'),
                       'cache': not app.config['debug']['debug_on_error'],
                       'globals': template_globals}

    ### OLD ###
    # app.renderer = web.template.render(base='base', **template_kwargs)

    # # Init a second web.py renderer without any base template
    # app.standalone_renderer = web.template.render(**template_kwargs)
    ###########

    ### Jinja2 ###
    app.renderer = render_jinja(os.path.join(get_root_path(), 'templates/'))
    app.renderer._lookup.globals.update(base='base.html', **template_globals)

    app.standalone_renderer = render_jinja(os.path.join(get_root_path(), 'templates/'))
    app.standalone_renderer._lookup.globals.update(**template_globals)
    ###########

    # Init loggers
    load_loggers_stats()
    # Determine logging level and user feedback when an internal error occurs based on ICTV core config
    level = logging.INFO
    if app.config['debug']['debug_on_error']:
        level = logging.DEBUG
        app.internalerror = web.debugerror
    loggers_to_init = ['app', 'pages', 'screens', 'plugin_manager', 'storage_manager', 'local_login', 'database', 'transcoding_queue']
    for logger_name in loggers_to_init:
        init_logger(logger_name, level, rotation_interval=app.config['logs']['rotation_interval'], backup_count=app.config['logs']['backup_count'])

    # Init the renderer used for slide, capsule, channel and screen rendering
    app.ictv_renderer = ICTVRenderer(app)
    # Init the plugin manager, used as a gateway between ICTV core and its plugins.
    app.plugin_manager = PluginManager(app)

    # Init the download manager, a download queue which asynchronously downloads assets from the network
    app.download_manager = DownloadManager()
    # Init the cleanup manager which will regularly cleanup unused cached assets
    app.cleanup_scheduler = CleanupScheduler()
    app.cleanup_scheduler.start()
    # Init the video transcoding queue which will convert videos to WebM format using FFmpeg
    app.transcoding_queue = TranscodingQueue()

    # Add an hook to make session available through web.ctx for plugin webapps
    def session_hook():
        web.ctx.session = app.session
        web.template.Template.globals['session'] = app.session

    app.add_processor(web.loadhook(session_hook))

    # Add a preprocessor to populate web.ctx with meaningful values when app is run behind a proxy
    app.add_processor(proxy_web_ctx_processor)
    # Add a preprocessor to encapsulate every SQL requests in a transaction on a per HTTP request basis
    app.add_processor(get_request_errors_preprocessor(logging.getLogger('database'), logging.getLogger('pages')))
    # Add an general authentication processor to handle user authentication
    app.add_processor(get_authentication_processor(app))
    # Add a hook to clean feedbacks from the previous request and prepare next feedbacks to be shown to the user
    app.add_processor(web.unloadhook(rotate_feedbacks))

    # Instantiate plugins through the plugin manager
    app.plugin_manager.instantiate_plugins(app)

    # Load themes and templates into database
    sqlhub.doInTransaction(load_templates_and_themes)

    return app


def close_app(app):
    """ Closes all the threads used by the app. """
    app.transcoding_queue.stop()
    app.download_manager.stop()
    app.cleanup_scheduler.stop()
    app.plugin_manager.stop()


def main(config_file):
    logger = logging.getLogger('app')
    try:
        app = get_app(config_file)
        if is_test() or app.config['debug']['serve_static']:
            os.chdir(get_root_path())
            if not os.path.exists(os.path.join(get_root_path(), 'sessions')):
                os.mkdir(os.path.join(get_root_path(), 'sessions'))
        if not is_test():
            app.run()
        else:
            return app
    except Exception as e:
        logger.error('Exception encountered when starting the application', exc_info=True)
        raise e
