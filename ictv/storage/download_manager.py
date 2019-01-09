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

import asyncio
from datetime import datetime
from queue import Queue

import os
import threading

import aiohttp
import magic
import werkzeug.http
from sqlobject import sqlhub

from ictv.common import get_root_path
from ictv.database import SQLObjectThreadConnection


class DownloadManager(object):
    def __init__(self):
        self._loop = asyncio.get_event_loop()
        self._thread = threading.Thread(target=self._run_loop)
        self._post_process_queue = Queue()
        self._post_processing_thread = threading.Thread(target=self._post_process_asset)
        self._thread.start()
        self._post_processing_thread.start()
        self._pending_tasks = {}

    def __del__(self):
        self.stop()

    def enqueue_asset(self, asset):
        """ Enqueues the given asset to the download queue. Marks the asset as in flight when enqueued."""
        if asset.id not in self._pending_tasks:
            def enqueue_post_process_asset(task):
                mime_type, file_size = task.result()
                asset.created = datetime.now()
                if mime_type is not None and file_size is not None:
                    self._post_process_queue.put((mime_type, file_size, asset))

            task = asyncio.run_coroutine_threadsafe(DownloadManager._cache_asset(asset.filename + (asset.extension or ''), asset.path), self._loop)
            asset.in_flight = True
            task.add_done_callback(enqueue_post_process_asset)
            self._pending_tasks[asset.id] = task

    def has_pending_task_for_asset(self, asset_id):
        """ Returns whether or not the download manager has a pending download task for the given asset. """
        return asset_id in self._pending_tasks

    def get_pending_task_for_asset(self, asset_id):
        """ Returns the corresponding task to the given asset. """
        return self._pending_tasks[asset_id]

    def clear_pending_task_for_asset(self, asset_id):
        """ Resets the status of the task associated with the given asset. """
        if self.has_pending_task_for_asset(asset_id):
            del self._pending_tasks[asset_id]

    def stop(self):
        if self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join()

    def _run_loop(self):
        sqlhub.threadConnection = SQLObjectThreadConnection.get_conn()
        asyncio.set_event_loop(self._loop)
        if not self._loop.is_closed() and not self._loop.is_running():
            self._loop.run_forever()
            self._loop.close()

    def _post_process_asset(self):
        sqlhub.threadConnection = SQLObjectThreadConnection.get_conn()
        while True:
            mime_type, file_size, asset = self._post_process_queue.get()
            asset.in_flight = False
            asset.mime_type = mime_type
            asset.file_size = file_size

    @staticmethod
    async def _cache_asset(url, path):
        file_path = os.path.join(get_root_path(), path)
        if os.path.exists(file_path):
            last_modified = werkzeug.http.http_date(os.stat(file_path).st_mtime)
        else:
            last_modified = None
        content = await DownloadManager._get_content(url, last_modified)
        if not content:
            return None, None
        with open(file_path, 'wb') as f:
            f.write(content)
        return magic.from_buffer(content, mime=True), len(content)

    @staticmethod
    async def _get_content(url, last_modified=None):
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={'If-Modified-Since': last_modified} if last_modified else {}) as resp:
                if resp.status is 304:
                    return None
                elif resp.status is 200:
                    return await resp.read()
                else:
                    return None
