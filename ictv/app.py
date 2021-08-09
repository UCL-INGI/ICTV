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
import yaml
from sqlobject import SQLObjectNotFound, sqlhub
from sqlobject.dberrors import DatabaseError

import flask
from flask import Flask, session
from flask.views import MethodView

import werkzeug

import ictv
import ictv.common
from ictv import database, pages
from ictv.common import get_root_path
from ictv.models.log_stat import LogStat
from ictv.models.role import UserPermissions
from ictv.models.template import Template
from ictv.models.user import User
from ictv.common.feedbacks import rotate_feedbacks, get_feedbacks, pop_previous_form, get_next_feedbacks
from ictv.common.logging import init_logger, load_loggers_stats
from ictv.common.utils import make_tooltip, make_alert, generate_secret, pretty_print_size, timesince, is_test, sidebar, urls
from ictv.database import SQLObjectThreadConnection, close_database
from ictv.pages.utils import ICTVAuthPage, PermissionGate
from ictv.pages.logs_page import LogsPage
from ictv.plugin_manager.plugin_manager import PluginManager
from ictv.renderer.renderer import ICTVRenderer
from ictv.storage.cache_manager import CleanupScheduler
from ictv.storage.download_manager import DownloadManager
from ictv.storage.transcoding_queue import TranscodingQueue

import ictv.flask.response as resp
from ictv.flask.migration_adapter import render_jinja, FrankenFlask
from ictv.flask.mapping import init_flask_url_mapping

class IndexPage(ICTVAuthPage):
    @sidebar
    def get(self):
        return self.renderer.home(homepage_description=self.config['homepage_description'], user_disabled=User.get(self.session['user']['id']).disabled)


def get_db_thread_preprocessor():
    def db_thread_preprocessor():
        #Avoid processing for static files
        if '/static/' in flask.request.path:
            return
        sqlhub.threadConnection = SQLObjectThreadConnection.get_conn()
    return db_thread_preprocessor

def database_error_handler(e):
    logging.getLogger('database').error('An error occured while executing queries for request %s', flask.request.path, exc_info=True)

def internal_error_handler(e):
    logging.getLogger('pages').error('An error occured while executing request %s', flask.request.path, exc_info=True)



def load_templates_and_themes():
    Template.deleteMany(None)
    for template in next((os.walk(os.path.join(get_root_path(), 'renderer/templates/'))))[2]:
        Template(name=template.replace('.html', ''))

def get_saml_processor(app):
    def saml_processor(handler):
        if 'user' not in app.session:
            flask.abort(resp.seeother('/shibboleth?sso'))
        handler()
    return saml_processor


def get_local_authentication_processor(app):
    def local_authentication_processor(handler):
        if 'user' not in app.session and not flask.request.path.startswith('/login') and not flask.request.path.startswith('/reset'):
            flask.abort(resp.seeother('/login'))
        handler()
    return local_authentication_processor


def get_authentication_processor(app):
    mode_to_processor = {'saml2': get_saml_processor(app), 'local': get_local_authentication_processor(app)}

    def authentication_processor():
        #Avoid processing for static files
        if '/static/' in flask.request.path:
            return

        def post_auth():
            if 'user' in app.session:
                User.get(id=app.session['user']['id'])
                app.session.pop('sidebar', None)

        urls = app.url_map.bind('')
        view_func = app.view_functions.get(urls.match(flask.request.path,method=flask.request.method)[0]).__dict__
        if view_func!={} and issubclass(view_func['view_class'], ICTVAuthPage):
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
        post_auth()

    return authentication_processor


def get_web_ctx_processor():
    def web_ctx_processor():
        """
            Populate the g variable to mimic the old web.py web.ctx variable
            using meaningful values when behind a proxy.
            values available in g are:
                ["ip","host","homedomain","protocol","query","homepath"]

        """
        if flask.request.headers.getlist("X-Forwarded-For"):
           flask.g.ip = flask.request.headers.getlist("X-Forwarded-For")[0]
        else:
           flask.g.ip = flask.request.remote_addr

        if flask.request.headers.getlist("X-Forwarded-Host"):
           flask.g.host  = flask.request.headers.getlist("X-Forwarded-Host")[0]
        else:
           flask.g.host = flask.request.url.split('/')[2]

        flask.g.homedomain = '%s//%s' % (flask.request.url.split("//")[0], flask.g.host)
        flask.g.protocol = flask.request.url.split(":")[0]
        flask.g.query = ("?" if flask.request.query_string.decode()!="" else "")+flask.request.query_string.decode()
        flask.g.home = flask.request.url_root
        flask.g.homepath = flask.g.home.split(flask.g.homedomain+"/")[-1]

    return web_ctx_processor


def dump_log_stats():
    from ictv.common.logging import loggers_stats
    LogStat.dump_log_stats(loggers_stats)


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
        config = yaml.unsafe_load(f)
    with open(os.path.join(get_root_path(), 'configuration.metadata' + os.extsep + 'yaml')) as f:
        metadata = yaml.unsafe_load(f)
    with open(os.path.join(get_root_path(), 'configuration.default' + os.extsep + 'yaml')) as f:
        defaults = yaml.unsafe_load(f)

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
            config_dict['default_slides'] = yaml.unsafe_load(default_slides_file)

        return config_dict

    return load_default_slides(config)

def get_app(config, sessions_path=""):
    """
        Returns the flask main application of ICTV.
        Currently, only one application can be run a time due to how data such as assets, database, config files
        or plugins is stored.
    """
    if database.database_path is None:
        database.database_path = config['database_uri']

    # Create a base flask application
    app = FrankenFlask(__name__)

    # The following line might be used to speedup queries
    app.config["SEND_FILE_MAX_AGE_DEFAULT"]=300

    app.config.update(**config)

    init_flask_url_mapping(app)

    app.version = ictv.common.__version__

    with open(os.path.join(get_root_path(), 'info' + os.extsep + 'yaml')) as f:
        # Loads ICTV user info texts
        info_texts = yaml.unsafe_load(f)

    # Load the SMTP config into web.py
    smtp_conf = app.config.get('smtp', None)
    if smtp_conf:
        app.config['MAIL_DEFAULT_SENDER'] = smtp_conf['sender_name']
        app.config['MAIL_SERVER'] = smtp_conf['host']
        app.config['MAIL_PORT'] = smtp_conf['port']
        app.config['MAIL_USERNAME'] = smtp_conf.get('username', '')
        app.config['MAIL_PASSWORD'] = smtp_conf.get('password', '')
        app.config['MAIL_USE_TLS'] = smtp_conf.get('starttls', False)

    # Create a persistent HTTP session storage for the app
    app.secret_key = 'fwerrknu384nzAUGGDAG238hmnasd'

    # Populate the jinja templates globals
    template_globals = {'session': app.session,
                        'get_feedbacks': get_feedbacks, 'get_next_feedbacks': get_next_feedbacks,
                        'pop_previous_form': pop_previous_form,
                        'UserPermissions': UserPermissions, 'json': json,
                        'str': str, 'sorted': sorted, 'hasattr': hasattr, 'sidebar_collapse': False, 'show_header': True,
                        'show_footer': True, 're': re, 'info': info_texts, 'make_tooltip': make_tooltip,
                        'make_alert': make_alert, 'escape': html.escape,
                        'show_reset_password':  'local' in app.config['authentication'],
                        'homedomain': lambda: "/".join(flask.request.url.split('/')[:3]), 'generate_secret': generate_secret,
                        'version': lambda: app.version, 'pretty_print_size': pretty_print_size, 'timesince': timesince,
                        'User': User, 'get_user': lambda: User.get(app.session['user']['id'])}

    ### Jinja2 renderer ###
    app.renderer = render_jinja(os.path.join(get_root_path(), 'templates/'))
    app.renderer._lookup.globals.update(base='base.html', **template_globals)

    app.standalone_renderer = render_jinja(os.path.join(get_root_path(), 'templates/'))
    app.standalone_renderer._lookup.globals.update(**template_globals)

    # Init loggers
    load_loggers_stats()
    # Determine logging level and user feedback when an internal error occurs based on ICTV core config
    level = logging.INFO

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

    # Add an general authentication processor to handle user authentication
    app.register_before_request(get_authentication_processor,cascade=True,needs_app=True)

    # Add a preprocessor to populate flask.g and mimic the old web.ctx
    app.register_before_request(get_web_ctx_processor,cascade=True)

    # Add a preprocessor to encapsulate every SQL requests in a transaction on a per HTTP request basis
    app.register_before_request(get_db_thread_preprocessor,cascade=True)
    app.prepare_error_handler(DatabaseError,lambda:database_error_handler)
    app.prepare_error_handler(werkzeug.exceptions.InternalServerError,lambda:internal_error_handler)

    # Add a hook to clean feedbacks from the previous request and prepare next feedbacks to be shown to the user
    app.register_after_request(lambda:rotate_feedbacks,cascade=True,needs_app=False)

    # Instantiate plugins through the plugin manager
    app.plugin_manager.instantiate_plugins(app)

    # Load themes and templates into database
    sqlhub.doInTransaction(load_templates_and_themes)

    return app.get_app_dispatcher()



def close_app(app):
    """ Closes all the threads used by the app. """
    app.transcoding_queue.stop()
    app.download_manager.stop()
    app.cleanup_scheduler.stop()
    app.plugin_manager.stop()


def main(config):
    logger = logging.getLogger('app')
    try:
        app = get_app(config)
        if is_test() or app.config['debug']['serve_static']:
            cwd = os.getcwd()
            os.chdir(get_root_path())
            if not os.path.exists(os.path.join(get_root_path(), 'sessions')):
                os.mkdir(os.path.join(get_root_path(), 'sessions'))
            os.chdir(cwd)
        if not is_test():
            address_port = config['address_port'].rsplit(':',1)
            werkzeug.serving.run_simple(address_port[0],int(address_port[1]),app,use_debugger=config['debug']!=None)
        else:
            return app
    except Exception as e:
        logger.error('Exception encountered when starting the application', exc_info=True)
        raise e
