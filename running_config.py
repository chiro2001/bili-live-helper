import json
import os

from constant import Constant


class RunningConfig:
    FILENAME = 'bili-live-helper.json'
    VERSION = 0.01

    def __init__(self) -> None:
        self.config = {
            'debug': True,
            'offset': [0, 0],
            'version': RunningConfig.VERSION,
            'pool-size': 12,
            'font': '微软雅黑',
            'font-size': 13,
            'font-weight': 75,
            'font-bold': False,
            'border-width': 4,
            'room': 744432,
            'window-opacity': 0.4,
            'send-danmaku-press-time': 2.0,
            'send-danmaku-press-times': 2,
            'send-danmaku-press-key': 'ctrl',
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
                    # print(data)
                    for key in self.config:
                        # print(f"key = {'{%' + key + '%}'}, val = {str(self.config[key])}")
                        data = data.replace('{%' + key + '%}', str(self.config[key]))
                    # print(os.path.join('conf/', filename_new))
                    with open(os.path.join('conf/', filename_new), 'w', encoding='utf8') as w:
                        w.write(data)

        self.save()

    def save(self):
        self.config['debug'] = Constant.debug
        # logger.warning(f"save config: {self.config}")
        with open(self.FILENAME, "w", encoding="utf-8") as f:
            json.dump(self.config, f, sort_keys=True, indent=2, ensure_ascii=False)
