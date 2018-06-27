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

import json

from sqlobject import sqlhub
from sqlobject.sqlbuilder import Select

from ictv.models.asset import Asset
from ictv.models.channel import PluginChannel
from ictv.app import sidebar
from ictv.pages.utils import PermissionGate, ICTVAuthPage


class StoragePage(ICTVAuthPage):
    @PermissionGate.super_administrator
    def GET(self):
        return self.render_page()

    @PermissionGate.super_administrator
    def POST(self):
        return self.render_page()

    @sidebar
    def render_page(self):
        channels = []
        total_size = 0
        for channel in Asset.select().throughTo.plugin_channel.distinct():
            channel_info = {'id': channel.id, 'name': channel.name, 'plugin': channel.plugin.name, 'assets_count': channel.assets.count(),
                            'assets_size': channel.assets.sum(Asset.q.file_size) or 0, 'cache_percentage': 0}
            cache_size = channel.assets.filter(Asset.q.is_cached == True).sum(Asset.q.file_size)
            if cache_size is not None:
                channel_info['cache_percentage'] = cache_size / channel_info['assets_size']
            total_size += (channel_info['assets_size'] if channel_info['assets_size'] is not None else 0)
            channels.append(channel_info)
        for channel_info in channels:
            channel_info['percentage'] = ((channel_info['assets_size'] / total_size) if channel_info['assets_size'] and total_size is not None else 0)
        return self.renderer.storage(channels=channels)


class StorageChannel(ICTVAuthPage):
    @PermissionGate.super_administrator
    def GET(self, channel_id):
        return self.render_page(channel_id)

    @sidebar
    def render_page(self, channel_id):
        channel = PluginChannel.get(channel_id)
        con = sqlhub.threadConnection
        select_query = Select(['mime_type', 'SUM(file_size)'], where=Asset.q.plugin_channel == channel_id, staticTables=['asset'], groupBy='mime_type')
        labels = []
        data = []
        for type, size in con.queryAll(con.sqlrepr(select_query)):
            labels.append(type)
            data.append(size)
        palette = [(0.86, 0.37119999999999997, 0.33999999999999997), (0.86, 0.7612000000000001, 0.33999999999999997), (0.56880000000000008, 0.86, 0.33999999999999997), (0.33999999999999997, 0.86, 0.50120000000000009), (0.33999999999999997, 0.82879999999999987, 0.86), (0.33999999999999997, 0.43879999999999986, 0.86), (0.63119999999999976, 0.33999999999999997, 0.86), (0.86, 0.33999999999999997, 0.69879999999999964)]
        background_color = []
        border_color = []
        for R,G,B in palette:
            background_color.append('rgba(%d, %d, %d, 0.95)' % (int(R*255), int(G*255), int(B*255)))
            border_color.append('rgba(%d, %d, %d, 1)' % (int(R*255), int(G*255), int(B*255)))

        chart_data = {'labels': labels, 'datasets': [{'data': data, 'backgroundColor': background_color}]}
        return self.renderer.storage_channel(channel=channel, chart_data=json.dumps(chart_data))
