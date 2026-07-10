# 🏙️ 三明市城市扩张遥感分析（2000-2025）

> **基于 Landsat 影像 + Google Earth Engine 的城市建成区时空变化分析**
>
> 一键运行，自动生成城市扩张地图、统计图表和可视化报告。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)

---

## 📸 输出预览（运行后自动生成）

```
outputs/
├── maps/
│   ├── 三明市_2000_建成区分布.png      # 各年份城市范围
│   ├── 三明市_2010_建成区分布.png
│   ├── 三明市_2020_建成区分布.png
│   └── 三明市_2000_2025_扩张动图.gif   # 城市扩张动画
├── charts/
│   ├── 建成区面积年际变化.png           # 面积变化柱状图
│   ├── 各阶段扩张速率.png               # 扩张速率折线图
│   └── 扩张方向雷达图.png               # 各方向扩张雷达图
└── stats/
    └── 面积统计表.csv                   # 每年精确统计数据
```

---

## 🚀 快速开始（30 分钟搞定）

### 第 1 步：环境准备

```bash
# 克隆仓库
git clone https://github.com/你的用户名/urban-expansion-sanming.git
cd urban-expansion-sanming

# 安装依赖
pip install -r requirements.txt
```

### 第 2 步：注册 Google Earth Engine（免费，仅此一次）

1. 打开 [https://earthengine.google.com/signup/](https://earthengine.google.com/signup/)
2. 用 Google 账号登录（没有就注册一个）
3. 选择「Unpaid usage」（非商业用途）
4. 等待审批邮件（通常 **1-3 天**）

审批通过后，在终端运行一次认证：

```bash
earthengine authenticate
```

### 第 3 步：运行分析

```bash
# 方式一：命令行一键运行（推荐新手）
python src/urban_analysis.py

# 方式二：Jupyter Notebook 逐步运行
jupyter notebook notebooks/urban_expansion_analysis.ipynb
```

### 第 4 步：修改城市（如果你想换一个地方分析）

打开 `src/urban_analysis.py` 或 Notebook，改一行：

```python
# 把三明的经纬度改成你想分析的城市
ROI = ee.Geometry.Point([117.64, 26.26]).buffer(15000)  # ← 改这里！
#                        ↑经度   ↑纬度           ↑缓冲区半径(米)
```

---

## 📂 项目结构

```
urban-expansion-sanming/
├── README.md                           # 本说明文档
├── requirements.txt                    # Python 依赖
├── .gitignore                          # 不提交到 Git 的文件
├── LICENSE                             # MIT 开源协议
│
├── src/
│   └── urban_analysis.py              # 核心分析脚本（一键运行）
│
├── notebooks/
│   └── urban_expansion_analysis.ipynb # Jupyter Notebook（逐步教学版）
│
├── outputs/                            # 自动生成的输出（不上传 Git）
│   ├── maps/
│   ├── charts/
│   └── stats/
│
└── report/
    └── 课程设计报告_模板.md            # 课程设计报告模板
```

---

## 🔬 技术原理

```
Landsat 5/8 影像（2000, 2005, 2010, 2015, 2020, 2025）
        │
        ▼
   云掩膜 + 去云处理
        │
        ▼
   计算 NDBI（归一化建筑指数）
   NDBI = (SWIR1 - NIR) / (SWIR1 + NIR)
        │
        ▼
   阈值分割 → 提取建成区
        │
        ▼
   面积统计 + 叠加分析
        │
        ▼
   可视化输出（地图 + 图表 + 动画）
```

**NDBI（归一化建筑指数）** 是提取城市建成区最经典的方法。建成区在短波红外（SWIR）反射率高、近红外（NIR）反射率低，比值能有效区分建筑和植被。

---

## 🛠 技术栈

| 工具 | 用途 |
|------|------|
| **Google Earth Engine** | 云端遥感数据存取 + 计算 |
| **geemap** | Python 调用 GEE 的可视化库 |
| **rasterio** | 本地栅格数据读写 |
| **numpy** | 数值计算 |
| **matplotlib** | 静态图表绘制 |
| **pandas** | 统计分析 |
| **PIL (Pillow)** | GIF 动图合成 |

---

## 📊 分析指标

| 指标 | 公式 | 含义 |
|------|------|------|
| 建成区面积 | 像元数 × 像元面积 | 城市不透水面总面积 |
| 年均扩张速率 | (A₂ - A₁) / (t₂ - t₁) | 每年新增建成区面积 |
| 扩张强度指数 | (A₂ - A₁) / A₁ × 100% / n | 建成区年增长率 |
| 紧凑度 | 2√(πA) / P | 城市形态紧凑程度 |

---

## 🌍 应用到其他城市

修改 `config` 字典，一行切换：

```python
# 北京
config = {"city_name": "北京", "lon": 116.41, "lat": 39.90, "buffer": 25000}

# 上海
config = {"city_name": "上海", "lon": 121.47, "lat": 31.23, "buffer": 20000}

# 你自己的城市
config = {"city_name": "XX市", "lon": 经度, "lat": 纬度, "buffer": 缓冲区半径米}
```

---

## ⚠️ 常见问题

**Q: GEE 审批要多久？**
A: 通常 1-3 个工作日，偶尔当天就通过。

**Q: 没有 Google 账号怎么办？**
A: 注册一个 Gmail 即可，完全免费。

**Q: 运行报错 `ee.AuthenticationException`？**
A: 在终端运行 `earthengine authenticate` 完成认证。

**Q: 能不用 GEE 吗？**
A: 可以，但需要手动下载 5-6 景 Landsat 影像（约 6GB）。见 `notebooks/` 中的备选方案。

---

## 📝 License

MIT License — 随便用，商业用途也可以，保留署名就行。

---

## 👤 关于作者

- 遥感科学与技术专业 大三
- 这个项目是我的课程设计作品
- 欢迎 Star ⭐ + Fork 🍴