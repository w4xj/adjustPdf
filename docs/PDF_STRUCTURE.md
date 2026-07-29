# PDF 文件结构深入阅读指南

> 本文以 `testFile/20260722.pdf` 为实际样本，从字节级结构、对象语法、页面树、内容流、图片、文字、批注、交叉引用到增量更新，逐层解释怎样阅读 PDF。

## 阅读目标

读完本文后，你应该能够：

- 理解为什么 PDF 不能当作普通 TXT 顺序阅读；
- 看懂 `3 0 obj`、`<< >>`、`20645 0 R`、`stream` 等基本语法；
- 从 Catalog 找到 Pages，再找到具体 Page；
- 判断一页是文字页、图片扫描页，还是混合页；
- 理解 `/MediaBox`、`/CropBox`、`/Rotate` 的关系；
- 理解为什么直接搜索 `/Rotate` 次数不可靠；
- 理解 xref、xref stream、object stream 和增量保存；
- 使用本项目的检查脚本安全分析 PDF。

---

# 一、PDF 整体结构

## 1.1 PDF 本质是什么

PDF 不是一篇从上到下排列的普通文本，而是一个由对象组成的二进制文档。对象之间通过编号互相引用，阅读器通过交叉引用索引快速定位对象。

可以把 PDF 想象成一个小型对象数据库：

~~~text
对象 1：文档根目录 Catalog
对象 2：页面树 Pages
对象 3：第一页 Page
对象 20645：第一页绘制指令 Contents
对象 20646：第一页扫描图片 Image XObject
对象 20782：交叉引用流 XRef
~~~

## 1.2 传统 PDF 的物理组成

传统 PDF 通常可以分为：

~~~text
Header 文件头
  ↓
Body 对象区
  ↓
Cross-reference table 交叉引用表
  ↓
Trailer 文件尾字典
  ↓
startxref
%%EOF
~~~

## 1.3 你的 PDF 使用的现代结构

`20260722.pdf` 是 PDF 1.7，并使用了对象流和交叉引用流：

~~~text
%PDF-1.7
  ↓
普通间接对象
  +
ObjStm 压缩对象流
  +
页面、图片、字体和内容数据流
  ↓
XRef Stream 交叉引用流
  ↓
startxref 37342990
%%EOF
~~~

因此，TXT 编辑器只能看到未压缩对象的一部分。压缩对象、JPEG 图片、字体和 xref 数据会显示成乱码。

## 1.4 物理结构和逻辑结构要分开理解

物理结构回答“对象存储在哪里”：

- 文件头在哪里；
- 对象在什么字节位置；
- 是否放在对象流里；
- xref 怎样索引它。

逻辑结构回答“对象表示什么”：

- Catalog 是文档根；
- Pages 是页面树；
- Page 是页面；
- Contents 是绘制程序；
- Resources 是字体和图片资源。

初学时建议先理解逻辑结构，再研究物理存储。

---

# 二、文件头

## 2.1 版本行

你的文件开头是：

~~~pdf
%PDF-1.7
~~~

它声明 PDF 基础版本为 1.7。注意，Catalog 中还可能存在扩展级别或其他兼容信息，因此版本行不是全部能力说明。

## 2.2 二进制标记行

紧接着可以看到类似：

~~~text
%âãÏÓ
~~~

这一行是注释，因为以 `%` 开头。它包含高位字节，用于提示传输程序：这个文件含有二进制数据，必须按二进制文件保存和传输。

## 2.3 PDF 中的注释

在普通对象语法区域，`%` 到行尾属于注释。例如：

~~~pdf
% 这是注释
3 0 obj
~~~

但是进入 `stream` 后，里面的字节由流的格式决定，不能继续按照普通注释规则理解。

## 2.4 空白字符

PDF 语法允许空格、制表符、回车和换行分隔标记。对象可以排版得很漂亮，也可以挤在一行。因此不要依赖缩进判断结构，应依赖 `<< >>`、`[ ]`、`obj/endobj` 等定界符。

---

# 三、PDF 对象怎么读

## 3.1 PDF 的八类基础对象

PDF 的基础对象类型包括：

| 类型 | 示例 | 含义 |
|---|---|---|
| Boolean | `true`、`false` | 布尔值 |
| Number | `270`、`841.92` | 整数或实数 |
| String | `(Hello)`、`<FEFF...>` | 字符串或字节串 |
| Name | `/Page`、`/Rotate` | 以 `/` 开头的名称 |
| Array | `[0 0 841.92 595.2]` | 有序集合 |
| Dictionary | `<< /Type /Page >>` | 键值集合 |
| Stream | `stream ... endstream` | 大块字节数据 |
| Null | `null` | 空值 |

间接对象和间接引用建立在这些基础对象之上。

## 3.2 间接对象

你的第一页是：

~~~pdf
3 0 obj
<<
/Type /Page
/Rotate 270
/MediaBox [0.0 0.0 841.92 595.2]
>>
endobj
~~~

`3 0 obj` 的三部分是：

- `3`：对象编号；
- `0`：生成号，通常翻译为代号或版本号；
- `obj`：对象开始。

`endobj` 表示这个间接对象结束。

## 3.3 字典

字典使用 `<<` 和 `>>`：

~~~pdf
<<
/Type /Page
/Rotate 270
>>
~~~

字典键通常是 Name，例如 `/Type`；值可以是任何 PDF 对象，例如 `/Page`、数字、数组、字典或引用。

## 3.4 Name 对象

Name 以 `/` 开头：

~~~pdf
/Type
/Page
/Rotate
/FlateDecode
~~~

它不是文件路径，也不是注释，而是 PDF 内部的标识符。特殊字符可以用 `#` 加十六进制转义。

## 3.5 字符串

圆括号字符串：

~~~pdf
(Hello PDF)
~~~

十六进制字符串：

~~~pdf
<48656C6C6F>
~~~

字符串不一定直接对应 Unicode 文本。它可能使用 PDFDocEncoding、UTF-16，或者只是字体编码后的字符码。

---

# 四、间接引用怎么读

## 4.1 基本语法

~~~pdf
/Contents 20645 0 R
~~~

`20645 0 R` 表示引用第 20645 号、第 0 代对象。`R` 是 Reference。

可以类比为：

~~~python
page["Contents"] = objects[20645]
~~~

## 4.2 为什么要使用引用

引用可以：

- 让多个页面共享同一字体；
- 让多个对象引用同一图片；
- 避免在页面字典中塞入大量内容；
- 允许阅读器按需加载对象；
- 支持对象级增量更新。

## 4.3 直接对象和间接对象

直接对象直接嵌在字典里：

~~~pdf
/Group << /Type /Group /S /Transparency >>
~~~

间接对象通过引用连接：

~~~pdf
/Resources 20644 0 R
~~~

图片、字体、页面和大数据流通常使用间接对象。

## 4.4 怎样沿引用阅读

看到 `20645 0 R` 后，不要继续猜，应让 PDF 工具解析第 20645 号对象。手工搜索只对未压缩对象有效；对象如果位于 `/ObjStm` 中，TXT 搜索可能完全找不到。

---

# 五、数组怎么读

## 5.1 数组基础

数组使用方括号：

~~~pdf
/MediaBox [0.0 0.0 841.92 595.2]
~~~

这里包含四个数字。PDF 不要求数组元素全部是同一种类型，例如：

~~~pdf
[/PDF /ImageC 12 0 R]
~~~

## 5.2 MediaBox

页面边界通常写成：

~~~pdf
[llx lly urx ury]
~~~

含义是：

- `llx`：左下角 X；
- `lly`：左下角 Y；
- `urx`：右上角 X；
- `ury`：右上角 Y。

你的第一页：

~~~pdf
/MediaBox [0.0 0.0 841.92 595.2]
~~~

因此底层宽度和高度是：

~~~text
width  = 841.92 - 0.0 = 841.92
height = 595.2 - 0.0 = 595.2
~~~

它在底层是横版。

## 5.3 CropBox

`CropBox` 是阅读器显示或裁剪时使用的区域。若没有显式的 CropBox，通常会继承 MediaBox。你的第一页两者都是：

~~~text
841.92 × 595.2
~~~

## 5.4 其他 Box

印刷相关 PDF 还可能有：

- `/BleedBox`：出血区域；
- `/TrimBox`：裁切后的成品区域；
- `/ArtBox`：内容或插图区域。

初学时先重点看 MediaBox、CropBox 和 Rotate。

---

# 六、这个 PDF 的对象关系

## 6.1 从根对象开始

你的文件尾部 XRef 指向：

~~~pdf
/Root 1 0 R
~~~

所以根对象是 1 0 R。解析后，它是 Catalog：

~~~pdf
1 0 obj
<<
/AcroForm 20494 0 R
/Lang (zh)
/Metadata 20475 0 R
/Outlines 1149 0 R
/Pages 2 0 R
/StructTreeRoot 1256 0 R
/Type /Catalog
/ViewerPreferences 20476 0 R
>>
endobj
~~~

## 6.2 Catalog 中重要的入口

| 键 | 作用 |
|---|---|
| `/Pages` | 页面树入口 |
| `/Outlines` | 书签目录 |
| `/Metadata` | XMP 元数据 |
| `/AcroForm` | 交互表单和签名 |
| `/StructTreeRoot` | 结构树、辅助功能和标签 |
| `/ViewerPreferences` | 阅读器显示偏好 |
| `/Lang` | 文档语言，这里是中文 `zh` |

## 6.3 用树形图理解

~~~text
1 0 obj  Catalog 文档根对象
└─ /Pages 2 0 R
   └─ 2 0 obj  Pages 页面树
      ├─ /Count 397
      └─ /Kids [3 0 R, 23 0 R, 26 0 R, ...]
         └─ 3 0 obj  第一页 Page
            ├─ /MediaBox
            ├─ /Rotate
            ├─ /Contents 20645 0 R
            ├─ /Resources 20644 0 R
            └─ /Annots [20763 0 R 20766 0 R]
~~~

PDF 阅读器打开第一页时，大体就是沿着这棵树找到第一页。

---

# 七、页面树

## 7.1 Pages 对象

你的 Pages 对象包含：

~~~pdf
/Type /Pages
/Count 397
/Kids [3 0 R 23 0 R 26 0 R ...]
~~~

`/Count 397` 是页面总数。`/Kids` 是子节点数组。

## 7.2 Kids 可能不是直接页面

页面树的 Kids 既可以是 `/Page`，也可以是下一级 `/Pages` 节点：

~~~text
Pages 根节点
├─ Pages 分组节点
│  ├─ Page
│  ├─ Page
│  └─ Page
└─ Page
~~~

这样可以用树形结构共享属性，例如统一的 Resources 或 MediaBox。

## 7.3 Parent 和继承

页面通常有：

~~~pdf
/Parent 2 0 R
~~~

某些页面属性可以从父 Pages 节点继承。PDF 解析器会计算最终有效值，而 TXT 搜索只能看到某个对象中实际写出的字节。

这就是“原文件搜索只有一次 `/Rotate 270`，解析后发现 17 页有效旋转”的重要原因之一。除此之外，对象流和压缩也会让原始搜索结果不完整。

## 7.4 Page 对象和页面显示

单页对象最重要的内容通常是：

~~~pdf
/Type /Page
/Parent 2 0 R
/MediaBox [...]
/CropBox [...]
/Rotate 270
/Resources ...
/Contents ...
/Annots ...
~~~

先看 Page 字典，再沿 Contents、Resources 和 Annots 继续深入。

---

# 八、第一页对象

第一页是 3 0 R。解析后的主要字典如下：

~~~pdf
3 0 obj
<<
/Contents 20645 0 R
/Group <<
    /CS /DeviceRGB
    /S /Transparency
    /Type /Group
>>
/MediaBox [0.0 0.0 841.92 595.2]
/Parent 2 0 R
/Resources 20644 0 R
/Rotate 270
/Tabs /S
/Type /Page
/Annots [20763 0 R 20766 0 R]
>>
endobj
~~~

## 8.1 `/Type /Page`

表明这是单个页面，而不是页面树。

## 8.2 `/Group`

这里设置透明度组和颜色空间：

- `/CS /DeviceRGB`：设备 RGB 颜色空间；
- `/S /Transparency`：透明度组；
- `/Type /Group`：这是一个页面图形组。

## 8.3 `/Tabs /S`

这和页面中表单、批注的键盘切换顺序有关。

## 8.4 `/Annots`

表示第一页有两个交互对象，后文会详细解释。

---

# 九、Contents 是什么

## 9.1 Contents 的职责

`Contents` 保存“如何绘制这一页”的指令，类似一个小型绘图程序。它通常不会直接保存完整图片或字体，而是通过 Resources 引用这些资源。

第一页引用：

~~~pdf
/Contents 20645 0 R
~~~

## 9.2 Stream 形式

内容流通常是：

~~~pdf
20645 0 obj
<<
/Filter /FlateDecode
>>
stream
压缩后的字节
endstream
endobj
~~~

读取时先读取字典中的 Filter，再解压 stream。

## 9.3 你的第一页解压内容

实际解压后是：

~~~pdf
0.24000 0 0 0.24000 0 0 cm
q
3508 0 0 2480 0 0 cm
/Im17 Do
Q
~~~

它没有 `BT`、`Tj`、`TJ` 等普通文字指令，只有一个图片绘制调用 `/Im17 Do`。

---

# 十、第一页绘制指令怎么读

PDF 内容流采用“操作数在前，操作符在后”的形式。例如：

~~~pdf
100 200 m
~~~

表示把当前路径移动到坐标 `(100, 200)`，其中 `m` 是 move-to 操作符。

## 10.1 `cm` 坐标变换

~~~pdf
0.24000 0 0 0.24000 0 0 cm
~~~

六个数字构成二维仿射变换矩阵：

~~~text
[ a b c d e f ]
~~~

它可以表达缩放、旋转、错切和平移。这里主要把 X、Y 均缩放为 0.24。

## 10.2 `q` 和 `Q`

~~~pdf
q
...
Q
~~~

- `q`：保存当前图形状态；
- `Q`：恢复之前保存的图形状态。

图形状态包括坐标变换、线宽、颜色、透明度等。使用 q/Q 可以防止局部绘制影响后续内容。

## 10.3 第二个 `cm`

~~~pdf
3508 0 0 2480 0 0 cm
~~~

它把单位方形变换成 3508 × 2480 的区域，为后面的图片绘制建立坐标。

## 10.4 `/Im17 Do`

~~~pdf
/Im17 Do
~~~

`Do` 执行一个命名 XObject。阅读器会在页面 Resources 的 `/XObject` 字典中查找 `/Im17`。

## 10.5 第一个 `cm` 和图片尺寸如何组合

图片对象本身是 3508 × 2480。内容流先设置 3508 × 2480，再整体缩放 0.24：

~~~text
3508 × 0.24 = 841.92
2480 × 0.24 = 595.20
~~~

这正好等于第一页的 MediaBox：

~~~text
841.92 × 595.2
~~~

因此扫描图完整铺满了底层横版页面。然后 `/Rotate 270` 再让阅读器竖向显示它。

## 10.6 常见图形操作符

| 操作符 | 作用 |
|---|---|
| `m` | 移动路径起点 |
| `l` | 画直线 |
| `c` | 贝塞尔曲线 |
| `re` | 矩形 |
| `S` | 描边 |
| `f` | 填充 |
| `w` | 线宽 |
| `rg` | 非描边 RGB 颜色 |
| `RG` | 描边 RGB 颜色 |
| `cm` | 坐标变换 |
| `Do` | 绘制 XObject |

---

# 十一、为什么能确定第一页是扫描图片

第一页的资源中包含：

~~~pdf
/XObject <<
    /Im17 20646 0 R
>>
~~~

对象 20646 的主要属性是：

~~~pdf
/Type /XObject
/Subtype /Image
/Width 3508
/Height 2480
/ColorSpace /DeviceRGB
/BitsPerComponent 8
/Filter /DCTDecode
~~~

## 11.1 `/Subtype /Image`

明确表明它是图像 XObject。

## 11.2 `/DCTDecode`

DCT 是 JPEG 常用的离散余弦变换压缩。该流通常可以看作嵌入 PDF 的 JPEG 图像数据。

## 11.3 `/BitsPerComponent 8`

每个颜色分量使用 8 位。配合 DeviceRGB，常见情况下每像素有 R、G、B 三个颜色分量。

## 11.4 为什么不能直接提取文字

第一页内容流只告诉阅读器“画一张图片”，没有告诉阅读器图片中有哪些汉字。因此：

- PDF 阅读器能显示；
- 文本提取工具可能得到空文本；
- 搜索和复制正文可能失败；
- 要获得文字需要 OCR。

扫描页也可能额外附带 OCR 文本层，但你的第一页内容分析表明主要内容是图片。

---

# 十二、文字页面的 Contents 一般长什么样

## 12.1 基本文字对象

普通文字内容常见：

~~~pdf
BT
/F1 12 Tf
100 700 Td
(Hello PDF) Tj
ET
~~~

含义：

- `BT`：开始文字对象；
- `/F1 12 Tf`：选择 F1 字体，字号 12；
- `100 700 Td`：移动文字位置；
- `(Hello PDF) Tj`：绘制字符串；
- `ET`：结束文字对象。

## 12.2 常见文字操作符

| 操作符 | 作用 |
|---|---|
| `BT`、`ET` | 开始、结束文字对象 |
| `Tf` | 设置字体和字号 |
| `Td`、`TD` | 移动文字位置 |
| `Tm` | 设置文字矩阵 |
| `Tj` | 绘制字符串 |
| `TJ` | 绘制字符串数组并调整字距 |
| `T*` | 移动到下一文本行 |
| `Tc` | 字符间距 |
| `Tw` | 单词间距 |
| `Tz` | 水平缩放 |
| `TL` | 行距 |

## 12.3 为什么看到 Tj 也未必能读懂中文

PDF 中的字符串可能是字体字符码，不一定是 Unicode。例如：

~~~pdf
<001200340056> Tj
~~~

要把字符码恢复成中文，通常需要：

- 字体编码信息；
- `/Encoding`；
- `/ToUnicode` CMap；
- 字体的字形和字符映射。

如果 ToUnicode 缺失或错误，页面看起来正常，但复制出来可能乱码。

## 12.4 文字、图片和矢量图可以混合

一个页面可以同时包含：

- 背景扫描图片；
- 透明 OCR 文字层；
- 页眉页脚文字；
- 矢量线条；
- 表单和批注。

因此不能只看某一个操作符，要综合 Contents 和 Resources。

---

# 十三、Annots 是什么

第一页包含：

~~~pdf
/Annots [20763 0 R 20766 0 R]
~~~

Annots 是页面批注数组。它可以包含链接、文本批注、图章、附件、表单控件和签名控件。

## 13.1 第一个批注

解析结果包括：

~~~pdf
/Type /Annot
/Subtype /Widget
/FT /Sig
/Rect [640 247.20001 640 247.20001]
~~~

- `/Subtype /Widget`：表单控件外观；
- `/FT /Sig`：签名字段；
- `/Rect`：批注在页面上的矩形区域。

这里 Rect 的宽高接近 0，可能是不可见或辅助性的签名控件。

## 13.2 第二个批注

解析结果包括：

~~~pdf
/Type /Annot
/Subtype /Stamp
/IT /AttachedImg
/Rect [448.63995 192.20001 476.13995 247.20001]
~~~

它是图章类批注，并带有附加图片含义。

## 13.3 Appearance Stream

批注常通过 `/AP` 指定外观流：

~~~pdf
/AP << /N 20765 0 R >>
~~~

阅读器显示批注时可能绘制这个 Form XObject，而不仅仅依赖批注字典。

## 13.4 为什么页面旋转会影响批注

页面内容和批注矩形是两套坐标数据。把页面旋转固化到 Contents 后，如果没有同步变换 `/Rect`、`/QuadPoints`、`/AP` 等，页面图像可能正常，但点击区域可能偏移。因此工具会对含 Annots 的页面给出警告。

---

# 十四、stream 为什么是乱码

## 14.1 Stream 的基本形式

~~~pdf
20645 0 obj
<<
/Length 123
/Filter /FlateDecode
>>
stream
二进制数据
endstream
endobj
~~~

字典描述 stream，stream 到 endstream 之间保存真正的数据。

## 14.2 Length

`/Length` 表示流长度，但在某些文件中它也可能是间接引用：

~~~pdf
/Length 20800 0 R
~~~

## 14.3 Filter

`/Filter` 表示数据如何编码或压缩。常见过滤器：

| Filter | 常见数据 |
|---|---|
| `/FlateDecode` | zlib/Deflate 压缩的内容流 |
| `/DCTDecode` | JPEG 图片 |
| `/JPXDecode` | JPEG 2000 图片 |
| `/CCITTFaxDecode` | 黑白扫描图 |
| `/ASCII85Decode` | ASCII85 编码 |
| `/LZWDecode` | LZW 压缩 |

## 14.4 多重 Filter

过滤器可以是数组：

~~~pdf
/Filter [/ASCII85Decode /FlateDecode]
~~~

需要按数组顺序执行解码。

## 14.5 为什么不能把 stream 直接另存为 TXT

同样的 stream 可能代表：

- 页面绘制命令；
- JPEG 图片；
- 字体程序；
- XMP 元数据；
- xref 索引。

必须先看对象字典中的 `/Type`、`/Subtype` 和 `/Filter`，再决定怎么解码。

---

# 十五、ObjStm 对象流

## 15.1 你的文件开头就有 ObjStm

文件开头可以看到：

~~~pdf
20647 0 obj
<<
/Filter /FlateDecode
/First 1902
/Length 3994
/N 200
/Type /ObjStm
>>
stream
压缩后的多个小对象
endstream
endobj
~~~

## 15.2 ObjStm 的键

- `/Type /ObjStm`：对象流；
- `/N 200`：流中包含的对象数量；
- `/First 1902`：对象数据正文开始位置；
- `/Length 3994`：压缩流长度；
- `/Filter /FlateDecode`：先用 Flate 解压。

## 15.3 为什么文本搜索会漏对象

对象流里的内容先被压缩。原始字节中没有可直接搜索的完整对象文本，所以：

- TXT 编辑器看不到所有对象；
- `/Rotate` 搜索次数不等于有效旋转页面数；
- `obj` 关键字次数也不等于对象数量；
- `stream` 关键字次数也不一定等于所有数据流数量。

PDF 解析器会先解压并建立对象表，所以解析结果比文本搜索可靠。

## 15.4 如何在分析文件时处理 ObjStm

初学者不建议自己手动解析 ObjStm。使用：

- pypdf；
- QPDF；
- MuPDF；
- Adobe Acrobat Preflight；

先把对象解析出来，再分析对象内容。

---

# 十六、XRef 是什么

## 16.1 XRef 的作用

XRef 是交叉引用索引，用来回答：

~~~text
对象 3 在文件的哪个偏移？
对象 20645 在哪个对象流？
对象 20782 是否是最新版本？
~~~

没有 XRef，阅读器就需要从头扫描所有对象，效率和可靠性都会下降。

## 16.2 传统 xref 表

旧式 PDF 可能有：

~~~pdf
xref
0 4
0000000000 65535 f
0000000017 00000 n
0000000081 00000 n
0000000145 00000 n
trailer
<< /Root 1 0 R /Size 4 >>
~~~

每行包含对象偏移、生成号和状态。

## 16.3 你的文件使用 XRef Stream

你的文件尾部有类似：

~~~pdf
20782 0 obj
<<
/Length 91
/ID [<...> <...>]
/Info 1148 0 R
/Root 1 0 R
/Prev 37196193
/Type /XRef
/Size 20783
/Index [0 2 3 1 20494 1 20763 19]
/W [1 4 0]
/Filter /FlateDecode
>>
stream
压缩后的 xref 数据
endstream
endobj
~~~

## 16.4 XRef Stream 中重要的键

| 键 | 含义 |
|---|---|
| `/Type /XRef` | 这是交叉引用流 |
| `/Size 20783` | 对象编号范围上限 |
| `/Root 1 0 R` | 文档根对象 |
| `/Info 1148 0 R` | 文档信息字典 |
| `/ID [...]` | 文档标识符 |
| `/Prev 37196193` | 前一个增量版本的 xref 位置 |
| `/W [1 4 0]` | xref 每条记录的字段宽度 |
| `/Index [...]` | xref 覆盖的对象编号范围 |

---

# 十七、startxref 和 EOF

## 17.1 文件尾部

你的文件最后是：

~~~pdf
startxref
37342990
%%EOF
~~~

## 17.2 startxref 的含义

`37342990` 是文件字节偏移，表示最新 XRef 对象从文件的哪个位置开始。

阅读器通常先读取文件尾部，再跳到这个偏移位置。

## 17.3 %%EOF 的含义

`%%EOF` 表示 PDF 文件结束。它通常出现在文件最后，但某些损坏或增量保存文件可能在 EOF 后还存在额外字节。

## 17.4 为什么文件有 /Prev

你的 XRef 字典包含：

~~~pdf
/Prev 37196193
~~~

这说明 PDF 可能经历过增量保存。增量保存不会重写整个旧文件，而是把新对象、新 xref 和新尾部追加到后面。

因此一个 PDF 可能存在多代对象和多个 xref。阅读器从最后一个版本开始，沿 `/Prev` 回溯。

---

# 十八、推荐的 PDF 阅读顺序

不要从文件第一行开始逐字阅读所有内容。建议采用下面的顺序。

## 18.1 第一步：看文件尾部

先找：

~~~pdf
startxref
...
%%EOF
~~~

记录 startxref 的偏移。

## 18.2 第二步：看 XRef

根据 startxref 找到最新 xref，确认：

- `/Root` 是哪个对象；
- `/Size` 有多少对象编号；
- 是否有 `/Prev`；
- 是普通 xref 还是 `/Type /XRef` 流。

## 18.3 第三步：看 Catalog

从 `/Root` 进入 Catalog，重点看：

- `/Pages`；
- `/Metadata`；
- `/Outlines`；
- `/AcroForm`；
- `/StructTreeRoot`。

## 18.4 第四步：看 Pages

在 Pages 中确认：

- 总页数；
- Kids 数量；
- 页面树分组；
- 可继承的公共属性。

## 18.5 第五步：看 Page

对目标页检查：

- `/MediaBox`；
- `/CropBox`；
- `/Rotate`；
- `/Contents`；
- `/Resources`；
- `/Annots`。

## 18.6 第六步：看 Contents

先解压，再判断是：

- 图片绘制；
- 文字绘制；
- 矢量图形；
- 混合内容。

## 18.7 第七步：看 Resources

根据 Contents 中的名字去 Resources 查找：

- 图片 XObject；
- Form XObject；
- 字体；
- 色彩空间；
- ExtGState 透明度和混合模式。

## 18.8 第八步：看 Annots 和表单

只有在需要分析链接、签名、批注或表单时，才继续检查 `/Annots`、`/AP`、`/AcroForm`。

---

# 十九、使用项目检查脚本

## 19.1 检查第一页

在项目根目录执行：

~~~powershell
$env:PYTHONUTF8 = "1"
$env:PYTHONPATH = "$PWD\src"
.\.venv\Scripts\python.exe .\scripts\inspect_pdf.py .\testFile\20260722.pdf --page 1
~~~

## 19.2 检查其他页面

例如检查第 4 页：

~~~powershell
.\.venv\Scripts\python.exe .\scripts\inspect_pdf.py .\testFile\20260722.pdf --page 4
~~~

## 19.3 脚本输出怎么理解

脚本分为四个区域：

### 原始文件

显示文件大小、文件头、关键字计数和文件尾。关键字计数只是线索，不能用来统计页面属性。

### 文档结构

显示 PDF 版本、页数、Trailer、Root、Catalog 和 Pages。

### 指定页面

显示 Page 字典的有效属性，包括 Rotate、MediaBox、Contents、Resources 和 Annots。

### 解压后的 Contents 和 XObject

显示可以直接阅读的页面指令，以及页面调用的图片、Form 等资源。

## 19.4 用 pypdf 统计有效 Rotate

不要搜索原始二进制文本，可以这样统计每页有效旋转：

~~~powershell
$env:PYTHONPATH = "$PWD\src"
.\.venv\Scripts\python.exe -c "from pypdf import PdfReader; from collections import Counter; r=PdfReader('testFile/20260722.pdf', strict=False); print(Counter(int(p.rotation or 0) for p in r.pages))"
~~~

这个命令统计的是解析器计算出的页面有效属性，而不是原始字节中出现了多少次 `/Rotate`。

## 19.5 用 PyMuPDF 观察显示尺寸

如果想验证页面显示效果，可以把页面渲染成图片，再比较处理前后图片尺寸和像素。项目的测试已经这样验证了第一页。

---

# 二十、不要直接用 TXT 修改 PDF

## 20.1 为什么不能直接替换 `/Rotate`

PDF 中的 `/Rotate` 只是一个页面属性，但 PDF 还依赖：

- xref 中的对象偏移；
- 对象流中的压缩索引；
- 页面内容坐标；
- 批注矩形和外观流；
- 签名和增量更新；
- 页面树继承关系。

直接把：

~~~pdf
/Rotate 270
~~~

替换成：

~~~pdf
/Rotate 0
~~~

可能造成：

- 阅读器显示方向改变；
- xref 偏移失效；
- 对象流长度不匹配；
- 数字签名失效；
- 批注位置偏移；
- PDF 无法打开。

## 20.2 正确的旋转固化

正确流程是：

~~~text
读取 PDF
  ↓
解析页面有效 Rotate
  ↓
把旋转变换应用到 Contents 和页面边界
  ↓
设置 Rotate=0
  ↓
重新计算对象和 xref
  ↓
写出新 PDF
  ↓
重新打开验证
~~~

本项目使用 pypdf 的：

~~~python
page.transfer_rotation_to_content()
~~~

而不是只写：

~~~python
page.rotate(-270)
~~~

前者会转换页面内容和页面边界，后者主要只是改变页面旋转属性。

## 20.3 什么时候可以使用 TXT 编辑器

TXT 编辑器适合：

- 查看文件头；
- 查看未压缩对象；
- 找 startxref；
- 观察对象字典；
- 学习 PDF 语法。

不适合：

- 修改 PDF；
- 解压对象流；
- 处理 JPEG 和字体；
- 修复 xref；
- 固化页面旋转。

## 20.4 最重要的判断原则

看到 PDF 中的文字时，要问四个问题：

1. 这是直接对象还是间接引用？
2. 这个对象是否在 ObjStm 中？
3. 这个 stream 使用了什么 Filter？
4. 这是逻辑属性，还是阅读器解析后的有效属性？

只要这四个问题没有弄清楚，就不要根据 TXT 搜索结果判断 PDF 是否真的只有一个对象或一页。

---

# 附录 A：本测试文件的第一条阅读结论

对 `testFile/20260722.pdf`，第一页可以总结为：

~~~text
PDF 1.7 文档
  ↓
Catalog 1 0 R
  ↓
Pages 2 0 R，Count=397
  ↓
Page 3 0 R
  ├─ MediaBox=841.92×595.2，底层横版
  ├─ Rotate=270，阅读器显示为竖版
  ├─ Contents=20645 0 R
  │  └─ 绘制图片 Im17
  ├─ Image 20646 0 R，3508×2480 JPEG
  └─ Annots 两个，包含签名控件和图章
~~~

这就是“第一页是横版扫描图，通过 Rotate=270 正常显示成竖版”的完整结构。

# 附录 B：进一步工具

当你熟悉 pypdf 后，可以了解：

- QPDF：用于查看和规范化 PDF 结构；
- MuPDF：用于渲染和检查显示效果；
- Adobe Acrobat Preflight：用于专业 PDF 结构分析；
- OCR 工具：用于把扫描图片变成文字层。

QPDF 的 QDF 模式可以把某些对象流展开，便于学习，但展开后的文件主要用于分析，不建议直接把它当作最终交付文件。

## 附录 B.1 PKCS7 签名数据解析

PDF 签名字段的 `/Contents` 值通常是 DER 编码的 PKCS7/CMS SignedData。程序使用 `src/adjust_pdf/signature_parser.py` 中的自定义 ASN.1 解析器提取证书信息：

```
ContentInfo
  └─ contentType = 1.2.840.113549.1.7.2 (signedData)
  └─ content [0] EXPLICIT
       └─ SignedData
            ├─ version
            ├─ digestAlgorithms
            ├─ contentInfo
            ├─ certificates [0] IMPLICIT     ← X.509 证书
            │   └─ Certificate
            │        ├─ TBSCertificate
            │        │   ├─ serialNumber
            │        │   ├─ issuer           ← 颁发者
            │        │   ├─ validity         ← 有效期
            │        │   └─ subject          ← 主题（内含 CN=签名人）
            │        ├─ signatureAlgorithm
            │        └─ signatureValue
            ├─ crls [1] IMPLICIT（可选）
            └─ signerInfos
                 └─ SignerInfo
                      ├─ version
                      ├─ sid (IssuerAndSerialNumber)
                      ├─ digestAlgorithm
                      ├─ signedAttrs [0] OPTIONAL
                      ├─ signatureAlgorithm
                      ├─ signature
                      └─ unsignedAttrs [1] OPTIONAL  ← 时间戳令牌
```

解析器纯 Python 实现，支持国密 SM2/SM3 OID（1.2.156.10197.1.*），不依赖 OpenSSL。解析失败不会影响签名检测主流程。

签名事件分组规则：文档中 `/AcroForm /Fields` 的每个 `/FT /Sig` 字段作为一个签名字段计数。多个字段若指向同一 PKCS7 数据（同一 `/V` 字典），则归为同一签署事件。

# 附录 C：参考资料

- Adobe PDF 1.7 Reference / PDF 32000-1: PDF 语法和对象模型；
- pypdf 文档：页面、旋转、内容流和对象处理；
- QPDF 文档：QDF、对象流和交叉引用结构。

本文档的示例和结论优先根据本地 `testFile/20260722.pdf` 实际解析结果整理。
