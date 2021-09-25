import json
import utils
from TCP_monitor import TCP_monitor
from OnlineHeart import OnlineHeart
from LotteryResult import LotteryResult
from Tasks import Tasks
from connect import connect
from rafflehandler import Rafflehandler
import asyncio
from login import login
from printer import Printer
from statistics import Statistics
from bilibili import bilibili
from bilibiliCilent import bilibiliClient
import threading
import biliconsole
from schedule import Schedule
import configloader
import os
import asyncio
from MultiRoom import get_area_list


async def danmaku_parser(dic: dict):
    def parse_decoration(info_content: list) -> dict:
        if info_content is None or (isinstance(info_content, list) and len(info_content) == 0):
            return {'raw': info_content}
        return {
            'raw': info_content,
            'name': info_content[1]
        }
    print(f'dic = {dic}')
    cmd = dic.get('cmd', None)
    if cmd is None:
        return
    if cmd == 'DANMU_MSG':
        info: list = dic.get('info', None)
        if info is None:
            return
        # [[0, 1, 25, 16777215, 1632549680269, 1632548590, 0, '107e34ef', 0, 0, 0, '', 0, '{}', '{}'],
        # 'none',
        # [12070196, '芝楼', 0, 0, 0, 10000, 1, ''],
        # [],
        # [14, 0, 6406234, '>50000', 0],
        # ['', ''], 0, 0, None,
        # {'ts': 1632549680, 'ct': 'C4228DDC'}, 0, 0, None, None, 0, 210]
        decoration = parse_decoration(info[3]).get('name', None)
        print(f'{f"[{decoration}]" if decoration is not None else ""}{info[2][1]}: {info[1]}')
    else:
        pass


async def test_main():
    # 744432, 4767523, 631
    client = bilibiliClient(744432, "None", danmaku_parser=danmaku_parser)
    try:
        while True:
            await client.connectServer()
            if client.connected:
                break
            print(f"re-connecting...")
    except KeyboardInterrupt:
        print(f"closing...")
        client.close_connection()


if __name__ == '__main__':
    main_loop = asyncio.get_event_loop()
    main_loop.run_until_complete(test_main())
