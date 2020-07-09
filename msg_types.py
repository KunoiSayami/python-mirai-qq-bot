# -*- coding: utf-8 -*-
# qqbot.py
# Copyright (C) 2020 KunoiSayami
#
# This module is part of python-mirai-qq-bot and is released under
# the AGPL v3 License: https://www.gnu.org/licenses/agpl-3.0.txt
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
from abc import ABCMeta
from dataclasses import dataclass
from typing import Dict


@dataclass
class MessageChain(metaclass=ABCMeta):
	def gdict(self) -> Dict[str, str]:
		return NotImplemented

@dataclass
class Plain(MessageChain):
	text: str
	def gdict(self) -> Dict[str, str]:
		return {'type': 'Plain', 'text': self.text}

@dataclass
class Image(MessageChain):
	imageId: str
	def gdict(self) -> Dict[str, str]:
		return {'type': 'Image', 'imageId': self.imageId}