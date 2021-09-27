import json
import traceback

import pymongo

from base_logger import logger
from danmaku import Danmaku


class DanmakuLogger:
    DEFAULT_FILENAME_DATA_TXT = 'danmaku_data.log.txt'
    DEFAULT_FILENAME_TEXT_TXT = 'danmaku_text.log.txt'
    DEFAULT_DB = 'bili_live_helper'
    DEFAULT_COL = 'danmaku'

    def __init__(self, **kwargs):
        self.client = pymongo.MongoClient()
        self.filename_data = kwargs.get('filename_data', DanmakuLogger.DEFAULT_FILENAME_DATA_TXT)
        self.filename_text = kwargs.get('filename_text', DanmakuLogger.DEFAULT_FILENAME_TEXT_TXT)
        self.db = self.client[kwargs.get('database', DanmakuLogger.DEFAULT_DB)]
        self.col = self.db[kwargs.get('collection', DanmakuLogger.DEFAULT_COL)]

    def log(self, danmaku: Danmaku, print_it: bool = True):
        if print_it:
            logger.info(f'{str(danmaku)}')
        try:
            with open(self.filename_data, 'a+', encoding='utf8') as f:
                f.write(json.dumps(danmaku.dump()) + "\n")
            with open(self.filename_text, 'a+', encoding='utf8') as f:
                f.write(f'[{str(danmaku.receive_time).split(".")[0]}] {str(danmaku)}\n')
        except Exception as e:
            logger.error(f"{e.__class__.__name__} when logging danmaku")
            traceback.print_exc()
        try:
            self.col.insert_one(danmaku.__getstate__())
        except Exception as e:
            logger.error(f"{e.__class__.__name__} when logging danmaku")
            traceback.print_exc()

    # 获取最近几条内容
    def tail(self, count: int = 10) -> list:
        data = self.col.find({}, {'_id': 0}).sort("receive_time", -1).limit(count)
        danmaku_tail = [Danmaku.load(d) for d in data]
        # print(danmaku_tail)
        return danmaku_tail
