"""
========================================================================
遥感指数计算模块 — NDBI / NDVI / MNDWI
========================================================================

三类核心指数：
    NDBI  — 归一化建筑指数    → 提取建成区（建筑、道路、不透水面）
    NDVI  — 归一化植被指数    → 提取植被覆盖区（辅助验证建成区）
    MNDWI — 改进归一化水体指数 → 提取水体（排除建成区中的水体干扰）

波段顺序（已在 gee_utils 中统一）：
    [0]蓝 [1]绿 [2]红 [3]近红外 [4]中红外1 [5]中红外2

依赖：ee (Google Earth Engine)
"""

import ee


# ============================================================
# NDBI — 归一化建筑指数
# ============================================================
def calc_ndbi(image: ee.Image) -> ee.Image:
    """
    计算 NDBI（Normalized Difference Built-up Index）。

    公式：
        NDBI = (SWIR1 - NIR) / (SWIR1 + NIR)

    原理：
        建成区（混凝土、沥青、屋顶）在短波红外（SWIR1）反射率高、
        在近红外（NIR）反射率低，因此 NDBI 值较高。
        植被则相反——NIR 高、SWIR1 低，因此 NDBI 低（通常为负值）。

    取值范围：-1.0 ~ +1.0
        - > -0.05  → 可能是建成区（常用阈值）
        - >  0.00  → 很可能是建成区
        - < -0.20 → 很可能是植被

    参数:
        image: 6 波段 Landsat 影像 [蓝,绿,红,近红,中红外1,中红外2]

    返回:
        带 "NDBI" 波段的新影像
    """
    nir = image.select(3)         # 近红外
    swir1 = image.select(4)       # 中红外1
    ndbi = swir1.subtract(nir).divide(swir1.add(nir)).rename("NDBI")
    return image.addBands(ndbi)


# ============================================================
# NDVI — 归一化植被指数（最经典的遥感指数）
# ============================================================
def calc_ndvi(image: ee.Image) -> ee.Image:
    """
    计算 NDVI（Normalized Difference Vegetation Index）。

    公式：
        NDVI = (NIR - Red) / (NIR + Red)

    原理：
        健康植被在近红外（NIR）反射率很高（细胞结构散射），
        在红光波段吸收很强（叶绿素光合作用），因此 NDVI 为正值。
        建成区和裸土的红光与近红外差异较小，NDVI 接近零。

    取值范围：-1.0 ~ +1.0
        - > 0.5  → 茂密植被（森林、草地旺季）
        - 0.2~0.5 → 稀疏植被（城市绿地、农田）
        - 0~0.2   → 裸土、建成区
        - < 0     → 水体

    参数:
        image: 6 波段 Landsat 影像

    返回:
        带 "NDVI" 波段的新影像
    """
    nir = image.select(3)         # 近红外
    red = image.select(2)         # 红光
    ndvi = nir.subtract(red).divide(nir.add(red)).rename("NDVI")
    return image.addBands(ndvi)


# ============================================================
# MNDWI — 改进归一化水体指数（辅助掩膜水体）
# ============================================================
def calc_mndwi(image: ee.Image) -> ee.Image:
    """
    计算 MNDWI（Modified Normalized Difference Water Index）。

    公式：
        MNDWI = (Green - SWIR1) / (Green + SWIR1)

    原理：
        水体在绿光波段有一定反射率，在短波红外几乎完全吸收，
        因此 MNDWI 为正值时可以识别水体。
        MNDWI 比 NDWI 更准确，能更好地区分建成区和水体。

    取值范围：-1.0 ~ +1.0
        - > 0  → 水体
        - < 0  → 非水体（植被、建成区、裸土）

    参数:
        image: 6 波段 Landsat 影像

    返回:
        带 "MNDWI" 波段的新影像
    """
    green = image.select(1)       # 绿光
    swir1 = image.select(4)       # 中红外1
    mndwi = green.subtract(swir1).divide(green.add(swir1)).rename("MNDWI")
    return image.addBands(mndwi)


# ============================================================
# 批量计算所有指数
# ============================================================
def calc_all_indices(image: ee.Image) -> ee.Image:
    """
    对一张影像一次性计算 NDBI + NDVI + MNDWI。
    这只是把上面三个函数串起来，方便调用。

    参数:
        image: 6 波段 Landsat 影像

    返回:
        带 "NDBI", "NDVI", "MNDWI" 三个新波段的影像
    """
    image = calc_ndbi(image)
    image = calc_ndvi(image)
    image = calc_mndwi(image)
    return image


# ============================================================
# 快速参考表
# ============================================================
"""
指数速查：

    想分析什么？         用哪个指数？      怎么看？
    ─────────────────────────────────────────────────────────
    城市扩张/建成区       NDBI            越大越可能是建筑
    植被变化/绿化率       NDVI            越大越绿
    水体变化/湖泊河流     MNDWI           正值=水体
    建筑 vs 裸土区分      NDBI + NDVI     NDBI正+NDVI低=建筑；NDBI正+NDVI中=裸土
    水体干扰排除          MNDWI           先用MNDWI把水体mask掉再提取建成区

典型组合分析：
    建成区 = (NDBI > -0.05) & (NDVI < 0.2) & (MNDWI < 0)
    （同时满足：建筑指数高 + 不是植被 + 不是水体 → 置信度更高）
"""
