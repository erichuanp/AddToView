import json
import os
import time
from datetime import datetime

import requests
import Login

# region 初始化
cookie_filename = ''
UID = ''
Viewed_txt = []
session = requests.session()  # 开启会话
cookies = ''


class Video:
    def __init__(self, VideoTitle, BVNumber, ReleaseTime, Uploader):
        self.VideoTitle = VideoTitle
        self.BVNumber = BVNumber
        self.ReleaseTime = ReleaseTime
        self.Uploader = Uploader

    def __str__(self):
        return f"Video Title (视频标题): {self.VideoTitle}, BV Number (BV号): {self.BVNumber}, Release Time (发布时间): {self.ReleaseTime}, Uploader (上传者): {self.Uploader}"


# 读取cookie
def scan(cookie_json):
    for rtn in os.listdir('.'):
        if rtn.find(cookie_json) != -1:
            return rtn
    return 0


while scan('_cookie.json') == 0:
    Login.login_code()
cookie_filename = scan('_cookie.json')

with open(cookie_filename, 'r', encoding='utf-8') as f:
    cookies = json.load(f)


def init():
    global Viewed_txt
    global cookies
    global UID
    global cookie_filename
    # 创建或为读取文件做准备
    configs = {
        'metadata': {
            '注意': 'metadata什么都不影响，仅作注释用。请编辑config，0代表否，1代表是。',
            'BilibiliLocation': '如果正在使用Bilibili的Windows客户端，可以输入其地址，请用引号括起来。',
            'AskUser': '是否询问用户，启用该项后，程序不会读取config内容，而是询问用户。',
            'Remove': '是否移除已观看的视频？',
            'Add': '是否添加未观看的视频？',
            'PrintLogs': '是否输出运行日志？',
            'AutoExit': '是否自动关闭程序？',
            'OpenBilibili': '是否打开哔哩哔哩？',
            'DaysBefore': '需要多少天以前到现在的视频？请输入正确的天数而不是0或1，默认是三天之内。',
            'BlackList': '标题包括的关键词，一旦标题中包含这些关键词，则不会被添加或观看。'
        },
        'config': {
            'BilibiliLocation': '',
            'AskUser': 1,
            'Remove': 1,
            'Add': 1,
            'PrintLogs': 1,
            'OpenBilibili': 1,
            'AutoExit': 1,
            'DaysBefore': 3,
            'BlackList': ['我的很大', '你可要', '狠狠地忍住哦']
        }
    }
    if not os.path.exists('config.json') or json.load(open('config.json', 'r', encoding='utf-8'))['config'].keys() != \
            configs['config'].keys():
        with open('config.json', 'w', encoding='utf-8') as con:
            json.dump(configs, con, indent=4, ensure_ascii=False)
    with open('Viewed.txt', 'a'):
        pass
    # 检查并获取cookie文件名

    UID = cookies['DedeUserID']

    # 读取已看列表
    Viewed_txt = file_read('Viewed.txt')


# 读取文件
def file_read(name):
    rtn = []
    for line in open(name, 'r', encoding='utf-8').readlines():
        line = line.replace('\n', '')
        rtn.append(line)
    return rtn


# endregion

# region 读取所有视频的主循环
Videos = []  # 所有视频


def addVideosToArray(end_time, blackList):
    all_vids = []
    page = 0  # 当前页数
    keep = True
    while keep:
        page += 1
        print('正在获取第' + str(page) + '页视频')
        if page == 1:  # 第一次
            url = 'https://api.vc.bilibili.com/dynamic_svr/v1/dynamic_svr/dynamic_new?uid=' + UID + \
                  '&type_list=8&from=&platform=web'
            result = session.get(url=url, cookies=cookies, data={'uid': UID}).json()  # 调用GET请求
            history_offset = str(result['data']['history_offset'])
        else:
            url = 'https://api.vc.bilibili.com/dynamic_svr/v1/dynamic_svr/dynamic_history?uid=' + UID + \
                  '&offset_dynamic_id=' + history_offset + '&type=8&from=&platform=web'
            result = session.get(url=url, cookies=cookies,
                                 data={'uid': UID, 'offset_dynamic_id': history_offset}).json()
            history_offset = str(result['data']['next_offset'])

        if result['code'] == -412:
            print('错误代码：-412，请求被拦截。')
            break
        video_cards = result["data"]["cards"]
        for card in video_cards:
            card_detail = json.loads(card["card"])
            if card_detail["pubdate"] > end_time and all(card["desc"]["bvid"] not in line for line in Viewed_txt):
                if all(black not in card_detail["title"] for black in blackList):
                    all_vids.append(Video(card_detail["title"], card["desc"]["bvid"], card_detail["pubdate"],
                                          card_detail["owner"]["name"]))
            elif card_detail["pubdate"] <= end_time:
                keep = False
                break
    return all_vids


# endregion

# region 添加视频到稍后再看
suc_BV = []


def addVideoHelper(vid):
    return session.post(url='http://api.bilibili.com/x/v2/history/toview/add', cookies=cookies,
                        data={'bvid': vid.BVNumber, 'csrf': cookies['bili_jct']})


def addVideosToView(vids):
    code = 0
    msg = ''
    while code != 90001:
        if not vids:
            break
        vid = vids.pop(0)
        code = int(addVideoHelper(vid).headers['Bili-Status-Code'])
        i = 0
        while code == -509 or code == -702:
            i += 1
            print(
                '[失败] ' + vid.BVNumber + ' 添加失败，错误代码：' + str(code) + '，等待3秒后，尝试第' + str(i) + '次添加。')
            time.sleep(3)
            code = int(addVideoHelper(vid).headers['Bili-Status-Code'])
        if code == 0:
            suc_BV.append(vid)
            msg += '[成功] ' + vid.BVNumber + ' 添加成功'
        elif code == 90005 or code == 90002:
            suc_BV.append(vid)
            msg += '[警告] ' + vid.BVNumber + ' 已经删除，错误代码：' + str(code) + '，原因：非常规视频类型，可能是版权问题'
        else:
            msg += '[警告] ' + vid.BVNumber + ' 添加失败，错误代码：' + str(code) + '，原因是：'
            match code:
                case -101:
                    msg += '账号未登录'
                case -111:
                    msg += 'csrf校验失败'
                case -400:
                    msg += '请求错误'
                case -412:
                    msg += '请求被拦截'
                case -509:
                    msg += '第二次添加失败，请再运行程序一次'
                case 90001:
                    msg += '列表已满'
                case 90003:
                    msg += '稿件已被删除'
        msg += '。\n'
    return msg


# endregion

# region 移除已看视频
def delToView():
    session.post(url='http://api.bilibili.com/x/v2/history/toview/del', cookies=cookies,
                 data={'viewed': 'true', 'csrf': cookies['bili_jct']})
    return '[移除]已经移除已观看的视频。\n'


# endregion

# region 更新 Viewed.txt
def update_viewed():
    with open('Viewed.txt', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    for BV in suc_BV:
        if all(BV.BVNumber not in line for line in lines):
            lines.append(f'【{BV.BVNumber}】上传时间：{BV.ReleaseTime} {BV.Uploader}：《{BV.VideoTitle}》\n')
    lines.append(f'{datetime.now().strftime('%Y/%m/%d %H:%M:%S')} 记录了{len(suc_BV)}个视频\n')
    # 如果行数超过600，删除前300行以保证Viewed.txt的大小
    if len(lines) > 600:
        lines = lines[300:]
    with open('Viewed.txt', 'w', encoding='utf-8') as f:
        f.writelines(lines)
# endregion
