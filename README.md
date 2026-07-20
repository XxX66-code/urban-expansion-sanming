# 🏙️ 城市扩张遥感分析系统 v2.0

> **基于 Landsat + Google Earth Engine 的多城市、多指数城市扩张时空分析**
>
> 一键运行 → 建成区提取 + NDBI/NDVI/MNDWI + 精度验证 + 多城市对比

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)

---

## 🆕 v2.0 更新

| v1.0（旧） | v2.0（新） |
|-----------|-----------|
| 单城市（三明） | **双城市对比（三明 + 福州）** |
| 仅 NDBI 提取 | **NDBI + NDVI + MNDWI 三指数联合** |
| 无精度验证 | **混淆矩阵 + Kappa 系数 + F1 分数** |
| 方向雷达（模拟数据） | **八方向扇形统计（真实 GEE 计算）** |
| 单文件脚本 | **8 模块架构，清晰分层** |
| 基础图表 | **+ NDVI 趋势 + 多城对比 + 精度图表** |

---

## 📸 输出预览

```
outputs/
├── maps/                                    # 地图输出
│   ├── 三明市_2000_交互地图.html            # 交互式地图（浏览器打开）
│   ├── 三明市_2025_真彩色.png               # 静态地图（报告插图）
│   ├── 三明市_2000_vs_2025_对比图.png       # 首尾年对比
│   └── 三明市_2000_2025_扩张动图.gif        # 25年扩张动画
│
├── charts/                                  # 统计图表
│   ├── 三明市_建成区面积年际变化.png         # 面积柱状图
│   ├── 三明市_各阶段扩张速率.png            # 速率折线图
│   ├── 三明市_NDVI趋势.png                  # 植被变化趋势
│   ├── 三明市_扩张方向雷达图.png            # 八方向分布
│   ├── 三明市_2025_精度评估.png             # 精度条形图
│   └── 城市对比_综合对比图.png              # 多城对比
│
└── stats/                                   # 数据表格
    ├── 三明市_面积统计表.csv                # 逐年面积 + 增长率
    ├── 三明市_2025_精度评估.csv              # 精度指标
    └── 城市对比汇总.csv                     # 多城对比汇总
```

---

## 🚀 快速开始（3 步）

### 第 1 步：安装依赖

```bash
git clone https://github.com/XxX66-code/urban-expansion-sanming.git
cd urban-expansion-sanming
pip install -r requirements.txt
```

### 第 2 步：注册 GEE（免费，仅一次）

1. 打开 [earthengine.google.com/signup](https://earthengine.google.com/signup/)
2. 用 Google 账号登录 → 选择 **"Unpaid usage"**（非商业用途）
3. 等待审批邮件（通常 **1-3 个工作日**）

审批通过后在终端认证：

```bash
earthengine authenticate
```

### 第 3 步：运行分析

```bash
# 一键运行全部分析（推荐）
python src/main.py

# 或者在 Jupyter 中逐步学习
jupyter notebook notebooks/urban_expansion_analysis.ipynb
```

---

## 📂 项目结构

```
urban-expansion-sanming/
├── README.md                           # 本说明文档
├── requirements.txt                    # Python 依赖
├── .gitignore                          # 不上传的文件
├── LICENSE                             # MIT 开源协议
│
├── src/                                # 源码（模块化架构）
│   ├── __init__.py                     # 包初始化
│   ├── config.py                       # 全局配置（城市/年份/阈值）
│   ├── gee_utils.py                    # GEE 初始化 + 云掩膜 + 影像获取
│   ├── indices.py                      # NDBI / NDVI / MNDWI 指数计算
│   ├── urban_extraction.py             # 建成区提取 + 面积统计 + 方向分析
│   ├── accuracy.py                     # 精度验证（混淆矩阵 + Kappa 系数）
│   ├── stats.py                        # 统计分析 + CSV 导出
│   ├── visualization.py                # 全部可视化（地图/图表/动图）
│   ├── main.py                         # 🔥 主入口（一键运行）
│   └── urban_analysis.py               # 旧版入口（自动转发到 main.py）
│
├── notebooks/
│   └── urban_expansion_analysis.ipynb  # Jupyter Notebook 教学版
│
├── outputs/                            # 自动生成（不上传 Git）
│   ├── maps/     → 地图 + 动图
│   ├── charts/   → 统计图表
│   └── stats/    → CSV 数据表
│
└── report/
    └── 课程设计报告_模板.md            # 课程设计报告模板
```

---

## 🔬 技术原理

```
                    ┌─────────────────────────┐
                    │  Landsat 5/8 影像        │
                    │  (2000–2025, 每5年)      │
                    └──────────┬──────────────┘
                               │
                    ┌──────────▼──────────────┐
                    │  云掩膜 + 中值合成       │
                    │  (QA_PIXEL bit 3/4/5)   │
                    └──────────┬──────────────┘
                               │
               ┌───────────────┼───────────────┐
               │               │               │
       ┌───────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
       │  NDBI 计算   │ │  NDVI 计算  │ │ MNDWI 计算  │
       │ (SWIR-NIR)/  │ │ (NIR-Red)/  │ │(Green-SWIR)/│
       │ (SWIR+NIR)   │ │ (NIR+Red)   │ │(Green+SWIR) │
       └───────┬──────┘ └──────┬──────┘ └──────┬──────┘
               │               │               │
               └───────────────┼───────────────┘
                               │
                    ┌──────────▼──────────────┐
                    │  综合阈值分割            │
                    │  建成区 = NDBI高        │
                    │         & NDVI低        │
                    │         & 非水体(MNDWI) │
                    └──────────┬──────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
   ┌──────▼──────┐   ┌────────▼────────┐   ┌───────▼──────┐
   │ 面积统计    │   │ 精度验证        │   │ 方向分析     │
   │ 逐年km²     │   │ 混淆矩阵+Kappa │   │ 八扇形统计   │
   └──────┬──────┘   └────────┬────────┘   └───────┬──────┘
          │                    │                    │
          └────────────────────┼────────────────────┘
                               │
                    ┌──────────▼──────────────┐
                    │  可视化 + 统计输出       │
                    │  地图 / 图表 / GIF / CSV│
                    └─────────────────────────┘
```

### 三个指数的分工

| 指数 | 公式 | 干什么用 |
|------|------|---------|
| **NDBI** | (SWIR1−NIR)/(SWIR1+NIR) | 主力：提取建成区。建筑 SWIR 高、NIR 低 → NDBI 正值 |
| **NDVI** | (NIR−Red)/(NIR+Red) | 辅助：排除植被。植被 NIR 高 → NDVI > 0.2 |
| **MNDWI** | (Green−SWIR1)/(Green+SWIR1) | 辅助：排除水体。水体 SWIR 吸收 → MNDWI > 0 |

---

## 🌍 添加你自己的城市

编辑 `src/config.py`，加一行：

```python
CITIES = {
    # ...已有城市...
    "北京市": {
        "lon": 116.41,
        "lat": 39.90,
        "buffer": 30000,          # 大城市半径大一些
        "description": "首都，典型圈层式扩张",
    },
}
```

经纬度去这里拾取：[https://api.map.baidu.com/lbsapi/getpoint/](https://api.map.baidu.com/lbsapi/getpoint/)

---

## 📊 分析指标说明

| 指标 | 公式 | 含义 |
|------|------|------|
| 建成区面积 | Σ(像元面积 × 建成区二值) | 城市不透水面总面积 |
| 年均扩张速率 | (A₂−A₁)/(t₂−t₁) | 每年平均新增面积 |
| 扩张强度 | 增长率/年数 | 相对初始面积的增长速度 |
| 总体精度(OA) | (TP+TN)/总样本 | 分类正确的比例 |
| Kappa 系数 | (Po−Pe)/(1−Pe) | 排除随机一致性的分类质量 |
| NDVI 均值 | mean(NDVI) | 区域平均植被覆盖度 |

---

## ⚠️ 常见问题

<details>
<summary><b>Q: GEE 审批要多久？</b></summary>
通常 1-3 个工作日。建议用 Gmail 注册，选 "Unpaid usage"。
</details>

<details>
<summary><b>Q: 报错 ee.AuthenticationException？</b></summary>
终端运行 <code>earthengine authenticate</code> 完成认证。
</details>

<details>
<summary><b>Q: 运行时特别慢？</b></summary>
GEE 计算在云端进行，第一次运行较慢（冷启动），之后会快很多。如果 GEE 没认证好，程序会进入演示模式。
</details>

<details>
<summary><b>Q: 精度验证的真实性？</b></summary>
本项目的精度验证使用"双阈值交叉验证"——以严格阈值作为伪参考数据。这能评估分类的一致性，但不能替代实地验证。在论文中应标注这一点。
</details>

<details>
<summary><b>Q: 如何理解 Kappa 值？</b></summary>

| Kappa | 等级 |
|-------|------|
| > 0.80 | 几乎完美 |
| 0.60–0.80 | 较好 |
| 0.40–0.60 | 中等 |
| < 0.40 | 需改进 |

</details>

---

## 📝 License

MIT License — © 2024 遥感科学与技术

---

## 👤 关于

- 🎓 遥感科学与技术专业
- 📊 课程设计作品，已升级为简历级项目
- ⭐ 欢迎 Star + Fork
