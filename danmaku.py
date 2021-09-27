import copy
import datetime
import time


class Danmaku:
    class Decoration:
        def __init__(self, available: bool = False, name: str = '', level: int = 0, raw: list = None,
                     data: dict = None):
            if data is not None:
                self.name, self.level, self.available, self.raw = data.get('name'), \
                                                                  data.get('level'), \
                                                                  data.get('available'), \
                                                                  data.get('raw')
            else:
                self.name, self.level = name, level
                self.available = available
                self.raw: list = raw if raw is not None else []

        @staticmethod
        def parse(info_content: list):
            if info_content is None or (isinstance(info_content, list) and len(info_content) == 0):
                return Danmaku.Decoration(available=False, raw=info_content)
            return Danmaku.Decoration(available=True, name=info_content[1], level=0, raw=info_content)

        @staticmethod
        def load(data: dict):
            return Danmaku.Decoration(data=data)

    def __init__(self, dic: dict = None, data: dict = None):
        # super().__init__()
        if data is not None:
            self.cmd = data.get('cmd', None)
            self.decoration = Danmaku.Decoration.load(data.get('decoration'))
            self.name = data.get('name')
            self.text = data.get('text')
            self.receive_time = data.get('receive_time')
        else:
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
                [], text, [0, name], [None, deco] if deco is not None else [], [], [], 0, 0, None, {}, 0, 0, None, None,
                0, 0
            ]
        })

    @staticmethod
    # def from_str(text: str, name: str = 'Chiro', deco: str = '番茄大'):
    def system(text: str):
        return Danmaku.from_str(text, name='消息', deco='系统')

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

    @staticmethod
    def load(data: dict):
        return Danmaku(data=data)
