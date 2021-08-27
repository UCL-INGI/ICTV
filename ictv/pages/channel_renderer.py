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

from sqlobject import SQLObjectNotFound

from ictv.models.channel import PluginChannel, Channel
from ictv.pages.utils import ICTVPage


class ChannelRenderer(ICTVPage):
    def get(self, channel_id, secret):
        """ Render the capsules of this channel. """
        try:
            channel = Channel.get(channel_id)
            if channel.secret != secret:
                resp.forbidden()
        except SQLObjectNotFound:
            resp.notfound()
        channel_capsules = []
        already_added_channels = set()
        for plugin_channel in channel.flatten(keep_disabled_channels=True):
            if plugin_channel.id not in already_added_channels:
                if plugin_channel.plugin.activated == 'yes':
                    for capsule in self.plugin_manager.get_plugin_content(plugin_channel):
                        if len(capsule.get_slides()) > 0:
                            channel_capsules.append(capsule)
                already_added_channels.add(plugin_channel.id)
        return self.ictv_renderer.preview_capsules(channel_capsules, context='channel', auto_slide=True)
