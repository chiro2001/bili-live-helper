import asyncio
import datetime
import os
import copy
import json
import sys
import time
import traceback
import webbrowser
from queue import Queue
import qasync
import pymongo

from constant import Constant
import utils
from statistics import Statistics
from bilibiliCilent import bilibiliClient
from PyQt5.QtCore import QPoint, Qt, QSize
from PyQt5.QtGui import QMouseEvent, QFont, QPen, QFontMetrics, QPainter, QPainterPath, QBrush, QColor, QPixmap, QImage
from PyQt5.QtWidgets import QWidget, QApplication, QMenu, qApp, QLabel, QVBoxLayout
from qtpy import QtWidgets, QtCore, QtGui
from threading import Thread, Lock
from base_logger import logger
import numpy as np


class RunningConfig:
    FILENAME = 'bili-live-helper.json'
    VERSION = 0.11

    def __init__(self) -> None:
        self.config = {
            'debug': True,
            'offset': [0, 0],
            'version': 0.01,
            'room': 744432,
            'username': '',
            'password': ''
        }
        self.load()

    def load(self):
        try:
            with open(self.FILENAME, "r", encoding="utf-8") as f:
                c = json.load(f)
                if 'version' in c:
                    if c['version'] > RunningConfig.VERSION:
                        raise RuntimeError(f"Newer config file detected ({c['version']})")
                    else:
                        del c['version']
                self.config.update(c)
        except FileNotFoundError:
            pass
        Constant.debug = self.config['debug']
        # 替换 conf
        file_list = os.listdir('conf/')
        for filename in file_list:
            if filename.endswith('.template.conf'):
                with open(os.path.join('conf/', filename), 'r', encoding='utf8') as f:
                    filename_new = filename.replace('.template.conf', '.conf')
                    data = f.read()
                    for key in self.config:
                        data.replace('{%' + key + '%}', str(self.config[key]))
                    with open(os.path.join('conf/', filename_new), 'w', encoding='utf8') as w:
                        w.write(data)

        self.save()

    def save(self):
        self.config['debug'] = Constant.debug
        # logger.warning(f"save config: {self.config}")
        with open(self.FILENAME, "w", encoding="utf-8") as f:
            json.dump(self.config, f, sort_keys=True, indent=2, ensure_ascii=False)


class Danmaku(str):
    class Decoration:
        def __init__(self, available: bool = False, name: str = '', level: int = 0, raw: list = None):
            self.name, self.level = name, level
            self.available = available
            self.raw: list = raw if raw is not None else []

        @staticmethod
        def parse(info_content: list):
            if info_content is None or (isinstance(info_content, list) and len(info_content) == 0):
                return Danmaku.Decoration(available=False, raw=info_content)
            return Danmaku.Decoration(available=True, name=info_content[1], level=0, raw=info_content)

    def __init__(self, dic: dict):
        super().__init__()
        self.cmd = dic.get('cmd', None)
        info: list = dic.get('info', None)
        if info is None:
            raise ValueError(f"Need dic[cmd, info], got: {dic}")
        if self.cmd != 'DANMU_MSG':
            raise TypeError(f"Need dic[cmd=DANMU_MSG]! got: {self.cmd}")
        self.decoration: Danmaku.Decoration = Danmaku.Decoration.parse(info[3])
        try:
            self.name: str = info[2][1]
            self.text: str = info[1]
        except IndexError:
            raise ValueError(f"Error info format: {info}")
        self.receive_time = datetime.datetime.now()

    @staticmethod
    def parse(dic: dict):
        return Danmaku(dic)

    @staticmethod
    # def from_str(text: str, name: str = 'Chiro', deco: str = '番茄大'):
    def from_str(text: str, name: str = '', deco: str = None):
        return Danmaku({
            'cmd': "DANMU_MSG",
            'info': [
                [], text, [0, name], [None, deco] if deco is not None else [], [], [], 0, 0, None, {}, 0, 0, None, None, 0, 0
            ]
        })

    def __str__(self):
        return f"{'' if not self.decoration.available else f'[{self.decoration.name}]'}{self.name}: {self.text}"

    def __getstate__(self) -> dict:
        data = copy.deepcopy(self.__dict__)
        data['decoration'] = self.decoration.__dict__
        return data

    def dump(self) -> str:
        data = self.__getstate__()
        data['receive_time'] = str(self.receive_time)
        data['receive_time_utc'] = time.mktime(self.receive_time.timetuple())
        return data


class DanmakuLabel(QLabel):
    def __init__(self, *args, **kwargs):
        super(DanmakuLabel, self).__init__(*args, **kwargs)
        # logger.warning(f"DanmakuLabel({self.text()})")
        self.fm = QFontMetrics(self.font())
        self.font_id = id(self.font())
        self.pen_width_size = kwargs.get('pen_width', 4)
        self.danmaku: Danmaku = None
        self.cache_image: QPixmap = None
        self.cache_id: int = 0
        self.fixed_size: QSize = QSize(1, 1)

    def setText(self, danmaku: str) -> None:
        if isinstance(danmaku, Danmaku):
            self.danmaku = danmaku
            super(DanmakuLabel, self).setText(str(danmaku))
            # text = str(danmaku)
            text = danmaku.name
        else:
            super(DanmakuLabel, self).setText(danmaku)
            text = self.text()
        if len(text) == 0:
            self.setStyleSheet('')
        else:
            self.setStyleSheet('background-color: rgba(255, 251, 100, 60); color:rgb(255, 255, 255, 200)')
        self.adjustSize()

    def update_font_metrics(self):
        if self.font_id != id(self.font()):
            # logger.warning(f"updated font!")
            self.fm = QFontMetrics(self.font())
            self.font_id = id(self.font())

    def adjustSize(self) -> None:
        super(DanmakuLabel, self).adjustSize()
        self.setMargin(0)
        self.update_font_metrics()
        self.fixed_size = QSize(self.fm.width(str(self.danmaku)) + self.pen_width() * 2, self.fm.height())
        self.setFixedSize(self.fixed_size)
        # logger.warning(f'self.fixed_size = {self.fixed_size}')

    def pen_width(self) -> int:
        return self.pen_width_size

    def set_pen_width(self, pen_width: int):
        self.pen_width_size = pen_width

    def get_new_image(self):
        return QPixmap(QImage(np.zeros(shape=(self.fixed_size.height(), self.fixed_size.width(), 4), dtype=np.uint8),
                              self.fixed_size.width(), self.fixed_size.height(), QImage.Format_RGBA8888))

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        super(DanmakuLabel, self).paintEvent(event)
        self.adjustSize()
        if self.cache_image is None:
            self.cache_image = self.get_new_image()
            self.setPixmap(self.cache_image)
        # return

        if self.danmaku is not None and len(self.danmaku.name) > 0:
            if self.cache_id == id(self.danmaku):
                # logger.warning(f"{self.danmaku}, {id(self.danmaku)}, {self.text()}")
                # logger.warning(f"DanmakuLabel.paintEvent({self.text()}) CACHED")
                self.setPixmap(self.cache_image)
                pass
            else:
                # logger.warning(f"DanmakuLabel.paintEvent({self.danmaku}) UPDATED")
                colors = [QColor(127, 127, 127) for _ in range(4)]
                colors[1] = QColor(255, 127, 0)
                colors[3] = QColor(255, 255, 255)
                texts = ['' for _ in range(4)]
                texts[0] = '[' if self.danmaku.decoration.available else ''
                texts[1] = self.danmaku.decoration.name if self.danmaku.decoration.available else ''
                texts[2] = f"]{self.danmaku.name}: " if self.danmaku.decoration.available else f"{self.danmaku.name}: "
                texts[3] = self.danmaku.text
                painter = QPainter()
                # print(texts)
                self.cache_image = self.get_new_image()
                painter.begin(self.cache_image)
                # painter.begin(self)
                start_pos = 0
                for i in range(4):
                    path = QPainterPath()
                    path.addText(self.pen_width() + start_pos, self.fm.ascent(), self.font(), texts[i])
                    start_pos += self.fm.width(texts[i])
                    painter.setRenderHint(QPainter.Antialiasing)
                    pen = QPen(Qt.black)
                    pen.setWidth(self.pen_width())
                    painter.strokePath(path, pen)
                    painter.fillPath(path, QBrush(colors[i]))
                painter.end()
                self.cache_id = id(self.danmaku)
                self.setPixmap(self.cache_image)
        else:
            painter = QPainter()
            painter.begin(self)
            path = QPainterPath()
            path.addText(self.pen_width(), self.fm.ascent(), self.font(), self.text())
            painter.setRenderHint(QPainter.Antialiasing)
            pen = QPen(Qt.black)
            pen.setWidth(self.pen_width())
            painter.strokePath(path, pen)
            painter.fillPath(path, QBrush(QColor(255, 255, 255)))
            painter.end()


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

    def log(self, danmaku: Danmaku):
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


class Main(QWidget):
    def __init__(self, debug: bool = False):
        super().__init__()
        try:
            self.running_config = RunningConfig()
        except json.decoder.JSONDecodeError as e:
            msg_box = QtWidgets.QMessageBox()
            msg_box.critical(QWidget=self, p_str=f"配置文件{RunningConfig.FILENAME}错误", p_str_1=str(e), buttons=msg_box.Yes)
            sys.exit(1)
        Constant.debug = debug

        self._start_pos = None
        self._end_pos = None
        self._is_tracking = False
        self._move_lock = Lock()
        self._is_quiting = False

        self.setWindowFlags(Qt.FramelessWindowHint |
                            QtCore.Qt.WindowStaysOnTopHint | Qt.Tool)
        # 设置窗口背景透明
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setWindowOpacity(0.7)
        self.show()

        self.lock = Lock()

        try:
            pass
        except Exception as e:
            msg_box = QtWidgets.QMessageBox()
            msg_box.critical(self, f"无法加载{self.running_config.config['target']}", str(e), msg_box.Yes | msg_box.Ignore)
            if msg_box.Ignore:
                self.actor.load(self.running_config.config['target'], generate=True)
            else:
                sys.exit(1)

        self.insert_queue: Queue = Queue()

        screen_rect = app.desktop().screenGeometry()
        # width, height = screen_rect.width(), screen_rect.height()
        self.running_config.config['offset'][0] = min(self.running_config.config['offset'][0],
                                                      screen_rect.width() - 480)
        self.running_config.config['offset'][1] = min(self.running_config.config['offset'][1],
                                                      screen_rect.height() - 480)
        self.running_config.save()
        self.move(*self.running_config.config['offset'])
        # self.move(0, 0)

        self.font = QFont()
        # 字体
        self.font.setFamily('微软雅黑')
        # 加粗
        # self.font.setBold(True)
        # 大小
        self.font.setPointSize(13)
        self.font.setWeight(75)
        self.fm = QFontMetrics(self.font)

        self.labels = [DanmakuLabel(self) for _ in range(self.running_config.config.get('pool_size', 10) + 1)]
        # [0] 为即将插入的弹幕
        # 垂直布局相关属性设置
        self.vbox = QVBoxLayout()
        # self.vbox_border = QVBoxLayout()
        # self.vbox = QHBoxLayout()
        self.vbox.setSpacing(0)
        self.vbox.setContentsMargins(0, 0, 0, 0)
        # self.vbox.setDirection(QVBoxLayout.BottomToTop)
        self.vbox.setDirection(QVBoxLayout.TopToBottom)
        # self.vbox_border.addChildLayout(self.vbox)

        # self.setLayout(self.vbox_border)
        self.setLayout(self.vbox)

        self.anim: QtCore.QPropertyAnimation = None

        self.th_loop = Thread(target=self.loop, daemon=True)
        self.th_loop.start()
        self.th_insert = Thread(target=self.do_insert, daemon=True)

        self.danmaku_pool = [None for _ in range(self.running_config.config.get('pool_size', 10))]
        for i in range(self.running_config.config.get('pool_size', 10)):
            # text = f'[{i:2}]HI测试测试TEST' if i % 2 == 0 else 'TTTT'
            text = ''
            danmaku = Danmaku.from_str(text)
            self.danmaku_pool[i] = danmaku

        self.danmaku_logger = DanmakuLogger()

        self.update_labels()
        self.th_insert.start()
        self.client: bilibiliClient = None
        self.client_loop_start()

    async def danmaku_parser(self, dic: dict):
        # print(f'dic = {dic}')
        cmd = dic.get('cmd', None)
        if cmd is None:
            return
        if cmd == 'DANMU_MSG':
            danmaku = Danmaku(dic)
            logger.info(f'received: {danmaku}')
            self.insert_danmaku(danmaku)
        else:
            pass

    def client_loop_start(self):
        # asyncio.create_task(self.client_loop())
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.client_loop())
        # asyncio.ensure_future(self.client_loop(), loop=_loop_main_window)

    async def client_loop(self):
        self.client = bilibiliClient(self.running_config.config['room'], "None", danmaku_parser=self.danmaku_parser)
        try:
            while True:
                await self.client.connectServer()
                if self.client.connected:
                    break
                logger.warning(f"re-connecting...")
        except KeyboardInterrupt:
            logger.warning(f"closing...")
            self.client.close_connection()

    def update_labels(self):
        for i in range(len(self.labels)):
            try:
                danmaku = self.danmaku_pool[i]
            except IndexError:
                danmaku = Danmaku.from_str('')
            label = self.labels[i]
            label.setAlignment(Qt.AlignLeft)
            label.setText(danmaku)
            label.setFont(self.font)
            self.vbox.addWidget(label, 0, Qt.AlignLeft)

    def insert_danmaku(self, danmaku: Danmaku):
        self.danmaku_logger.log(danmaku)
        self.insert_queue.put(danmaku)

    def do_insert(self):
        # print(f'do_insert start.')
        danmaku = self.insert_queue.get(block=True)
        # logger.warning(f"got danmaku to insert: {danmaku}")
        vbox_size = [self.vbox.geometry().width(), self.vbox.geometry().height()]
        if vbox_size[0] == vbox_size[1] == 0:
            time.sleep(0.1)
            self.do_insert()
        # logger.warning(f'vbox_size = {vbox_size}')
        self.lock.acquire()
        self.danmaku_pool = [danmaku, *(self.danmaku_pool[:-1])]
        self.vbox.removeWidget(self.labels[-1])
        self.labels = [self.labels[-1], *(self.labels[:-1])]
        self.labels[0].setText(danmaku)
        self.vbox.addWidget(self.labels[0], 0, Qt.AlignLeft)
        self.lock.release()

        # self.anim = QtCore.QPropertyAnimation(self.vbox, b'geometry')
        # self.anim.setDuration(1500)
        # # start, end = QRect(0, self.labels[0].height(), *vbox_size), QRect(0, 0, *vbox_size)
        # # logger.warning(f'start: {start}, end: {end}')
        # # self.anim.setStartValue(start)
        # end = self.vbox.geometry()
        # end = QRect(end.x(), end.y() + 28, end.width(), end.height())
        # logger.warning(f'end: {end}')
        # self.anim.setEndValue(end)
        # self.anim.start()
        # time.sleep(1.5)

        # self.insert_queue.task_done()
        # print(f'do_insert done.')
        self.do_insert()

    # 重写移动事件
    def mouseMoveEvent(self, e: QMouseEvent):
        self._move_lock.acquire()
        self._end_pos = e.pos() - self._start_pos
        self.move(self.pos() + self._end_pos)
        self._move_lock.release()

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.LeftButton:
            self._move_lock.acquire()
            self._is_tracking = True
            self._start_pos = QPoint(e.x(), e.y())
            self._move_lock.release()

        if e.button() == Qt.RightButton:
            menu = QMenu(self)
            debug_action = menu.addAction(f"{'关闭' if Constant.debug else '打开'}调试")
            about_action = menu.addAction("关于")
            quit_action = menu.addAction("退出")
            action = menu.exec_(self.mapToGlobal(e.pos()))
            if action == quit_action:
                self.exit()
            elif action == about_action:
                webbrowser.open('https://github.com/chiro2001/bili-live-helper')
            elif action == debug_action:
                Constant.debug = not Constant.debug
                self.running_config.save()

    def mouseReleaseEvent(self, e: QMouseEvent):
        self._move_lock.acquire()
        if self._end_pos is None:
            self._move_lock.release()
            return
        target: QPoint = self.pos() + self._end_pos
        self.running_config.config['offset'] = [target.x(), target.y()]
        self.running_config.save()
        if e.button() == Qt.LeftButton:
            self._is_tracking = False
            self._start_pos = None
            self._end_pos = None
        if e.button() == Qt.RightButton:
            self._is_tracking = False
            self._start_pos = None
            self._end_pos = None
        self._move_lock.release()

    def loop(self):
        try:
            ii = 1
            while True:
                # self.insert_danmaku(Danmaku.from_str(f'Test: [{ii:2}]'))
                ii += 1
                # print(f'insert done')
                time.sleep(2)
        except Exception as e:
            logger.error(e)
            if Constant.debug:
                traceback.print_exc()
            if not Constant.debug:
                msg_box = QtWidgets.QMessageBox()
                msg_box.critical(self, f"未知错误({e.__class__.__name__})", str(e), msg_box.Yes)
                self.exit()

    def exit(self):
        self._is_quiting = True
        qApp.quit()
        sys.exit(1)


if __name__ == '__main__':
    app = qasync.QApplication(sys.argv)
    _loop_main_window = qasync.QEventLoop(app)
    asyncio.set_event_loop(_loop_main_window)
    ex = Main(debug=True)
    sys.exit(app.exec_())
