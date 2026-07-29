# 发布指南

## 发布前检查

1. 更新 `src/adjust_pdf/__init__.py` 中的版本号；
2. 更新 `pyproject.toml`；
3. 更新 `resources/version_info.txt`；
4. 更新 `CHANGELOG.md`；
5. 确认 `requirements.txt` 和 `requirements-dev.txt` 的固定版本可安装；
6. 运行全部测试；
7. 构建单文件 EXE；
8. 在没有安装 Python 的 Windows 电脑或虚拟机中验收。

## 构建命令

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1
```

## 构建产物

```text
dist\PDF-如一_v0.5.3.exe
```

## 人工验收

- 双击 EXE 可以打开窗口；
- PDF 可以通过选择窗口加入；
- PDF 可以拖到 EXE 图标上加入；
- 中文路径可以处理；
- `Rotate 90/180/270` 的页面显示方向不变；
- 输出目标页面 `Rotate = 0`；
- 原文件不变；
- 同名输出自动编号；
- 加密和损坏文件提示清楚；
- 含批注页面显示警告。

## 发布包建议

将以下文件一起压缩：

```text
PDF-如一_v0.5.3.exe
用户使用手册.pdf 或 USER_GUIDE.md
版本说明.txt
```
