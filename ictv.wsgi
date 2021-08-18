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

from ictv import database
from ictv.app import get_app, get_config
from ictv.database import update_database

""" Offers a WSGI function """

curdir = os.path.dirname(__file__)
config_file = os.path.join(curdir, 'configuration.yaml')

if not os.path.isfile(config_file):
    raise Exception('File %s could not be found', config_file)

config = get_config(config_file)
if database.database_path is None:
    database.database_path = config['database_uri']

update_database()
app = get_app(config_file)
application = app.wsgi_app
