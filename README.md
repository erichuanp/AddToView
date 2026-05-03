# AddToView

Bilibili "稍后再看" 自动化助手。

抓取关注的 UP 主在过去 N 天发布的新视频，按用户配置的多维度黑名单过滤，再批量加入 *稍后再看*。提供玻璃拟态风格的网页面板查看、管理和操作。

> 5 年前在大二期间为自己写的小工具，正在重写为现代 web 应用。

## 架构

```
backend/   FastAPI + SQLAlchemy + SQLite + httpx (async)
frontend/  Vite + Vue 3 + TypeScript + Tailwind (玻璃拟态)
data/      SQLite 数据库与 cookie 文件 (gitignored)
```

## 快速开始

### Docker（跨平台，推荐）

```bash
docker compose up -d --build
# → 浏览器打开 http://localhost:8787
```

把 `*_cookie.json` 放进 `./data/` 目录，重启容器即可生效。也可以在网页里扫码登录，cookie 会自动写到 `./data/`。

### Windows 开发模式

```cmd
start.bat
```

首次运行会自动创建后端虚拟环境、安装前端依赖、启动两个服务（后端 :8787 + 前端 dev :5173）并打开浏览器。后续运行秒起。

## 手动启动

### 后端
```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # Windows
# 或 source .venv/bin/activate && pip install -r requirements.txt   # *nix
cp .env.example .env                            # 然后按需要编辑
.venv/Scripts/python -m uvicorn app.main:app --port 8787 --reload
```

API 文档：http://127.0.0.1:8787/docs

### 前端
```bash
cd frontend
npm install
npm run dev    # http://localhost:5173
```

## Cookie

把 `*_cookie.json` 放到 `data/` 目录下（兼容老文件名 `<uid>_cookie.json`），后端启动时会自动读取并写入数据库。Cookie 必须包含：

- `DedeUserID`
- `DedeUserID__ckMd5`
- `SESSDATA`
- `bili_jct`
- `Expires`（可选）

二维码登录页面将在 v2 上线（feature/qrcode-login 分支）。

## 路由

| 页面 | 路径 |
|---|---|
| 稍后再看 | `/` |
| 已过滤 | `/filtered` |
| 黑名单 | `/blacklist` |
| 设置 | `/settings` |

## 黑名单维度

`title_keyword`、`title_regex`、`owner_name`、`owner_mid`、`duration_lt`、`duration_gt`、`partition_tid`、`partition_name`、`tag_keyword`。

## License

私有项目，未公开发布。
