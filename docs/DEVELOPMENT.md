# 开发指南

## 1. 环境要求

- Windows 10/11；
- Python 3.11 或更高版本；
- PowerShell；
- Git（用于版本控制和 pre-commit）。

普通用户只需要使用构建后的 EXE，不需要安装 Python。

## 2. 创建虚拟环境

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
```

## 3. 安装依赖

项目的依赖统一声明在 `pyproject.toml`：

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

`requirements.txt` 和 `requirements-dev.txt` 仅作为兼容旧工作流的 pip 入口，不再重复维护依赖版本。

## 4. 运行程序

```powershell
.\.venv\Scripts\python.exe -m adjust_pdf
.\.venv\Scripts\python.exe .\main.py
```

## 5. 运行测试

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m pytest --cov=adjust_pdf --cov-report=term-missing
```

只运行核心引擎测试：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_pypdf_engine.py
```

## 6. 代码质量

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m nox
```

自动修复并格式化：

```powershell
.\.venv\Scripts\python.exe -m nox -s format
```

安装提交前检查：

```powershell
.\.venv\Scripts\python.exe -m pre_commit install
.\.venv\Scripts\python.exe -m pre_commit run --all-files
```

## 7. 命令行模式

```powershell
.\.venv\Scripts\python.exe -m adjust_pdf --cli input.pdf --inspect
.\.venv\Scripts\python.exe -m adjust_pdf --cli input.pdf
.\.venv\Scripts\python.exe -m adjust_pdf --cli input.pdf --mode first
.\.venv\Scripts\python.exe -m adjust_pdf --cli input.pdf --mode selected --pages 1,5-9,12
```

已签名 PDF 默认拒绝处理；确认风险后显式增加 `--allow-signed`。

## 8. 构建 EXE

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1 -Mode OneDir
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1 -SkipInstall
```

构建脚本默认执行测试、构建、EXE 冒烟测试和可用真实 PDF 样本的回归测试。

## 9. 目录职责

- `src/adjust_pdf/engines/`：PDF 引擎接口和具体实现；
- `src/adjust_pdf/service.py`：业务流程编排；
- `src/adjust_pdf/gui/`：PySide6 界面与交互；
- `src/adjust_pdf/*_report.py`：检查结果和风险报告格式化；
- `tests/`：单元测试、GUI 测试和 PDF 回归测试；
- `scripts/`：构建和 EXE 验证脚本；
- `docs/`：用户、开发、架构和发布文档。

不为了目录完整而创建空的 `utils/` 包；只有出现稳定的跨模块通用逻辑时才新增工具模块。

## 10. 编码和安全约定

- 文本文件统一使用 UTF-8；
- 面向用户的文字使用中文；
- 不覆盖输入 PDF；
- 不在 GUI 模块中编写 PDF 业务逻辑；
- 修改签名、批注、链接和表单相关逻辑时必须补充回归测试；
- 不提交个人 PDF、密钥、日志、构建产物或本地截图。
