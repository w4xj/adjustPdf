# 架构说明

## 目标

第一版只解决 PDF 页面旋转消除问题，同时为 QPDF、OCR、页面预览和批量处理保留扩展位置。

## 分层

```text
GUI / CLI
    ↓
PdfProcessingService
    ↓
PdfEngine 接口
    ↓
PypdfEngine
```

### GUI 和 CLI

GUI 使用 PySide6，CLI 使用 argparse。两者只负责接收用户输入、调用服务和显示结果，不直接操作 PDF。GUI 的背景、半透明卡片和 Qt 工作线程事件轮询均属于表现层。

### PdfProcessingService

负责验证输入路径、生成安全的输出文件名、调用 PDF 引擎和记录日志。

### PdfEngine

定义 `inspect()` 和 `process()` 两个接口。未来的 QPDF 引擎可以替换 pypdf 引擎而不影响界面。

### PypdfEngine

负责读取页面旋转、调用 `transfer_rotation_to_content()`、保存临时文件以及验证输出。

## 数据流

```text
选择输入 PDF
  → 验证路径和扩展名
  → 生成不重名输出路径
  → 读取 PDF
  → 将页面加入 PdfWriter
  → 固化目标页面旋转
  → 写入同目录临时文件
  → 重新打开并验证页数和 Rotate
  → 原子改名为最终输出文件
```

## 为什么先把页面加入 Writer

pypdf 建议对已经归属于 Writer 的页面修改内容。程序先复制所有页面到 Writer，再固化旋转，避免对游离页面修改内容。

## 安全边界

- 输出路径不得等于输入路径；
- 输出文件已存在时自动编号；
- 最终文件写入前必须通过重新读取验证；
- 失败时删除临时文件；
- 不上传 PDF；
- 日志不记录 PDF 内容。

## 扩展方向

### QPDF 引擎

用于增强带批注、链接和表单 PDF 的兼容性。

### OCR 模块

应独立放在 `ocr/` 中，不能与页面结构处理混在 pypdf 引擎里。

### 页面预览

可以使用单独的渲染模块生成缩略图，GUI 只消费渲染结果。
