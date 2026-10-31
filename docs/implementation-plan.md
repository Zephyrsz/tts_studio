# TTS Studio Refactoring Implementation Plan

**Goal:** 在独立子项目中完成已确认的前后端分离重构，并保留全部 TTS 工作流。
**Architecture:** 前端静态 ES modules 通过 REST API 操作后端。后端 domain 定义数据和状态，application 管理批次，infrastructure 负责供应商、磁盘和系统目录选择。AI 模型定义保存在 config/models.json，音色保存在 data/voice_list.csv。
**Tech Stack:** Python 3.11+ 标准库、原生 HTML/CSS/JavaScript，无生产第三方依赖。
**Approved Spec:** 2026-10-31 对话已确认的 tts_studio_refactored 方案。

## Constraints
- 旧文件与当前服务保持原样；新项目不得 import 父目录旧脚本或复制密钥。
- 基础 TTS 多音色、克隆、1–10 并发（1 串行）、失败隔离、停止排队任务。
- 默认保存 outputs/{timestamp}/text.txt 和 {timestamp}-{voice}.{format}，不覆盖。
- 刷新网页可恢复同一后端进程中的任务；后端重启不自动重发付费请求。
- 密钥只保存在请求处理和执行期间，不在 API 状态或文件记录中返回。

## Tasks
- [ ] 1. 编写后端行为测试：有效/无效请求、PCM/WAV、克隆、并发上限与补位、停止、文件保存/错误、HTTP 同源限制和音频路由。运行 `python3 -m unittest discover -s backend/tests -v` 确认缺失实现时失败。
- [ ] 2. 实现 backend/domain/{models,states}.py，api/schemas.py，infrastructure/{catalog,openrouter_provider,storage,directory_picker}.py，application/{batch_service,synthesis_service}.py，config.py，api/routes.py 与 server.py。以可替换供应商测试真实服务，不发出网络合成。
- [ ] 3. 保留现有 HTML/CSS，拆分 frontend/src/{api,app}.js、state、components、audio 模块。只提交一次批次创建，轮询后端状态；试听/下载直接请求任务音频。编写浏览器测试验证批量、刷新恢复、克隆、取消、保存路径与手机布局。
- [ ] 4. 添加独立前端静态/代理服务、根 run.py 和 start.command，分别监听 8770/8771，运行 HTTP 集成测试和浏览器测试。
- [ ] 5. 写 README、架构/API/配置说明与示例配置，跑后端全量测试、JS 检查、浏览器测试及桌面/手机截图检查。确认旧文件未改，新项目无旧代码依赖。
