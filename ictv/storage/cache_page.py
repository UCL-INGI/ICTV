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

from ictv.models.asset import Asset
from ictv.pages.utils import ICTVPage

import ictv.flask.response as resp

class CachePage(ICTVPage):
    def get(self, asset_id):
        """ Waits for the given asset to be downloaded. Redirects the user to the asset when done. """
        try:
            asset_id = int(asset_id)
            if self.download_manager.has_pending_task_for_asset(asset_id):
                task = self.download_manager.get_pending_task_for_asset(asset_id)
                task.result()
            resp.seeother('/' + Asset.get(asset_id)._get_path(force=True))  # Task is complete but asset may be still marked as in flight
        except SQLObjectNotFound:
            resp.notfound()
        except KeyError:
            resp.seeother('/cache/' + str(asset_id))
