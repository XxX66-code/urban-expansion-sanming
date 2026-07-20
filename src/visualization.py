"""
========================================================================
可视化模块 — 地图 + 图表 + 动图 + 多城市对比
========================================================================

所有输出图片自动保存到 outputs/ 目录。

函数一览：
    地图类：
        save_interactive_map()      交互式 HTML 地图
        save_static_map()           静态 PNG 地图（报告用）
        save_comparison_map()       2000 vs 2025 对比地图

    图表类：
        save_area_chart()           建成区面积年际变化柱状图
        save_rate_chart()           各阶段扩张速率折线图
        save_direction_radar()      城市扩张方向雷达图（真实数据）
        save_multi_city_comparison() 多城市对比图
        save_ndvi_trend()           NDVI 均值变化趋势图

    动图：
        save_expansion_gif()        城市扩张 GIF 动图

依赖：matplotlib, numpy, PIL, geemap, ee
     src/config.py
"""

import os
import io
import urllib.request
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from PIL import Image
import ee
import geemap

from src.config import (
    MAPS_DIR, CHARTS_DIR, VIZ, ANALYSIS_CONFIG, CITIES
)


# ============================================================
# 样式常量
# ============================================================
COLOR_PRIMARY = "#E74C3C"     # 主色（建成区红）
COLOR_SECONDARY = "#3498DB"   # 辅色（对比蓝）
COLOR_GREEN = "#27AE60"       # NDVI 绿
COLOR_ORANGE = "#F39C12"       # 橙色
COLOR_PURPLE = "#8E44AD"       # 紫色
COLORS_CITIES = [COLOR_PRIMARY, COLOR_SECONDARY, COLOR_GREEN, COLOR_ORANGE]

# 八方向（顺时针，正北起）
DIRECTION_LABELS = ["北", "东北", "东", "东南", "南", "西南", "西", "西北"]


# ============================================================
# 交互式地图
# ============================================================
def save_interactive_map(image: ee.Image, roi: ee.Geometry,
                          year: int, city_name: str,
                          built_up: ee.Image = None) -> str:
    """
    保存交互式 HTML 地图（可在浏览器中缩放、拖动）。

    地图包含：
        - 真彩色影像底图
        - 建成区红色叠加层（如果提供）
        - 研究区边界

    参数:
        image:     Landsat 真彩色影像
        roi:       研究区域
        year:      年份
        city_name: 城市名
        built_up:  建成区二值图（可选）

    返回:
        保存路径
    """
    Map = geemap.Map()
    Map.centerObject(roi, 11)

    # 真彩色底图
    Map.addLayer(image, VIZ["true_color"], f"{year}年 真彩色影像")

    # 建成区叠加
    if built_up:
        Map.addLayer(
            built_up.updateMask(built_up),
            {"palette": VIZ["built_up_palette"], "opacity": VIZ["built_up_opacity"]},
            f"{year}年 建成区",
        )

    # 研究区边界
    Map.addLayer(roi, {"color": "white"}, "研究区边界")

    html_path = os.path.join(MAPS_DIR, f"{city_name}_{year}_交互地图.html")
    Map.to_html(html_path)
    print(f"  [✓] 交互地图: {os.path.basename(html_path)}")
    return html_path


# ============================================================
# 静态地图（用于报告插图）
# ============================================================
def save_static_map(image: ee.Image, roi: ee.Geometry,
                     year: int, city_name: str,
                     built_up: ee.Image = None) -> str:
    """
    保存 PNG 静态地图（适合插入课程设计报告/论文）。

    通过 geemap 的 download_ee_image 导出高分辨率图片。
    """
    save_path = os.path.join(MAPS_DIR, f"{city_name}_{year}_真彩色.png")

    try:
        bands = VIZ["true_color"]["bands"]
        vis = {
            "min": VIZ["true_color"]["min"],
            "max": VIZ["true_color"]["max"],
            "gamma": VIZ["true_color"]["gamma"],
        }
        geemap.download_ee_image(
            image, region=roi, bands=bands,
            vis_params=vis, filename=save_path, scale=30,
        )
        print(f"  [✓] 静态地图: {os.path.basename(save_path)}")
    except Exception as e:
        print(f"  [!] 静态地图下载失败: {e}")

    return save_path


# ============================================================
# 2000 vs 2025 对比地图
# ============================================================
def save_comparison_map(image_early: ee.Image, image_late: ee.Image,
                         roi: ee.Geometry, city_name: str,
                         year_early: int = 2000, year_late: int = 2025) -> str:
    """
    保存 2000 vs 2025 对比图（并排或上下）。

    使用 matplotlib 子图，左边=早期，右边=近期。
    """
    fig, axes = plt.subplots(1, 2, figsize=(18, 8))

    for ax, image, year in zip(axes, [image_early, image_late], [year_early, year_late]):
        try:
            # 获取 GEE 缩略图 URL 并加载
            url = image.getThumbURL({
                "region": roi,
                "dimensions": "900x700",
                "bands": VIZ["true_color"]["bands"],
                "min": str(VIZ["true_color"]["min"]),
                "max": str(VIZ["true_color"]["max"]),
                "gamma": str(VIZ["true_color"]["gamma"]),
                "format": "png",
            })
            response = urllib.request.urlopen(url)
            img = Image.open(io.BytesIO(response.read()))
            ax.imshow(img)
        except Exception:
            ax.text(0.5, 0.5, f"影像加载失败\n{year}", transform=ax.transAxes,
                    ha="center", va="center", fontsize=14, color="gray")

        ax.set_title(f"{year} 年", fontsize=16, fontweight="bold")
        ax.axis("off")

    fig.suptitle(f"{city_name} 城市扩张对比（{year_early} vs {year_late}）",
                 fontsize=18, fontweight="bold", y=0.98)

    plt.tight_layout()
    save_path = os.path.join(MAPS_DIR, f"{city_name}_{year_early}_vs_{year_late}_对比图.png")
    plt.savefig(save_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"  [✓] 对比地图: {os.path.basename(save_path)}")
    return save_path


# ============================================================
# 建成区面积柱状图
# ============================================================
def save_area_chart(stats_df, city_name: str) -> str:
    """
    建成区面积年际变化柱状图。

    柱体用暖色渐变，标注数值，顶部显示总增长量。
    """
    years = stats_df["年份"].tolist()
    areas = stats_df["建成区面积(km²)"].tolist()

    fig, ax = plt.subplots(figsize=(10, 6))

    # 暖色渐变（越近越红）
    colors = plt.cm.YlOrRd(np.linspace(0.4, 0.9, len(years)))
    bars = ax.bar(years, areas, color=colors, edgecolor="white",
                  linewidth=1.5, width=2.5)

    # 柱顶标注
    for bar, area in zip(bars, areas):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(areas) * 0.015,
                f"{area:.1f}",
                ha="center", va="bottom",
                fontsize=11, fontweight="bold")

    # 增长标注
    growth = areas[-1] - areas[0]
    ax.annotate(
        f"+{growth:.1f} km²\n增长 {growth / areas[0] * 100:.1f}%",
        xy=(years[-1], areas[-1]),
        xytext=(years[-1] - 8, areas[-1] * 1.15),
        arrowprops=dict(arrowstyle="->", color=COLOR_PRIMARY, lw=1.5),
        fontsize=11, color="darkred", fontweight="bold",
    )

    ax.set_xlabel("年份", fontsize=13)
    ax.set_ylabel("建成区面积 (km²)", fontsize=13)
    ax.set_title(f"{city_name} 建成区面积年际变化（{years[0]}-{years[-1]}）",
                 fontsize=15, fontweight="bold")
    ax.set_ylim(0, max(areas) * 1.2)

    plt.tight_layout()
    save_path = os.path.join(CHARTS_DIR, f"{city_name}_建成区面积年际变化.png")
    plt.savefig(save_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"  [✓] 面积柱状图: {os.path.basename(save_path)}")
    return save_path


# ============================================================
# 扩张速率折线图
# ============================================================
def save_rate_chart(stats_df, city_name: str) -> str:
    """
    各阶段年均扩张速率折线图。

    展示每 5 年的平均扩张速度，快速识别哪个阶段城市扩张最快。
    """
    years = stats_df["年份"].tolist()
    areas = stats_df["建成区面积(km²)"].tolist()

    # 计算各时段速率
    periods = [f"{years[i - 1]}–{years[i]}" for i in range(1, len(years))]
    rates = [(areas[i] - areas[i - 1]) / (years[i] - years[i - 1])
             for i in range(1, len(years))]

    fig, ax = plt.subplots(figsize=(10, 6))

    ax.plot(periods, rates, "o-", color=COLOR_PRIMARY, linewidth=2.5,
            markersize=10, markerfacecolor="white", markeredgewidth=2)
    ax.fill_between(range(len(periods)), rates, alpha=0.12, color=COLOR_PRIMARY)

    # 标注速率值
    for i, rate in enumerate(rates):
        offset = (0, 12) if rate >= 0 else (0, -20)
        ax.annotate(f"{rate:.2f}", (i, rate),
                    textcoords="offset points", xytext=offset,
                    ha="center", fontsize=11, fontweight="bold")

    ax.set_xlabel("时间段", fontsize=13)
    ax.set_ylabel("年均扩张速率 (km²/年)", fontsize=13, color=COLOR_PRIMARY)
    ax.tick_params(axis="y", labelcolor=COLOR_PRIMARY)
    ax.set_title(f"{city_name} 各阶段城市扩张速率", fontsize=15, fontweight="bold")

    plt.tight_layout()
    save_path = os.path.join(CHARTS_DIR, f"{city_name}_各阶段扩张速率.png")
    plt.savefig(save_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"  [✓] 速率折线图: {os.path.basename(save_path)}")
    return save_path


# ============================================================
# 扩张方向雷达图（使用真实分析数据）
# ============================================================
def save_direction_radar(direction_stats: dict, city_name: str, year: int = None) -> str:
    """
    城市扩张方向雷达图。

    参数:
        direction_stats: {"北": 0.12, "东北": 0.18, ...}（比例，和为 1）
        city_name:       城市名
        year:            年份（可选，用于标题）
    """
    if not direction_stats:
        print("  [!] 方向数据为空，跳过雷达图")
        return ""

    # 确保按固定顺序排列
    values = [direction_stats.get(d, 0.0) for d in DIRECTION_LABELS]

    angles = np.linspace(0, 2 * np.pi, len(DIRECTION_LABELS), endpoint=False).tolist()
    values_closed = values + values[:1]
    angles_closed = angles + angles[:1]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))

    ax.plot(angles_closed, values_closed, "o-", color=COLOR_PRIMARY,
            linewidth=2, markersize=8, markerfacecolor="white", markeredgewidth=2)
    ax.fill(angles_closed, values_closed, alpha=0.2, color=COLOR_PRIMARY)

    # 标注比例
    for angle, val, label in zip(angles, values, DIRECTION_LABELS):
        if val > 0.01:
            ax.annotate(f"{val:.1%}", xy=(angle, val),
                        xytext=(angle, val + max(values) * 0.15),
                        fontsize=9, fontweight="bold", ha="center")

    ax.set_xticks(angles)
    ax.set_xticklabels(DIRECTION_LABELS, fontsize=12)
    ax.set_yticklabels([])

    title = f"{city_name} 城市扩张方向分布"
    if year:
        title += f"（{year}年）"
    ax.set_title(title, fontsize=14, fontweight="bold", pad=20)

    plt.tight_layout()

    filename = f"{city_name}"
    if year:
        filename += f"_{year}"
    filename += "_扩张方向雷达图.png"

    save_path = os.path.join(CHARTS_DIR, filename)
    plt.savefig(save_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"  [✓] 方向雷达图: {os.path.basename(save_path)}")
    return save_path


# ============================================================
# NDVI 趋势图
# ============================================================
def save_ndvi_trend(stats_df, city_name: str) -> str:
    """
    NDVI 均值变化趋势图。

    展示城市绿化程度的年际变化（NDVI 下降=植被减少=城市化加剧）。
    """
    years = stats_df["年份"].tolist()

    # 检查 NDVI 数据是否可用
    if "NDVI均值" not in stats_df.columns:
        print("  [!] 无 NDVI 数据，跳过趋势图")
        return ""

    ndvi_vals = []
    for v in stats_df["NDVI均值"]:
        if isinstance(v, (int, float)) and not (isinstance(v, float) and np.isnan(v)):
            ndvi_vals.append(v)
        else:
            ndvi_vals.append(np.nan)

    fig, ax = plt.subplots(figsize=(10, 6))

    ax.plot(years, ndvi_vals, "o-", color=COLOR_GREEN, linewidth=2.5,
            markersize=10, markerfacecolor="white", markeredgewidth=2)
    ax.fill_between(years, ndvi_vals, alpha=0.1, color=COLOR_GREEN)

    for yr, val in zip(years, ndvi_vals):
        if not np.isnan(val):
            ax.annotate(f"{val:.4f}", (yr, val),
                        textcoords="offset points", xytext=(0, 12),
                        ha="center", fontsize=10)

    ax.set_xlabel("年份", fontsize=13)
    ax.set_ylabel("NDVI 均值", fontsize=13, color=COLOR_GREEN)
    ax.tick_params(axis="y", labelcolor=COLOR_GREEN)
    ax.set_title(f"{city_name} 植被指数(NDVI)年际变化", fontsize=15, fontweight="bold")

    # 添加趋势箭头
    if len(ndvi_vals) >= 2 and not np.isnan(ndvi_vals[0]) and not np.isnan(ndvi_vals[-1]):
        diff = ndvi_vals[-1] - ndvi_vals[0]
        direction = "下降" if diff < 0 else "上升"
        ax.text(0.02, 0.95, f"NDVI {direction} {abs(diff):.4f}\n{'→ 城市化 + 植被减少' if diff < 0 else '→ 绿化改善'}",
                transform=ax.transAxes, fontsize=11, verticalalignment="top",
                bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5))

    plt.tight_layout()
    save_path = os.path.join(CHARTS_DIR, f"{city_name}_NDVI趋势.png")
    plt.savefig(save_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"  [✓] NDVI趋势图: {os.path.basename(save_path)}")
    return save_path


# ============================================================
# 多城市对比图
# ============================================================
def save_multi_city_comparison(cities_stats: dict) -> str:
    """
    多城市建成区面积对比图。

    并排柱状图，不同城市不同颜色，直观对比扩张差异。
    """
    if len(cities_stats) < 2:
        print("  [!] 少于 2 个城市，跳过对比图")
        return ""

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    # ---- 子图1：面积年际变化对比 ----
    ax1 = axes[0]
    for i, (city, df) in enumerate(cities_stats.items()):
        color = COLORS_CITIES[i % len(COLORS_CITIES)]
        years = df["年份"].tolist()
        areas = df["建成区面积(km²)"].tolist()
        ax1.plot(years, areas, "o-", color=color, linewidth=2.5,
                 markersize=8, label=city)
        # 标注终点
        ax1.annotate(f"{areas[-1]:.1f}", (years[-1], areas[-1]),
                     textcoords="offset points", xytext=(8, 0),
                     fontsize=10, color=color, fontweight="bold")

    ax1.set_xlabel("年份", fontsize=13)
    ax1.set_ylabel("建成区面积 (km²)", fontsize=13)
    ax1.set_title("建成区面积年际变化对比", fontsize=14, fontweight="bold")
    ax1.legend(fontsize=11)
    ax1.grid(True, alpha=0.3)

    # ---- 子图2：年均扩张速率对比 ----
    ax2 = axes[1]
    x_positions = []
    all_labels = []
    bar_width = 0.35

    for i, (city, df) in enumerate(cities_stats.items()):
        years = df["年份"].tolist()[1:]  # 从第二个年份开始
        areas = df["建成区面积(km²)"].tolist()
        rates = [(areas[j] - areas[j - 1]) / (years[j - 1] - years[j - 2] if j >= 2 else 5)
                 for j in range(1, len(areas))]
        periods = [f"{df['年份'].tolist()[j - 1]}-{df['年份'].tolist()[j]}"
                   for j in range(1, len(areas))]

        x = np.arange(len(periods)) + i * bar_width
        ax2.bar(x, rates, bar_width, color=COLORS_CITIES[i], label=city,
                edgecolor="white", linewidth=0.8)

        if i == 0:
            all_labels = periods
        x_positions.append(x)

    # 设置 x 轴标签
    ax2.set_xticks(np.arange(len(all_labels)) + bar_width / 2)
    ax2.set_xticklabels(all_labels, rotation=45, ha="right")
    ax2.set_ylabel("年均扩张速率 (km²/年)", fontsize=13)
    ax2.set_title("各阶段年均扩张速率对比", fontsize=14, fontweight="bold")
    ax2.legend(fontsize=11)
    ax2.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    save_path = os.path.join(CHARTS_DIR, "城市对比_综合对比图.png")
    plt.savefig(save_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"  [✓] 城市对比图: {os.path.basename(save_path)}")
    return save_path


# ============================================================
# 城市扩张 GIF 动图
# ============================================================
def save_expansion_gif(images_dict: dict, roi: ee.Geometry,
                        city_name: str) -> str:
    """
    生成城市扩张 GIF 动图。

    将所有年份的真彩色影像合成为循环播放的 GIF，
    直观展示城市从早期到近期的发展过程。

    参数:
        images_dict: {2000: image, 2005: image, ...}
        roi:         研究区域
        city_name:   城市名
    """
    frames = []

    for year in sorted(images_dict.keys()):
        image = images_dict[year]
        try:
            url = image.getThumbURL({
                "region": roi,
                "dimensions": "800x600",
                "bands": VIZ["true_color"]["bands"],
                "min": str(VIZ["true_color"]["min"]),
                "max": str(VIZ["true_color"]["max"]),
                "gamma": str(VIZ["true_color"]["gamma"]),
                "format": "png",
            })
            response = urllib.request.urlopen(url)
            img = Image.open(io.BytesIO(response.read()))

            # 在图片上加年份水印（简单版：没有 PIL 绘图的就用文件名）
            frames.append(img)
        except Exception as e:
            print(f"    动图 {year} 年加载失败: {e}")
            continue

    if frames:
        gif_path = os.path.join(MAPS_DIR, f"{city_name}_2000_2025_扩张动图.gif")
        frames[0].save(
            gif_path,
            save_all=True,
            append_images=frames[1:],
            duration=800,       # 每帧 0.8 秒
            loop=0,             # 无限循环
        )
        print(f"  [✓] 扩张动图: {os.path.basename(gif_path)}")
        return gif_path
    else:
        print("  [!] 动图生成失败（没有有效帧）")
        return ""


# ============================================================
# 精度验证可视化
# ============================================================
def save_accuracy_figure(metrics: dict, city_name: str, year: int = None) -> str:
    """
    精度评估结果可视化（条形图展示各项指标）。
    """
    if "错误" in metrics:
        return ""

    # 提取可可视化的指标
    labels = ["总体精度(OA)", "Kappa系数", "制图精度(召回率)",
              "用户精度(精确率)", "F1分数"]
    values = [metrics.get(l, 0) for l in labels]

    fig, ax = plt.subplots(figsize=(8, 5))
    colors_bar = [COLOR_GREEN, COLOR_SECONDARY, COLOR_PRIMARY,
                  COLOR_ORANGE, COLOR_PURPLE]

    bars = ax.barh(labels, values, color=colors_bar, edgecolor="white", linewidth=1.2)

    for bar, val in zip(bars, values):
        ax.text(bar.get_width() + 0.01, bar.get_y() + bar.get_height() / 2,
                f"{val:.3f}", va="center", fontsize=11, fontweight="bold")

    ax.set_xlim(0, 1.0)
    ax.set_xlabel("分值", fontsize=13)

    title = f"{city_name} 精度评估"
    if year:
        title += f"（{year}年）"
    ax.set_title(title, fontsize=14, fontweight="bold")

    plt.tight_layout()

    filename = f"{city_name}"
    if year:
        filename += f"_{year}"
    filename += "_精度评估.png"

    save_path = os.path.join(CHARTS_DIR, filename)
    plt.savefig(save_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"  [✓] 精度图表: {os.path.basename(save_path)}")
    return save_path
