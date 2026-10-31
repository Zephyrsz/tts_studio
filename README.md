# Kotoba TTS Studio（前后端分离版）

这是 tts_test 的独立重构子项目，旧版文件不会被本项目导入或修改。

## 启动

进入 tts_studio_refactored 目录，设置 OPENROUTER_API_KEY 后运行 python3 run.py。
打开 http://127.0.0.1:8770。后端 API 在 http://127.0.0.1:8771。

模型目录在 config/models.json，音色目录在 data/voice_list.csv，不要把密钥写入项目文件。

## 架构

- backend/domain：音色、批次、任务和合成请求模型。
- backend/application：批次并发调度、停止、状态持久化。
- backend/infrastructure：OpenRouter、音频存储、目录选择和音色目录。
- backend/server.py：HTTP API 边界，不包含页面代码。
- frontend/src：API 客户端、批次状态轮询、表单和结果渲染。
- frontend/index.html 与 style.css：页面结构和浅色视觉样式。

## 批次输出

后端先创建 outputs/{timestamp} 并写入 text.txt，每个任务完成后原子保存音频。已有批次目录或音频不会覆盖。刷新前端会从后端读取批次；后端重启后不会重发未完成的付费请求。

## 测试

运行 python3 -m unittest discover -s backend/tests -v 和 node frontend/tests/smoke.mjs。
