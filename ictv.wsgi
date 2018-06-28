#!/usr/bin/env python3
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

from ictv.common import get_root_path
from ictv.app import get_app
from ictv.database import update_database, create_database

""" Offers a WSGI function """

curdir = os.path.dirname(__file__)
if not os.path.exists(os.path.join(get_root_path(), 'database.sqlite')):
    create_database()
else:
    update_database()
app = get_app(os.path.join(curdir, 'configuration.yaml'), curdir)
session = app.session
application = app.wsgifunc()
