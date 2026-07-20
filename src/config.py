"""
========================================================================
全局配置模块
========================================================================
所有可调参数集中在这里，修改一个地方就能切换城市、年份、阈值等。

使用方法：
    from src.config import CITIES, ANALYSIS_CONFIG, OUTPUT_DIR

    # 添加新城市：在 CITIES 字典里加一行
    # 改年份：改 ANALYSIS_CONFIG["years"]
"""

import os

# ============================================================
# 城市配置（经纬度去百度地图拾取：https://api.map.baidu.com/lbsapi/getpoint/）
# ============================================================
CITIES = {
    "三明市": {
        "lon": 117.64,         # 中心经度
        "lat": 26.26,          # 中心纬度
        "buffer": 15000,       # 缓冲区半径（米），覆盖整个市区
        "description": "福建省中西部地级市，典型山区河谷城市",
    },
    "福州市": {
        "lon": 119.30,
        "lat": 26.07,
        "buffer": 25000,       # 省会城市范围更大
        "description": "福建省省会，沿海平原城市，扩张模式与三明形成对比",
    },
}

# ============================================================
# 分析参数
# ============================================================
ANALYSIS_CONFIG = {
    # --- 年份序列（每 5 年一个节点）---
    "years": [2000, 2005, 2010, 2015, 2020, 2025],

    # --- NDBI 建成区阈值 ---
    # NDBI > threshold → 建成区
    # 常见取值范围：-0.2 ~ 0.1，城市越大越偏正
    "ndbi_threshold": -0.05,

    # --- NDVI 植被阈值（用于辅助验证）---
    # NDVI > 0.2 说明有植被覆盖，NDVI > 0.5 说明植被茂密
    # 建成区 NDVI 通常 < 0.2
    "ndvi_vegetation_threshold": 0.2,

    # --- MNDWI 水体阈值（用于排除水体干扰）---
    # MNDWI > 0 → 水体，建成区不应包含水体
    "mndwi_water_threshold": 0.0,

    # --- 云量过滤上限（百分比）---
    "max_cloud_cover": 30,

    # --- Landsat 地表反射率缩放因子（Collection 2）---
    "scale_factor": 0.0000275,     # 缩放
    "offset": -0.2,                # 偏移

    # --- 精度验证 ---
    "validation": {
        "n_samples": 500,                       # 随机采样点数
        "strict_ndbi_threshold": 0.05,          # 严格阈值（作为参考验证）
        "random_seed": 42,                      # 随机种子（保证可复现）
    },

    # --- 方向分析 ---
    "direction_sectors": 8,        # 扇形数量（8 = 八个方向）
}

# ============================================================
# 路径设置
# ============================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
MAPS_DIR = os.path.join(OUTPUT_DIR, "maps")
CHARTS_DIR = os.path.join(OUTPUT_DIR, "charts")
STATS_DIR = os.path.join(OUTPUT_DIR, "stats")
REPORT_DIR = os.path.join(BASE_DIR, "report")

# 确保输出目录存在
for d in [MAPS_DIR, CHARTS_DIR, STATS_DIR]:
    os.makedirs(d, exist_ok=True)

# ============================================================
# 可视化参数
# ============================================================
VIZ = {
    # 真彩色显示参数（Landsat Collection 2 SR）
    "true_color": {
        "bands": [2, 1, 0],       # R, G, B 波段索引
        "min": 8000,               # 反射率缩放后的最小值
        "max": 18000,              # 反射率缩放后的最大值
        "gamma": 1.4,              # 伽马校正（>1 变亮）
    },
    # 假彩色（近红外，用于突出植被）
    "false_color": {
        "bands": [3, 2, 1],       # NIR, R, G
        "min": 8000,
        "max": 18000,
        "gamma": 1.4,
    },
    # 建成区叠加色
    "built_up_palette": ["#FF4444"],     # 亮红
    "built_up_opacity": 0.5,
    # NDVI 配色
    "ndvi_palette": ["#8B4513", "#FFD700", "#228B22"],
}

# ============================================================
# matplotlib 全局样式
# ============================================================
try:
    import matplotlib
    matplotlib.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
    matplotlib.rcParams["axes.unicode_minus"] = False
except ImportError:
    pass  # 如果 matplotlib 没装，后面会报更明确的错误
