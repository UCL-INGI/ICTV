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
import platform

from setuptools import setup

import ictv.common

is_running_on_macos = platform.system() == 'Darwin'

retval = setup(
    name='ictv',
    version=ictv.common.__version__,
    packages=['ictv', 'ictv.common', 'ictv.libs', 'ictv.models', 'ictv.pages', 'ictv.plugin_manager', 'ictv.renderer', 'ictv.storage', 'ictv.tests'],
    package_dir={'ictv': 'ictv'},
    url='https://github.com/UCL-INGI/ICTV',
    license='GNU AGPL v3',
    author='Michel François, Piraux Maxime, Taffin Ludovic, Nicolas Detienne, Pierre Reinbold',
    author_email='',
    description='ICTV is a simple content management system for digital signage on multiple screens.',
    install_requires=['sqlobject', 'typing', 'icalendar', 'pyyaml', 'urllib3', 'web.py>=0.40.dev0',
                      'yamlordereddictloader', 'pyquery', 'BeautifulSoup4', 'python-magic', 'aiohttp', 'wand',
                      'feedparser', 'qrcode', 'selenium', 'python3-saml', 'pymediainfo'],
    setup_requires=['pytest-runner', 'pytest-env'] if not is_running_on_macos else [],
    tests_require=['pytest', 'pytest-xdist', 'pytest-cov', 'paste', 'nose'],
    dependency_links=['https://github.com/formencode/formencode.git#egg=FormEncode'],
    scripts=['ictv-setup-database', 'ictv-webapp', 'ictv-tests'] if os.environ.get('SETUP_ENV') != 'travis' else [],
    include_package_data=True,
)
