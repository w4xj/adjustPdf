# 贡献指南

感谢你为「PDF·如一」贡献代码、文档或问题反馈。

## 开发环境

项目使用 Python 3.11 或更高版本，推荐在 Windows 10/11 上开发：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

## 开发流程

1. 从 `main` 或当前稳定分支创建功能分支。
2. 优先为行为变化补充测试。
3. 保持 PDF 业务逻辑位于 `service.py` 或引擎模块，GUI 只负责交互和展示。
4. 不要覆盖用户原始 PDF；涉及签名、批注、链接或表单时，保留现有安全警告。
5. 更新必要的文档和 `CHANGELOG.md`。
6. 提交前运行质量检查：

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest
```

也可以运行：

```powershell
.\.venv\Scripts\python.exe -m nox
```

## 提交规范

提交信息建议使用简短的动词开头，例如：

- `feat: 增加按页码处理模式`
- `fix: 修复中文路径下的输出命名`
- `docs: 更新发布说明`
- `test: 增加签名保护回归测试`
- `chore: 更新开发工具配置`

## Pull Request

Pull Request 请说明：

- 变更目的和主要实现；
- 测试命令及结果；
- 是否影响 GUI、CLI、PDF 输出或 EXE 构建；
- 是否需要同步更新文档或版本记录。

请不要提交密码、证书、个人 PDF、构建产物、日志或未经压缩的大型截图。
