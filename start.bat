@echo off
echo ============================================
echo     AI Test Assistant - 启动脚本
echo ============================================
echo.

cd /d "%~dp0"

echo 正在检查 Python 环境...
python --version
if %errorlevel% neq 0 (
    echo 错误: 未找到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

echo.
echo 正在检查依赖...
python -c "import streamlit" >nul 2>&1
if %errorlevel% neq 0 (
    echo 正在安装依赖...
    pip install -r requirements.txt
)

echo.
echo 正在启动 AI Test Assistant...
echo 应用将在浏览器中自动打开
echo 本地访问地址: http://localhost:8501
echo.

python -m streamlit run main.py

pause