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

import logging
import os
import magic

from sqlobject import SQLObjectNotFound

from ictv import get_root_path
from ictv.models.asset import Asset

logger = logging.getLogger('storage_manager')


class StorageManager(object):
    _storage_path = os.path.join(get_root_path(), 'static', 'storage')

    def __init__(self, channel_id):
        super(StorageManager, self).__init__()

        if not os.path.exists(StorageManager._storage_path):
            os.mkdir(StorageManager._storage_path, mode=0o744)
        self.assets_directory = os.path.join(StorageManager._storage_path, str(channel_id))
        if not os.path.exists(self.assets_directory):
            os.mkdir(self.assets_directory, mode=0o744)
        self.channel_id = channel_id

    def create_asset(self, filename=None, user=None, mime_type=None):
        """
            Creates an empty asset for this channel with the given info and returns it.
            :param filename: the original filename of the file, it should include the file extension if one exists.
            :param user: the user who requested its storage
            :param mime_type: The expected MIME type of the file
            :return Asset: the corresponding Asset
        """
        extension = None
        if filename is not None:
            filename, extension = os.path.splitext(filename)

        return Asset(plugin_channel=self.channel_id, filename=filename, user=user,
                     extension=extension if extension is not None and len(extension) > 0 else None,
                     mime_type=mime_type)

    def store_file(self, content, filename=None, user=None):
        """
            Stores the given file and returns the corresponding Asset.
            :param content: a binary string or buffer representing the file content
            :param filename: the original filename of the file, it should include the file extension if one exists.
            :param user: the user who requested its storage
            :return Asset: the corresponding Asset
        """
        asset = self.create_asset(filename, user, magic.from_buffer(content, mime=True))
        asset.file_size = len(content)
        asset.write_to_asset_file(content)
        return asset

    def delete_all_assets(self):
        """ Deletes all assets of this channel and corresponding files on the filesystem. """
        Asset.deleteBy(plugin_channel=self.channel_id)

    @staticmethod
    def get_asset_path(asset_id):
        """ Returns the path to the asset on the filesystem if it exists, or None otherwise. """
        try:
            asset = Asset.get(asset_id)
        except SQLObjectNotFound:
            logger.warning('Tried to get asset path for unknown asset id %d', asset_id)
            return None
        return asset.path
