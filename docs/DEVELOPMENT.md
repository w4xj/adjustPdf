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

运行依赖只有 pypdf。pytest、PyInstaller 和 PyMuPDF 是开发依赖；PyMuPDF 只用于视觉一致性测试，不会打包进正式程序。

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
## 8. 页面旋转检查

GUI 中的“检查页面旋转”调用 `PdfProcessingService.inspect()`，不会写入输出文件。检查结果使用 `rotation_report.py` 格式化，再由主线程显示到可滚动窗口。

后台检查通过队列把事件传回 Tkinter 主线程，避免大型 PDF 读取时冻结窗口。报告和文件列表使用同一个 `DocumentInfo` 数据模型。

新增相关模块：

```text
src/adjust_pdf/rotation_report.py
```
## 9. 数字签名预检

`PypdfEngine.inspect()` 会扫描 AcroForm 签名字段和 Catalog `/Perms /DocMDP`。只有同时存在有效 `/ByteRange` 和非空 `/Contents` 时，字段才被判定为已写入签名数据。

相关模块：

```text
src/adjust_pdf/models.py             SignatureInfo
src/adjust_pdf/signature_report.py   风险提示和签名报告
src/adjust_pdf/engines/pypdf_engine.py
```

GUI 点击“开始处理”后先在后台执行签名预检。预检失败时整批中止；检测到签名时必须在主线程显示风险确认窗口。命令行默认拒绝已签名文件，只有显式传入 `--allow-signed` 才允许处理。

这里的检测不执行证书链、吊销状态、时间戳或密码学有效性验证。
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

## 14. LTY 背景皮肤

皮肤源图为 `assets/lty.jpg`，构建资源为 `resources/skins/lty.png`。Tkinter 通过全窗口 Canvas 显示背景，内容面板使用深色 ttk 样式覆盖在背景上。

相关文件：

```text
assets/lty.jpg
resources/skins/lty.png
scripts/create_skin_assets.ps1
src/adjust_pdf/gui/main_window.py
```

构建脚本会把 `resources/skins/lty.png` 放入 PyInstaller 的 `resources/skins` 目录。GUI 通过 `resource_path()` 同时兼容源码和 one-file EXE。

皮肤代码不能直接调用 PDF 引擎，PDF 处理功能应继续通过 `PdfProcessingService` 使用。
