from MyQR import myqr
import requests
import json
import cv2
import os
import re

url1 = 'https://passport.bilibili.com/x/passport-login/web/qrcode/generate'
url2 = 'https://passport.bilibili.com/x/passport-login/web/qrcode/poll'
url3 = 'https://api.bilibili.com/x/web-interface/nav'


def login_code():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }
    url_json = requests.get(url1, headers=headers).json()
    qr_url = url_json['data']['url']
    key = url_json['data']['qrcode_key']

    myqr.run(words=qr_url, colorized=True, save_name=f"{key}.jpg")

    img_1 = cv2.imread(f"{key}.jpg")
    cv2.imshow(key, img_1)
    cv2.waitKey()

    data1 = {"qrcode_key": key}
    r1 = requests.get(url2, data=data1, headers=headers).json()
    print(r1)
    try:
        text1 = r1['data']['url'].replace('https://passport.biligame.com/crossDomain?', '')
        text2 = re.split("&", text1)

        cookie = {}
        for text3 in text2:
            text4 = re.split("=", text3)
            if text4[0] == "gourl":
                continue
            cookie[text4[0]] = text4[1]
        user_json = requests.get(url3, cookies=cookie, headers=headers).json()
        uid = user_json['data']['mid']

        with open(f"{uid}_cookie.json", "w", encoding='utf-8') as f:
            json.dump(cookie, f)
        f.close()

        os.remove(f"{key}.jpg")

        return 'UID: ' + uid + '的Cookie已经创建完毕'
    except:
        return f"错误码:{r1['data']}"


if __name__ == '__main__':
    code = login_code()
    print(code)
