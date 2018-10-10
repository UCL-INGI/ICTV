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

import importlib
import logging
import os
import sys
import pkgutil
from datetime import timedelta, datetime
from urllib.parse import urlparse

import zlib

import yaml

from ictv.models.asset import Asset
from ictv.common.logging import StatHandler
from ictv.common.utils import make_qrcode, is_test
from ictv.common import get_root_path
from ictv.models.channel import PluginChannel
from ictv.models.plugin import Plugin
from ictv.models.role import Role
from ictv.models.user import User
from ictv.plugin_manager.email_digester import EmailDigester
from ictv.plugin_manager.plugin_utils import MisconfiguredParameters
from ictv.renderer.renderer import Templates
from ictv.storage.cache_manager import CacheManager
from ictv.storage.storage_manager import StorageManager
from ictv.plugin_manager.plugin_capsule import PluginCapsule

logger = logging.getLogger('plugin_manager')


class PluginManager(object):
    def __init__(self, app):
        # path to the directory of the plugins
        self.path = "ictv.plugins"
        self.plugins_modules = {}  # A plugin name to Python module mapping, containing all plugin modules loaded
        self.plugins_apps = {}  # A plugin name to web.py application mapping, containing all plugin webapp loaded
        self.app = app
        self.cache = {}
        alert_template_limits_config = app.config.get('alert_template_limits', {})
        self.template_limits_emailing_activated = alert_template_limits_config.get('activated', False)
        if self.template_limits_emailing_activated:
            self.template_limits_email_digester = EmailDigester(
                timedelta(hours=alert_template_limits_config['digest_hour_interval']),
                subject=alert_template_limits_config['subject'])
        self.missing_dependencies = {}  # A plugin name to list of missing modules mapping

    def stop(self):
        if self.template_limits_emailing_activated:
            self.template_limits_email_digester.stop()

    def get_plugin_content(self, channel):
        """
            Imports the channel plugin if needed and returns the channel content as an Iterable[PluginCapsule].
            If the channel has caching activated and the cache is still fresh, the content will be returned from cache
            for fast content retrieval rather than recomputed.
        """
        logger_extra = {'channel_name': channel.name, 'channel_id': channel.id}
        plugin_logger = get_logger(channel.plugin.name, channel)
        now = datetime.now()
        if channel.id in self.cache \
                and channel.cache_activated \
                and self.cache[channel.id]['retrieval_time'] + timedelta(minutes=channel.cache_validity) > now:
            content = self.cache[channel.id]['content']
            logger.debug('Content for plugin %s and channel %d was served from cache', channel.plugin.name, channel.id)
        else:
            try:
                plugin = self.get_plugin(channel.plugin.name)
                content = plugin.get_content(channel.id)
                self.cache[channel.id] = {'retrieval_time': now, 'content': content}
            except MisconfiguredParameters as e:
                logger.warning('Plugin %s and channel %d reported %d faulty parameter(s)', channel.plugin.name, channel.id, len(e))
                plugin_logger.warning('Some parameters were misconfigured', extra=logger_extra, exc_info=True)
                return []
            except Exception as e:
                logger.warning('Encountered exception when retrieving content for plugin %s and channel %d',
                               channel.plugin.name, channel.id)
                plugin_logger.warning('Encountered exception when retrieving content:',
                                      extra=logger_extra, exc_info=True)
                return []
        try:
            content, filtered_out_content = self.filter_non_complying_content(content,
                                                                              channel.keep_noncomplying_capsules)

            if filtered_out_content:
                for non_complying_fields in filtered_out_content:
                    logger.warning(
                        'A capsule has been filtered out because one of its slides did not comply with its template limits for plugin %s and channel %d',
                        channel.plugin.name, channel.id)
                    plugin_logger.warning('One slide had %d non complying field(s). It\' content was the following:',
                                          len(non_complying_fields), extra=logger_extra)
                    for field in non_complying_fields:
                        plugin_logger.warning(
                            'Id %s from template %s has a length of %d but only %d characters are permitted. It\'s text was "%s"',
                            *field, extra=logger_extra)
                if self.template_limits_emailing_activated:
                    self.send_email_alert(channel, filtered_out_content)

            self.dereference_assets(content)
            self.cache_assets(content, channel.id)
            return content
        except Exception as e:
            logger.warning('Encountered exception when post-processing content for plugin %s and channel %d',
                           channel.plugin.name, channel.id, exc_info=True)
            return []

    def load_plugin(self, plugin_name, reload):
        """ Imports the Python module corresponding to the given plugin name. """
        module_path = self.path + '.' + plugin_name + '.' + plugin_name
        if reload and plugin_name in self.plugins_modules:
            module = importlib.reload(self.plugins_modules[plugin_name])
        else:
            module = importlib.import_module(module_path)

        self.plugins_modules[plugin_name] = module

    @staticmethod
    def list_plugins():
        """
            Lists the plugins available in the Python path.
            Does not reflect the loaded plugins nor the plugins present in database.
        """
        plugins_package = 'ictv.plugins.'
        return list(m.replace(plugins_package, '') for i, m, ispkg in pkgutil.walk_packages((f.path for f in pkgutil.iter_importers(plugins_package)), plugins_package) if ispkg)

    def get_plugin(self, plugin_name, reload=False):
        """
            :param plugin_name: the name of the module of the plugin to get
            :param reload: whether the module should be reloaded or imported
            :return: the module of the plugin named plugin_name. It automatically loads the plugin if it is not already loaded.
        """
        if reload or plugin_name not in self.plugins_modules.keys():
            self.load_plugin(plugin_name, reload=reload)
        return self.plugins_modules[plugin_name]

    def get_plugin_webapp(self, plugin_name):
        """
            Returns the web-app of the plugin named plugin_name.
            It automatically loads the plugin and webapp if it is not already loaded.
            :param plugin_name: the plugin name
            :return: the web-app of the plugin
        """
        if plugin_name not in self.plugins_apps:
            module = importlib.import_module(self.path + '.' + plugin_name + ".app")
            self.plugins_apps[plugin_name] = module.get_app(self.app)
        return self.plugins_apps[plugin_name]

    def instantiate_plugins(self, app):
        """
            Iterates over the plugins present in the plugin directory and instantiate each of them.
            :param app: The ICTV Core web.py app
        """
        # two alternatives : select activated plugins and then query on PluginChannel to get the channel number
        # or                 select all channels and add mapping if its plugin is activated.
        Plugin.update_plugins(self.list_plugins())  # Updates plugins database
        plugins = [p for p in Plugin.select() if p.channels]  # PluginChannel.select().throughTo.plugin.distinct() is not working a.t.m., see https://github.com/sqlobject/sqlobject/issues/137
        for p in plugins:
            if p.activated == 'yes':
                self.instantiate_plugin(app, p)
            elif p.activated == 'no':
                self.missing_dependencies[p.name] = self.get_plugin_missing_dependencies(p.name)

    def instantiate_plugin(self, app, plugin):
        """
            Loads the plugin. Returns whether the plugin could be instantiated or not.
            Plugin state may be changed to disabled if an error occurs.
        """
        self.missing_dependencies[plugin.name] = self.get_plugin_missing_dependencies(plugin.name)
        if self.missing_dependencies[plugin.name]:
            plugin.activated = 'no'
            logger.warning(
                'Plugin %s has missing dependencies, could not instantiate it. Plugin is now disabled' % plugin.name)
            get_logger(plugin.name).error('Could not instantiate plugin due to the following missing modules: %s'
                                          % (', '.join(self.missing_dependencies[plugin.name])))
            return False
        try:
            plugin_module = self.get_plugin(plugin.name, reload=True)
        except ImportError:
            plugin.activated = 'no'
            logger.error('Encountered an exception when importing plugin %s' % plugin.name, exc_info=True)
            return False

        if hasattr(plugin_module, 'install'):
            getattr(plugin_module, 'install')()
        if hasattr(plugin_module, 'update'):
            getattr(plugin_module, 'update')(plugin)
        if plugin.static:
            static_dir = os.path.join(plugin.package_path, "static")
            os.makedirs(static_dir, exist_ok=True)
            if os.path.isdir(static_dir):
                link_name = os.path.join(get_root_path(), 'static/plugins', plugin.name)
                if not os.path.exists(link_name):
                    os.makedirs(os.path.dirname(link_name), exist_ok=True)
                    os.symlink(static_dir, link_name, target_is_directory=True)
            else:
                plugin.activated = 'no'
                logger.warning(
                    'Plugin %s static directory is a file, could not instantiate it. Plugin is now disabled' % plugin.name)
                return False
        if plugin.webapp:
            self.add_mappings(app, plugin)
        return True

    def add_mapping(self, app, channel, plugin_webapp=None):
        """ Adds a mapping to ICTV Core web.py routing. """
        if plugin_webapp is None:
            plugin_webapp = self.get_plugin_webapp(channel.plugin.name)
        app.add_mapping('/channels/%d/' % channel.id, plugin_webapp)

    def add_mappings(self, app, plugin):
        """ Adds a mapping for each of the channels associated with the given plugin. """
        for c in plugin.channels:
            self.add_mapping(app, c, plugin_webapp=self.get_plugin_webapp(plugin.name))

    def invalidate_cache(self, plugin_name, channel_id):
        """ Invalidates both Plugin Manager cache and the plugin's cache if it have one. """
        self.cache.pop(channel_id, None)
        plugin = self.get_plugin(plugin_name)
        if hasattr(plugin, 'invalidate_cache'):
            try:
                logger.debug('Cleaning cache for plugin %s and channel %d', plugin_name, channel_id)
                getattr(plugin, 'invalidate_cache')(channel_id)
            except Exception:
                logger.warning('An Exception was encountered when cleaning the cache for plugin %s and channel %d',
                               plugin_name, channel_id, exc_info=True)

    def get_last_update(self, channel_id):
        """ Returns the timestamp of the last cached update for this channel, or None if none exists. """
        return self.cache.get(channel_id, {}).get('retrieval_time')

    @staticmethod
    def get_plugins_modules():
        """ Returns a list of Python modules containing all the plugin modules found in the plugin directory. """
        dirs = next(os.walk(os.path.join(get_root_path(), 'plugins')))[1]
        if '__pycache__' in dirs:
            dirs.remove("__pycache__")
        modules_list = []
        for d in dirs:
            try:
                modules_list.append(importlib.import_module("ictv.plugins." + d + "." + d))
            except ModuleNotFoundError:
                raise Warning('Directory %s did not contain a valid plugin module' % d)
        return modules_list

    @staticmethod
    def dereference_assets(capsules):
        """
            Dereference assets files contained in the given capsules.
            Replaces them with an input-type usable by the renderer.
            It also prefixes src attribute in an absolute path if a local path is detected.
        """
        for capsule in capsules:
            for slide in capsule.get_slides():
                for field_type, input_data in slide.get_content().items():
                    if field_type.startswith('image-') or field_type.startswith('logo-') or field_type.startswith(
                            'background-'):
                        file_ref = input_data.pop('file', None)
                        if file_ref is not None:
                            input_type = 'video' if _is_video(file_ref) else 'src'
                            input_data[input_type] = '/' + StorageManager.get_asset_path(file_ref)
                        else:
                            for input_type in ('src', 'video'):
                                if input_data.get(input_type) and not _is_url(input_data[input_type]) \
                                        and not input_data[input_type].startswith('/static/') \
                                        and not input_data[input_type].startswith('/cache/'):
                                    # Transform the local relative path to the root to an url relative to the domain
                                    input_data[input_type] = '/static/' + input_data[input_type]

    def cache_assets(self, capsules, channel_id):
        """ Caches both remote assets and QR codes. """
        cache_manager = CacheManager(channel_id, self.app.download_manager)
        for capsule in capsules:
            for slide in capsule.get_slides():
                for field_type, input_data in slide.get_content().items():
                    if field_type.startswith('image-') or field_type.startswith('logo-') or field_type.startswith(
                            'background-'):
                        asset = None
                        if 'src' in input_data and _is_url(input_data['src']):
                            asset = cache_manager.cache_file_at_url(input_data['src'])
                        elif 'qrcode' in input_data and input_data['qrcode']:
                            qrcode_filename = 'qrcode_' + hex(zlib.adler32(input_data['qrcode'].encode()))
                            asset = cache_manager.get_cached_file(qrcode_filename)
                            if asset is None:
                                asset = cache_manager.cache_file(make_qrcode(input_data['qrcode']),
                                                                 qrcode_filename + os.extsep + 'svg')
                        if asset:
                            input_data['src'] = ('/' + asset.path) if asset.path is not None else '/cache/' + str(
                                asset.id)

    @staticmethod
    def filter_non_complying_content(capsules, keep_capsules=False):
        """
            Filter capsules that contains non-complying slides according to the character limit of each template field.
            Depending on the keep_capsules, capsules containing non-complying slides are kept or not in the filtered content.
            When capsules are kept, the non-complying slides are removed and added to the filtered out content.
            Return both filtered and filtered out content.
        """
        filtered_capsules = []
        filtered_out_content = []
        for capsule in capsules:
            comply = True
            complying_slides = []
            for slide in capsule.get_slides():
                non_complying_fields = Templates.get_non_complying_fields(slide)
                if non_complying_fields:
                    comply = False
                    filtered_out_content.append(non_complying_fields)
                else:
                    complying_slides.append(slide)
            if comply:
                filtered_capsules.append(capsule)
            elif keep_capsules and complying_slides:
                filtered_capsules.append(FilteredCapsule(complying_slides, capsule.get_theme()))
        return filtered_capsules, filtered_out_content

    def send_email_alert(self, channel, filtered_out_content):
        message = 'the content of channel %s contained a total of %d slide(s) with non-complying field(s):\n' % (
            channel.name, len(filtered_out_content))
        for slide in filtered_out_content:
            for f in slide:
                message += 'The field %s from template %s allows up to %d characters but it was provided with "%s" for a total of %d characters.\n' % (
                    f[0], f[1], f[3], f[4], f[2])
            message += '\n'
        message_hash = hash(message)
        message = ('At %s, ' % datetime.now()) + message
        if Role.selectBy(channel=channel, permission_level='channel_administrator').count() == 0:
            for super_admin in User.selectBy(super_admin=True):
                self.template_limits_email_digester.add_email(super_admin, message, message_hash)
        else:
            for administrator in Role.selectBy(channel=channel,
                                            permission_level='channel_administrator').throughTo.user:
                self.template_limits_email_digester.add_email(administrator, message, message_hash)

    def check_all_plugins_dependencies(self):
        """
            Updates the `missing_dependencies` list
        """
        for p in self.list_plugins():
            self.missing_dependencies[p] = self.get_plugin_missing_dependencies(p)
            if self.missing_dependencies[p]:
                logger.warning(
                    "Plugin %s has missing dependencies, it won't be able to be instantiated." % p)
                get_logger(p).error('There are missing dependencies for this plugin. Please install the following '
                                    'modules: %s '
                                    % (', '.join(self.missing_dependencies[p])))
            elif self.missing_dependencies[p] is None:
                del self.missing_dependencies[p]

    @staticmethod
    def get_plugin_missing_dependencies(plugin_name):
        """
            Returns the dependencies that are not met for the given plugin.
            If all are met or the plugin could not be found or has no dependencies, it returns an empty list.
        """
        path = os.path.join(Plugin.selectBy(name=plugin_name).getOne().package_path, 'config.yaml')
        failed_import = []
        if os.path.isfile(path):
            with open(path, 'r') as f:
                config = yaml.load(f)
                if 'dependencies' in config['plugin']:
                    for module_name in config['plugin']['dependencies']:
                        try:
                            importlib.import_module(module_name)
                        except ImportError:
                            failed_import.append(module_name)
                            logger.info('Import failed for module %s when checking dependencies of plugins %s' % (
                                module_name, plugin_name))
        else:
            return None
        return failed_import


def get_logger(plugin_name, channel=None):
    """
        Returns a Python Logger for plugins already configured with a FileHandler outputting the login the plugin
        directory. If a channel is provided, the default formatting outputs its name and id in a unified way for all plugins.
    """
    # TODO: handle name interferences with core loggers
    logger_name = plugin_name + ('_plugin' if not channel else '_channels')
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    if not channel:
        formatter = logging.Formatter('%(levelname)s : %(asctime)s - %(message)s')
    else:
        formatter = logging.Formatter(
            '%(levelname)s : %(asctime)s [PluginChannel %(channel_name)s (%(channel_id)s)] - %(message)s')
    dirname = Plugin.selectBy(name=plugin_name).getOne().package_path
    if os.path.isdir(os.path.join(dirname)):
        if not logger.hasHandlers():
            logger_file_path = os.path.join(dirname, logger_name + os.path.extsep + 'log')
            file_handler = logging.FileHandler(logger_file_path)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            logger.addHandler(StatHandler(logger_name, logger_file_path))
        return logger
    else:
        raise Exception('the plugin with name %s is not a valid plugin' % plugin_name)


class FilteredCapsule(PluginCapsule):
    """ A capsule that contains only slides that are complying with the template limits. """

    def __init__(self, slides, theme):
        self.slides = slides
        self.theme = theme

    def get_slides(self):
        return self.slides

    def get_theme(self):
        return self.theme


def _is_url(url):
    o = urlparse(url)
    return o.scheme != '' or o.netloc != ''


def _is_video(file_ref):
    asset = Asset.get(file_ref)
    return asset.mime_type.startswith('video')
