# PDF·如一

> PDF 页面旋转固化、页面属性检查、PDF 结构修复与数字签名风险检测工具。

[![Version](https://img.shields.io/badge/version-0.5.4-blue.svg)](CHANGELOG.md)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

PDF·如一面向 Windows 桌面用户，也支持从 Python 源码运行。它可以读取 PDF 页面属性、将页面 `/Rotate` 旋转属性固化到页面内容中，并对部分因电子签章或合并软件产生异常交叉引用的 PDF 提供只读兼容检查和无签章结构修复。

## 目录

- [功能概览](#功能概览)
- [快速开始（普通用户）](#快速开始普通用户)
- [输出文件](#输出文件)
- [签名与电子印章安全策略](#签名与电子印章安全策略)
- [从源码运行](#从源码运行)
- [命令行 CLI](#命令行-cli)
- [CLI 参数](#cli-参数)
- [构建 Windows EXE](#构建-windows-exe)
- [无皮肤版本](#无皮肤版本)
- [测试与代码质量](#测试与代码质量)
- [常见问题](#常见问题)
- [项目结构](#项目结构)
- [已知限制](#已知限制)
- [文档与许可证](#文档与许可证)

## 功能概览

### 页面处理

- 固化页面 `/Rotate` 属性，保持页面视觉方向不变；
- 默认只处理第一页；
- 处理全部存在旋转属性的页面；
- 按页码处理，例如 `1,5-9,12`；
- 输出到指定目录，不覆盖原始文件；
- 输出前使用临时文件，验证成功后再生成最终文件；
- 页面包含链接、批注或表单区域时给出警告。

### 页面检查

- **检查页面旋转**：显示旋转页面、角度、尺寸和签名信息；
- **检查页面属性**：逐页显示宽度、高度、旋转角度和批注状态；
- 支持检查部分非标准 xref 结构，解决部分文件的 `Could not read Boolean object` 读取错误。

### PDF 结构修复

- **修复 PDF 结构**：针对空 xref、重复对象映射等特定结构异常，重建为普通解析器可以读取的 PDF；
- 只处理确认没有已写入数字签名、电子签章和 Stamp 印章批注的文件；
- 不覆盖原始文件，输出文件使用 `_结构已修复` 后缀；
- 写出后校验页数、页面框、旋转、页面内容流和批注状态。

### 其他

- 支持一个或多个 PDF 文件；
- 支持拖放 PDF 到 GUI 或 Windows EXE；
- 支持中文文件名和中文路径；
- 解析标准 PDF 数字签名、PKCS7/CMS 证书和签署事件；
- 可构建为不依赖 Python 环境的 Windows 单文件 EXE；
- 提供 LTY 背景皮肤，也支持构建无皮肤版本。

## 界面预览

![PySide6 LTY 透明皮肤](screenshot/pyside6-0.5.2-exe-final.png)

## 快速开始（普通用户）

### 使用 Windows EXE

1. 从 `dist` 目录获取 `PDF-如一_v0.5.4.exe`；
2. 双击运行，或将一个或多个 PDF 拖到 EXE 图标上；
3. 点击“添加 PDF”继续添加文件；
4. 建议先点击“检查页面旋转”或“检查页面属性”；
5. 如果文件出现 `Could not read Boolean object`，且确认没有签章，可以点击“修复 PDF 结构”；
6. 选择处理模式和输出位置；
7. 点击“开始处理”；
8. 在输出目录中查看生成的新文件。

> EXE 用户不需要安装 Python、pypdf、PySide6 或 PyInstaller。

### GUI 按钮说明

| 按钮 | 用途 | 是否生成新文件 |
| --- | --- | --- |
| 检查页面旋转 | 检查每页有效 `/Rotate` 和签名状态 | 否 |
| 检查页面属性 | 查看每页宽度、高度、旋转和批注状态 | 否 |
| 修复 PDF 结构 | 修复特定 xref 异常，严格拒绝签章文件 | 是，`_结构已修复.pdf` |
| 开始处理 | 按处理选项固化页面旋转 | 是，`_旋转已固化.pdf` |

## 输出文件

程序不会覆盖输入文件。默认输出到输入 PDF 所在目录，也可以在 GUI 中选择输出目录，或通过 CLI 使用 `--output-dir`。

### 页面旋转处理

```text
输入：材料.pdf
输出：材料_旋转已固化.pdf
```

如果目标文件已经存在，会自动生成：

```text
材料_旋转已固化_2.pdf
材料_旋转已固化_3.pdf
```

### PDF 结构修复

```text
输入：材料.pdf
输出：材料_结构已修复.pdf
```

结构修复成功后，输出文件应当可以被普通 `pypdf` 以 `strict=False` 方式正常读取。原始文件仍然保留。

## 签名与电子印章安全策略

### 页面旋转处理

GUI 会在“开始处理”前进行签名预检。检测到已写入的标准数字签名时，GUI 默认停止；用户明确确认风险后才可以继续生成一个签名验证会失效的新文件。

CLI 默认也拒绝处理已签名文件。只有明确确认风险后，才可以添加：

```text
--allow-signed
```

### PDF 结构修复

结构修复比页面旋转处理更加严格，**没有签章风险绕过选项**。以下情况会直接拒绝：

- 存在已写入的数字签名或电子签章；
- 页面批注中存在 `/Subtype /Stamp`；
- 无法完整检查页面批注；
- 文件不属于当前兼容修复器能够识别的目标 xref 异常。

如果印章只是页面内容中的普通图片，且没有标准数字签名或 Stamp 批注结构，程序无法仅凭视觉判断其是否属于有效电子印章，需要人工确认。

> 任何重新写入 PDF 的操作都可能使已有签名失效。正式验签、归档或提交时，应始终保留并使用原始签章文件。

## 从源码运行

### 环境要求

- Windows 10/11（GUI 和 EXE 主要面向 Windows）；
- Python 3.11 或更高版本；
- Git（如果从 Git 仓库获取源码）。

### 创建虚拟环境并安装依赖

第一步，创建虚拟环境并升级 pip。

PowerShell：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
```

CMD：

```cmd
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
```

第二步，根据用途选择一种安装方式。

仅运行 GUI 或 CLI：

```cmd
.venv\Scripts\python.exe -m pip install -e .
```

参与开发、运行测试或构建 EXE：

```cmd
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

也可以使用兼容的 requirements 入口：

```cmd
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

### 启动 GUI

PowerShell：

```powershell
.\.venv\Scripts\python.exe -m adjust_pdf
```

CMD：

```cmd
.venv\Scripts\python.exe -m adjust_pdf
```

也可以直接运行：

```cmd
.venv\Scripts\python.exe main.py
```

### 查看 CLI 帮助

```cmd
.venv\Scripts\python.exe -m adjust_pdf --cli --help
```

安装为可编辑包后，也可以使用项目脚本入口：

```cmd
adjust-pdf
adjust-pdf-cli --help
```

其中 `adjust-pdf` 启动 GUI，`adjust-pdf-cli` 启动命令行接口。

## 命令行 CLI

CLI 适合批量处理、自动化脚本和无 GUI 环境。CLI 入口有两种写法，功能相同：

```cmd
.venv\Scripts\python.exe -m adjust_pdf --cli <文件或文件列表> [参数]
adjust-pdf-cli <文件或文件列表> [参数]
```

### 只检查，不生成文件

检查页面旋转、页面尺寸、批注和签名信息：

```cmd
.venv\Scripts\python.exe -m adjust_pdf --cli "input.pdf" --inspect
```

多个文件：

```cmd
.venv\Scripts\python.exe -m adjust_pdf --cli "a.pdf" "b.pdf" --inspect
```

### 处理全部旋转页面

```cmd
.venv\Scripts\python.exe -m adjust_pdf --cli "input.pdf" --mode rotated
```

### 只处理第一页

`first` 是默认模式：

```cmd
.venv\Scripts\python.exe -m adjust_pdf --cli "input.pdf" --mode first
```

也可以省略 `--mode first`：

```cmd
.venv\Scripts\python.exe -m adjust_pdf --cli "input.pdf"
```

### 按指定页码处理

```cmd
.venv\Scripts\python.exe -m adjust_pdf --cli "input.pdf" --mode selected --pages "1,3-5,9"
```

页码规则：

- 页码从 `1` 开始；
- 使用逗号分隔多个页码或范围；
- `3-5` 表示第 3、4、5 页；
- 允许混合使用，例如 `1,3-5,9`；
- `--mode selected` 必须同时提供 `--pages`。

### 指定输出目录

```cmd
.venv\Scripts\python.exe -m adjust_pdf --cli "input.pdf" --mode rotated --output-dir "D:\PDF\output"
```

### 已签名文件

默认情况下，CLI 拒绝处理已签名 PDF：

```cmd
.venv\Scripts\python.exe -m adjust_pdf --cli "signed.pdf" --mode rotated
```

如果已经确认新文件的签名验证会失效，可以显式允许：

```cmd
.venv\Scripts\python.exe -m adjust_pdf --cli "signed.pdf" --mode rotated --allow-signed
```

`--allow-signed` **只适用于页面旋转处理，不适用于“修复 PDF 结构”**。结构修复目前只提供 GUI 入口，并且始终拒绝已签章文件。

## CLI 参数

| 参数 | 类型/取值 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `files` | 一个或多个路径 | 必填 | 输入 PDF 文件，可使用引号包裹含空格或中文的路径 |
| `--inspect` | 开关 | 关闭 | 只检查，不生成输出文件 |
| `--mode` | `first` / `rotated` / `selected` | `first` | 选择处理第一页、全部旋转页或指定页 |
| `--pages` | 页码文本 | 空 | 仅 `selected` 模式使用，例如 `1,3-5,9` |
| `--output-dir` | 文件夹路径 | 输入文件目录 | 指定输出目录 |
| `--allow-signed` | 开关 | 关闭 | 允许页面旋转处理已签名文件；有签章风险 |
| `--help` | 开关 | 关闭 | 显示帮助信息 |

### CLI 返回码

| 返回码 | 含义 |
| ---: | --- |
| `0` | 所有输入文件处理或检查成功 |
| `1` | 至少一个文件处理失败，或签名策略拒绝处理 |
| `2` | 发生未预期错误或命令行参数错误 |

## 构建 Windows EXE

### 推荐方式：使用构建脚本

构建脚本会根据当前版本号执行以下步骤：

1. 使用现有 `.venv`，或创建 `.venv-build`；
2. 安装 `requirements-dev.txt`；
3. 运行 pytest；
4. 构建 PyInstaller EXE；
5. 运行 EXE 冒烟测试；
6. 如果存在真实测试文件，执行真实 PDF、按页码和签名安全回归测试；
7. 输出带版本号的文件。

PowerShell：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build.ps1
```

构建单目录版本：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build.ps1 -Mode OneDir
```

构建脚本参数：

| 参数 | 说明 |
| --- | --- |
| `-Mode OneFile` | 单文件 EXE，默认，方便分发 |
| `-Mode OneDir` | 目录版 EXE，启动和更新资源更方便 |
| `-SkipInstall` | 不执行依赖安装，适合依赖已经准备好的环境 |
| `-SkipTests` | 不运行 pytest；不建议日常发布时使用 |
| `-SkipSmokeTest` | 不运行 EXE 冒烟和真实 PDF 回归；不建议日常发布时使用 |

### CMD 直接打包

如果不想执行构建脚本，或当前 PowerShell 策略不允许执行 `.ps1`，可以在项目根目录的 CMD 中直接运行：

```cmd
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --windowed --onefile --name "PDF-如一" --paths ".\src" --icon ".\resources\app.ico" --add-data ".\resources\app.ico;resources" --add-data ".\resources\skins\lty.png;resources/skins" --version-file ".\resources\version_info.txt" ".\main.py"
```

该命令生成：

```text
dist\PDF-如一.exe
```

如果需要按版本号重命名，当前版本为 `0.5.4`：

```cmd
move /Y "dist\PDF-如一.exe" "dist\PDF-如一_v0.5.4.exe"
```

### PyInstaller 参数说明

| 参数 | 作用 |
| --- | --- |
| `--noconfirm` | 自动覆盖 PyInstaller 的旧构建目录，不交互确认 |
| `--clean` | 构建前清理 PyInstaller 缓存和临时分析结果 |
| `--windowed` | 构建 Windows GUI 程序，启动时不显示控制台窗口 |
| `--onefile` | 将程序、Python 运行时和依赖封装为一个 EXE |
| `--name` | 设置生成的 EXE 名称 |
| `--paths ".\src"` | 将 `src` 加入模块搜索路径 |
| `--icon` | 设置 Windows EXE 图标 |
| `--add-data` | 将图标、皮肤等非 Python 资源加入 EXE |
| `--version-file` | 写入 Windows 文件版本、产品版本和描述 |
| `.\main.py` | PyInstaller 使用的程序入口 |

## 无皮肤版本

“不带皮肤”表示不把 `resources/skins/lty.png` 加入 EXE。程序找不到皮肤资源时会使用内置深色背景；界面的透明卡片、金色边框和按钮样式仍然保留。

CMD 一行命令：

```cmd
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --windowed --onefile --name "PDF-如一_无皮肤" --paths ".\src" --icon ".\resources\app.ico" --add-data ".\resources\app.ico;resources" --version-file ".\resources\version_info.txt" ".\main.py"
```

输出文件：

```text
dist\PDF-如一_无皮肤.exe
```

如果希望连 Windows 图标也不包含，可以同时删除 `--icon` 和图标对应的 `--add-data`：

```cmd
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --windowed --onefile --name "PDF-如一_无皮肤无图标" --paths ".\src" --version-file ".\resources\version_info.txt" ".\main.py"
```

> 如果希望完全移除透明卡片和配色，而不仅是移除背景图片，需要修改或禁用 `MainWindow._apply_style()`，这不是单纯调整 PyInstaller 参数能够完成的。

## 测试与代码质量

### 运行全部测试

```cmd
.venv\Scripts\python.exe -m pytest
```

### 运行指定测试

```cmd
.venv\Scripts\python.exe -m pytest tests\test_pypdf_engine.py -q
```

### Ruff 静态检查和格式检查

```cmd
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
```

自动格式化：

```cmd
.venv\Scripts\python.exe -m ruff format .
```

### 统一开发任务

```cmd
.venv\Scripts\python.exe -m nox
```

### 安装 Git hooks

```cmd
.venv\Scripts\python.exe -m pre_commit install
```

### 构建后冒烟测试

```cmd
.venv\Scripts\python.exe scripts\smoke_test_exe.py "dist\PDF-如一_v0.5.4.exe"
```

完整发布流程建议使用 `scripts\build.ps1`，因为它会额外执行真实 PDF、按页码和签名安全测试。

## 常见问题

### PowerShell 提示禁止执行脚本

使用临时执行策略：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build.ps1
```

如果环境仍然阻止 `.ps1`，使用上面的“CMD 直接打包”命令。

### 提示找不到 PyInstaller

确认已经安装开发依赖：

```cmd
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

然后检查：

```cmd
.venv\Scripts\python.exe -m PyInstaller --version
```

### EXE 打开后没有背景图片

确认构建命令包含：

```text
--add-data ".\resources\skins\lty.png;resources/skins"
```

无皮肤版本没有该资源，会使用内置深色背景，这是预期行为。

### 出现 Could not read Boolean object

先使用“检查页面旋转”或“检查页面属性”。当前版本会尝试兼容读取部分空 xref 和重复对象映射。如果希望生成标准结构的新文件，可使用 GUI 的“修复 PDF 结构”，但只有未签章且属于支持范围的文件才允许修复。

### 已签名 PDF 为什么被拒绝

重新写入 PDF 会改变字节内容和交叉引用，原数字签名通常会失效。页面旋转处理可以在明确承担风险后继续；结构修复始终拒绝已签章文件。

### 为什么处理后文件大小不同

PDF 重新写出时，对象顺序、xref、压缩方式和序列化格式可能变化。程序重点校验页面尺寸、旋转、内容流和输出可读性，不保证输出文件与输入文件二进制一致。

### 如何查看日志

GUI 和 CLI 启动时会初始化应用日志。遇到问题时，可同时提供：

- 输入文件的错误提示；
- 应用显示或生成的日志；
- Python 和 Windows 版本；
- 使用的命令或操作步骤。

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
│   │   ├── compatible_reader.py  异常 xref 兼容解析
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
- 数字签名 PDF 默认拒绝处理，因为输出文件的签名验证会失效；明确确认风险后可在 CLI 中使用 `--allow-signed`；
- 结构修复不支持任意 PDF 损坏，只处理当前兼容器能够确认的特定 xref 异常；
- 普通图片形式的红章不一定具有标准签名或 Stamp 结构，程序无法仅凭视觉判断；
- 当前只处理未加密或空密码 PDF，不会尝试破解密码。

## 文档与许可证

### 相关文档

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

### 许可证

本项目采用 [MIT License](LICENSE)。
