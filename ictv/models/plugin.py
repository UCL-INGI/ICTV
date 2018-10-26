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
import os

import itertools
import yaml
import yamlordereddictloader
from sqlobject import StringCol, BoolCol, EnumCol, SQLMultipleJoin, JSONCol, IntCol

from ictv.common import get_root_path
from ictv.models.channel import PluginChannel, ChannelBundle
from ictv.models.ictv_object import ICTVObject
from ictv.models.plugin_param_access_rights import PluginParamAccessRights
from ictv.models.subscription import Subscription


class Plugin(ICTVObject):
    name = StringCol(notNone=True, alternateID=True)
    description = StringCol(default=None)
    version = IntCol(notNone=True, default=0)
    activated = EnumCol(notNone=True, enumValues=['yes', 'no', 'notfound'])
    webapp = BoolCol(notNone=True, default=False)
    static = BoolCol(notNone=True, default=False)
    channels_params = JSONCol(notNone=True, default={})  # The type and default param's values needed by every plugin instance
    channels = SQLMultipleJoin('PluginChannel')
    params_access_rights = SQLMultipleJoin('PluginParamAccessRights')
    cache_activated_default = BoolCol(default=True)
    cache_validity_default = IntCol(default=60)
    keep_noncomplying_capsules_default = BoolCol(default=False)
    drop_silently_non_complying_slides_default = BoolCol(default=False)

    def _get_channels_number(self):
        """ Return the number of channels instantiated with this plugin. """
        return self.channels.count()

    def _get_screens_number(self):
        """ Return the number of screens that are subscribed to channels of this plugin. """
        plugin_channels = PluginChannel.select().filter(PluginChannel.q.plugin == self)
        screens = set(plugin_channels.throughTo.subscriptions.throughTo.screen.distinct())
        bundles = set(c for c in ChannelBundle.select() if any(bc.plugin == self for bc in c.flatten()))
        for b in bundles:
            screens |= set(Subscription.select().filter(Subscription.q.channel == b).throughTo.screen.distinct())
        return len(screens)

    def _get_package_path(self):
        """ Returns the path to the package of this plugin. """
        try:
            m = importlib.import_module('ictv.plugins.' + self.name)
            return m.__path__[0]
        except ImportError:
            return None


    @classmethod
    def update_plugins(cls, dirs):
        """
        Takes the list of the plugins directories located in ictv/plugins and updates
        the database if they're not in db
        :param dirs: The directory listing of ictv/plugins
        :return: the list of plugins present in updated database
        """
        s = set()
        plugins_list = []
        for p in Plugin.select():
            s.add(p.name)
            if p.name not in dirs:
                # Plugin exists in database but was not found in the plugins directory
                p.activated = 'notfound'
            else:
                path = os.path.join(p.package_path, 'config.yaml')
                if os.path.isfile(path):
                    # Plugin is considered to be found
                    if p.activated == 'notfound':
                        p.activated = 'no'
                    with open(path, 'r') as f:
                        config = yaml.load(f, Loader=yamlordereddictloader.Loader)
                        p.webapp = config['plugin']['webapp']
                        p.static = config['plugin']['static']
                        p.description = config['plugin'].get('description', None)
                        if 'channels_params' in config:
                            # The plugin has channel specific parameters that can be changed from channel to channel
                            order = 0
                            for k, v in config['channels_params'].items():
                                p.channels_params[k] = v  # Sets the parameter to its default value
                                if 'order' not in p.channels_params[k]:
                                    p.channels_params[k]['order'] = order
                                    order += 1
                                if PluginParamAccessRights.selectBy(plugin=p, name=k).getOne(None) is None:
                                    PluginParamAccessRights(plugin=p, name=k)
                            for k in list(p.channels_params):
                                if k not in config['channels_params'].keys():
                                    p.channels_params.pop(k)
                                    PluginParamAccessRights.deleteBy(plugin=p, name=k)

                            p.channels_params = p.channels_params  # Force SQLObject update
                else:
                    p.activated = 'notfound'

            plugins_list.append(p)
        for p in dirs:
            if p not in s:
                # Plugin was not in database, it should be added but not activated
                plugins_list.append(Plugin(name=p, activated='no'))
        return plugins_list


