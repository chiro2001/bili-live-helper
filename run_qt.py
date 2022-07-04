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
import requests

from constant import Constant
import utils
from danmaku import Danmaku
from danmaku_logger import DanmakuLogger
from running_config import RunningConfig
from statistics import Statistics
from bilibiliCilent import bilibiliClient
from login import login
from PyQt5.QtCore import QPoint, Qt, QSize, pyqtSignal
from PyQt5.QtGui import QMouseEvent, QFont, QPen, QFontMetrics, QPainter, QPainterPath, QBrush, QColor, QPixmap, QImage
from PyQt5.QtWidgets import QWidget, QApplication, QMenu, qApp, QLabel, QVBoxLayout, QMainWindow, QLineEdit, \
    QPushButton, QHBoxLayout
from qtpy import QtWidgets, QtCore, QtGui
from threading import Thread, Lock
from base_logger import logger
import numpy as np
from pynput import keyboard


class DanmakuLabel(QLabel):
    def __init__(self, *args, pen_width: int = 4, **kwargs):
        super(DanmakuLabel, self).__init__(*args, **kwargs)
        # logger.warning(f"DanmakuLabel({self.text()})")
        self.fm = QFontMetrics(self.font())
        self.font_id = id(self.font())
        self.pen_width_size = pen_width
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


# noinspection PyUnresolvedReferences
class DanmakuInput(QWidget):
    signal = pyqtSignal(str)

    def __init__(self, parent: QWidget, config: RunningConfig):
        super(DanmakuInput, self).__init__(parent)
        self.running_config = config
        self.box = QHBoxLayout()
        self.box.setDirection(QVBoxLayout.LeftToRight)
        self.box.setSpacing(0)
        self.box.setContentsMargins(0, 0, 0, 0)
        self.line_edit = QLineEdit()
        self.line_edit.editingFinished.connect(self.on_finish)
        self.box.addWidget(self.line_edit)
        self.button = QPushButton("&Send")
        self.button.clicked.connect(self.on_finish)
        self.box.addWidget(self.button)
        self.setLayout(self.box)

    def on_finish(self):
        text = self.line_edit.text()
        if len(text) == 0:
            return
        self.line_edit.clearFocus()
        self.line_edit.setText("")
        # print(text)
        self.signal.emit(text)


# noinspection PyUnresolvedReferences
class Main(QWidget):
    def __init__(self, debug: bool = False):
        super(Main, self).__init__()
        try:
            self.running_config = RunningConfig()
        except json.decoder.JSONDecodeError as e:
            msg_box = QtWidgets.QMessageBox()
            msg_box.critical(self, f"配置文件{RunningConfig.FILENAME}错误", str(e), msg_box.Yes)
            sys.exit(1)
        Constant.debug = debug

        self._start_pos = None
        self._end_pos = None
        self._is_tracking = False
        self._move_lock = Lock()
        self._is_quiting = False

        self.setWindowFlags(
            Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WA_TransparentForMouseEvents)
        # 设置窗口背景透明
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setWindowOpacity(self.running_config.config.get('window-opacity', 0.4))

        # self.setMaximumWidth(520)

        self.show()

        self.lock = Lock()
        self.pressed_time = []
        self.pressed_lock = Lock()
        self.danmaku_input = DanmakuInput(self, self.running_config)
        self.danmaku_input.signal.connect(self.send_danmaku)

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

        # self.activated: bool = None

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
        self.font.setFamily(self.running_config.config.get('font', '微软雅黑'))
        # self.font.setFamily("SimHei")
        # 加粗
        self.font.setBold(self.running_config.config.get('font-bold', False))
        # 大小
        self.font.setPointSize(self.running_config.config.get('font-size', 12))
        self.font.setWeight(self.running_config.config.get('font-weight', 75))
        self.fm = QFontMetrics(self.font)

        self.resize(QSize(400, self.fm.height() * (self.running_config.config.get('pool-size', 4) + 1)))

        # self.labels = [DanmakuLabel(self) for _ in range(self.running_config.config.get('pool-size', 10) + 1)]
        self.labels = [DanmakuLabel(self, pen_width=self.running_config.config.get('border-width', 4)) for _ in
                       range(self.running_config.config.get('pool-size', 10))]
        # [0] 为即将插入的弹幕
        # 垂直布局相关属性设置

        self.vbox = QVBoxLayout()
        self.vbox_border = QVBoxLayout()
        self.vbox_border.setSpacing(0)
        self.vbox_border.setContentsMargins(0, 0, 0, 0)
        # self.vbox = QHBoxLayout()
        # self.vbox = QHBoxLayout()
        self.vbox.setSpacing(0)
        self.vbox.setContentsMargins(0, 0, 0, 0)
        # self.vbox.setDirection(QVBoxLayout.BottomToTop)
        self.vbox.setDirection(QVBoxLayout.TopToBottom)
        # self.vbox_border.addChildLayout(self.vbox)

        vbox_widget = QWidget()
        vbox_widget.setLayout(self.vbox)
        # self.vbox_boarder.addWidget(self.vbox)
        self.vbox_border.addWidget(vbox_widget)
        self.vbox_border.addWidget(self.danmaku_input)
        self.setLayout(self.vbox_border)
        # self.setLayout(self.vbox)

        self.anim: QtCore.QPropertyAnimation = None

        self.th_send_danmaku_listener = Thread(target=self.send_danmaku_listener, daemon=True)
        self.th_loop = Thread(target=self.loop, daemon=True)
        self.th_loop.start()
        self.th_insert = Thread(target=self.do_insert, daemon=True)

        self.danmaku_pool = [None for _ in range(self.running_config.config.get('pool-size', 10))]
        for i in range(self.running_config.config.get('pool-size', 10)):
            # text = f'[{i:2}]HI测试测试TEST' if i % 2 == 0 else 'TTTT'
            text = ''
            danmaku = Danmaku.from_str(text)
            self.danmaku_pool[i] = danmaku

        self.danmaku_logger = DanmakuLogger()

        self.update_labels()
        self.th_insert.start()
        self.client: bilibiliClient = None
        # th = Thread(target=self.client_loop)
        # th.setDaemon(True)
        # th.start()
        
        self.client_loop_start()

    def global_keyboard_hook_start(self):
        while not self._is_quiting:
            try:
                self.pressed_lock.acquire()
                self.pressed_time = []
                self.pressed_lock.release()
                with keyboard.Listener(
                        on_press=self.on_keyboard_press,
                        on_release=self.on_keyboard_release)as listener:
                    listener.join()
            except Exception as e:
                logger.error(f"kbk_hook(): {e.__class__.__name__} {e}")

    @staticmethod
    def get_key_code(key):
        try:
            key_code = chr(key.vk)
        except AttributeError:
            key_code = key.name
        return key_code

    def on_keyboard_press(self, key):
        key_code = self.get_key_code(key)
        # print('pressed', key_code)
        if self.running_config.config.get('send-danmaku-press-key', 'ctrl') in key_code:
            self.pressed_lock.acquire()
            self.pressed_time.append((time.time(), key_code))
            self.pressed_lock.release()

    def send_danmaku(self, text: str, max_length: int = 19, retry: int = 3):
        # 自动分割话语
        danmaku_split = [text[(start * max_length):(start + 1) * max_length] for start in
                         range(len(text) // max_length + 1)]
        if len(danmaku_split) > 1:
            logger.warning(f"long danmaku: {danmaku_split}")
        for danmaku in danmaku_split:
            resp = self.client.bilibili.send_danmaku(danmaku, roomid=self.running_config.config.get('room'))
            js = json.loads(resp.content)
            if js['code'] != 0:
                logger.warning(f'Send failed! {danmaku} {resp.text}')
                self.insert_queue.put(Danmaku.system(f"发送错误: {js.get('message')}"))
                if js.get('message') != '超出限制长度' and retry > 1:
                    self.send_danmaku(danmaku, retry=retry - 1)
            if len(danmaku_split) > 1:
                time.sleep(5)

    def on_keyboard_release(self, key):
        key_code = self.get_key_code(key)
        # print('released', key_code)
        to_show: bool = False
        self.pressed_lock.acquire()
        try:
            time_now = time.time()
            if len(self.pressed_time) > 0:
                while time_now - self.pressed_time[0][0] > self.running_config.config.get('send-danmaku-press-time',
                                                                                          2.0):
                    # print(f'deleted: {self.pressed_time[0]}')
                    self.pressed_time = self.pressed_time[1:]
            if self.running_config.config.get('send-danmaku-press-key', 'ctrl') in key_code:
                count = 0
                for i in range(len(self.pressed_time) - 1, -1, -1):
                    if self.pressed_time[i][1] == key_code:
                        count += 1
                        if count >= self.running_config.config.get('send-danmaku-press-times', 2):
                            # logger.warning(f'show()!!')
                            to_show = True
                            break
        except IndexError:
            pass
        self.pressed_lock.release()
        if to_show:
            # state: int = int(self.windowState())
            # logger.warning(f"state now: {state}, active: {Qt.WindowActive}")
            # logger.warning(f"state & Qt.WindowActive = {state & Qt.WindowActive}")
            # if state & Qt.WindowActive != 0:
            #     self.setWindowState(Qt.WindowNoState | Qt.WindowMinimized)
            # else:

            # if self.activated is None or not self.activated:
            #     self.activated = True
            #
            # else:
            #     self.activated = False
            #     self.setWindowState(Qt.WindowNoState)

            # if self.isActiveWindow():
            #     pass
            # else:
            #     self.activateWindow()
            # self.raise_()
            logger.warning(f"activate!")
            self.activateWindow()
            time.sleep(1)
            self.setWindowState(self.windowState() & Qt.WindowMinimized | Qt.WindowActive)
            time.sleep(1)
            self.showNormal()
            time.sleep(1)
            self.danmaku_input.line_edit.setFocus()

    def start_new_window(self):
        self.danmaku_input.show()

    def send_danmaku_listener(self):
        self.global_keyboard_hook_start()

    async def danmaku_parser(self, dic: dict):
        # print(f'dic = {dic}')
        cmd = dic.get('cmd', None)
        if cmd is None:
            return
        if cmd == 'DANMU_MSG':
            danmaku = Danmaku(dic)
            # logger.info(f'received: {danmaku}')
            self.insert_danmaku(danmaku, print_it=True, save=True)
        else:
            pass

    def client_loop_start(self):
        # asyncio.create_task(self.client_loop())
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.client_loop())
        # asyncio.ensure_future(self.client_loop(), loop=_loop_main_window)

    def log(self, text: str, console: bool = True, **kwargs):
        if console:
            print('[SYS]', text)
        danmaku: Danmaku = Danmaku.system(text)
        self.insert_danmaku(danmaku=danmaku, save=False, **kwargs)

    async def client_loop(self):
        self.log('加载往期弹幕...')
        old_danmaku = self.danmaku_logger.tail(count=self.running_config.config.get('pool-size', 10))
        old_danmaku.reverse()
        for danmaku in old_danmaku:
            # print(danmaku)
            self.insert_danmaku(danmaku=danmaku, save=False)
        self.log('正在登录账号...')
        try:
            login_result = await login().login_new()
        except Exception as e:
            traceback.print_exception()
        if login_result is not None:
            self.log('账号登录失败!')
            logger.warning(f"{login_result}")
        else:
            self.log('账号登录成功')
        self.log('正在连接服务器...')
        try:
            self.client = bilibiliClient(self.running_config.config['room'], "None", danmaku_parser=self.danmaku_parser)
        except Exception as e:
            self.log(f'服务器连接失败！{e.__class__.__name__}: {e}')
            return
        self.log(f'服务器连接成功')
        # resp = self.client.bilibili.send_danmaku('HI!!', roomid=744432)
        # logger.warning(f'{resp.text}')
        self.th_send_danmaku_listener.start()
        try:
            while True:
                await self.client.connectServer()
                if self.client.connected:
                    break
                # logger.warning(f"re-connecting...")
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

    def insert_danmaku(self, danmaku: Danmaku, save: bool = True, show: bool = True, **kwargs):
        if save:
            self.danmaku_logger.log(danmaku, **kwargs)
        if show:
            self.insert_queue.put(danmaku)

    def do_insert(self):
        # vbox_size = [self.vbox.geometry().width(), self.vbox.geometry().height()]
        # if vbox_size[0] == vbox_size[1] == 0:
        #     time.sleep(0.1)
        #     self.do_insert()
        
        # print(f'do_insert start.')
        danmaku = self.insert_queue.get(block=True)
        # logger.warning(f"got danmaku to insert: {danmaku}")
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
                time.sleep(20)
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
    main_ = Main(debug=True)
    # _conf = RunningConfig()
    # window_ = DanmakuInput(_conf)
    # window_.show()
    sys.exit(app.exec_())
