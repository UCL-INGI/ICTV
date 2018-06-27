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

import fcntl
import os
import threading
from logging import getLogger

from web.session import DiskStore

logger = getLogger('app')


class PessimisticThreadSafeDiskStore(DiskStore):
    """ Custom DiskStore that guarantees threadsafe access to session files in a pessimistic way. """
    def __init__(self, root):
        super().__init__(root)

    def __getitem__(self, key):
        path = self._get_path(key)

        if os.path.exists(path):
            with open(path, 'rb') as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                pickled = f.read()
                fcntl.flock(f, fcntl.LOCK_UN)
            return self.decode(pickled)
        else:
            raise KeyError(key)

    def __setitem__(self, key, value):
        path = self._get_path(key)
        pickled = self.encode(value)
        try:
            if os.path.exists(path):
                with open(path, 'rb') as lock:
                    f = open(path, 'wb')
                    fcntl.flock(lock, fcntl.LOCK_EX)
                    try:
                        f.write(pickled)
                    finally:
                        f.close()
                    fcntl.flock(lock, fcntl.LOCK_UN)
            else:
                with open(path, 'wb') as f:
                    fcntl.flock(f, fcntl.LOCK_EX)
                    f.write(pickled)
                    fcntl.flock(f, fcntl.LOCK_UN)
        except IOError:
            logger.warning('An Exception was encountered when writing to session file %s ' % path, exc_info=True)


class OptimisticThreadSafeDisktore(DiskStore):
    """ Custom DiskStore that guarantees threadsafe access to session files in a optimistic way. """

    def __init__(self, root):
        super().__init__(root)

    def __setitem__(self, key, value):
        """ Adapted from https://github.com/webpy/webpy/pull/239. """
        path = self._get_path(key)
        pickled = self.encode(value)
        try:
            tname = path + os.extsep + threading.current_thread().getName()
            with open(tname, 'wb') as f:
                f.write(pickled)
            os.rename(tname, path)
        except IOError:
            logger.warning('An Exception was encountered when writing to session file %s ' % path, exc_info=True)
