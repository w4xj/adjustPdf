# 发布指南

## 发布前检查

1. 确认 `pyproject.toml`、`src/adjust_pdf/__init__.py`、README 和 `resources/version_info.txt` 使用同一版本号；
2. 在 `CHANGELOG.md` 中补充本次版本记录；
3. 确认运行时和开发依赖可以从 `pyproject.toml` 安装；
4. 运行 Ruff 检查和全部测试；
5. 构建单文件 EXE；
6. 运行 EXE 冒烟测试及可用的真实 PDF 回归测试；
7. 在干净的 Windows 环境中验证 EXE 可以启动、选择 PDF、拖放 PDF 和生成输出；
8. 检查发布包中没有日志、个人文件和临时截图。

## 检查命令

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest
```

## 构建命令

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1
```

构建产物示例：

```text
dist\PDF-如一_v0.5.3.exe
```

## 人工验收

- 双击 EXE 可以打开窗口；
- 可以通过选择窗口添加 PDF；
- 可以将 PDF 拖到 EXE 图标上；
- 中文路径和中文文件名可以正常处理；
- `Rotate = 90/180/270` 的页面视觉方向不变；
- 输出页面的 `Rotate = 0`；
- 原始 PDF 不会被覆盖；
- 同名输出会自动编号；
- 加密、损坏和签名 PDF 的提示清晰；
- 包含批注、链接或表单的页面显示风险警告。
