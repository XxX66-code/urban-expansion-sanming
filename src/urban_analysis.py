"""
========================================================================
过渡文件 — 保留以兼容旧引用

原 urban_analysis.py 的功能已拆分为多个模块：
    config.py, gee_utils.py, indices.py,
    urban_extraction.py, accuracy.py, stats.py,
    visualization.py, main.py

新入口：python src/main.py
========================================================================
"""

import sys
import os

print("""
╔══════════════════════════════════════════════╗
║  urban_analysis.py 已升级为模块化架构！     ║
║                                              ║
║  旧：python src/urban_analysis.py            ║
║  新：python src/main.py                      ║
║                                              ║
║  功能不变，但新增了：                        ║
║  ✅ 多城市对比（三明 + 福州）               ║
║  ✅ NDVI + MNDWI 双指数辅助                 ║
║  ✅ 精度验证（Kappa 系数）                  ║
║  ✅ 真实方向分析                            ║
║  ✅ 模块化代码结构                          ║
╚══════════════════════════════════════════════╝
""")

# 如果用户坚持用旧入口，自动转发到新入口
response = input("\n是否自动运行新的 main.py？[Y/n]: ").strip().lower()
if response in ("", "y", "yes"):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.main import main
    main()
else:
    print("请手动运行: python src/main.py")
