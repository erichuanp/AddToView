import json
import os
import time

import requests
import Login

# region 初始化
cookie_filename = ''
UID = ''
Viewed_txt = []
session = requests.session()  # 开启会话
cookies = ''


# 读取cookie
def scan(cookie_json):
    for rtn in os.listdir('.'):
        if rtn.find(cookie_json) != -1:
            return rtn
    return 0


while scan('_cookie.json') == 0:
    Login.login_code()
cookie_filename = scan('_cookie.json')


def loadCookies():
    global cookies
    with open(cookie_filename, 'r', encoding='UTF-8') as f:
        cookies = json.load(f)


loadCookies()


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
            'DaysBefore': '需要多少天以前到现在的视频？请输入正确的天数而不是0或1，默认是三天之内。'
        },
        'config': {
            'BilibiliLocation': '',
            'AskUser': 1,
            'Remove': 1,
            'Add': 1,
            'PrintLogs': 1,
            'OpenBilibili': 1,
            'AutoExit': 1,
            'DaysBefore': 3
        }
    }
    if not os.path.exists('config.json') or json.load(open('config.json', 'r', encoding='utf-8'))['config'].keys() != configs['config'].keys():
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
    for line in open(name, 'r').readlines():
        line = line.replace('\n', '')
        rtn.append(line)
    return rtn


# endregion

# region 提取特定页面元素的帮助函数
# start 和 element_len 需自行填写
def extract_elem(in_page, element, start, element_len):
    rtn = []
    while not in_page.find(element) == -1:
        offset = in_page.find(element) + start
        rtn.append(in_page[offset:offset + element_len])
        in_page = in_page[offset:]
    return rtn


# endregion

# region 读取所有BV号的主循环
all_BV = []  # 所有BV号


def get_all_BV(end_time):
    global all_BV
    history_offset = 0  # 时间偏移量
    page = 0  # 当前页数
    keep = True
    while keep:
        page += 1
        print('正在解析第' + str(page) + '页中...')  # 可以comment掉
        if page == 1:  # 第一次
            url = 'https://api.vc.bilibili.com/dynamic_svr/v1/dynamic_svr/dynamic_new?uid=' + UID + \
                  '&type_list=8&from=&platform=web'
            result = session.get(url=url, cookies=cookies, data={'uid': UID}).text  # 调用GET请求
            if result[8:10] == '-6':
                print('错误代码：-6，请重新登录。')
                Login.login_code()
                page -= 1
                loadCookies()
                continue
            history_offset = result[result.find('history_offset') + 16:result.find(',"_gt_":0}}')]
        else:
            url = 'https://api.vc.bilibili.com/dynamic_svr/v1/dynamic_svr/dynamic_history?uid=' + UID + \
                  '&offset_dynamic_id=' + history_offset + '&type=8&from=&platform=web'
            result = session.get(url=url, cookies=cookies, data={'uid': UID, 'offset_dynamic_id': history_offset}).text
            history_offset = result[result.find('next_offset') + 13:result.find(',"_gt_":0}}')]
        for BV in extract_elem(result, 'bvid', 7, 12):
            print(BV, end=', ')
            all_BV.append(BV)
        print('\n')
        if '{"code":-412,"message":"请求被拦截","ttl":1,"data":null}' in result:
            print('错误代码：-412，请求被拦截。')
            break
        for TS in extract_elem(result, 'timestamp', 11, 10):
            if int(TS) < end_time:
                keep = False
                break
    all_BV = sorted(set(all_BV), key=all_BV.index)  # 整理所有BV号
    return all_BV
# endregion

# region 从BV号列表中去除已看视频
BVs = []


def get_BVs(end_time):
    global BVs
    get_all_BV(end_time)
    BVs = all_BV  # 最终用来添加到稍后再看的BV号列表

    for viewed_BV in Viewed_txt:
        if viewed_BV in all_BV:
            BVs.remove(viewed_BV)
    return BVs


# endregion

# region 添加BV号
suc_BV = []


def add_BV():
    code = 0
    msg = ''
    while code != 90001:
        if not BVs:
            break
        BV = BVs.pop()
        response = session.post(url='http://api.bilibili.com/x/v2/history/toview/add', cookies=cookies,
                                data={'bvid': BV, 'csrf': cookies['bili_jct']})
        code = int(response.headers['Bili-Status-Code'])
        i = 0
        while code == -509 or code == -702:
            i += 1
            print('[失败] ' + BV + ' 添加失败，错误代码：' + str(code) + '，等待3秒后，尝试第' + str(i) + '次添加。')
            time.sleep(3)
            response = session.post(url='http://api.bilibili.com/x/v2/history/toview/add', cookies=cookies,
                                    data={'bvid': BV, 'csrf': cookies['bili_jct']})
            code = int(response.headers['Bili-Status-Code'])
        if code == 0:
            suc_BV.append(BV)
            msg += '[成功] ' + BV + ' 添加成功'
        elif code == 90005 or code == 90002:
            suc_BV.append(BV)
            msg += '[警告] ' + BV + ' 已经删除，错误代码：' + str(code) + '，原因：非常规视频类型，可能是版权问题'
        else:
            msg += '[警告] ' + BV + ' 添加失败，错误代码：' + str(code) + '，原因是：'
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
def del_to_view():
    response = session.post(url='http://api.bilibili.com/x/v2/history/toview/del', cookies=cookies,
                            data={'viewed': 'true', 'csrf': cookies['bili_jct']})
    code = response.headers['Bili-Status-Code']
    if code != '0':
        return '[警告]移除已观看视频的功能发生错误' + code + '。\n'
    else:
        return '[移除]已经移除已观看的视频。\n'


# endregion

# region 更新 Viewed.txt
def update_viewed():
    with open('Viewed.txt', 'r') as f:
        lines = f.readlines()
    for BV in suc_BV:
        if BV + '\n' not in lines:
            lines.append(BV + '\n')

    # 如果行数超过3000，删除前1000行以保证Viewed.txt的大小
    if len(lines) > 3000:
        lines = lines[1000:]
    with open('Viewed.txt', 'w') as f:
        f.writelines(lines)
# endregion
