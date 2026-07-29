# PDF 页面旋转固化工具

这是一个面向 Windows 用户的小工具，用来将 PDF 页面的 `/Rotate` 旋转属性真正固化到页面内容中。

处理前后，页面肉眼看到的方向应保持一致；处理后的目标页面旋转属性为 `0`，页面宽高和内容坐标会按实际方向调整。

## 当前版本

`0.5.2`

## 适用场景

例如某一页底层是横版：

```text
MediaBox = 841.92 × 595.2
Rotate = 270
```

阅读器依靠 `Rotate = 270` 将它显示成竖版。本工具处理后，结果通常接近：

```text
MediaBox = 595.2 × 841.92
Rotate = 0
```

页面仍然正常竖向显示，但不再依赖旋转属性。

## 主要功能

- 选择一个或多个 PDF；
- 默认选中“仅处理第一页”；
- 支持“所有存在旋转属性的页面”；
- 支持“按页码处理”，例如 `1,5-9,12`；
- 支持在处理前点击“检查页面旋转”，列出所有有效 `Rotate` 不为 `0` 的页面；
- 支持把 PDF 直接拖到 EXE 图标上；
- 支持中文文件名和中文路径；
- 不覆盖原文件；
- 输出文件自动命名并避免重名；
- 写入临时文件并验证后再生成最终文件；
- 对加密、损坏或不可写文件显示中文错误；
- 检测到批注、链接或表单区域时给出警告；
- 处理前检测标准 PDF 数字签名，发现签章时要求二次确认；
- 可以打包成不需要 Python 环境的 Windows EXE；
- GUI 已重构为 PySide6，使用 `assets/lty.jpg` 提供全窗口 LTY 背景；功能区采用高透明玻璃卡片，表格/输入框/按钮也尽量透出壁纸，目标是几乎能看到原图；
- 电子签章风险使用红色常驻警示条显示。

## 界面预览

下图为 0.5.2 高透明皮肤验收效果，展示几乎通透的 LTY 原图、玻璃态控件和红色签章风险提示：

![PySide6 LTY 高透明皮肤效果](screenshot/pyside6-0.5.2-exe-final.png)

## 普通用户快速使用

1. 找到 `PDF旋转固化工具.exe`；
2. 双击打开；
3. 点击“添加 PDF”；
4. 可先点击“检查页面旋转”，确认哪些页面带旋转属性；
5. 默认保持“仅处理第一页”；如需处理其他页面，可选择“所有存在旋转属性的页面”或“按页码处理”；
6. 点击“开始处理”；
7. 在原 PDF 旁边找到 `原文件名_旋转已固化.pdf`。

完整操作说明见：[用户使用手册](docs/USER_GUIDE.md)。
皮肤布局、资源替换和构建说明见：[LTY 界面皮肤完整说明](docs/SKIN.md)。

## 开发者快速开始

### 安装依赖

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

### 运行测试

```powershell
.\.venv\Scripts\python.exe -m pytest
```

### 运行源代码

```powershell
$env:PYTHONPATH = "$PWD\src"
.\.venv\Scripts\python.exe .\main.py
```

### 构建单文件 EXE

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1
```

输出文件：`dist\PDF旋转固化工具.exe`。

构建脚本会安装依赖、运行测试、构建 EXE，并使用 EXE 处理测试 PDF 进行冒烟验证。

## 命令行模式

检查 PDF：

```powershell
$env:PYTHONPATH = "$PWD\src"
.\.venv\Scripts\python.exe -m adjust_pdf --cli input.pdf --inspect
```

处理 PDF：

```powershell
.\.venv\Scripts\python.exe -m adjust_pdf --cli input.pdf
```

只处理第一页：

```powershell
.\.venv\Scripts\python.exe -m adjust_pdf --cli input.pdf --mode first
```

处理指定页面：

```powershell
.\.venv\Scripts\python.exe -m adjust_pdf --cli input.pdf --mode selected --pages 1,3-5
```

## 项目结构

```text
src/adjust_pdf/
├─ app.py                 程序总入口
├─ cli.py                 命令行界面
├─ models.py              数据模型
├─ paths.py               输入输出路径
├─ service.py             应用服务
├─ exceptions.py          中文业务异常
├─ logging_config.py      文件日志
├─ engines/
│  ├─ base.py             PDF 引擎接口
│  └─ pypdf_engine.py     pypdf 实现
└─ gui/
   └─ main_window.py      Tkinter 窗口
```

详细设计见：[架构说明](docs/ARCHITECTURE.md)。

## 测试重点

自动化测试覆盖：

- `Rotate = 0/90/180/270`；
- 页面宽高变化；
- 多页混合旋转；
- 仅第一页；
- 指定页面；
- 中文路径；
- 输出文件重名；
- 加密 PDF；
- 批注警告；
- 处理前后页面渲染效果一致；`testFile/20260722.pdf` 存在时还会运行真实 397 页 PDF 回归测试。

## 已知限制

### 不包含 OCR

本工具只负责固化页面旋转，不会将扫描图片识别成文字，也不会直接导出 TXT。

### 批注和链接

当前 pypdf 引擎会固化页面内容和页面边界。含有链接、批注或表单的页面会显示警告，请处理后检查点击区域。后续计划增加 QPDF 引擎。

### 电子签名和电子印章

程序会检测标准 PDF 数字签名结构，自动解析 PKCS7/CMS SignedData 提取证书信息，并按**签署事件**分组展示签名人、证书序列号、颁发机构、有效期和时间戳状态。图形界面检测到签名时会先弹窗确认，默认取消；命令行模式默认拒绝处理已签名 PDF，需要明确添加 `--allow-signed`。继续处理会使新生成文件的签名验证失效，原文件不会被覆盖。

支持国密 SM2/SM3 证书标准（四川CA等），无需外部密码学库。

### 加密 PDF

当前版本只允许未加密或空密码 PDF。需要密码的 PDF 会被拒绝，不会尝试破解。

## 其他文档

- [用户使用手册](docs/USER_GUIDE.md)
- [开发指南](docs/DEVELOPMENT.md)
- [架构说明](docs/ARCHITECTURE.md)
- [发布指南](docs/RELEASE.md)
- [常见问题](docs/TROUBLESHOOTING.md)
- [PDF 结构阅读指南](docs/PDF_STRUCTURE.md)
- [签章风险说明](docs/SIGNATURE_WARNING.md)
- [界面皮肤说明](docs/SKIN.md)
- [版本记录](CHANGELOG.md)
- [PDF 结构阅读指南](docs/PDF_STRUCTURE.md)
