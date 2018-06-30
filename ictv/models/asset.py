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

import os
from datetime import datetime
from sqlobject import ForeignKey, StringCol, BigIntCol, DateTimeCol, BoolCol

from ictv.common import get_root_path
from ictv.models.ictv_object import ICTVObject
from sqlobject.events import RowDestroyedSignal, listen


class Asset(ICTVObject):
    """ Represents the metadata of a file stored by the StorageManager. """
    plugin_channel = ForeignKey('PluginChannel', notNone=True, cascade=True)
    user = ForeignKey('User')  # The user who uploaded the file, if known
    filename = StringCol(default=None)  # The original filename of the asset, beginning with a period
    mime_type = StringCol(default=None)  # The MIME type associated with the file
    extension = StringCol(default=None)
    file_size = BigIntCol(default=None)  # File size in kilobytes
    created = DateTimeCol(default=DateTimeCol.now)
    last_reference = DateTimeCol(default=DateTimeCol.now)
    in_flight = BoolCol(default=False)  # Is this asset being cached at the moment
    is_cached = BoolCol(default=False)  # Is this asset a cached asset from CacheManager

    def _get_path(self, force=False):
        """ Returns the path to the asset on the filesystem or None if the asset file is being cached. """
        self.last_reference = datetime.now()
        if not force and self.in_flight:
            return None
        elif force:
            self.in_flight = False  # Prevent failures in the caching process to block asset in flight mode
        return os.path.join('static', 'storage',
                            str(self.plugin_channel.id),
                            str(self.id) + (self.extension if self.extension is not None else ''))

    def write_to_asset_file(self, content):
        """ Writes the content to the asset file. """
        asset_path = os.path.join(get_root_path(), self.path)
        os.makedirs(os.path.dirname(asset_path), exist_ok=True)
        with open(asset_path, 'wb') as f:
            f.write(content)


def on_asset_deleted(instance, kwargs):
    """ Deletes the file associated with this asset when this asset is deleted. """
    try:
        os.remove(os.path.join(get_root_path(), instance.path))
    except (OSError, TypeError) as e:
        # TODO: log message to app.log
        print(e)

listen(on_asset_deleted, Asset, RowDestroyedSignal)
