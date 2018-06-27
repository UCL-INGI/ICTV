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

from abc import ABCMeta, abstractmethod
from typing import Iterable

from ictv.plugin_manager.plugin_slide import PluginSlide


class PluginCapsule(metaclass=ABCMeta):
    @abstractmethod
    def get_slides(self) -> Iterable[PluginSlide]:
        """ Return a sorted iterable of slides contained in this capsule. """
        pass

    @abstractmethod
    def get_theme(self) -> str:
        """
            Return the theme of this capsule.
            The theme is the name of a corresponding template without file extensions.
        """
        pass
