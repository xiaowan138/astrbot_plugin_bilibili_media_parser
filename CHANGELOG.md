# 更新记录

## v1.1.0

- 新增 B 站专栏（CV）解析：支持 `bilibili.com/read/cv...` 链接，展示标题、作者、分类、字数、摘要与统计。
- 新增 B 站直播解析：支持 `live.bilibili.com/...` 链接，展示标题、主播、分区、在线人数与直播状态。
- 新增 B 站动态解析：支持 `bilibili.com/opus/...`、`t.bilibili.com/...` 链接，展示作者、内容、图片与点赞/评论/转发统计。
- 新增通用内容卡片模板（`templates/content_card.html`），统一渲染专栏/直播/动态。
- 插件名称更新为「B站全内容解析」。

## v1.0.1

- 修复 B 站音频解析接口错误：改用正确的 `www.bilibili.com/audio/music-service-c/web/song/info` 接口，并修正 UP 主 UID 字段读取（`uid` 而非 `mid`），音频解析现在可以正常工作。
- 短链解析支持识别音频（AU）链接。

## v1.0.0

- 首个版本。自动识别并解析 B 站视频/音频链接、`BV`/`AV` 号、`b23.tv` 短链和 QQ 小程序分享。
- 视频解析支持长图卡片：封面、UP 主、统计、热门评论与源链接。
- 音频解析支持 `bilibili.com/audio/au...` 链接的长图卡片与文本模式。
- 可选使用 AstrBot 已配置的模型商生成视频 AI 总结（基于公开字幕或登录后 AI 字幕）。
- 可选视频下载（基于妖狐直链），带编号有效期、权限、冷却、每日上限、并发与体积/时长限制。
- 可选 `faster-whisper` 语音转写总结（需手动安装 ffmpeg 与 faster-whisper）。
