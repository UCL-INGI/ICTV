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
import shutil

import paste
import unittest
import web
from yaml import dump
from paste.fixture import TestApp

from ictv import get_root_path
from ictv.models.building import Building
from ictv.models.channel import PluginChannel
from ictv.models.plugin import Plugin
from ictv.models.screen import Screen
from ictv.models.user import User
from ictv.app import get_app, close_app
from ictv.database import setup_database, create_database, load_plugins, close_database, \
    database_path
from ictv.plugin_manager.plugin_manager import PluginManager

web.webapi.debug.write = lambda _: None  # Monkey patch web.py to avoid paste lint error and get proper tracebacks
paste.lint.check_content_type = lambda *_: None

class ICTVTestCase(unittest.TestCase):

    config = {
        'default_theme': 'ucl',
        'authentication': ['local'],
        'debug': {
            'autologin': True,
            'dummy_login': True,
            'debug_on_error': True,
            'serve_static': True
        },
        'database_uri': '',
        'smtp': {
            'host': 'smtp.sgsi.ucl.ac.be',
            'starttls': True,
            'sender_name': 'ICTV <no-reply@ictv2.info.ucl.ac.be>',
            'username': 'changeme@somedomain.com',
            'password': 'secret',
            'port': 587
        },
        'alert_template_limits': {
            'subject': 'ICTV: Some of your channels do not comply with templates limits',
            'digest_hour_interval': 24.0,
            'activated': True
        },
        'client': {'root_password': '', 'authorized_keys': ''}
    }

    def run_as(self, users, f):
        """ Runs f as each user in the users list """
        for user in users:
            self.ictv_app.test_user = {"email": user}
            f()

    def setUp(self, middleware=lambda: None):
        setup_database()
        create_database()
        load_plugins()
        middleware()
        for plugin in Plugin.select():
            plugin.activated = 'yes'
        with open(file='/tmp/config.yaml',mode='w+') as outfile:
            dump(self.config,outfile, default_flow_style=False)
        self.ictv_app = get_app('/tmp/config.yaml')
        print(self.ictv_app)
        self.testApp = TestApp(self.ictv_app.wsgifunc())

    def tearDown(self):
        close_app(self.ictv_app)
        close_database()
        os.unlink(database_path.replace('sqlite://', ''))


def create_fake_plugin(fake_plugin_root):
    shutil.rmtree(fake_plugin_root, ignore_errors=True)
    os.mkdir(fake_plugin_root)
    with open(os.path.join(fake_plugin_root, 'fake_plugin' + os.extsep + 'py'), 'w') as f:
        f.write("""
from ictv.models.channel import PluginChannel
from ictv.plugin_manager.plugin_capsule import PluginCapsule
from ictv.plugin_manager.plugin_slide import PluginSlide

def get_content(channel_id):
    channel = PluginChannel.get(channel_id)
    return [FakePluginCapsule('', channel.name, 5000)]


class FakePluginCapsule(PluginCapsule):
    def __init__(self, img_src, text, duration):
        self._slides = [FakePluginSlide(img_src, text, duration)]

    def get_slides(self):
        return self._slides

    def get_theme(self):
        return None

    def __eq__(self, other):
        if isinstance(other, FakePluginCapsule):
            print(self.get_slides()[0].get_content(), other.get_slides()[0].get_content())
            return self.get_slides()[0].get_content() == other.get_slides()[0].get_content()
        return False


class FakePluginSlide(PluginSlide):
    def __init__(self, img_src, text, duration):
        self._duration = duration
        self._content = {'background-1': {'src': img_src, 'size': 'contain'}, 'title-1': {'text': text}, 'text-1': {'text': ''}}

    def get_duration(self):
        return self._duration

    def get_content(self):
        return self._content

    def get_template(self) -> str:
        return 'template-background-text-center'
    """.strip())
    with open(os.path.join(fake_plugin_root, '__init__' + os.extsep + 'py'), 'w'):
        pass
    with open(os.path.join(fake_plugin_root, 'config' + os.extsep + 'yaml'), 'w') as f:
        f.write("""
plugin:
  webapp: no
  static: no
  description: 'This is a fake plugin for testing purpose'
channels_params:
  string_param:
    name: 'String parameter'
    placeholder: ''
    type: str
    default: 'default string'
  int_param:
    name: 'Integer parameter'
    placeholder: ''
    type: int
    default: 1
    min: 0
    max: 10
  float_param:
    name: 'Float parameter'
    placeholder: ''
    type: float
    default: -inf
  boolean_param:
    name: 'Boolean parameter'
    placeholder: ''
    type: bool
    default: yes
  template_param:
    name: 'Template parameter'
    placeholder: ''
    type: template
    default: ~""".strip())


class FakePluginTestCase(ICTVTestCase):
    fake_plugin_root = os.path.join(get_root_path(), 'plugins', 'fake_plugin')

    def setUp(self, fake_plugin_middleware=lambda: None, ictv_middleware=lambda: None):
        create_fake_plugin(self.fake_plugin_root)
        fake_plugin_middleware()
        super(FakePluginTestCase, self).setUp(middleware=ictv_middleware)

    def tearDown(self):
        shutil.rmtree(self.fake_plugin_root)
        super(FakePluginTestCase, self).tearDown()
