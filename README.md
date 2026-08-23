# B 站全内容解析

一个面向 AstrBot 的 B 站全内容解析插件。识别群聊中的 B 站视频、音频、专栏、直播、动态等链接、短链和 QQ 小程序转发，生成带封面、UP 主、统计数据、评论和源链接的长图卡片。

插件创建人：`xiaowan`

## 能做什么

- 自动识别 B 站视频链接（`BV`/`AV` 号）、音频链接（`bilibili.com/audio/au...`）、专栏链接（`bilibili.com/read/cv...`）、直播链接（`live.bilibili.com/...`）、动态链接（`bilibili.com/opus/...`、`t.bilibili.com/...`）、`b23.tv` 短链和 QQ 小程序分享。
- 封面、头像、二维码会先完整下载，再渲染成长图，避免图片“还在加载就被截图”。
- 长图下方附带 B 站源链接；开启下载后，只在用户发送完整编号时下载视频。
- 视频卡片可显示热门评论、评论头像、昵称和回复。
- 可选使用 AstrBot 已保存的模型商生成视频 AI 总结。
- AI 总结支持 B 站公开字幕、登录后的 AI 字幕，以及可选的 `faster-whisper` 语音转写。
- 下载支持编号有效期、权限、冷却、每日上限、并发限制、时长/体积限制、状态查看和取消。
- 下载与语音转写使用临时目录，发送或处理结束后自动清理视频文件。

## 安装

### 方式一：AstrBot WebUI

上传发布包：

`astrbot_plugin_bilibili_media_parser-v1.1.0.zip`

安装完成后，在插件管理页面点击重载。

### 方式二：手动安装

把插件目录放到：

```text
AstrBot/data/plugins/astrbot_plugin_bilibili_media_parser
```

然后安装基础依赖并重载插件：

```bash
pip install -r data/plugins/astrbot_plugin_bilibili_media_parser/requirements.txt
```

插件要求 AstrBot `>=4.5.7,<5`。

## 第一次配置：只改这几项

安装后打开 AstrBot WebUI → 插件 → B 站视频解析。新手只需要按自己的需求选择下面的项目：

| 目的 | 配置项 | 推荐做法 |
| --- | --- | --- |
| 只解析链接 | 不需要改配置 | 安装后即可使用 |
| 开启 AI 总结 | `enable_ai_summary` | 打开，并确保 AstrBot 已配置聊天模型 |
| 固定总结模型 | `summary_provider_id` | 通常留空，跟随当前会话即可 |
| 显示评论 | `featured_comment_count` | 默认 2；不想显示可填 0 |
| 开启视频下载 | `enable_video_download` | 打开，再填写 `yaohud_api_key` |
| 开启语音转写 | `enable_voice_transcription` | 先安装 ffmpeg 和 faster-whisper，再打开 |

所有配置项的名称都带有分类前缀：`【基础】`、`【AI 总结】`、`【评论】`、`【视频下载】`、`【高级】`。一般不需要修改高级项。

## AI 总结怎么工作

AI 总结关闭时不会调用模型。

开启后，插件按下面顺序准备内容：

1. 读取 B 站公开视频字幕。
2. 如果填写了 `bilibili_sessdata`，尝试读取登录后可见的 B 站 AI 自动字幕。
3. 如果打开 `enable_voice_transcription`，下载临时视频，用 `faster-whisper` 转写语音，再把文字交给模型。
4. 如果以上都没有内容，默认不生成总结；只有打开 `summary_fallback_to_metadata` 后，才会使用标题和简介生成概要。

### 语音转写安装

语音转写是可选的，插件不会默认安装大型语音依赖。开启前需要手动安装 `ffmpeg` 和 `faster-whisper`：

```bash
# Debian/Ubuntu 示例，其他发行版请换成对应的包管理器命令
sudo apt-get update
sudo apt-get install -y ffmpeg python3-pip
pip install -r requirements-voice.txt
```

安装完成后，在 WebUI 中打开 `enable_voice_transcription` 并填写 `yaohud_api_key`。语音转写首次使用会下载模型并缓存。CPU 推荐 `small + int8`；有可用 NVIDIA CUDA 时可选择 `cuda + float16`。

## 视频下载

开启 `enable_video_download` 并配置妖狐 API Key 后，解析卡片会显示类似：

```text
需要视频文件时，发送“视频下载 8978”即可下载本视频。
发送“视频下载 状态”可查看下载进度。
```

只有完整匹配编号的命令才会下载，不会因为聊天中出现“视频下载”几个字就触发。

可用命令：

| 命令 | 作用 |
| --- | --- |
| `视频下载 8978` | 下载卡片对应的视频 |
| `视频下载 8978 P2` | 下载多 P 视频的第 2P |
| `视频下载 状态` | 查看当前任务状态 |
| `视频下载 查看` | 查看当前任务状态的别名 |
| `视频下载查询` | 查看当前任务状态的别名 |
| `视频下载 取消` | 取消排队中或下载中的任务 |

如果视频没有达到下载条件，默认不会在卡片中显示无效下载提示。这个行为由 `hide_download_hint_when_unavailable` 控制。

## 配置速查

### 基础

- `duplicate_window_seconds`：重复链接拦截秒数，默认 15，填 0 关闭。
- `duplicate_scope`：按会话或按发送者分别判断重复。
- `render_mode`：默认 `image_card`；渲染服务不可用时可临时改 `text`。
- `show_error_message`：解析失败时是否在聊天中提示。

### AI 总结

- `enable_ai_summary`：总开关，默认关闭。
- `summary_provider_id`：留空跟随当前会话模型。
- `summary_max_chars`：总结输出长度，默认 320。
- `subtitle_max_chars`：送入模型的字幕上限，默认 12000。
- `subtitle_page_limit`：读取的分 P 数，默认 3，填 0 读取全部。
- `summary_fallback_to_metadata`：没有字幕时是否退回标题/简介，默认关闭。
- `bilibili_sessdata`：可选的 B 站 Cookie `SESSDATA`，只用于 B 站字幕请求。
- `enable_voice_transcription`：是否使用本地语音转写，默认关闭。

### 评论

- `featured_comment_candidates`：热门评论候选数，默认 8。
- `featured_comment_count`：主评论数，默认 2。
- `comment_reply_count`：每条评论的回复数，默认 2。
- `comment_timeout_seconds`：评论接口超时，默认 5 秒。

### 视频下载

- `yaohud_api_key`：下载或语音转写所需的妖狐 API Key。
- `enable_video_download`：下载总开关，默认关闭。
- `video_download_auto_send`：解析后自动下载并发送 P1，默认关闭；开启后不显示下载编号，仍会经过全部下载限制。
- `hide_download_hint_when_unavailable`：不满足条件时隐藏下载提示，默认开启。
- `video_download_permission`：`all`、`admin` 或 `allowlist`。
- `video_download_allowlist`：白名单用户 ID，英文逗号分隔。
- `video_download_request_ttl_seconds`：编号有效期，默认 300 秒。
- `video_download_cooldown_seconds`：单用户冷却，默认 30 秒。
- `video_download_daily_limit`：每日下载上限，默认 5。
- `video_download_max_queue`：等待下载的任务上限，默认 10，填 0 关闭。
- `video_download_max_duration_seconds`：最长视频时长，默认 900 秒。
- `video_download_max_mb`：临时视频体积上限，默认 100 MB。
- `video_download_max_concurrency`：同时下载数，默认 1。

## 常见问题

### 卡片显示“封面暂时无法加载”

插件会先下载并校验封面，再生成长图。如果仍失败，检查服务器是否能访问 B 站图片域名，或先将 `render_mode` 改成 `text` 确认接口本身正常。

### AI 总结只有标题和简介

默认不会把标题和简介冒充视频内容。请优先配置 `bilibili_sessdata` 读取 AI 字幕；或安装 ffmpeg/faster-whisper 并打开语音转写。也可以打开 `summary_fallback_to_metadata`，但准确度会有限。

### 视频下载失败

确认 `yaohud_api_key` 正确、视频没有超过时长/体积限制，并检查日志中的直链错误。下载文件使用 Base64 发送给 NapCat，过大的文件可能被平台拒绝。

### 如何关闭某个功能

在 WebUI 中关闭对应的 `enable_*` 开关即可。修改需要重载插件的项目，配置提示中会明确标注。

## 数据与隐私

- 基础视频信息来自 B 站公开接口。
- 妖狐 Key 只在下载/语音转写需要获取临时直链时使用。
- `bilibili_sessdata` 只附加到 B 站接口，不会发送给妖狐、图床或视频直链。
- 下载和转写用的视频文件在处理结束后自动清理；语音模型缓存会保留。

## 开发与测试

```bash
python -m unittest discover -s tests -v
```

## 许可证

MIT
