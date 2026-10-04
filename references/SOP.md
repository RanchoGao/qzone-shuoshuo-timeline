# QQ 空间导出 · 标准操作程序（SOP）

> 把 QQ 空间的**说说**和**日志**，连同**图片、评论、转发、定位**，导出成本地 Markdown 存档。
> 本文件是这套流程的**唯一执行规范**：每一阶段写清 目标 / 输入 / 输出 / 执行步骤 / 通过标准 / 常见故障。
> 面向的是**自己和家人数据的备份**，所有操作都在本机完成。

**版本** 1.0.0 **·** 适用平台 Windows / macOS / Linux **·** 前置：Python 3.8+、Node 18+、Chrome/Edge

---

## 0. 流程总览

```
┌─ 阶段 A  身份与凭据 ────────────────────────────────────────┐
│  A1 启动调试浏览器 → A2 取 uin 与 g_tk → A3 校验登录态        │
│  产出：data/auth.json                                        │
└─────────────────────────────────────────────────────────────┘
                            ↓ g_tk / uin
┌─ 阶段 B  原始数据抓取 ──────────────────────────────────────┐
│  B1 说说列表分页 → B2 日志列表+正文 → B3 落盘 JSON            │
│  产出：data/shuoshuo.json、data/blog.json                    │
└─────────────────────────────────────────────────────────────┘
                            ↓ 图片 URL 清单
┌─ 阶段 C  图片本地化 ────────────────────────────────────────┐
│  C1 构建清单 → C2 并发下载 → C3 失效重试 → C4 完整性校验      │
│  产出：images/*、data/images.json                            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─ 阶段 D  Markdown 生成 ─────────────────────────────────────┐
│  D1 文本清洗 → D2 HTML 转 MD → D3 排序聚合 → D4 渲染验收     │
│  产出：QQ空间存档.md                                          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─ 阶段 E  交付与收尾 ────────────────────────────────────────┐
│  E1 关闭浏览器 → E2 清除凭据 → E3 交付说明                   │
└─────────────────────────────────────────────────────────────┘
```

阶段之间**严格串行**：B 依赖 A 产出的 `g_tk`，C 依赖 B 的 URL 清单，D 依赖 B、C 两边的产物。

---

## 阶段 A　身份与凭据

### 目标
拿到调用 QQ 空间 CGI 接口的两把钥匙：**当前登录用户的 QQ 号（uin）**和**接口签名（g_tk）**。

### 输入
本机已安装的 Chrome 或 Edge；用户可扫码或用 QQ 客户端完成登录。

### 输出
`data/auth.json`，形如 `{"uin": "...", "g_tk": ...}`。

### 为什么这样做
QQ 空间没有导出 API，`g_tk` 也无法从页面 DOM 里直接读到。所以做法是：**在真实浏览器里登录，然后在页面上下文调用同源接口**——Cookie 由浏览器自动携带，既不用手工拼 Cookie 头，也不用处理 httpOnly 和 GBK 编码。

### 执行步骤

**A1　启动带调试端口的浏览器**

```bash
# Windows（Git Bash）
"/c/Program Files/Google/Chrome/Application/chrome.exe" \
  --remote-debugging-port=9222 \
  --user-data-dir="<工作目录>/.chrome-profile" \
  --no-first-run --no-default-browser-check \
  "https://user.qzone.qq.com" > /dev/null 2>&1 &

curl -s --noproxy '*' http://127.0.0.1:9222/json/version   # 返回 JSON 即启动成功
```

必须用**独立的 `--user-data-dir`**——不要碰用户日常的浏览器配置。macOS 用 `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`，Linux 用 `google-chrome`。

**A2　取 uin 与 g_tk**

```bash
NODE_PATH="<含 puppeteer-core 的 node_modules>" node scripts/status.js
```

`g_tk`（又叫 bkn）是 `p_skey` 的 djb2 变体哈希，**所有 CGI 接口都必须带它**：

```js
let hash = 5381;
for (const ch of skey) { hash += (hash << 5) + ch.charCodeAt(0); hash &= 0xffffffff; }
return hash & 0x7fffffff;
```

取 Cookie 走 CDP 的 `Network.getAllCookies`——`page.cookies()` 读不到 httpOnly 的 `p_skey`。优先用 `p_skey`，取不到时回退 `skey`。

**A3　校验登录态**

`status.js` 输出必须满足：`loggedIn: true` 且 `uin` 非空。若未登录，**脚本不应该自己填账号密码**——让用户在弹出的窗口里扫码，完成后重跑 A2。

### 通过标准
- `data/auth.json` 存在，`uin` 为纯数字，`g_tk` 为 8–10 位正整数
- 当前页面 URL 位于 `https://user.qzone.qq.com` 下（后续 `fetch` 需要同源）

### 常见故障

| 现象 | 原因 | 处理 |
|---|---|---|
| 9222 端口连不上 | 浏览器没起来 / 环境变量里的 HTTP 代理拦了 localhost | 用 `--noproxy '*'` 访问；确认进程已启动 |
| 有 `uin` 但 `p_skey` 为空 | 登录态过期或被挤下线 | 重新扫码登录后重跑 A2 |
| 接口全返回 `code: -3000` 之类 | `g_tk` 算错 | 用 `skey` 重算；确认哈希末尾是 `& 0x7fffffff` |

---

## 阶段 B　原始数据抓取

### 目标
把全部说说、日志正文、评论抓下来，**原样存 JSON**。这一步只做传输，不做清洗。

### 输入
阶段 A 的 `uin`、`g_tk`；页面上下文的同源 `fetch` 能力。

### 输出
- `data/shuoshuo.json` — 说说数组，每条含正文、时间、图片列表、评论、转发、定位
- `data/blog.json` — 日志数组，每条含标题、发布时间、正文 HTML / 纯文本、图片、评论

### 执行步骤

**B1　说说列表分页**

```bash
NODE_PATH=... node scripts/fetch_shuoshuo.js
```

每次 `num=20`，翻页用 `pos` 递增；失败重试 4 次，退避 2.5s×(次数)。**每页抓完立刻落盘**，中断后重跑会跳过已有 `tid`。

附带一步：当某条的 `pictotal > pic.length`（列表只返回前几张图）时，补调详情接口补齐。

**B2　日志列表 + 正文**

```bash
NODE_PATH=... node scripts/fetch_blog.js
```

1. 列表接口的 `statYear` 必须是**有效年份**，空值会报"错误的统计年份"；它只影响侧栏统计，不过滤列表本身
2. 逐篇拉正文：返回的是整页 HTML，正文在 `#blogDetailDiv`，元数据在内联变量 `g_oBlogData`
3. 用浏览器里的 `DOMParser` 解析（不是正则），避免 `<td>` 这种嵌套标签数错

**B3　落盘校验**

接口返回的是 JSONP（`_Callback({...});`），要剥掉外壳再解析；偶尔返回非严格 JSON，需要兜底。

### 通过标准
- `shuoshuo.json` 条数 == 接口返回的 `total`（实测 1573 条对得上）
- `blog.json` 条数 == `get_abs` 返回的 `totalNum`
- 每篇日志的 `contentHtml` 长度 > 0
- `code` 字段全程为 `0`

### 常见故障

| 现象 | 原因 | 处理 |
|---|---|---|
| 列表翻到末尾报 FAIL | 超出总数后返回空列表 | 属正常终态，看是否已达 total |
| 频繁触发风控（code 非 0） | 请求太密 | 把 `DELAY` 从 700ms 调到 1500ms 以上，重跑会自动续传 |
| 日志列表返回 -4003 | `statYear` 无效 | 填当前年份 |
| 中文乱码 | 响应是 GBK | 博客接口显式传 `inCharset=utf-8&outCharset=utf-8` |

> **接口路径会变。** 拿不准时不要猜：打开对应页面、监听 `page.on('request')` 过滤 `cgi-bin`，几秒就能嗅出当前真实地址。用 `scripts/sniff.js`。

---

## 阶段 C　图片本地化

### 目标
把说说和日志里的每一张图下载到本地，并记录「图片位置 → 本地文件名」的映射。

### 输入
B 阶段产物中的图片 URL；`data/images.json` 是运行期映射表。

### 输出
`images/`（按内容命名）+ `data/images.json`（供 D 阶段查找）。

### 执行步骤

**C1　构建清单**

| 来源 | 取哪个字段 | 说明 |
|---|---|---|
| 说说 | `pic[i].url2` | `url2` 是原图（路径以 `/b` 结尾）；`url3` 是缩略版、`url1`/`smallurl` 更小。**必须取 url2** |
| 日志 | `<img orgsrc="...">` | `src` 只是 `loading.gif`，真图在 `orgsrc` |

命名规则：`ss_<说说tid>_<序号>.<ext>`、`blog_<日志id>_<序号>.<ext>`。

**C2　并发下载**

```bash
python scripts/download_images.py
```

8 线程；每个 URL 先试原协议、失败换 https；扩展名按 **magic bytes** 判断（不信 URL 后缀）。已存在的文件自动跳过，可反复重跑。

**C3　失效重试**

```bash
python scripts/retry_failed.py
```

专治两类问题：`p.qpimg.cn/cgi-bin/cgi_imgproxy?url=<真实地址>` 这个代理服务已经停摆（返回 502）——要解出内层 `url` 参数直连；以及部分老图床已下线。

**C4　完整性校验**

Markdown 里每张图的路径，必须在 `images/` 里真实存在。

### 通过标准
- `images/` 内文件数 == `images.json` 中 `ok: true` 的数量
- 无 0 字节、无 HTML 错误页（用 magic bytes 已拦住）
- 校验脚本输出「缺失文件: 0」

### 已知不可恢复的情况
2012 年前后引用的第三方图床（蚂蜂窝、腾讯微博图床、各类已关站的博客图床）客观上已不存在。实测 732 张图，722 张可取、10 张永久失效。处理方式：**在 Markdown 里保留原始 URL 并标注失效**，不静默丢弃。

> ⚠️ 日志的 `orgsrc` 带 `dis_t`/`dis_k` 时效签名，**抓完必须尽快下载**，隔太久会返回 403。

---

## 阶段 D　Markdown 生成

### 目标
把 JSON 转成一份人类可读、可长期保存、能被 Obsidian / VS Code / Typora 直接打开的 Markdown。

### 输入
`shuoshuo.json`、`blog.json`、`images.json`、`auth.json`。

### 输出
`QQ空间存档.md`（含统计头部、年度分布表、逐年正文）。

### 执行步骤

**D1　文本清洗**

| 原文 | 转换后 | 备注 |
|---|---|---|
| `@{uin:123,nick:张三,who:1}` | `@张三` | 保留可读昵称 |
| `[em]e113[/em]` | `[呲牙]` | `e100` 起是经典 QQ 表情表 |
| `[em]e328051[/em]` | `[表情]` | 新版 VIP 表情无公开映射，降级处理 |
| 正文里的 `\n` | 行尾两个空格 | Markdown 硬换行，否则渲染时被吞 |
| 行首 `#` `>` `-` `1.` `\|` | 转义 | 防止纯文本被当成标题/列表/表格 |

> ⚠️ 有序列表要转义**点号**（`1\. x`），不能转义数字——`\1` 在 CommonMark 里不是合法转义，会原样显示。

**D2　HTML → Markdown（仅日志）**

用 `html.parser` 走一遍 SAX：`p/div/tr` 等块级标签断行、`br` 换行、`img` 查 `images.json` 换成 `![](images/xxx)`、`b/i` 转 `**`/`*`。不用 BeautifulSoup，保持零依赖。

**D3　排序聚合**

日志与说说合并，**按时间戳倒序**，按年份分组，每年一个 `# YYYY 年` 标题。每条的总标题格式为 `## 2025-12-26 22:25 · 说说`。

**D4　渲染验收**

```bash
python scripts/gen_markdown.py
```

必须逐个检查：多行正文有没有被并成一段、列表项有没有断成两行、引用块有没有意外嵌套。

### 通过标准
- `Markdown 引用图片数` == `images/` 文件数，且缺失为 0
- 日志正文段落间有空行分隔，没有挤成一坨
- 显示为 `\数字` 的序列不应存在

---

## 阶段 E　交付与收尾

### E1　关闭浏览器
```bash
NODE_PATH=... node scripts/close.js
```
必须执行，否则 Chromium 进程常驻后台。

### E2　清除凭据
**必做，不可跳过：**

1. `data/auth.json` 里的 `cookieStr`（如有）删除——这是有效登录凭据
2. `.chrome-profile/` 整个目录删除——里面是完整的 QQ 登录态

```bash
rm -rf .chrome-profile        # 或用 mv 移到工作区外
```

> 注意：`.chrome-profile/` 通常有上千个文件，可能触发批量删除保护。此时**不要用非正当方式绕过**，改为 `mv` 到项目外，或者直接告诉用户手动删。

### E3　交付说明
向用户说清三件事：**导出了什么**（条数、时间跨度、图片数）、**哪些没办到**（失效图片及其原因）、**移动时的注意事项**（`.md` 与 `images/` 必须一起移动）。

---

## 验证清单（每次交付前逐项打勾）

- [ ] 说说条数 == 接口 `total`
- [ ] 日志条数 == `get_abs` 的 `totalNum`
- [ ] 每篇日志正文非空
- [ ] `images/` 文件数 == Markdown 里引用的图片数（非失效项）
- [ ] 随机抽 3 条正文，渲染正常（换行在、图片在、评论在）
- [ ] `auth.json` 无 `cookieStr`
- [ ] `.chrome-profile/` 已删除或已移出项目
- [ ] 浏览器进程已关闭

---

## 合规与边界

1. **只导出自己的空间。** 这套流程依赖自己的登录态，导出他人数据前需明确授权。
2. **数据默认留在本机。** 产物含 QQ 号、昵称、好友昵称、定位等个人信息，不要未经同意上传公网。
3. **遵守调用频率。** 接口有风控，出现非 0 返回码就加大间隔，不要并发猛刷。
4. **仅限个人备份。** 不得用于抓取、转售或公开发布他人内容。

---

## 主要模块索引

| 模块 | 文件 | 对应阶段 |
|---|---|---|
| CDP 连接 / g_tk / 页面内 fetch | `scripts/lib.js` | A |
| 登录态检查 | `scripts/status.js` | A |
| 接口嗅探 | `scripts/sniff.js` | A / B 排障 |
| 说说抓取 | `scripts/fetch_shuoshuo.js` | B |
| 日志抓取 | `scripts/fetch_blog.js` | B |
| 图片下载 | `scripts/download_images.py` | C |
| 失效重试 | `scripts/retry_failed.py` | C |
| Markdown 生成 | `scripts/gen_markdown.py` | D |
| 关闭浏览器 | `scripts/close.js` | E |
| 接口速查 | `references/api-notes.md` | 全程 |
