# AddToView

B 站「稍后再看」自动化助手。

抓取你关注的 UP 主最近发布的视频，按自己设定的多维度黑名单（标题关键词 / 正则、UP 主、时长、分区、标签…）过滤，然后批量塞进「稍后再看」。配套一个网页面板，可以浏览队列、看 AI 摘要、批量管理。

> 五年前在大学期间为自己写的小工具，现在重写成了现代 web 应用。

## 跑起来

需要 Docker。

```bash
docker compose up -d --build
```

打开 `http://localhost:2233`，扫码登录即可。后端 API 同时挂在 `:2232`（给老 CLI 脚本用，比如 `curl http://localhost:2232/addtoview/` 一键同步并加入稍后再看）。

数据全部落在 `./data/`：SQLite 库、cookie 文件，删容器不会丢。

## 技术栈

- 后端：FastAPI + SQLAlchemy + SQLite + httpx
- 前端：Vue 3 + Vite + TypeScript + Tailwind
- AI 摘要：任意 OpenAI 兼容接口（豆包 / Kimi / OpenAI / 本地 Ollama 都行），在「设置」页配置
