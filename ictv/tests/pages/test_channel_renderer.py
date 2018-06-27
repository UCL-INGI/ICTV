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

from ictv.models.channel import PluginChannel, Channel
from ictv.models.plugin import Plugin
from ictv.tests import FakePluginTestCase


class ChannelRendererPageTest(FakePluginTestCase):
    def runTest(self):
        """ Tests the ChannelRenderer page. """
        Channel.deleteMany(None)
        fake_plugin = Plugin.byName('fake_plugin')
        plugin_channel = PluginChannel(plugin=fake_plugin, name='This is a cool channel', subscription_right='public')
        body = self.testApp.get(plugin_channel.get_preview_link(), status=200).body
        assert b'This is a cool channel' in body
        assert b"Reveal.toggleAutoSlide(true);" in body
        assert self.testApp.get(plugin_channel.get_preview_link() + 'incorrect_secret', status=403)
        assert self.testApp.get('/preview/channels/%d/incorrect_secret' % (plugin_channel.id + 42), status=404)
