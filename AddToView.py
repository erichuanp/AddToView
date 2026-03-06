import json
import time
import Core
import os

# region 初始化读取config文件
Core.init()
with open('config.json', 'r', encoding='utf-8') as con:
    config = json.load(con)['config']
# endregion

# region 询问并计算时间
if config['AskUser']:
    time_input = input(f'需要添加多少天以前的视频(默认为{config["DaysBefore"]})：')
    if not time_input.isdigit():
        print(f'输入了非数字，默认解析前{config["DaysBefore"]}天的视频。')
        time_input = config['DaysBefore']
else:
    time_input = config['DaysBefore']
end_time = int(time.time()) - int(time_input) * 86400  # 获取 time_input 天前的时间戳


# endregion

# region 添加BV号到稍后再看
def open_bilibili():
    if not config['BilibiliLocation']:
        print('BilibiliLocation为空，跳过打开哔哩哔哩。')
        return
    print('尝试打开哔哩哔哩...')
    os.system(f"\"{config['BilibiliLocation']}\"")


BVs = Core.addVideosToArray(end_time, config['BlackList'])
msg = ''
print('在此期间，有' + str(len(BVs)) + '个视频未看。\n')
if config['AskUser']:
    if input('是否要移除已看的视频(y/*)：') == 'y':
        msg += Core.delToView()
    if input('是否要添加到稍后再看(y/*)：') == 'y':
        msg += Core.addVideosToView(BVs)
    if input('是否要查看运行日志(y/*):') == 'y':
        print(msg)
    if input('是否要打开哔哩哔哩(y/*):') == 'y':
        open_bilibili()
else:
    if config['Remove']:
        msg += Core.delToView()
    if config['Add']:
        msg += Core.addVideosToView(BVs)
    if config['PrintLogs']:
        print(msg)
    if config['BilibiliLocation']:
        open_bilibili()
log = open('Log.txt', 'w')
log.write(msg)
log.close()

# endregion

# region 结束
Core.update_viewed()
print('程序已结束\n')

time.sleep(5)
if not config['AutoExit']:
    os.system('pause')
# endregion
