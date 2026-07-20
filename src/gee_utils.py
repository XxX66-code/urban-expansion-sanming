"""
========================================================================
GEE 工具模块 — Google Earth Engine 初始化 + 影像获取 + 云掩膜
========================================================================

这个模块封装了所有与 GEE 交互的操作：
    - init_gee()          初始化认证
    - get_roi()           创建研究区
    - get_landsat_image() 获取某一年份的 Landsat 中值合成影像

依赖：src/config.py
"""

import ee
from src.config import ANALYSIS_CONFIG


# ============================================================
# GEE 初始化
# ============================================================
_gee_initialized = False


def init_gee() -> bool:
    """
    初始化 Google Earth Engine。

    返回:
        True   — 初始化成功
        False  — 需要先运行 `earthengine authenticate` 认证
    """
    global _gee_initialized
    if _gee_initialized:
        return True

    try:
        ee.Initialize()
        _gee_initialized = True
        print("[✓] GEE 初始化成功")
        return True
    except ee.EEException:
        print("\n" + "!" * 60)
        print("[!] GEE 未认证，请先完成以下步骤：")
        print("    1. 注册 GEE：https://earthengine.google.com/signup/")
        print("    2. 终端运行：earthengine authenticate")
        print("    3. 按提示登录 Google 账号并授权")
        print("    4. 重新运行本脚本")
        print("!" * 60 + "\n")
        return False


def is_gee_ready() -> bool:
    """检查 GEE 是否已初始化（不尝试初始化）"""
    return _gee_initialized


# ============================================================
# 研究区域
# ============================================================
def get_roi(lon: float, lat: float, buffer: int) -> ee.Geometry:
    """
    创建一个以指定坐标为中心的圆形缓冲区作为研究区域。

    参数:
        lon:    中心经度
        lat:    中心纬度
        buffer: 缓冲区半径（米）

    返回:
        ee.Geometry — 圆形研究区域

    示例:
        roi = get_roi(117.64, 26.26, 15000)  # 三明市 15km 缓冲区
    """
    point = ee.Geometry.Point([lon, lat])
    return point.buffer(buffer)


# ============================================================
# 云掩膜
# ============================================================
def mask_cloud_landsat5(image: ee.Image) -> ee.Image:
    """
    Landsat 5 (TM) 云掩膜。

    使用 QA_PIXEL 波段的 bit 5（云标志）来识别和掩膜云像素。
    如果 QA_PIXEL 不存在，回退到 QA60 波段。

    参数:
        image: 单景 Landsat 5 影像

    返回:
        去云后的影像
    """
    # 尝试 QA_PIXEL（Collection 2 标准），否则用 QA60
    band_names = image.bandNames()
    if band_names.contains("QA_PIXEL").getInfo():
        qa = image.select("QA_PIXEL")
        # bit 5 = 云标志；1表示有云，我们取 eq(0) 保留无云像素
        cloud_mask = qa.bitwiseAnd(1 << 5).eq(0)
    else:
        qa = image.select("QA60")
        cloud_mask = qa.bitwiseAnd(1 << 10).eq(0)  # 密集云
    return image.updateMask(cloud_mask)


def mask_cloud_landsat8(image: ee.Image) -> ee.Image:
    """
    Landsat 8/9 (OLI) 云掩膜。

    使用 QA_PIXEL 波段的 bit 3（云）和 bit 4（云阴影）来掩膜。

    参数:
        image: 单景 Landsat 8/9 影像

    返回:
        去云后的影像
    """
    qa = image.select("QA_PIXEL")
    cloud_mask = qa.bitwiseAnd(1 << 3).eq(0)      # bit 3：云 → 掩膜
    shadow_mask = qa.bitwiseAnd(1 << 4).eq(0)     # bit 4：云阴影 → 掩膜
    return image.updateMask(cloud_mask.And(shadow_mask))


# ============================================================
# 获取 Landsat 影像
# ============================================================
def get_landsat_image(year: int, roi: ee.Geometry) -> tuple:
    """
    获取指定年份、指定区域的 Landsat 地表反射率中值合成影像。

    工作流程：
        1. 根据年份自动选择 Landsat 5 (≤2012) 或 Landsat 8 (>2012)
        2. 筛选全年影像，过滤云量 >30% 的场景
        3. 逐景做云掩膜
        4. 取中值合成（median）消除残余噪声
        5. 重命名为统一的 6 波段顺序：[蓝, 绿, 红, 近红, 中红外1, 中红外2]
        6. 裁剪到研究区

    参数:
        year: 年份（int）
        roi:  研究区域（ee.Geometry）

    返回:
        (image, sensor) 元组:
            image  — 6 波段中值合成影像（ee.Image）
            sensor — 传感器标识，"L5" 或 "L8"
    """
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"
    max_cloud = ANALYSIS_CONFIG["max_cloud_cover"]

    if year <= 2012:
        # --- Landsat 5 TM (1984–2012) ---
        # 波段：SR_B1(蓝), SR_B2(绿), SR_B3(红), SR_B4(近红), SR_B5(中红外1), SR_B7(中红外2)
        collection = (
            ee.ImageCollection("LANDSAT/LT05/C02/T1_L2")
            .filterBounds(roi)
            .filterDate(start_date, end_date)
            .filter(ee.Filter.lt("CLOUD_COVER", max_cloud))
            .map(mask_cloud_landsat5)
            .median()
        )
        image = collection.select(["SR_B1", "SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B7"])
        sensor = "L5"

    else:
        # --- Landsat 8/9 OLI (2013–至今) ---
        # 波段：SR_B2(蓝), SR_B3(绿), SR_B4(红), SR_B5(近红), SR_B6(中红外1), SR_B7(中红外2)
        collection = (
            ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
            .filterBounds(roi)
            .filterDate(start_date, end_date)
            .filter(ee.Filter.lt("CLOUD_COVER", max_cloud))
            .map(mask_cloud_landsat8)
            .median()
        )
        image = collection.select(["SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7"])
        sensor = "L8"

    # 裁剪 + 应用缩放因子（反射率 0-1 范围）
    image = image.clip(roi)

    return image, sensor


# ============================================================
# 波段索引说明（方便查询）
# ============================================================
"""
统一后的波段顺序（所有函数都按这个来）：

    索引  波段名    全称                    波长范围       用途
    ───────────────────────────────────────────────────────
    [0]   蓝       Blue                    0.45-0.52μm   海岸/气溶胶
    [1]   绿       Green                   0.52-0.60μm   植被健康
    [2]   红       Red                     0.63-0.69μm   植被类型
    [3]   近红外   NIR (Near Infrared)     0.77-0.90μm   植被茂密度
    [4]   中红外1  SWIR1 (Shortwave IR1)   1.55-1.75μm   建筑/裸土
    [5]   中红外2  SWIR2 (Shortwave IR2)   2.09-2.35μm   地质/矿物

常用指数公式：
    NDBI  = (SWIR1 - NIR)  / (SWIR1 + NIR)    → 用波段 [4] 和 [3]
    NDVI  = (NIR - Red)    / (NIR + Red)      → 用波段 [3] 和 [2]
    MNDWI = (Green - SWIR1)/ (Green + SWIR1)  → 用波段 [1] 和 [4]
"""
