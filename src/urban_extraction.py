"""
========================================================================
建成区提取模块 — 阈值分割 + 面积统计 + 方向分析
========================================================================

核心流程：
    1. extract_built_up()   → 用 NDBI 阈值提取建成区二值图
    2. extract_built_up_refined() → 综合 NDBI+NDVI+MNDWI 的更准确提取
    3. calc_built_up_area() → 计算建成区面积（km²）
    4. calc_direction_stats() → 八方向扇形分析（真实计算，非模拟数据）

依赖：
    ee (Google Earth Engine)
    src/config.py — 阈值参数
"""

import ee
import math
from src.config import ANALYSIS_CONFIG

# 八个方向的参数：名称 + 起始角度 + 终止角度（以正北为0°，顺时针）
SECTORS = [
    ("北",   337.5, 360.0),
    ("北",     0.0,  22.5),
    ("东北",  22.5,  67.5),
    ("东",    67.5, 112.5),
    ("东南", 112.5, 157.5),
    ("南",   157.5, 202.5),
    ("西南", 202.5, 247.5),
    ("西",   247.5, 292.5),
    ("西北", 292.5, 337.5),
]


# ============================================================
# 阈值提取
# ============================================================
def extract_built_up(image: ee.Image, threshold: float = None) -> ee.Image:
    """
    用 NDBI 单一阈值提取建成区（最简方法，适合快速分析）。

    公式：built_up = 1 if NDBI > threshold else 0

    参数:
        image:     包含 "NDBI" 波段的影像
        threshold: NDBI 阈值（默认用 config 里的 -0.05）

    返回:
        单波段影像 "built_up"（1=建成区, 0=非建成区）
    """
    if threshold is None:
        threshold = ANALYSIS_CONFIG["ndbi_threshold"]

    ndbi = image.select("NDBI")
    built_up = ndbi.gt(threshold).rename("built_up")
    return built_up


def extract_built_up_refined(image: ee.Image,
                              ndbi_threshold: float = None,
                              ndvi_threshold: float = None,
                              mndwi_threshold: float = None) -> ee.Image:
    """
    综合 NDBI + NDVI + MNDWI 三个指数提取建成区（更准确）。

    逻辑：
        建成区 = NDBI高 & NDVI低 & 不是水体
        即：   NDBI > ndbi_threshold
            AND NDVI < ndvi_threshold
            AND MNDWI < mndwi_threshold

    为什么加 NDVI 和 MNDWI？
        - 裸土的 NDBI 也高，但裸土 NDVI 比建成区高一点
        - 水体的 NDBI 也可能偏高（SWIR 吸收），但 MNDWI > 0

    参数:
        image:           包含 NDBI, NDVI, MNDWI 波段的影像
        ndbi_threshold:  NDBI 建成区下限（默认 -0.05）
        ndvi_threshold:  NDVI 植被上限（默认 0.2）
        mndwi_threshold: MNDWI 水体下限（默认 0.0）

    返回:
        单波段影像 "built_up_refined"（1=建成区, 0=非建成区）
    """
    if ndbi_threshold is None:
        ndbi_threshold = ANALYSIS_CONFIG["ndbi_threshold"]
    if ndvi_threshold is None:
        ndvi_threshold = ANALYSIS_CONFIG["ndvi_vegetation_threshold"]
    if mndwi_threshold is None:
        mndwi_threshold = ANALYSIS_CONFIG["mndwi_water_threshold"]

    ndbi = image.select("NDBI")
    ndvi = image.select("NDVI")
    mndwi = image.select("MNDWI")

    # 三个条件同时满足
    is_building = ndbi.gt(ndbi_threshold)
    is_not_vegetation = ndvi.lt(ndvi_threshold)
    is_not_water = mndwi.lt(mndwi_threshold)

    built_up = is_building.And(is_not_vegetation).And(is_not_water)
    return built_up.rename("built_up_refined")


# ============================================================
# 面积计算
# ============================================================
def calc_built_up_area(built_up_image: ee.Image, roi: ee.Geometry) -> float:
    """
    计算建成区面积（平方公里）。

    原理：
        1. 获取每个像元的实际面积（ee.Image.pixelArea()，单位 m²）
        2. 乘以建成区二值图（只有 1 的像元保留面积）
        3. 在研究区内求和（reduceRegion）
        4. 转换为 km²

    参数:
        built_up_image: 建成区二值图（1=建成区），单波段
        roi:            研究区域

    返回:
        area_km2: 建成区面积（km²），保留两位小数
    """
    # 像元面积 × 建成区掩膜 → 每个建成区像元的实际面积
    pixel_area = built_up_image.multiply(ee.Image.pixelArea())

    stats = pixel_area.reduceRegion(
        reducer=ee.Reducer.sum(),
        geometry=roi,
        scale=30,              # Landsat 分辨率
        maxPixels=1e9,         # 允许最大像元数
    )

    # 从结果字典中取出数值
    band_name = built_up_image.bandNames().get(0)  # "built_up" 或 "built_up_refined"
    area_m2 = ee.Number(stats.get(band_name))

    try:
        area_km2 = round(area_m2.divide(1e6).getInfo(), 2)  # m² → km²
    except Exception:
        area_km2 = 0.0

    return area_km2


# ============================================================
# 方向分析（扇形统计，用于雷达图）
# ============================================================
def _create_sector_wedge(center_lon: float, center_lat: float,
                          radius_meters: float,
                          start_angle: float, end_angle: float) -> ee.Geometry:
    """
    创建一个扇形楔形区域。

    通过角度→弧度转换，用近似公式生成扇形多边形。
    注意：这是球面近似，对城市尺度（10-30km半径）精度足够。

    参数:
        center_lon, center_lat: 城市中心经纬度
        radius_meters:          扇形半径（米）
        start_angle, end_angle: 扇形角度范围（度，正北=0，顺时针）

    返回:
        ee.Geometry.Polygon — 扇形区域
    """
    # 球面近似参数（在中纬度地区误差 < 1%）
    meters_per_deg_lon = 111320.0   # 赤道上的米/经度
    # 纬度方向的米/纬度近似（约 110540 在 30°N）

    points = [(center_lon, center_lat)]  # 从中心点开始

    # 按 5° 步长沿着弧添加点
    step = 5
    angles = []
    a = start_angle
    while a <= end_angle + 0.01:  # 小偏移确保包含终点
        angles.append(a)
        a += step

    for angle in angles:
        rad = math.radians(angle)
        # 近似：经度方向距离 / (cos(纬度) * 111320)
        lat_rad = math.radians(center_lat)
        dx = (radius_meters * math.sin(rad)) / (meters_per_deg_lon * math.cos(lat_rad))
        dy = (radius_meters * math.cos(rad)) / 110540.0
        points.append((center_lon + dx, center_lat + dy))

    points.append((center_lon, center_lat))  # 回到中心

    return ee.Geometry.Polygon([points])


def calc_direction_stats(built_up_image: ee.Image, roi: ee.Geometry,
                          center_lon: float, center_lat: float,
                          radius_meters: float) -> dict:
    """
    计算建成区在八个方向上的分布比例。

    原理：
        1. 将研究区分为 8 个 45° 扇形
        2. 每个扇区内统计建成区面积
        3. 计算各方向占总体建成区的比例

    参数:
        built_up_image: 建成区二值图
        roi:            研究区域
        center_lon:     城市中心经度
        center_lat:     城市中心纬度
        radius_meters:  分析半径（米）

    返回:
        {方向名: 比例} 的字典，例如 {"北": 0.12, "东北": 0.18, ...}
        比例之和 ≈ 1.0
    """
    direction_areas = {}
    merged_names = {}

    for name, start_angle, end_angle in SECTORS:
        try:
            wedge = _create_sector_wedge(
                center_lon, center_lat, radius_meters, start_angle, end_angle
            )
            # 扇形与研究区取交集（确保不超出城市范围）
            sector_roi = wedge.intersection(roi, ee.ErrorMargin(10))

            area = calc_built_up_area(built_up_image, sector_roi)

            # 合并同名扇区（"北" 跨 337.5-360 和 0-22.5 两段）
            if name in merged_names:
                merged_names[name] += area
            else:
                merged_names[name] = area
        except Exception:
            if name not in merged_names:
                merged_names[name] = 0.0

    # 转换为比例
    total = sum(merged_names.values())
    if total > 0:
        proportions = {k: round(v / total, 4) for k, v in merged_names.items()}
    else:
        proportions = {k: 0.0 for k in merged_names}

    return proportions


# ============================================================
# 逐年批量处理
# ============================================================
def process_all_years(years: list, roi: ee.Geometry,
                       get_image_func, use_refined: bool = False) -> tuple:
    """
    批量处理所有年份：获取影像 → 计算指数 → 提取建成区 → 统计面积。

    这个函数封装了单城市分析的完整循环，供 main.py 调用。

    参数:
        years:          年份列表，如 [2000, 2005, 2010, 2015, 2020, 2025]
        roi:            研究区域
        get_image_func: 获取影像的函数（从 gee_utils 传入）
        use_refined:    是否使用 NDBI+NDVI+MNDWI 综合提取

    返回:
        (stats_list, images_dict, builtup_dict) 三元组：
            stats_list:   [{"年份": 2000, "建成区面积(km²)": 12.3, "NDVI均值": 0.45}, ...]
            images_dict:  {2000: image, 2005: image, ...}  真彩色影像
            builtup_dict: {2000: built_up, 2005: built_up, ...}  建成区二值图
    """
    from src.indices import calc_all_indices

    stats_list = []
    images_dict = {}
    builtup_dict = {}

    for year in years:
        print(f"  [→] 处理 {year} 年...")

        # 获取影像
        image, sensor = get_image_func(year, roi)
        print(f"      传感器: Landsat {sensor}")

        # 计算所有指数
        image = calc_all_indices(image)

        # 提取建成区
        if use_refined:
            built_up = extract_built_up_refined(image)
            area_label = "built_up_refined"
        else:
            built_up = extract_built_up(image)
            area_label = "built_up"

        # 计算面积
        area = calc_built_up_area(built_up, roi)
        print(f"      建成区面积: {area} km²")

        # 计算 NDVI 均值（辅助分析城市绿化变化）
        ndvi_mean = _calc_mean_value(image, roi, "NDVI")

        stats_list.append({
            "年份": year,
            "建成区面积(km²)": area,
            "NDVI均值": ndvi_mean if ndvi_mean is not None else "N/A",
            "传感器": sensor,
        })

        images_dict[year] = image
        builtup_dict[year] = built_up

    return stats_list, images_dict, builtup_dict


def _calc_mean_value(image: ee.Image, roi: ee.Geometry, band: str) -> float:
    """计算某波段在研究区内的均值（辅助统计）"""
    try:
        stats = image.select(band).reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=roi,
            scale=30,
            maxPixels=1e9,
        )
        return round(ee.Number(stats.get(band)).getInfo(), 4)
    except Exception:
        return None
