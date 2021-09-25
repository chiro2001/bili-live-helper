from bilibili import bilibili
from printer import Printer
from connect import connect
import time
import random
import re
import datetime


def adjust_for_chinese(str):
    SPACE = '\N{IDEOGRAPHIC SPACE}'
    EXCLA = '\N{FULLWIDTH EXCLAMATION MARK}'
    TILDE = '\N{FULLWIDTH TILDE}'

    # strings of ASCII and full-width characters (same order)
    west = ''.join(chr(i) for i in range(ord(' '), ord('~')))
    east = SPACE + ''.join(chr(i) for i in range(ord(EXCLA), ord(TILDE)))

    # build the translation table
    full = str.maketrans(west, east)
    str = str.translate(full).rstrip().split('\n')
    md = '{:^10}'.format(str[0])
    return md.translate(full)


def CurrentTime():
    currenttime = int(time.mktime(datetime.datetime.now().timetuple()))
    return str(currenttime)


def seconds_until_tomorrow():
    today = datetime.date.today()
    tomorrow = today + datetime.timedelta(days=1)
    tomorrow_start_time = int(time.mktime(time.strptime(str(tomorrow), '%Y-%m-%d')))
    current_time = int(time.mktime(datetime.datetime.now().timetuple()))
    return tomorrow_start_time - current_time


async def fetch_medal(printer=True):
    if printer:
        Printer().printer('查询勋章信息', "Info", "green")
        print(
            '{} {} {:^12} {:^10} {} {:^6} '.format(adjust_for_chinese('勋章'), adjust_for_chinese('主播昵称'), '亲密度',
                                                   '今日的亲密度',
                                                   adjust_for_chinese('排名'), '勋章状态'))
    dic_worn = {'1': '正在佩戴', '0': '待机状态'}
    for _ in range(3):
        response = await bilibili().request_fetchmedal()
        json_response = await response.json(content_type=None)
        if json_response['code']:
            continue
        # 有时候dict获取不完整，包括最后一项"roomid"的后半部分缺失
        elif all(["roomid" not in medal for medal in json_response['data']['fansMedalList']]):
            continue
        else:
            break
    roomid = 0
    today_feed = 0
    day_limit = 0
    if json_response['code'] == 0:
        for i in json_response['data']['fansMedalList']:
            if i['status'] == 1:
                roomid = i.get('roomid', 0)  # 主站获取的勋章没有直播间
                today_feed = i['today_feed']
                day_limit = i['day_limit']
            if printer:
                print(
                    '{} {} {:^14} {:^14} {} {:^6} '.format(adjust_for_chinese(i['medal_name'] + '|' + str(i['level'])),
                                                           adjust_for_chinese(i['anchorInfo']['uname']),
                                                           str(i['intimacy']) + '/' + str(i['next_intimacy']),
                                                           str(i['todayFeed']) + '/' + str(i['dayLimit']),
                                                           adjust_for_chinese(str(i['rank'])),
                                                           dic_worn[str(i['status'])]))
        return roomid, today_feed, day_limit


async def fetch_user_info():
    response = await bilibili().request_fetch_user_info()
    response_ios = await bilibili().request_fetch_user_infor_ios()
    print('[{}] 查询用户信息'.format(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))))
    json_response = await response.json()
    json_response_ios = await response_ios.json()
    if json_response_ios['code'] == 0:
        gold_ios = json_response_ios['data']['gold']
    else:
        # {'code': 3, 'msg': 'user no login', 'message': 'user no login', 'data': []}
        gold_ios = None
    # print(json_response_ios)
    if (json_response['code'] == 0):
        data = json_response['data']
        # print(data)
        userInfo = data['userInfo']
        userCoinIfo = data['userCoinIfo']
        uname = userInfo['uname']
        achieve = data['achieves']
        user_level = userCoinIfo['user_level']
        silver = userCoinIfo['silver']
        gold = userCoinIfo['gold']
        identification = bool(userInfo['identification'])
        mobile_verify = bool(userInfo['mobile_verify'])
        user_next_level = userCoinIfo['user_next_level']
        user_intimacy = userCoinIfo['user_intimacy']
        user_next_intimacy = userCoinIfo['user_next_intimacy']
        user_level_rank = userCoinIfo['user_level_rank']
        billCoin = userCoinIfo['coins']
        bili_coins = userCoinIfo['bili_coins']
        print('# 用户名', uname)
        print('# 手机认证状况 {} | 实名认证状况 {}'.format(mobile_verify, identification))
        print('# 银瓜子', silver)
        print('# 通用金瓜子', gold)
        print('# ios可用金瓜子', gold_ios)
        print('# 硬币数', billCoin)
        print('# B币数', bili_coins)
        print('# 成就值', achieve)
        print('# 等级值', user_level, '———>', user_next_level)
        print('# 经验值', user_intimacy)
        print('# 剩余值', user_next_intimacy - user_intimacy)
        arrow = int(user_intimacy * 30 / user_next_intimacy)
        line = 30 - arrow
        percent = user_intimacy / user_next_intimacy * 100.0
        process_bar = '# [' + '>' * arrow + '-' * line + ']' + '%.2f' % percent + '%'
        print(process_bar)
        print('# 等级榜', user_level_rank)


async def fetch_bag_list(verbose=False, bagid=None, printer=True):
    response = await bilibili().request_fetch_bag_list()
    temp = []
    gift_list = []
    json_response = await response.json()
    if printer == True:
        print('[{}] 查询可用礼物'.format(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))))
    for i in range(len(json_response['data']['list'])):
        bag_id = (json_response['data']['list'][i]['bag_id'])
        gift_id = (json_response['data']['list'][i]['gift_id'])
        gift_num = str((json_response['data']['list'][i]['gift_num'])).center(4)
        gift_name = json_response['data']['list'][i]['gift_name']
        expireat = (json_response['data']['list'][i]['expire_at'])
        if expireat != 0:
            left_time = (expireat - int(CurrentTime()))
            left_days = (expireat - int(CurrentTime())) / 86400
            gift_list.append([gift_id, gift_num, bag_id, expireat])
        else:
            left_time = 999999999999999999
            left_days = 999999999999999999
            gift_list.append([gift_id, gift_num, bag_id, expireat])
        if bagid is not None:
            if bag_id == int(bagid):
                return gift_id
        else:
            if verbose:
                print("# 编号为" + str(bag_id) + '的' + gift_name + 'X' + gift_num, '(在' + str((left_days)) + '天后过期)')
            elif printer == True:
                print("# " + gift_name + 'X' + gift_num, '(在' + str((left_days)) + '天后过期)')

        if 0 < int(left_time) < 43200:  # 剩余时间少于半天时自动送礼
            temp.append([gift_id, gift_num, bag_id, expireat])
    # print(temp)
    return temp, gift_list


async def check_taskinfo():
    response = await bilibili().request_check_taskinfo()
    json_response = await response.json(content_type=None)
    # print(json_response)
    if json_response['code'] == 0:
        data = json_response['data']
        box_info = data['box_info']
        sign_info = data['sign_info']
        live_time_info = data['live_time_info']
        print('每日签到：')
        if sign_info['status'] == 1:
            print('# 该任务已完成')
        else:
            print('# 该任务未完成')

        # sign_info['signDaysList']已永远为空
        # if sign_info['signDaysList'] == list(range(1, sign_info['curDay'] + 1)):
        #     print('# 当前全勤')
        # else:
        #     print('# 出现断签')

        print('直播奖励：')
        if live_time_info['status'] == 1:
            print('# 已完成')
        else:
            print('# 未完成(目前本项目未实现自动完成直播任务)')


async def send_gift_web(roomid, giftid, giftnum, bagid):
    response = await bilibili().request_check_room(roomid)
    json_response = await response.json()
    if json_response["code"] != 0:
        Printer().printer(f"获取送礼房间{roomid}信息出错: {json_response}", "Error", "red")
        return
    ruid = json_response['data']['uid']
    biz_id = json_response['data']['room_id']
    response1 = await bilibili().request_send_gift_web(giftid, giftnum, bagid, ruid, biz_id)
    json_response1 = await response1.json()
    if json_response1['code'] == 0:
        Printer().printer(f"送出礼物{json_response1['data']['gift_name']}x{json_response1['data']['gift_num']}到{roomid}房间",
                          "Info",
                          "green")
    else:
        Printer().printer(f"错误:{json_response1['msg']}", "Error", "red")


async def check_room_true(roomid):
    response = await bilibili().request_check_room(roomid)
    json_response = await response.json(content_type=None)

    if json_response['code'] == 0:
        data = json_response['data']
        param1 = data['is_hidden']
        param2 = data['is_locked']
        param3 = data['encrypted']
        return param1, param2, param3
    else:
        Printer().printer(f"获取房间信息出错: {json_response}", "Error", "red")
        return [None]


async def check_up_name(name):
    roomid = 0
    response = await bilibili().query_guard(name)
    json_response = await response.json()
    while json_response['code'] == -111:
        temp = random.randint(0, len(name) - 1)
        split_str = name[temp:min(temp + 2, len(name))]
        response = await bilibili().query_guard(split_str)
        json_response = await response.json()
    for i in range(0, len(json_response['result'])):
        uname = str(json_response['result'][i]['uname'])
        temp = re.compile(r'<[^>]+>', re.S)
        ser_name = temp.sub('', uname)
        if str(ser_name) == str(name):
            roomid = json_response['result'][i]['roomid']
            return roomid
    return roomid


async def reconnect(area=None):
    if area is not None:
        await connect().recreate(area)
    await connect().check_connect(area)


async def check_area_list(area_list, **kwargs):
    for area_id in area_list:
        await connect().check_area(area_id, **kwargs)


async def fetch_gray_medals():
    gray_medals = []
    response = await bilibili().request_fetchmedal()
    json_response = await response.json(content_type=None)
    for i in range(0, len(json_response['data']['fansMedalList'])):
        if json_response['data']['fansMedalList'][i]['is_lighted'] == 0:
            gray_medal = {}
            gray_medal['medal_name'] = json_response['data']['fansMedalList'][i]['medal_name']
            gray_medal['roomid'] = json_response['data']['fansMedalList'][i]['roomid']
            gray_medals.append(gray_medal)
    return gray_medals


async def get_all_of_my_hearts():
    hearts = []
    response = await bilibili().request_fetch_bag_list()
    json_response = await response.json(content_type=None)
    for i in range(len(json_response['data']['list'])):
        gift_name = json_response['data']['list'][i]['gift_name']
        gift_id = (json_response['data']['list'][i]['gift_id'])
        if gift_name == "小心心" or gift_id == 30607:
            expireat = json_response['data']['list'][i]['expire_at']
            bag_id = json_response['data']['list'][i]['bag_id']
            gift_num = json_response['data']['list'][i]['gift_num']
            for _ in range(gift_num):
                hearts.append([bag_id, 1, expireat])

    return hearts


async def refresh_all_gray_medals():
    gray_medals = await fetch_gray_medals()
    hearts = await get_all_of_my_hearts()
    if hearts:
        for gray_medal in gray_medals:
            if len(hearts) > 0:
                heart = hearts.pop()
                await send_gift_web(gray_medal['roomid'], 30607, 1, heart[0])
            else:
                pass
    else:
        pass


async def refresh_medals_by_roomids(roomids):
    hearts = await get_all_of_my_hearts()
    if hearts:
        for roomid in roomids:
            if len(hearts) > 0:
                heart = hearts.pop()
                await send_gift_web(roomid, 30607, 1, heart[0])
            else:
                pass
    else:
        pass
