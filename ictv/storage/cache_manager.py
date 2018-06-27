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

import datetime
import logging
import time
import os
import sched
from threading import Thread, Lock

from urllib.error import URLError

from sqlobject import AND, sqlhub, sqlbuilder

from ictv.models.asset import Asset
from ictv.common.utils import is_test
from ictv.database import SQLObjectThreadConnection
from ictv.storage.storage_manager import StorageManager

logger = logging.getLogger('cache_manager')


class CacheManager(StorageManager):
    def __init__(self, channel_id, download_manager):
        super().__init__(channel_id)
        self.download_manager = download_manager

    def get_cached_file(self, filename):
        """
            Returns an Asset if this cache manager has a cached version of the given file for this channel
            or None if none exists.
        """
        return Asset.selectBy(plugin_channel=self.channel_id, filename=filename, is_cached=True).getOne(None)

    def cache_file(self, content, filename):
        """ Caches the given file and return the corresponding Asset. """
        asset = self.store_file(content, filename)
        asset.is_cached = True
        return asset

    def cache_file_at_url(self, url):
        """ Caches the remote file or retrieves its cached version if one exists. Returns None if an error occurs. """
        filename, extension = os.path.splitext(url)
        cache_asset_hash = hash(str(self.channel_id) + filename)
        asset = Asset.selectBy(plugin_channel=self.channel_id, filename=filename, is_cached=True).getOne(None)
        if asset is None:
            if CacheManager._get_lock(cache_asset_hash, blocking=False):
                try:
                    asset = Asset(plugin_channel=self.channel_id, filename=filename, user=None,
                                  extension=extension if extension is not None and len(extension) > 0 else None,
                                  is_cached=True)
                    self.download_manager.enqueue_asset(asset)
                except (URLError, OSError):
                    logger.warning('Exception encountered when attempting to cache file at url %s', url, exc_info=True)
                    CacheManager._release_lock(cache_asset_hash)
                    return None
                CacheManager._release_lock(cache_asset_hash)
            else:
                CacheManager._get_lock(cache_asset_hash, blocking=True)
                CacheManager._release_lock(cache_asset_hash)
                asset = Asset.selectBy(plugin_channel=self.channel_id, filename=filename, is_cached=True).getOne(None)
        return asset

    _name_to_lock = {}
    _master_lock = Lock()  # The lock of all locks

    @classmethod
    def _get_lock(cls, name, blocking=True):
        cls._master_lock.acquire()
        if name not in cls._name_to_lock:
            cls._name_to_lock[name] = Lock()
        lock = cls._name_to_lock[name]
        cls._master_lock.release()
        return lock.acquire(blocking=blocking)

    @classmethod
    def _release_lock(cls, name):
        cls._master_lock.acquire()
        if name in cls._name_to_lock:
            cls._name_to_lock[name].release()
            del cls._name_to_lock[name]
        cls._master_lock.release()


class CleanupScheduler(object):
    def __init__(self):
        self.conn = None
        self.s = sched.scheduler(timefunc=time.time)
        self.running = True
        self.t = Thread(target=self._run_sched)

    def __del__(self):
        self.stop()

    def _run_sched(self):
        sqlhub.threadConnection = SQLObjectThreadConnection.get_conn()
        while self.running:
            self.s.run(blocking=False)  # TODO: Is there a better way to run this ?
            time.sleep(0.5)

    def start(self):
        """ Starts the cleanup manager and run a first cleanup routine. """
        self.t.start()
        self.s.enter(1, 1, self.cleanup_cache)

    def stop(self):
        if self.running:
            self.running = False
            self.t.join()

    def cleanup_cache(self):
        """ Cleans up the cached assets by deleting all assets not referenced during this day. """
        today = datetime.date.today()
        unused_assets = Asset.selectBy(is_cached=True).filter(Asset.q.last_reference < sqlbuilder.func.date(str(today)))
        total_assets_size = 0
        if unused_assets.count() > 0:
            total_assets_size = unused_assets.sum(Asset.q.file_size)
        Asset.deleteMany(AND(Asset.q.last_reference < sqlbuilder.func.date(str(today)), Asset.q.is_cached == True))
        logger.info('Ran cache cleanup and deleted %d assets for a total size of %s', unused_assets.count(),
                    CleanupScheduler._human_readable_size(total_assets_size))
        next_cleanup = datetime.datetime.combine(today + datetime.timedelta(days=1), datetime.time(hour=23, minute=55))
        self.s.enterabs(time.mktime(next_cleanup.timetuple()), 1, self.cleanup_cache)

    @staticmethod
    def _human_readable_size(byte_size):
        suffixes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
        if byte_size == 0:
            return '0 B'
        i = 0
        while byte_size >= 1024 and i < len(suffixes) - 1:
            byte_size /= 1024.
            i += 1
        f = ('%.2f' % byte_size).rstrip('0').rstrip('.')
        return '%s %s' % (f, suffixes[i])
