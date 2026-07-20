"""
========================================================================
统计分析模块 — 增长率计算 + CSV 导出 + 多城市对比汇总
========================================================================

依赖：pandas, src/config.py
"""

import os
import pandas as pd
import numpy as np
from src.config import STATS_DIR


# ============================================================
# 计算统计指标
# ============================================================
def compute_statistics(stats_list: list) -> pd.DataFrame:
    """
    从逐年面积列表计算统计指标。

    添加的列：
        - 增长率(%)      相邻节点之间的百分比增长
        - 年均扩张(km²/年)  每 5 年间隔内的年均增量
        - 累计增长(km²)   相对于基准年的累计增长
        - 扩张强度(%)     年均增长率（相对于初始面积）

    参数:
        stats_list: [{"年份": 2000, "建成区面积(km²)": 12.3}, ...]

    返回:
        pandas DataFrame
    """
    df = pd.DataFrame(stats_list)

    # 增长率 = (当前-前一个)/前一个 × 100
    df["增长率(%)"] = df["建成区面积(km²)"].pct_change() * 100
    df["增长率(%)"] = df["增长率(%)"].round(1)

    # 年均扩张 = (当前-前一个) / 间隔年数
    areas = df["建成区面积(km²)"].values
    years = df["年份"].values
    annual_rates = [np.nan]
    for i in range(1, len(areas)):
        rate = (areas[i] - areas[i - 1]) / (years[i] - years[i - 1])
        annual_rates.append(round(rate, 3))
    df["年均扩张(km²/年)"] = annual_rates

    # 累计增长 = 当前 - 第一年
    baseline = areas[0]
    df["累计增长(km²)"] = [round(a - baseline, 2) for a in areas]

    # 扩张强度 = (当前-前一个) / 前一个 / 间隔年数 × 100（%）
    intensities = [np.nan]
    for i in range(1, len(areas)):
        intensity = (areas[i] - areas[i - 1]) / areas[i - 1] * 100 / (years[i] - years[i - 1])
        intensities.append(round(intensity, 2))
    df["扩张强度(%/年)"] = intensities

    return df


# ============================================================
# CSV 导出
# ============================================================
def save_stats_csv(df: pd.DataFrame, city_name: str) -> str:
    """
    保存统计表为 CSV 文件。

    参数:
        df:        统计数据 DataFrame
        city_name: 城市名（用于文件名）

    返回:
        保存路径
    """
    csv_path = os.path.join(STATS_DIR, f"{city_name}_面积统计表.csv")
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"  [✓] 统计表已保存: {csv_path}")
    return csv_path


# ============================================================
# 多城市对比汇总
# ============================================================
def create_comparison_table(cities_stats: dict) -> pd.DataFrame:
    """
    生成多城市对比汇总表。

    参数:
        cities_stats: {"三明市": DataFrame, "福州市": DataFrame}

    返回:
        汇总 DataFrame
    """
    records = []
    for city_name, df in cities_stats.items():
        base_year = df["年份"].min()
        end_year = df["年份"].max()
        base_area = df.loc[df["年份"] == base_year, "建成区面积(km²)"].values[0]
        end_area = df.loc[df["年份"] == end_year, "建成区面积(km²)"].values[0]
        total_growth = end_area - base_area
        total_growth_pct = round(total_growth / base_area * 100, 1) if base_area > 0 else 0
        avg_rate = round(total_growth / (end_year - base_year), 2)

        records.append({
            "城市": city_name,
            "起始年份": base_year,
            "终止年份": end_year,
            "起始面积(km²)": base_area,
            "终止面积(km²)": end_area,
            "总增长(km²)": round(total_growth, 2),
            "总增长率(%)": total_growth_pct,
            "年均扩张(km²/年)": avg_rate,
        })

    return pd.DataFrame(records)


def save_comparison_csv(df: pd.DataFrame) -> str:
    """保存城市对比汇总表"""
    csv_path = os.path.join(STATS_DIR, "城市对比汇总.csv")
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"  [✓] 对比汇总已保存: {csv_path}")
    return csv_path


# ============================================================
# 精度结果导出
# ============================================================
def save_accuracy_csv(metrics_dict: dict, city_name: str, year: int = None) -> str:
    """
    保存精度评估结果。

    参数:
        metrics_dict: accuracy.evaluate_accuracy() 返回的字典
        city_name:    城市名
        year:         年份（可选）

    返回:
        保存路径
    """
    filename = f"{city_name}"
    if year:
        filename += f"_{year}"
    filename += "_精度评估.csv"

    csv_path = os.path.join(STATS_DIR, filename)
    df = pd.DataFrame([metrics_dict])
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"  [✓] 精度报告已保存: {csv_path}")
    return csv_path
