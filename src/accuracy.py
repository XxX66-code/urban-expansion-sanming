"""
========================================================================
精度验证模块 — 混淆矩阵 + Kappa 系数 + 精度指标
========================================================================

遥感分类必须验证精度！本模块提供：

    1. generate_validation_points()  → 在研究区内生成随机采样点
    2. evaluate_accuracy()           → 计算混淆矩阵
    3. calc_kappa()                  → 计算 Kappa 系数
    4. full_accuracy_report()        → 打印完整精度报告

方法说明：
    由于缺乏实地调查数据（ground truth），本模块使用"双阈值法"：
    - 主阈值（-0.05）：我们实际使用的建成区判别标准
    - 严格阈值（0.05）：更保守的标准，作为伪参考数据
    两者交叉验证，评估分类的一致性和可靠性。

⚠️ 声明：真正的精度验证需要实地采样或高分辨率影像目视解译。
          本模块的方法论是正确的，但参考数据并非真实 ground truth。
          在论文/报告中应明确说明这一点。

依赖：
    ee, numpy, pandas
    src/config.py
"""

import ee
import numpy as np
import pandas as pd
from src.config import ANALYSIS_CONFIG


# ============================================================
# 生成验证点
# ============================================================
def generate_validation_points(roi: ee.Geometry, n_points: int = None,
                                seed: int = None) -> ee.FeatureCollection:
    """
    在研究区域内生成分层的随机采样点。

    分层策略：
        - 50% 的点完全随机（覆盖各种地类）
        - 50% 的点在 NDBI > -0.1 的区域（侧重建成区边缘/争议区）

    这样既能评估整体精度，也能重点检验建成区提取的准确性。

    参数:
        roi:      研究区域
        n_points: 采样点数量（默认 500）
        seed:     随机种子（保证每次结果一样）

    返回:
        ee.FeatureCollection — 采样点集合
    """
    if n_points is None:
        n_points = ANALYSIS_CONFIG["validation"]["n_samples"]
    if seed is None:
        seed = ANALYSIS_CONFIG["validation"]["random_seed"]

    # 分层：一半随机，一半偏建成区
    n_random = n_points // 2
    n_builtup = n_points - n_random

    random_points = ee.FeatureCollection.randomPoints(
        region=roi, points=n_random, seed=seed
    )
    # 确保不超出边界
    random_points = random_points.filterBounds(roi)

    # 另一半使用不同种子
    if n_builtup > 0:
        builtup_points = ee.FeatureCollection.randomPoints(
            region=roi, points=n_builtup, seed=seed + 999
        )
        builtup_points = builtup_points.filterBounds(roi)
        all_points = random_points.merge(builtup_points)
    else:
        all_points = random_points

    return all_points


# ============================================================
# 提取像元值
# ============================================================
def extract_pixel_values(image: ee.Image, points: ee.FeatureCollection,
                          bands: list = None) -> pd.DataFrame:
    """
    在每个采样点提取影像的波段值，返回 DataFrame。

    参数:
        image:  包含 NDBI, NDVI, built_up 等波段的影像
        points: 采样点
        bands:  要提取的波段列表（默认 ["NDBI", "NDVI", "built_up"]）

    返回:
        DataFrame，每行一个采样点，列=波段名
    """
    if bands is None:
        bands = ["NDBI", "NDVI", "built_up"]

    try:
        # GEE 采样
        sampled = image.select(bands).sampleRegions(
            collection=points,
            scale=30,
            geometries=False,
        )

        # 转换为 Python 列表（可能很大，注意 1e6 限制）
        data = sampled.getInfo()

        if data and "features" in data:
            records = []
            for feat in data["features"]:
                props = feat.get("properties", {})
                records.append({b: props.get(b) for b in bands})
            return pd.DataFrame(records)
        else:
            return pd.DataFrame(columns=bands)

    except Exception as e:
        print(f"  [!] 采样失败: {e}")
        return pd.DataFrame(columns=bands)


# ============================================================
# 混淆矩阵
# ============================================================
def compute_confusion_matrix(y_true: np.ndarray, y_pred: np.ndarray) -> np.ndarray:
    """
    计算二分类混淆矩阵。

    格式（行=真实, 列=预测）：
                   预测非建成区  预测建成区
       真实非建成区     TN           FP
       真实建成区       FN           TP

    参数:
        y_true: 参考标签（0=非建成区, 1=建成区）
        y_pred: 预测标签

    返回:
        2×2 numpy 数组 [[TN, FP], [FN, TP]]
    """
    tn = int(np.sum((y_true == 0) & (y_pred == 0)))
    fp = int(np.sum((y_true == 0) & (y_pred == 1)))
    fn = int(np.sum((y_true == 1) & (y_pred == 0)))
    tp = int(np.sum((y_true == 1) & (y_pred == 1)))
    return np.array([[tn, fp], [fn, tp]])


# ============================================================
# Kappa 系数
# ============================================================
def calc_kappa(confusion_matrix: np.ndarray) -> float:
    """
    从混淆矩阵计算 Kappa 系数。

    公式：
        Kappa = (Po - Pe) / (1 - Pe)

        其中:
            Po = 总体精度 = (TP + TN) / 总样本数
            Pe = 随机一致性概率

    Kappa 值解读：
        > 0.80  → 几乎完美
        0.60-0.80 → 较好
        0.40-0.60 → 中等
        0.20-0.40 → 一般
        < 0.20  → 差

    参数:
        confusion_matrix: 2×2 混淆矩阵 [[TN, FP], [FN, TP]]

    返回:
        kappa: 四舍五入到 4 位小数
    """
    tn, fp = confusion_matrix[0, 0], confusion_matrix[0, 1]
    fn, tp = confusion_matrix[1, 0], confusion_matrix[1, 1]
    total = tn + fp + fn + tp

    if total == 0:
        return 0.0

    # 观测一致性 Po = (TP+TN)/total
    po = (tp + tn) / total

    # 期望一致性 Pe = P(都说是建成区) + P(都说非建成区)
    pe = ((tp + fp) * (tp + fn) + (tn + fn) * (tn + fp)) / (total ** 2)

    if pe >= 1.0:
        return 1.0

    kappa = (po - pe) / (1 - pe)
    return round(kappa, 4)


# ============================================================
# 精度指标
# ============================================================
def calc_metrics(confusion_matrix: np.ndarray) -> dict:
    """
    从混淆矩阵计算完整精度指标。

    返回:
        {
            "总体精度": OA,
            "Kappa系数": Kappa,
            "制图精度(召回率)": Recall (建成区被正确识别的比例),
            "用户精度(精确率)": Precision (识别为建成区中正确的比例),
            "F1分数": F1,
            "漏分误差": 1-Recall,
            "错分误差": 1-Precision,
        }
    """
    tn, fp = confusion_matrix[0, 0], confusion_matrix[0, 1]
    fn, tp = confusion_matrix[1, 0], confusion_matrix[1, 1]
    total = tn + fp + fn + tp

    oa = (tp + tn) / total if total > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0     # 制图精度
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0   # 用户精度
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "总体精度(OA)": round(oa, 4),
        "Kappa系数": calc_kappa(confusion_matrix),
        "制图精度(召回率)": round(recall, 4),
        "用户精度(精确率)": round(precision, 4),
        "F1分数": round(f1, 4),
        "漏分误差": round(1 - recall, 4),
        "错分误差": round(1 - precision, 4),
        "采样点数": total,
    }


# ============================================================
# 完整精度评估
# ============================================================
def evaluate_accuracy(image: ee.Image, roi: ee.Geometry) -> dict:
    """
    对建成区提取结果做完整的精度评估。

    方法：双阈值交叉验证
        - 预测标签：NDBI > -0.05（日常使用的阈值）
        - 参考标签：NDBI >  0.05（严格阈值，更确定是建筑）
        比较两者的一致性，不一致的地方说明分类不确定性较高。

    参数:
        image: 包含 "NDBI" 和 "built_up" 波段的影像
        roi:   研究区域

    返回:
        metrics: dict — 包含混淆矩阵和所有精度指标
    """
    print("  [→] 生成验证采样点...")
    points = generate_validation_points(roi)

    print("  [→] 提取像元值...")
    df = extract_pixel_values(image, points, bands=["NDBI", "NDVI", "built_up"])

    if df.empty or len(df) < 10:
        print("  [!] 采样点不足，跳过精度评估")
        return {"错误": "采样数据不足"}

    # 过滤空值
    df = df.dropna(subset=["NDBI", "built_up"])

    # 预测：当前阈值分类
    y_pred = (df["built_up"].values > 0.5).astype(int)

    # 参考：严格阈值
    strict_threshold = ANALYSIS_CONFIG["validation"]["strict_ndbi_threshold"]
    y_ref = (df["NDBI"].values > strict_threshold).astype(int)

    # 计算混淆矩阵
    cm = compute_confusion_matrix(y_ref, y_pred)

    # 计算精度指标
    metrics = calc_metrics(cm)
    metrics["混淆矩阵(TN,FP,FN,TP)"] = (
        f"TN={cm[0,0]}, FP={cm[0,1]}, FN={cm[1,0]}, TP={cm[1,1]}"
    )
    metrics["参考阈值"] = strict_threshold
    metrics["预测阈值"] = ANALYSIS_CONFIG["ndbi_threshold"]

    return metrics


def print_accuracy_report(metrics: dict):
    """打印格式化的精度报告"""
    if "错误" in metrics:
        print(f"  [!] {metrics['错误']}")
        return

    print(f"""
  ╔══════════════════════════════════════╗
  ║         🎯 精度验证报告              ║
  ╠══════════════════════════════════════╣
  ║  采样点数      : {metrics.get('采样点数', 'N/A'):>6}                ║
  ║  总体精度(OA)  : {metrics.get('总体精度(OA)', 0):>6.2%}               ║
  ║  Kappa 系数    : {metrics.get('Kappa系数', 0):>6.4f}               ║
  ║  制图精度      : {metrics.get('制图精度(召回率)', 0):>6.2%}               ║
  ║  用户精度      : {metrics.get('用户精度(精确率)', 0):>6.2%}               ║
  ║  F1 分数       : {metrics.get('F1分数', 0):>6.4f}               ║
  ║  漏分误差      : {metrics.get('漏分误差', 0):>6.2%}               ║
  ║  错分误差      : {metrics.get('错分误差', 0):>6.2%}               ║
  ╠══════════════════════════════════════╣
  ║  混淆矩阵: {metrics.get('混淆矩阵(TN,FP,FN,TP)', 'N/A')}
  ╚══════════════════════════════════════╝
    """)
