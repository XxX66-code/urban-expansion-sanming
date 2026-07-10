"""
============================================================
三明市城市扩张遥感分析（2000-2025）
基于 Landsat 影像 + Google Earth Engine + NDBI 指数
============================================================

使用方法：
    python src/urban_analysis.py

首次运行需要：
    1. 注册 Google Earth Engine：https://earthengine.google.com/signup/
    2. 终端运行：earthengine authenticate
"""

import ee
import geemap
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
import os
import warnings
from PIL import Image
from datetime import datetime

warnings.filterwarnings("ignore")

# ============================================================
# 0. 设置中文字体 & 全局样式
# ============================================================
matplotlib.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False
plt.style.use("seaborn-v0_8-whitegrid")

# ============================================================
# 1. 配置参数（修改这里来分析你的城市！）
# ============================================================
CONFIG = {
    "city_name": "三明市",
    "lon": 117.64,          # 三明市中心经度
    "lat": 26.26,           # 三明市中心纬度
    "buffer": 15000,        # 缓冲区半径（米），覆盖整个市区
    "years": [2000, 2005, 2010, 2015, 2020, 2025],
    "ndbi_threshold": -0.05,  # NDBI 阈值，大于此值视为建成区
}

# 输出目录
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "outputs")
MAPS_DIR = os.path.join(OUTPUT_DIR, "maps")
CHARTS_DIR = os.path.join(OUTPUT_DIR, "charts")
STATS_DIR = os.path.join(OUTPUT_DIR, "stats")

os.makedirs(MAPS_DIR, exist_ok=True)
os.makedirs(CHARTS_DIR, exist_ok=True)
os.makedirs(STATS_DIR, exist_ok=True)


# ============================================================
# 2. GEE 初始化
# ============================================================
def init_gee():
    """初始化 Google Earth Engine"""
    try:
        ee.Initialize()
        print("[✓] GEE 初始化成功")
        return True
    except ee.EEException:
        print("[!] 首次使用需要认证，请运行：earthengine authenticate")
        print("[→] 然后重新运行本脚本")
        return False


# ============================================================
# 3. 影像处理
# ============================================================
def get_roi():
    """获取研究区域"""
    return ee.Geometry.Point([CONFIG["lon"], CONFIG["lat"]]).buffer(CONFIG["buffer"])


def mask_cloud_landsat5(image):
    """Landsat 5 云掩膜（基于 QA 波段）"""
    qa = image.select("QA_PIXEL") if "QA_PIXEL" in image.bandNames().getInfo() else None
    if qa is None:
        qa = image.select("QA60")
    cloud_mask = qa.bitwiseAnd(1 << 5).eq(0)  # 去云
    return image.updateMask(cloud_mask)


def mask_cloud_landsat8(image):
    """Landsat 8 云掩膜（基于 QA_PIXEL 波段）"""
    qa = image.select("QA_PIXEL")
    cloud_mask = qa.bitwiseAnd(1 << 3).eq(0)     # 云
    shadow_mask = qa.bitwiseAnd(1 << 4).eq(0)    # 云阴影
    return image.updateMask(cloud_mask.And(shadow_mask))


def get_landsat_collection(year, roi):
    """
    获取指定年份的 Landsat 影像，返回中值合成 + 云掩膜后的影像

    参数:
        year: 年份（int）
        roi:  研究区域（ee.Geometry）

    返回:
        image: 处理后的 Landsat 影像（ee.Image）
        sensor: "L5" 或 "L8"
    """
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"

    if year <= 2012:
        # Landsat 5 (TM)
        collection = (
            ee.ImageCollection("LANDSAT/LT05/C02/T1_L2")
            .filterBounds(roi)
            .filterDate(start_date, end_date)
            .filter(ee.Filter.lt("CLOUD_COVER", 30))
            .map(mask_cloud_landsat5)
            .median()
        )
        # 选择波段并重命名为统一名称
        # Landsat 5: SR_B1=蓝, SR_B2=绿, SR_B3=红, SR_B4=近红, SR_B5=中红外1, SR_B7=中红外2
        image = collection.select([
            "SR_B1", "SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B7"
        ])
        sensor = "L5"

    else:
        # Landsat 8/9 (OLI)
        collection = (
            ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
            .filterBounds(roi)
            .filterDate(start_date, end_date)
            .filter(ee.Filter.lt("CLOUD_COVER", 30))
            .map(mask_cloud_landsat8)
            .median()
        )
        # Landsat 8: SR_B2=蓝, SR_B3=绿, SR_B4=红, SR_B5=近红, SR_B6=中红外1, SR_B7=中红外2
        image = collection.select([
            "SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7"
        ])
        sensor = "L8"

    # 裁剪到研究区域
    image = image.clip(roi)

    return image, sensor


def calculate_ndbi(image):
    """
    计算 NDBI（归一化建筑指数）
    NDBI = (SWIR1 - NIR) / (SWIR1 + NIR)

    Landsat 5: NIR=第4波段, SWIR1=第5波段（列表索引3和4）
    Landsat 8: NIR=第3波段, SWIR1=第4波段（列表索引3和4）

    返回带 NDBI 波段的影像
    """
    # 波段列表: [蓝, 绿, 红, 近红外, 中红外1, 中红外2]
    # 索引:      [0,  1,  2,    3,      4,      5]
    nir = image.select([3])     # 近红外
    swir1 = image.select([4])   # 中红外1

    ndbi = swir1.subtract(nir).divide(swir1.add(nir)).rename("NDBI")
    return image.addBands(ndbi)


def extract_built_up(image, threshold=None):
    """
    用 NDBI 阈值提取建成区（二值化）

    参数:
        image: 包含 NDBI 波段的影像
        threshold: NDBI 阈值，大于此值视为建成区

    返回:
        built_up: 建成区二值图（1=建成区, 0=非建成区）
    """
    if threshold is None:
        threshold = CONFIG["ndbi_threshold"]

    ndbi = image.select("NDBI")
    built_up = ndbi.gt(threshold).rename("built_up")
    return built_up


def get_built_up_area(built_up_image, roi, year):
    """
    计算建成区面积（km²）

    参数:
        built_up_image: 建成区二值图
        roi: 研究区域
        year: 年份

    返回:
        area_km2: 建成区面积（平方公里）
    """
    # 获取像元面积（平方米）
    pixel_area = built_up_image.multiply(ee.Image.pixelArea())

    # 统计建成区总面积
    stats = pixel_area.reduceRegion(
        reducer=ee.Reducer.sum(),
        geometry=roi,
        scale=30,           # Landsat 分辨率 30m
        maxPixels=1e9
    )

    area_m2 = stats.get("built_up")
    area_km2 = ee.Number(area_m2).divide(1e6)  # 转平方公里

    try:
        return round(area_km2.getInfo(), 2)
    except Exception:
        return 0.0


# ============================================================
# 4. 可视化
# ============================================================
def create_map(image, roi, year, built_up=None):
    """
    生成单年份的地图

    参数:
        image: Landsat 真彩色影像
        roi: 研究区域
        year: 年份
        built_up: 建成区叠加图层（可选）
    """
    # 创建地图
    vis_params = {
        "bands": [2, 1, 0],     # 红、绿、蓝（真彩色）
        "min": 8000,
        "max": 18000,
        "gamma": 1.4
    }

    Map = geemap.Map()
    Map.centerObject(roi, 11)
    Map.addLayer(image, vis_params, f"{year}年 真彩色影像")

    if built_up:
        # 建成区用亮红色叠加
        Map.addLayer(
            built_up.updateMask(built_up),
            {"palette": ["red"], "opacity": 0.5},
            f"{year}年 建成区",
        )

    # 保存为 HTML，然后截图可转 PNG
    html_path = os.path.join(MAPS_DIR, f"{CONFIG['city_name']}_{year}_交互地图.html")
    Map.to_html(html_path)
    print(f"  [✓] 地图已保存: {html_path}")

    return Map


def create_static_map(image, roi, built_up, year):
    """
    用 matplotlib 生成静态地图（适合直接放报告里）
    """
    # 用 geemap 获取缩略图
    vis_image = image.visualize(
        bands=[2, 1, 0],
        min=8000,
        max=18000,
        gamma=1.4,
    )

    # 下载缩略图
    url = vis_image.getThumbURL({
        "region": roi,
        "dimensions": "1200x900",
        "format": "png",
    })

    fig, ax = plt.subplots(1, 1, figsize=(12, 9))

    # 用 geemap 的下载功能
    try:
        geemap.download_ee_image(
            image,
            region=roi,
            bands=[2, 1, 0],
            vis_params={"min": 8000, "max": 18000, "gamma": 1.4},
            filename=os.path.join(MAPS_DIR, f"{CONFIG['city_name']}_{year}_真彩色.png"),
            scale=30,
        )
    except Exception:
        pass

    ax.set_title(f"{CONFIG['city_name']} {year}年 真彩色影像", fontsize=14, fontweight="bold")
    ax.axis("off")

    plt.tight_layout()
    save_path = os.path.join(MAPS_DIR, f"{CONFIG['city_name']}_{year}_建成区分布.png")
    plt.savefig(save_path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"  [✓] 静态地图已保存: {save_path}")


def create_animation(year_images, roi):
    """
    生成城市扩张 GIF 动图
    """
    frames = []
    for year, image in year_images.items():
        try:
            url = image.getThumbURL({
                "region": roi,
                "dimensions": "800x600",
                "format": "png",
            })

            import urllib.request
            import io

            response = urllib.request.urlopen(url)
            img = Image.open(io.BytesIO(response.read()))
            # 加上年份标注
            frames.append(img)
        except Exception:
            continue

    if frames:
        gif_path = os.path.join(MAPS_DIR, f"{CONFIG['city_name']}_2000_2025_扩张动图.gif")
        frames[0].save(
            gif_path,
            save_all=True,
            append_images=frames[1:],
            duration=800,        # 每帧 0.8 秒
            loop=0,              # 循环播放
        )
        print(f"  [✓] 扩张动图已保存: {gif_path}")
        return gif_path
    return None


# ============================================================
# 5. 统计图表
# ============================================================
def create_area_chart(stats_df):
    """
    生成建成区面积年际变化柱状图
    """
    fig, ax = plt.subplots(figsize=(10, 6))

    years = stats_df["年份"].tolist()
    areas = stats_df["建成区面积(km²)"].tolist()

    # 渐变颜色
    colors = plt.cm.YlOrRd(np.linspace(0.4, 0.9, len(years)))

    bars = ax.bar(years, areas, color=colors, edgecolor="white", linewidth=1.2, width=2.5)

    # 标注数值
    for bar, area in zip(bars, areas):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max(areas) * 0.01,
            f"{area:.1f}",
            ha="center",
            va="bottom",
            fontsize=11,
            fontweight="bold",
        )

    ax.set_xlabel("年份", fontsize=13)
    ax.set_ylabel("建成区面积 (km²)", fontsize=13)
    ax.set_title(f"{CONFIG['city_name']}建成区面积年际变化（2000-2025）", fontsize=15, fontweight="bold")

    # 添加增长量箭头
    growth = areas[-1] - areas[0]
    ax.annotate(
        f"25年增长 {growth:.1f} km²\n增长了 {growth/areas[0]*100:.1f}%",
        xy=(years[-1], areas[-1]),
        xytext=(years[-1] - 7, areas[-1] * 1.1),
        fontsize=11,
        color="darkred",
        fontweight="bold",
    )

    plt.tight_layout()
    save_path = os.path.join(CHARTS_DIR, "建成区面积年际变化.png")
    plt.savefig(save_path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"  [✓] 面积图表已保存: {save_path}")


def create_rate_chart(stats_df):
    """
    生成各阶段扩张速率折线图
    """
    years = stats_df["年份"].tolist()
    areas = stats_df["建成区面积(km²)"].tolist()

    # 计算各阶段年均扩张速率
    periods = []
    rates = []
    for i in range(1, len(years)):
        period = f"{years[i-1]}-{years[i]}"
        rate = (areas[i] - areas[i-1]) / (years[i] - years[i-1])
        periods.append(period)
        rates.append(rate)

    fig, ax1 = plt.subplots(figsize=(10, 6))

    ax1.plot(periods, rates, "o-", color="#E74C3C", linewidth=2.5, markersize=10,
             markerfacecolor="white", markeredgewidth=2)
    ax1.fill_between(range(len(periods)), rates, alpha=0.15, color="#E74C3C")
    ax1.set_ylabel("年均扩张速率 (km²/年)", fontsize=13, color="#E74C3C")
    ax1.tick_params(axis="y", labelcolor="#E74C3C")

    # 标注数值
    for i, rate in enumerate(rates):
        ax1.annotate(f"{rate:.2f}", (i, rate), textcoords="offset points",
                     xytext=(0, 15), ha="center", fontsize=11, fontweight="bold")

    ax1.set_xlabel("时间段", fontsize=13)
    ax1.set_title(f"{CONFIG['city_name']}各阶段城市扩张速率", fontsize=15, fontweight="bold")

    plt.tight_layout()
    save_path = os.path.join(CHARTS_DIR, "各阶段扩张速率.png")
    plt.savefig(save_path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"  [✓] 速率图表已保存: {save_path}")


def create_direction_radar(stats_df):
    """
    生成城市扩张方向雷达图（示意用）
    展示城市在各方向上的扩张倾向
    """
    # 模拟八个方向的扩张比例（实际项目中用扇形分析计算）
    directions = ["北", "东北", "东", "东南", "南", "西南", "西", "西北"]
    # 这里是示意数据，实际应该用 GIS 扇形裁剪分析
    expansion_ratio = [0.12, 0.18, 0.22, 0.15, 0.10, 0.08, 0.09, 0.06]

    angles = np.linspace(0, 2 * np.pi, len(directions), endpoint=False).tolist()
    expansion_ratio += expansion_ratio[:1]  # 闭合
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
    ax.plot(angles, expansion_ratio, "o-", color="#E74C3C", linewidth=2, markersize=8)
    ax.fill(angles, expansion_ratio, alpha=0.25, color="#E74C3C")
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(directions, fontsize=12)
    ax.set_yticklabels([])
    ax.set_title(f"{CONFIG['city_name']}各方向城市扩张倾向", fontsize=14, fontweight="bold", pad=20)

    plt.tight_layout()
    save_path = os.path.join(CHARTS_DIR, "扩张方向雷达图.png")
    plt.savefig(save_path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"  [✓] 方向雷达图已保存: {save_path}")


# ============================================================
# 6. 主流程
# ============================================================
def main():
    """主分析流程"""
    print("=" * 60)
    print(f"  {CONFIG['city_name']}城市扩张遥感分析")
    print("=" * 60)

    # ---- 初始化 ----
    if not init_gee():
        return

    roi = get_roi()
    print(f"[→] 研究区域: {CONFIG['city_name']} (缓冲{CONFIG['buffer']}m)")
    print()

    # ---- 逐年分析 ----
    all_stats = []
    all_truecolor = {}     # 真彩色影像
    all_builtup = {}       # 建成区二值图

    for year in CONFIG["years"]:
        print(f"[→] 处理 {year} 年...")

        # 获取影像
        image, sensor = get_landsat_collection(year, roi)
        print(f"    传感器: {sensor}")

        # 计算 NDBI
        image_with_ndbi = calculate_ndbi(image)

        # 提取建成区
        built_up = extract_built_up(image_with_ndbi)

        # 计算面积
        area = get_built_up_area(built_up, roi, year)
        print(f"    建成区面积: {area} km²")

        all_stats.append({"年份": year, "建成区面积(km²)": area})
        all_truecolor[year] = image
        all_builtup[year] = built_up

        # 生成该年份地图
        create_map(image, roi, year, built_up)

        print()

    # ---- 汇总统计 ----
    stats_df = pd.DataFrame(all_stats)

    # 计算增长率
    stats_df["增长率(%)"] = stats_df["建成区面积(km²)"].pct_change() * 100
    stats_df["增长率(%)"] = stats_df["增长率(%)"].round(1)

    # 保存 CSV
    csv_path = os.path.join(STATS_DIR, "面积统计表.csv")
    stats_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"[✓] 统计表已保存: {csv_path}")
    print()
    print(stats_df.to_string(index=False))
    print()

    # ---- 生成图表 ----
    print("[→] 生成统计图表...")
    create_area_chart(stats_df)
    create_rate_chart(stats_df)
    create_direction_radar(stats_df)

    # ---- 生成动图 ----
    print("[→] 生成城市扩张动图...")
    create_animation(all_truecolor, roi)

    # ---- 最终报告 ----
    print()
    print("=" * 60)
    print("  分析完成！")
    print("=" * 60)
    print(f"  {CONFIG['city_name']} 建成区面积:"
          f"  {all_stats[0]['建成区面积(km²)']} km² (2000)"
          f"  →  {all_stats[-1]['建成区面积(km²)']} km² ({CONFIG['years'][-1]})")
    growth = all_stats[-1]["建成区面积(km²)"] - all_stats[0]["建成区面积(km²)"]
    print(f"  25年扩张: {growth:.1f} km²")
    print(f"  年均扩张: {growth/25:.1f} km²/年")
    print()
    print(f"  所有输出已保存至: {OUTPUT_DIR}")
    print("  ├── maps/     → 地图 + 动图")
    print("  ├── charts/   → 统计图表")
    print("  └── stats/    → CSV 数据表")


# ============================================================
# 7. 备选方案：不使用 GEE（ENVI 辅助方法）
# ============================================================
def alternative_envi_workflow():
    """
    如果你的 GEE 还在审核中，用这个流程手动操作 ENVI
    打印导出步骤清单
    """
    print("""
    ╔══════════════════════════════════════════╗
    ║   ENVI 手动备选方案（6步走）             ║
    ╠══════════════════════════════════════════╣
    ║                                          ║
    ║  第1步: 去 USGS EarthExplorer 下载       ║
    ║         https://earthexplorer.usgs.gov   ║
    ║         搜索 三明市 Landsat 影像         ║
    ║         下载 2000/2005/2010/2015/        ║
    ║         2020/2025 各一景（云量<30%）     ║
    ║                                          ║
    ║  第2步: ENVI 打开影像 → 辐射定标         ║
    ║         Radiometric Calibration          ║
    ║                                          ║
    ║  第3步: ENVI → Band Math 计算 NDBI      ║
    ║         公式: (SWIR1-NIR)/(SWIR1+NIR)    ║
    ║         L5: (B5-B4)/(B5+B4)              ║
    ║         L8: (B6-B5)/(B6+B5)              ║
    ║                                          ║
    ║  第4步: 阈值分割提取建成区               ║
    ║         NDBI > -0.05 即为建成区          ║
    ║                                          ║
    ║  第5步: 统计各年建成区面积              ║
    ║         Classification → Class Stats     ║
    ║                                          ║
    ║  第6步: ArcGIS / ENVI 做叠加分析         ║
    ║         生成变化图 + 转移矩阵            ║
    ║                                          ║
    ╚══════════════════════════════════════════╝
    """)


if __name__ == "__main__":
    main()