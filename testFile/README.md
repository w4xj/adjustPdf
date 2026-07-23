# 真实 PDF 测试文件

此目录用于放置不适合提交到代码仓库的大型真实 PDF 样本。

当前本地样本：

```text
20260722.pdf
```

该文件第一页的已知特征：

```text
页数：397
MediaBox：841.92 × 595.2
Rotate：270
显示效果：PDF 阅读器中正常竖向显示
```

处理后的验收要求：

```text
第一页 MediaBox：595.2 × 841.92
第一页 Rotate：0
阅读器显示方向与处理前一致
全部页面数量保持为 397
```

自动化测试和 EXE 回归测试会在该文件存在时使用它；文件不存在时会自动跳过。

运行真实样本 EXE 测试：

```powershell
.\.venv\Scripts\python.exe .\scripts\verify_real_fixture.py .\dist\PDF旋转固化工具.exe
```

生成的 `*_旋转已固化*.pdf` 属于测试产物，不应提交到仓库。
