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

from enum import Enum


class EnumMask(object):
    def __init__(self, value):
        self.value = value

    def __and__(self, other):
        return EnumMask(self.value & other.value)

    def __or__(self, other):
        return EnumMask(self.value | other.value)

    def __repr__(self):
        return "<{} : {}>".format(
            self.__class__.__name__,
            self.value
        )

    def __contains__(self, item):
        return (self.value & item.value) == item.value

    def __eq__(self, other):
        if isinstance(other, int):
            return self.value == other
        return self.value == other.value


class FlagEnum(Enum):
    def __or__(self, other):
        if isinstance(other, self.__class__):
            return EnumMask(self.value | other.value)
        elif isinstance(other, EnumMask):
            return other | self
        else:
            raise TypeError

    def __and__(self, other):
        if isinstance(other, self.__class__):
            return EnumMask(self.value & other.value)
        elif isinstance(other, EnumMask):
            return other & self
        else:
            raise TypeError

    def __contains__(self, item):
        if isinstance(item, self.__class__):
            return (self.value & item.value) == item.value
        elif isinstance(item, EnumMask):
            return (self & item) == item
        else:
            raise TypeError

    def __eq__(self, other):
        return self.value == other.value
