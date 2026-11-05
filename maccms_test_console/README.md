# MacCMS 测试操作台

本地运行的 Web 小工具，用于检测影视资源站（MacCMS / 苹果 CMS）与解析接口的**连通性与响应合法性**。所有请求由本机后端代发（绕过浏览器 CORS），仅发起 HTTP 请求并展示响应，**不下载、不中转任何视频内容**。

## 快速开始

无需安装依赖，仅用 Python 标准库：

```bash
cd maccms_test_console
python web_console.py          # 监听 0.0.0.0:8000
# 浏览器打开 http://localhost:8000
```

## 功能（标签页）

| 标签页 | 用途 |
|---|---|
| 单站测试 | 任意 URL + 方法（GET/POST/HEAD）+ 自定义 Header，看状态码/耗时/响应体。输入框带默认地址列表与 × 清空按钮。 |
| 批量测试 | 粘贴 `名称 \| URL` 清单（或一键载入默认清单），批量探测存活并汇总。 |
| MacCMS 结构 | 输入资源站根路径，① 列分类 → ② 列视频 → ③ 点 vod_id 下钻播放源并做 HEAD 检测。三步各自成卡片。 |
| 默认资源列表 | 展示 `STATIONS` 全部默认站点，点击地址复制，可一键载入批量测试 / 复制全部。 |
| Python 引擎测试 | 粘贴 TVBox / 影视仓 的 py 引擎代码，后端用桩替掉 `base.spider`，调用其 `homeContent`/`detailContent`/`playerContent` 等方法，并做返回结构（schema）校验；支持「运行全链路」一键走 home→detail→player。 |
| 配置生成 | 把 `名称 \| URL` 形式的已订阅点播源（MacCMS 标准接口）生成 TVBox / 影视仓 配置 JSON。支持单源/多源、全局类型与可搜索开关、可选壁纸与 spider 代码，一键「复制 JSON」或「下载 tvbox.json」。 |

## 维护默认地址清单

所有默认站点集中在前端 `console.html` 顶部的一个 `STATIONS` 数组，**只在此一处维护**，各预填列表自动同步：

```js
const STATIONS=[
  {name:'爱奇艺', url:'https://iqiyizyapi.com/api.php/provide/vod'},
  // 增删站点只改这里：{name:'新站', url:'https://xxx.com/api.php/provide/vod'}
];
```

## 项目结构

```
web_console.py   # 后端：零依赖（标准库），起服务 + 代发请求
console.html     # 前端：原生 HTML/JS，离线可用
README.md        # 本文档
```

后端接口：`GET /`（页面）、`POST /api/test`、`POST /api/batch`、`POST /api/maccms`、`POST /api/engine`（执行 Python 引擎代码，会运行你提供的任意代码，仅用于本地、且你信任的引擎）。

## 说明与免责

- 连通性 ≠ 能播放：API 在线只说明目录可达，播放源可能失效或被防盗链拦截，需用 MacCMS 第三步 HEAD 检测确认。
- 本工具为只读网络诊断工具，仅展示响应，不存储/分发/中转内容。
- 资源站 / 解析接口处于版权与平台条款的灰色地带，请仅用于个人技术研究，勿用于搭建或分发侵权服务。
