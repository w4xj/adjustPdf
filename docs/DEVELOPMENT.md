# 开发指南

## 1. 环境要求

构建电脑需要 Windows 10/11、Python 3.11 或更高版本以及 PowerShell。目标用户电脑不需要 Python。

## 2. 创建虚拟环境

```powershell
py -3.11 -m venv .venv
```

## 3. 安装依赖

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

运行依赖包括 pypdf 和 PySide6。pytest、PyInstaller 和 PyMuPDF 是开发依赖；PyMuPDF 只用于 PDF 视觉一致性测试，不会因为测试用途额外打包进正式程序。

## 4. 运行程序

项目使用 `src` 目录布局，直接运行前需要设置：

```powershell
$env:PYTHONPATH = "$PWD\src"
.\.venv\Scripts\python.exe .\main.py
```

在 PyCharm 中也可以将 `src` 标记为 Sources Root。

## 5. 运行测试

```powershell
.\.venv\Scripts\python.exe -m pytest
```

只运行核心引擎测试：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_pypdf_engine.py
```

## 6. 命令行模式

```powershell
$env:PYTHONPATH = "$PWD\src"
.\.venv\Scripts\python.exe -m adjust_pdf --cli input.pdf --inspect
.\.venv\Scripts\python.exe -m adjust_pdf --cli input.pdf
```

## 7. 页码选择功能

图形界面提供三种模式：

- 仅处理第一页：默认模式；
- 所有存在旋转属性的页面；
- 按页码处理：输入例如 `1,5-9,12`。

页码解析位于 `src/adjust_pdf/page_ranges.py`，GUI 和 CLI 共用同一套解析逻辑。解析结果会去重、排序，并在 PDF 引擎中继续检查是否超过当前文件总页数。

命令行示例：

```powershell
$env:PYTHONPATH = "$PWD\src"
.\.venv\Scripts\python.exe -m adjust_pdf --cli input.pdf --mode selected --pages 1,5-9,12
```
## 8. 页面旋转检查和页面属性检查

GUI 中的”检查页面旋转”和”检查页面属性”都调用 `PdfProcessingService.inspect()`，不会写入输出文件。前者只显示有旋转属性的页面，附带签名状态；后者逐页显示宽、高、旋转属性。

后台检查通过队列和 QTimer 把事件传回 Qt 主线程，避免大型 PDF 读取时冻结窗口。报告和文件列表使用同一个 `DocumentInfo` 数据模型。

相关模块：

```text
src/adjust_pdf/rotation_report.py          旋转和签名检查报告
src/adjust_pdf/page_properties_report.py    页面属性详细报告
```
## 9. 数字签名预检

`PypdfEngine.inspect()` 会扫描 AcroForm 签名字段和 Catalog `/Perms /DocMDP`。只有同时存在有效 `/ByteRange` 和非空 `/Contents` 时，字段才被判定为已写入签名数据。

程序还会自动解析 `/Contents` 中的 PKCS7/CMS SignedData DER 结构，提取证书信息（签名人、颁发机构、序列号、有效期）并检测时间戳。同一签署事件内的多个签名字段会自动合并分组展示。

相关模块：

```text
src/adjust_pdf/models.py              SignatureInfo
src/adjust_pdf/signature_report.py     风险提示和签名报告
src/adjust_pdf/signature_parser.py     PKCS7 解析和证书提取
src/adjust_pdf/engines/pypdf_engine.py
```

GUI 点击”开始处理”后先在后台执行签名预检。预检失败时整批中止；检测到签名时必须在主线程显示风险确认窗口。命令行默认拒绝已签名文件，只有显式传入 `--allow-signed` 才允许处理。

PKCS7 解析使用自定义 ASN.1 DER 解析器（配合 asn1crypto 库），支持国密 SM2/SM3 标准证书，不依赖 OpenSSL 或 cryptography 等对国密算法支持有限的库。解析失败不会影响签名检测结果，证书信息字段保持空值。
## 10. 构建 EXE

单文件版本：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1
```

目录版本：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1 -Mode OneDir
```

跳过重复安装依赖：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1 -SkipInstall
```

不建议跳过测试。如需排查构建问题，可临时使用 `-SkipTests -SkipSmokeTest`。

## 11. 清理构建文件

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\clean.ps1
```

脚本只会删除项目内的 `build/`、`dist/` 和 `.pytest_cache/`。

## 12. 添加新的 PDF 引擎

新引擎需要实现 `PdfEngine` 中的 `inspect()` 和 `process()`。例如未来增加 `src/adjust_pdf/engines/qpdf_engine.py`，再通过 `PdfProcessingService(engine=QpdfEngine())` 使用，GUI 不需要重写。

## 13. 编码约定

- 所有文本文件使用 UTF-8；
- 用户可见文字使用中文；
- 不直接覆盖输入 PDF；
- 不在 GUI 模块中写 PDF 业务逻辑；
- 新功能必须补充测试和文档。

## 14. PySide6 与 LTY 背景皮肤

GUI 使用 PySide6。`BackgroundWidget` 在 `paintEvent()` 中按比例铺满并居中裁剪 `resources/skins/lty.png`；主布局使用四张半透明 `QFrame` 卡片承载标题、文件列表、处理选项和执行状态。

关键实现：

```text
BackgroundWidget.paintEvent()    背景缩放、居中裁剪和轻度渐变
MainWindow._build_widgets()      四张卡片和全部控件
MainWindow._apply_style()        RGBA 半透明、红色警示、表格与按钮样式
QTimer + queue.Queue             将工作线程事件安全地转回 GUI 主线程
```

开发环境安装 `requirements.txt` 时会安装 PySide6。构建脚本会打包 `resources/skins/lty.png` 和应用图标，PyInstaller 自动分析 Qt 依赖。

截图验收可以使用 `QT_QPA_PLATFORM=offscreen` 创建真实 Qt 窗口，再用 `QWidget.grab()` 保存 PNG；这能在不依赖人工截屏的情况下检查背景、控件尺寸和默认状态。

皮肤代码不能直接调用 PDF 引擎，所有检查和处理仍通过 `PdfProcessingService`。完整说明见 [SKIN.md](SKIN.md)。
