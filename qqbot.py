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
import asyncio
import datetime
import logging
import traceback
from configparser import ConfigParser
from dataclasses import dataclass
from typing import Callable, Dict, List, TypeVar, Union, Awaitable

import aiofiles
import aiohttp

import msg_types
from msg_types import MessageChain

T = TypeVar('T')

class QQBotBasicException(Exception):
    def __init__(self, obj: Dict[str, T]):
        super().__init__()
        self.obj = obj

class LoginException(QQBotBasicException): pass

class LogoutException(QQBotBasicException): pass

@dataclass
class Message:
    pass

@dataclass
class GroupMessageText(Message):
    group: int
    sender: int
    text: str
    source: int

class StopPropagation(StopAsyncIteration):
    pass

@dataclass
class MiraiConfig:
    qq_id: int
    auth_key: str
    host: str
    need_login: bool
    password: str

    @classmethod
    def create_from_config(cls, config: ConfigParser) -> 'MiraiConfig':
        self = cls(config.getint('mirai', 'qq'), config.get('mirai', 'api_key'), config.get('mirai', 'web_hook'),
                   config.getboolean('login', 'enable'), '')
        return self

class MiraiClient:
    def __init__(self, config: ConfigParser):
        self.logger: logging.Logger = logging.getLogger('qqbot')
        self.logger.setLevel(logging.DEBUG)

        self.config: MiraiConfig = MiraiConfig.create_from_config(config)

        self.session: aiohttp.ClientSession = aiohttp.ClientSession(raise_for_status=True)

        self.session_key: str = ''
        self._logined: bool = False
        self.start_time: datetime.datetime = datetime.datetime.now().replace(microsecond=0)

        self._msg_handles: List[Callable[['MiraiClient', Dict[str, T]], Awaitable[T]]] = []
        self._has_handle: bool = False

    async def start(self) -> None:
        #await self.login()
        await self.register()
        #print(self.session_key)
        await self.verify()
        await self.enable_websocket_status()

    async def register(self) -> None:
        async with self.session.post(f'http://{self.config.host}/auth', json={'authKey': self.config.auth_key}) as response:
            obj = await response.json()
            if obj['code'] != 0:
                raise LoginException(obj)
            self.session_key = obj['session']
            self._logined = True
            self.start_time = datetime.datetime.now().replace(microsecond=0)

    async def verify(self) -> None:
        async with self.session.post(f'http://{self.config.host}/verify', json={'sessionKey': self.session_key, 'qq': self.config.qq_id}) as response:
            obj = await response.json()
            if obj['code'] != 0:
                raise LoginException(obj)
            self._logined = True

    async def release(self) -> None:
        async with self.session.post(f'http://{self.config.host}/release', json={'sessionKey': self.session_key, 'qq': self.config.qq_id}) as response:
            obj = await response.json()
            if obj['code'] != 0:
                raise LoginException(obj)
            self._logined = False

    def add_header(self, header: Callable[['MiraiClient', Dict[str, T]], Awaitable[T]]) -> None:
        self._msg_handles.append(header)
        self._has_handle = True

    async def run(self) -> None:
        async with self.session.ws_connect(f'http://{self.config.host}/all?sessionKey={self.session_key}') as ws:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    self.logger.debug(msg.data)
                    for handle in self._msg_handles:
                        self._start_handle(handle, msg.data)
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    self.logger.warning('Got aiohttp.WSMsgType.ERROR, stop loop')
            await ws.close()

    async def _boostrap_start_handle(self, handle: Callable[['MiraiClient', Dict[str, T]], Awaitable[T]], msg: Dict[str, T]) -> None:
        try:
            await handle(self, msg)
        except:
            traceback.print_exc()

    def _start_handle(self, handle: Callable[['MiraiClient', Dict[str, T]], Awaitable[T]], msg: Dict[str, T]) -> None:
        if msg['data'][0].get('messageChain') is None: return
        msg_text = self.parse_group_message(msg)
        sender = msg['data'][0]['sender']['id']
        group_id = msg['data'][0]['sender']['group']['id']
        message_obj = GroupMessageText(group_id, sender, msg_text, msg['data'][0]['messageChain'][0]['id'])
        asyncio.run_coroutine_threadsafe(self._boostrap_start_handle(handle, message_obj), asyncio.get_event_loop())

    async def _poll(self) -> Dict[str, T]:
        async with self.session.get(f'http://{self.config.host}/fetchMessage', params={'sessionKey': self.session_key, 'count':1}, raise_for_status=False) as response:
            if response.status == 500:
                return {'count': 0, 'data': []}
            response.raise_for_status()
            return await response.json()

    @staticmethod
    def parse_group_message(data: Dict[str, Dict]) -> str:
        return ''.join(x['text'] for x in data['data'][0]['messageChain'] if x['type'] == 'Plain').replace('\r', '\n')

    def generate_message_params(self, group_id: int, message_chain: List[MessageChain], **kwargs) -> Dict[str, T]:
        obj = {'sessionKey': self.session_key, 'target': group_id, 'messageChain': [x.gdict() for x in message_chain]}
        obj.update(kwargs)
        return obj

    async def send_group_message(self, group_id: int, message_chain: Union[List[MessageChain], str, MessageChain], **kwargs) -> None:
        # Backward compatible
        if isinstance(message_chain, str):
            message_chain = [msg_types.Plain(message_chain)]
        elif isinstance(message_chain, MessageChain):
            message_chain = [message_chain]

        retries = 3
        while retries > 0:
            try:
                await self._send_group_message(group_id, message_chain, **kwargs)
                break
            except aiohttp.ClientResponseError as e:
                self.logger.error('Got %d error (retry times: %d)', e.status, retries)
                if e.status < 500:
                    break
            retries -= 1

    async def send_group_image(self, group_id: int, img_path: str, **kwargs) -> None:
        image = await self._upload_image(img_path)
        await self.send_group_message(group_id, [image], **kwargs)

    async def _send_group_message(self, group_id: int, message_chain: List[MessageChain], **kwargs) -> None:
        async with self.session.post(f'http://{self.config.host}/sendGroupMessage', json=self.generate_message_params(group_id, message_chain, **kwargs)):
            pass

    async def _upload_image(self, path: str, type_: str='group') -> msg_types.Image:
        async with aiofiles.open(path, 'rb') as fin:
            async with self.session.post(f'http://{self.config.host}/uploadImage', data=self.generate_upload_image_params(type_, await fin.read())) as response:
                obj = await response.json()
                return msg_types.Image(obj['imageId'])

    def generate_upload_image_params(self, type_: str, file: bytes) -> Dict[str, T]:
        return {'sessionKey': self.session_key, 'type': type_, 'img': file}

    async def stop(self) -> None:
        await self.release()

    async def check_websocket_status(self) -> bool:
        async with self.session.get(f'http://{self.config.host}/config', params={'sessionKey': self.session_key}) as response:
            obj = await response.json()
            return obj.get('enableWebsocket', False)

    async def enable_websocket_status(self) -> bool:
        if not await self.check_websocket_status():
            async with self.session.post(f'http://{self.config.host}/config', json={'sessionKey': self.session_key, 'enableWebsocket': True}):
                return True
        return False

    async def check_id_online(self) -> bool:
        async with self.session.get(f'http://{self.config.host}/managers', params={'qq': self.config.qq_id}) as response:
            obj = await response.json()
            return isinstance(obj, list)
    
    def generate_login_params(self) -> Dict[str, Union[str, List[str]]]:
        return {'authKey': self.config.auth_key, 'name': 'login', 'args': [self.config.qq_id, self.config.password]}

    async def register_login_command(self) -> None:
        async with self.session.post(f'http://{self.config.host}/command/register', json={
            "authKey": self.config.auth_key,
            "name": "login",
            "alias": ["lg", "SignIn"],
            "description": "login"
        }) as response:
            print(await response.text())

    async def do_login(self) -> None:
        async with self.session.post(f'http://{self.config.host}/command/send', json=self.generate_login_params()) as response:
            print(await response.text())
    
    async def login(self) -> None:
        self.logger.warning('Use deprecated login function, please login manually')
        if self.config.need_login:
            self.logger.debug('Request login, check is bot online')
            if not await self.check_id_online():
                await self.register_login_command()
                await self.do_login()
                self.logger.info('Login successfully')
            else:
                self.logger.info('Already logined.')

async def main():
    config = ConfigParser()
    config.read('config.ini')
    bot = MiraiClient(config)
    await bot.start()
    try:
        await bot.run()
    finally:
        await bot.stop()

if __name__ == "__main__":
    try:
        import coloredlogs
    except ModuleNotFoundError:
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(funcName)s - %(lineno)d - %(message)s')
    else:
        coloredlogs.install(logging.DEBUG, fmt='%(asctime)s,%(msecs)03d - %(levelname)8s - %(name)s - %(funcName)s - %(lineno)d - %(message)s')
    logging.getLogger('urllib3.connectionpool').setLevel(logging.INFO)
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass
