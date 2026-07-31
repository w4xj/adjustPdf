# PDF·如一

PDF 页面旋转固化与数字签名风险检测工具。它将页面的 `Rotate` 属性固化到页面内容和尺寸中，在保持视觉效果基本不变的同时，让输出 PDF 不再依赖页面旋转属性。

## 当前版本

`0.5.3`

## 主要功能

- 选择一个或多个 PDF 文件；
- 默认仅处理第一页；
- 处理所有存在旋转属性的页面；
- 按页码处理，例如 `1,5-9,12`；
- 处理前检查页面旋转和页面尺寸；
- 支持拖放 PDF 到 Windows EXE；
- 支持中文文件名和中文路径；
- 不覆盖原始文件，自动生成不重复的输出文件名；
- 写入临时文件并完成结果验证后再生成最终文件；
- 对加密、损坏、批注、链接和表单区域给出明确提示；
- 检测标准 PDF 数字签名，解析 PKCS7/CMS 证书信息并按签署事件展示；
- GUI 使用 PySide6 和 LTY 背景皮肤；
- 可构建为不依赖 Python 环境的 Windows EXE。

## 界面预览

![PySide6 LTY 透明皮肤](screenshot/pyside6-0.5.2-exe-final.png)

## 普通用户快速使用

1. 双击 `PDF-如一.exe`；
2. 点击“添加 PDF”，或将 PDF 拖到 EXE 图标上；
3. 可先点击“检查页面旋转”或“检查页面属性”；
4. 选择处理模式；
5. 点击“开始处理”；
6. 在原 PDF 所在目录中找到自动生成的输出文件。

完整说明见[用户使用手册](docs/USER_GUIDE.md)。

## 开发环境

项目采用 `src` 目录布局，要求 Python 3.11 或更高版本。

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

运行源代码：

```powershell
.\.venv\Scripts\python.exe -m adjust_pdf
```

直接运行 CLI：

```powershell
.\.venv\Scripts\python.exe -m adjust_pdf --cli input.pdf --inspect
.\.venv\Scripts\python.exe -m adjust_pdf --cli input.pdf --mode selected --pages 1,3-5
```

## 测试与代码质量

运行全部测试：

```powershell
.\.venv\Scripts\python.exe -m pytest
```

运行 Ruff 检查：

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
```

运行统一开发任务：

```powershell
.\.venv\Scripts\python.exe -m nox
```

安装 Git hooks：

```powershell
.\.venv\Scripts\python.exe -m pre_commit install
```

## 构建 Windows EXE

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1
```

构建脚本会安装开发依赖、运行测试、构建单文件 EXE，并执行冒烟测试。输出文件位于：

```text
dist\PDF-如一_v0.5.3.exe
```

如需构建目录版：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1 -Mode OneDir
```

## 项目结构

```text
adjustPdf/
├── src/adjust_pdf/
│   ├── app.py                    GUI/CLI 总入口
│   ├── cli.py                    命令行参数与执行入口
│   ├── models.py                 数据模型
│   ├── service.py                应用服务编排
│   ├── paths.py                  输入输出路径处理
│   ├── page_ranges.py            页码解析
│   ├── page_properties_report.py 页面属性报告
│   ├── rotation_report.py        旋转检查报告
│   ├── signature_parser.py       PKCS7/CMS 签名解析
│   ├── signature_report.py       签名风险报告
│   ├── logging_config.py         日志配置
│   ├── exceptions.py             业务异常
│   ├── engines/
│   │   ├── base.py               PDF 引擎接口
│   │   └── pypdf_engine.py       pypdf 实现
│   └── gui/
│       └── main_window.py        PySide6 主窗口
├── tests/                        自动化测试
├── docs/                         用户、开发、架构和发布文档
├── scripts/                      构建、检查和验证脚本
├── resources/                    图标、皮肤和版本资源
├── pyproject.toml                包元数据与工具配置
└── requirements*.txt             pip 兼容入口
```

## 已知限制

- 当前工具不包含 OCR，不会把扫描图片识别为文本；
- 包含批注、链接或表单的页面会显示警告，处理后应人工检查交互区域；
- 数字签名 PDF 默认拒绝处理，因为输出文件的签名验证会失效；确认风险后可在 CLI 中使用 `--allow-signed`；
- 当前只处理未加密或空密码 PDF，不会尝试破解密码。

## 文档

- [用户使用手册](docs/USER_GUIDE.md)
- [开发指南](docs/DEVELOPMENT.md)
- [架构说明](docs/ARCHITECTURE.md)
- [发布指南](docs/RELEASE.md)
- [故障排查](docs/TROUBLESHOOTING.md)
- [PDF 结构阅读指南](docs/PDF_STRUCTURE.md)
- [签名风险说明](docs/SIGNATURE_WARNING.md)
- [界面皮肤说明](docs/SKIN.md)
- [版本记录](CHANGELOG.md)
- [贡献指南](CONTRIBUTING.md)
- [行为准则](CODE_OF_CONDUCT.md)

## 许可证

本项目采用 [MIT License](LICENSE)。
