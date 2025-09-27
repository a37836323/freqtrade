@echo off
chcp 65001 >nul
echo.
echo ================================================
echo   前向分析 (WFA) 策略评测器 V2.0
echo   Strategy_Simple_Indicator_Test 专用
echo   🆕 自定义参数生成 + 直接回测评估
echo ================================================
echo.
echo 🎯 V2.0 新特性：
echo    ✅ 自定义参数生成（不依赖freqtrade hyperopt）
echo    ✅ 支持网格搜索和随机搜索
echo    ✅ 直接回测评估，更简单可控
echo    ✅ 详细的参数稳定性分析
echo.
echo 💡 使用建议：
echo    - 首次运行建议使用随机搜索（300个组合）
echo    - 网格搜索适合参数范围较小的情况
echo    - 可通过wfa_config_v2.json调整参数
echo.

pause

echo.
echo ⏳ 正在启动WFA评测器V2.0...
echo.

python WFA_Strategy_Evaluator_V2.py

echo.
echo 📊 WFA评测V2.0完成！
echo.
echo 📝 请查看生成的报告文件：
echo    - wfa_evaluation_v2_*.log (详细日志)
echo    - wfa_results_v2_*.json (完整结果)
echo    - wfa_windows_summary_v2_*.csv (窗口摘要)
echo.
echo 🔍 关键改进：
echo    ✅ 解决了hyperopt无法运行的问题
echo    ✅ 参数生成过程完全透明可控
echo    ✅ 支持多种优化策略
echo    ✅ 详细的参数稳定性分析
echo.

pause
