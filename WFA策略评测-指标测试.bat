@echo off
chcp 65001 >nul
echo.
echo ================================================
echo   前向分析 (WFA) 策略评测器
echo   Strategy_Simple_Indicator_Test 专用
echo ================================================
echo.
echo 🎯 即将开始前向分析评测...
echo 📊 这将需要较长时间（预计1-3小时）
echo 💡 建议在开始前确保：
echo    1. Freqtrade环境正常工作
echo    2. 数据已下载完整
echo    3. 配置文件路径正确
echo.

pause

echo.
echo ⏳ 正在启动WFA评测器...
echo.

python WFA_Strategy_Evaluator.py

echo.
echo 📊 WFA评测完成！
echo 📝 请查看生成的报告文件：
echo    - wfa_evaluation_*.log (详细日志)
echo    - wfa_results_*.json (完整结果)
echo    - wfa_windows_summary_*.csv (窗口摘要)
echo    - wfa_oos_trades_*.csv (交易记录)
echo.

pause
