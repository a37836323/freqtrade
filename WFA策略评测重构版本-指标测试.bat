@echo off
chcp 65001
echo.
echo ==========================================
echo  🔍 WFA策略评测器 重构版本
echo ==========================================
echo  ✨ 特性：模块化设计 + 自动参数检测
echo  📊 策略：Strategy_Simple_Indicator_Test  
echo  🎯 方法：前向分析 (Walk-Forward Analysis)
echo ==========================================
echo.

cd /d "%~dp0"

echo 🚀 启动WFA策略评测重构版本...
echo.

python wfa_v2_refactored/main.py

echo.
echo ==========================================
echo  📊 分析完成！
echo  📝 请查看生成的日志和结果文件
echo ==========================================
echo.
pause
