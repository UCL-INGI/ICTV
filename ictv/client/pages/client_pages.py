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
from zipfile import ZipFile
import flask

from ictv.common import get_root_path
from ictv.pages.utils import ICTVPage
import ictv.flask.response as resp

class Kickstart(ICTVPage):
    """ A simple page that serves KS files, providing a way to adapt the client deployment further in the future. """
    def get(self, file):
        path = os.path.join(get_root_path(), 'client', 'ks', file)
        if os.path.exists(path):
            flags = 'r'
            if self._path_has_ext(path, 'zip'):
                flags += 'b'
                make_client_zip()
            with open(path, flags) as f:
                content = f.read()
            if self._path_has_ext(path, 'ks') or self._path_has_ext(path, 'cfg'):
                content = content.format(ictv_root_url=flask.g.homedomain, **self.config['client'])

            response = flask.Response(content)
            response.headers['Content-Type'] = 'application/zip'
            return response
        resp.notfound()

    @staticmethod
    def _path_has_ext(path, ext):
        return os.path.splitext(path)[1] == os.extsep + ext


def make_system_zip():
    system_zip_path = os.path.join(get_root_path(), 'client', 'ks', 'system' + os.extsep + 'zip')
    if os.path.exists(system_zip_path):
        os.unlink(system_zip_path)

    def add_file(file):
        system_zip.write(os.path.join(get_root_path(), 'client', 'ks', file), arcname=file)

    with ZipFile(system_zip_path, 'w') as system_zip:
        add_file(os.path.join('etc', 'pam.d', 'xserver'))
        add_file(os.path.join('home', 'ictv', '.xinitrc'))


def make_client_zip():
    client_zip_path = os.path.join(get_root_path(), 'client', 'ks', 'client' + os.extsep + 'zip')
    if os.path.exists(client_zip_path):
        os.unlink(client_zip_path)

    def add_file(file):
        client_zip.write(os.path.join(get_root_path(), 'client', file), arcname=file)

    with ZipFile(client_zip_path, 'w') as client_zip:
        add_file('cache_daemon.py')
        add_file('static/bootstrap.html')
        add_file('static/jquery.min.js')
        add_file('static/jquery.xmlrpc.min.js')
        add_file('static/waiting_screen.html')
        with open(os.path.join(get_root_path(), 'client', 'static', 'config' + os.extsep + 'json')) as client_config_file:
            client_zip.writestr('static/config.json', client_config_file.read() % flask.g.homedomain)

make_system_zip()
