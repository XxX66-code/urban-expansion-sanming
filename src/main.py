"""
========================================================================
城市扩张遥感分析 — 主流程（多城市对比版）
========================================================================

一键运行：
    python src/main.py

功能：
    1. 对每个城市：获取 Landsat 影像 → NDBI+NDVI+MNDWI → 建成区提取 → 面积统计
    2. 精度验证（混淆矩阵 + Kappa 系数）
    3. 方向分析（8 方向扇形统计）
    4. 生成全部输出：地图 + 图表 + 动图 + CSV
    5. 多城市对比汇总

首次使用：
    pip install -r requirements.txt
    earthengine authenticate         # 仅一次

========================================================================
"""

import os
import sys
import pandas as pd

# 将项目根目录加入搜索路径（支持从任意目录运行）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import (
    CITIES, ANALYSIS_CONFIG, OUTPUT_DIR, MAPS_DIR, CHARTS_DIR, STATS_DIR
)
from src.gee_utils import init_gee, get_roi, get_landsat_image
from src.urban_extraction import (
    process_all_years, calc_direction_stats,
    extract_built_up, calc_built_up_area,
)
from src.indices import calc_all_indices
from src.accuracy import evaluate_accuracy, print_accuracy_report
from src.stats import (
    compute_statistics, save_stats_csv,
    create_comparison_table, save_comparison_csv,
    save_accuracy_csv,
)
from src.visualization import (
    save_interactive_map, save_static_map, save_comparison_map,
    save_area_chart, save_rate_chart, save_direction_radar,
    save_multi_city_comparison, save_ndvi_trend,
    save_expansion_gif, save_accuracy_figure,
)


# ============================================================
# 单城市分析
# ============================================================
def analyze_city(city_name: str, city_config: dict,
                  years: list, skip_accuracy: bool = False) -> dict:
    """
    对单个城市执行完整的城市扩张分析。

    参数:
        city_name:    城市名（如 "三明市"）
        city_config:  城市配置字典 {"lon": ..., "lat": ..., "buffer": ...}
        years:        年份列表
        skip_accuracy: 跳过精度验证（GEE 计算量大时使用）

    返回:
        { "stats_df": DataFrame, "images": dict, "builtup": dict,
          "accuracy": dict, "direction": dict }
    """
    print(f"\n{'=' * 60}")
    print(f"  📍 {city_name} — {city_config['description']}")
    print(f"{'=' * 60}")

    # 1. 创建研究区
    roi = get_roi(city_config["lon"], city_config["lat"], city_config["buffer"])
    print(f"  [→] 研究区: 中心({city_config['lon']}, {city_config['lat']}), "
          f"半径 {city_config['buffer']}m")

    # 2. 逐年份批处理
    print(f"\n  [→] 开始逐年分析 ({len(years)} 个年份)...")
    stats_list, images_dict, builtup_dict = process_all_years(
        years, roi, get_landsat_image, use_refined=False
    )

    # 3. 统计分析
    stats_df = compute_statistics(stats_list)
    print(f"\n  [→] 统计结果:")
    print(stats_df.to_string(index=False))
    save_stats_csv(stats_df, city_name)

    # 4. 精度验证（对最新年份）
    accuracy = None
    if not skip_accuracy and builtup_dict:
        latest_year = max(years)
        print(f"\n  [→] 精度验证（{latest_year}年）...")
        try:
            # 需要完整的指数影像
            latest_image = images_dict[latest_year]
            accuracy = evaluate_accuracy(latest_image, roi)
            if accuracy:
                print_accuracy_report(accuracy)
                save_accuracy_csv(accuracy, city_name, latest_year)
                save_accuracy_figure(accuracy, city_name, latest_year)
        except Exception as e:
            print(f"  [!] 精度验证失败: {e}")

    # 5. 方向分析（对最新年份）
    direction = None
    if builtup_dict:
        latest_year = max(years)
        print(f"\n  [→] 方向分析（{latest_year}年）...")
        try:
            direction = calc_direction_stats(
                builtup_dict[latest_year], roi,
                city_config["lon"], city_config["lat"],
                city_config["buffer"]
            )
            save_direction_radar(direction, city_name, latest_year)
            print(f"      方向分布: {direction}")
        except Exception as e:
            print(f"  [!] 方向分析失败: {e}")

    # 6. 可视化
    print(f"\n  [→] 生成可视化...")

    # 地图
    for year in years:
        if year in images_dict and year in builtup_dict:
            save_interactive_map(
                images_dict[year], roi, year, city_name, builtup_dict[year]
            )
            save_static_map(images_dict[year], roi, year, city_name, builtup_dict[year])

    # 对比地图（最早 vs 最新）
    first_year, last_year = min(years), max(years)
    if first_year in images_dict and last_year in images_dict:
        save_comparison_map(
            images_dict[first_year], images_dict[last_year],
            roi, city_name, first_year, last_year,
        )

    # 图表
    save_area_chart(stats_df, city_name)
    save_rate_chart(stats_df, city_name)
    save_ndvi_trend(stats_df, city_name)

    # 动图
    save_expansion_gif(images_dict, roi, city_name)

    return {
        "stats_df": stats_df,
        "images": images_dict,
        "builtup": builtup_dict,
        "accuracy": accuracy,
        "direction": direction,
    }


# ============================================================
# 主入口
# ============================================================
def main():
    """主分析函数 — 分析所有配置的城市并生成对比报告"""
    print("\n" + "=" * 60)
    print("  🏙️  城市扩张遥感分析系统 v2.0")
    print("  基于 GEE + Landsat + NDBI/NDVI/MNDWI")
    print("=" * 60)

    # ---- 初始化 GEE ----
    if not init_gee():
        print("\n[→] GEE 未就绪，尝试切换到离线演示模式...")
        run_demo_mode()
        return

    # ---- 逐城市分析 ----
    years = ANALYSIS_CONFIG["years"]
    all_city_results = {}
    all_city_stats = {}
    first_error = None

    for city_name, city_config in CITIES.items():
        try:
            result = analyze_city(city_name, city_config, years)
            all_city_results[city_name] = result
            all_city_stats[city_name] = result["stats_df"]
        except Exception as e:
            print(f"\n  [!] {city_name} 分析失败: {e}")
            first_error = e
            continue

    if not all_city_stats:
        print("\n[!] 所有城市分析都失败了。")
        if first_error:
            raise first_error
        return

    # ---- 多城市对比（仅当有 ≥2 个城市） ----
    if len(all_city_stats) >= 2:
        print(f"\n{'=' * 60}")
        print("  📊 多城市对比分析")
        print(f"{'=' * 60}")

        # 对比图表
        save_multi_city_comparison(all_city_stats)

        # 对比汇总表
        comparison_df = create_comparison_table(all_city_stats)
        save_comparison_csv(comparison_df)
        print("\n  [→] 城市对比汇总:")
        print(comparison_df.to_string(index=False))

    # ---- 完成 ----
    print(f"\n{'=' * 60}")
    print("  ✅ 全部分析完成！")
    print(f"{'=' * 60}")
    print(f"\n  输出目录: {OUTPUT_DIR}")
    print(f"  ├── maps/      → 地图 + 动图 ({len(os.listdir(MAPS_DIR))} 个文件)")
    print(f"  ├── charts/    → 统计图表 ({len(os.listdir(CHARTS_DIR))} 个文件)")
    print(f"  └── stats/     → CSV 数据表 ({len(os.listdir(STATS_DIR))} 个文件)")
    print(f"\n  分析城市: {', '.join(all_city_stats.keys())}")
    print(f"  年份跨度: {min(years)}–{max(years)}")

    for city, result in all_city_results.items():
        areas = result["stats_df"]["建成区面积(km²)"].tolist()
        growth = areas[-1] - areas[0]
        print(f"  {city}: {areas[0]} → {areas[-1]} km² (+{growth:.1f} km²)")

    print()


# ============================================================
# 演示模式（GEE 未认证时）
# ============================================================
def run_demo_mode():
    """
    GEE 未认证时的演示模式。

    打印完整的分析流程说明和代码示例，让用户了解工具的功能。
    """
    print("""
    ╔══════════════════════════════════════════════════╗
    ║          🔧 GEE 未认证 — 离线演示模式            ║
    ╠══════════════════════════════════════════════════╣
    ║                                                  ║
    ║  要运行完整分析，需要 GEE 账号（免费）：           ║
    ║  1. 访问 https://earthengine.google.com/signup/   ║
    ║  2. 用 Google 账号注册（选 Unpaid Usage）         ║
    ║  3. 等待审批邮件（通常 1-3 个工作日）              ║
    ║  4. 审批后终端运行：earthengine authenticate      ║
    ║  5. 重新运行：python src/main.py                  ║
    ║                                                  ║
    ╠══════════════════════════════════════════════════╣
    ║  项目已升级（v2.0），新增功能：                    ║
    ║  ✅ 多城市对比（三明 + 福州）                     ║
    ║  ✅ NDVI + MNDWI 双指数辅助验证                  ║
    ║  ✅ 混淆矩阵 + Kappa 系数精度评估                 ║
    ║  ✅ 八方向扇形分析（真实计算，非模拟数据）         ║
    ║  ✅ 模块化架构（8 个源码文件）                    ║
    ║  ✅ 多城市对比图表                                ║
    ╚══════════════════════════════════════════════════╝
    """)

    print("\n  📁 项目结构:")
    print("""    src/
    ├── config.py           配置（城市/年份/阈值）
    ├── gee_utils.py        GEE 初始化 + 影像获取
    ├── indices.py          NDBI / NDVI / MNDWI 计算
    ├── urban_extraction.py 建成区提取 + 面积 + 方向
    ├── accuracy.py         精度验证（混淆矩阵 + Kappa）
    ├── stats.py            统计 + CSV 导出
    ├── visualization.py    全部可视化（地图/图表/动图）
    └── main.py             主流程 ← 你在这里
    """)

    print("  📖 学习建议:")
    print("     1. 先看 config.py — 了解有哪些参数可以调")
    print("     2. 再看 indices.py — 理解 NDBI/NDVI/MNDWI 公式")
    print("     3. 然后看 urban_extraction.py — 建成区是怎么提取的")
    print("     4. 最后看 main.py — 整个分析流程是怎么串联的")
    print()


# ============================================================
# 命令行快捷入口
# ============================================================
if __name__ == "__main__":
    main()
