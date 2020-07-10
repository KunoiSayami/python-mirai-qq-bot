# -*- coding: utf-8 -*-
# msg_types.py
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
from dataclasses import dataclass
from typing import Dict, TypeVar

mixType = TypeVar('mixType', str, int)
inputType = Dict[str, mixType]

@dataclass
class MessageChain:
    pass

@dataclass(init=False)
class Source(MessageChain):
    id: int
    time: int

    def __init__(self, obj: inputType) -> None:
        super().__init__()
        self.id = obj['id']
        self.time = obj['time']

@dataclass(init=False)
class Image(MessageChain):
    imageId: str
    url: str
    #path: Optional[str]

    def __init__(self, obj: inputType) -> None:
        super().__init__()
        self.imageId = obj['imageId']
        self.url = obj['url']

@dataclass(init=False)
class Sender(MessageChain):
    id: int
    def __init__(self, obj: inputType) -> None:
        self.id = obj['id']


