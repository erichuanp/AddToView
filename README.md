# B站一键添加到稍后再看
### 自动添加指定日期附近之前的已关注的UP的视频到稍后再看
利用Login.py实现二维码登录B站，以此获取Cookie来读取用户的稍后再看列表和已关注UP主最近发布的视频。\
以页为单位，在自定义天数之前，添加时间段内的视频到稍后再看，并保存未添加到稍后再看的视频列表。


**编译**：请pip install所需库（注意cv2需pip install opencv-python，且注意cv2的大小写）

**使用**：将AddToView.exe放在一个单独的文件夹内，双击运行，必要的话请添加快捷方式到桌面。


# Credits
### Main.py、Core.py
by B站：[加把劲假面骑士][1]
### Login.py
by 忘了抄的是哪位大神的了，纯净版[这边请][2]


[1]: https://space.bilibili.com/4689754
[2]: https://github.com/CreeberSlime/Bilibili_Cookie_QRCodeLogin
