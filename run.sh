#!/bin/bash

echo "启动 Git统计分析仪表板..."
echo

# 检查Python是否安装
if ! command -v python3 &> /dev/null; then
    if ! command -v python &> /dev/null; then
        echo "错误: 未找到Python，请先安装Python 3.8+"
        exit 1
    else
        PYTHON_CMD=python
    fi
else
    PYTHON_CMD=python3
fi

echo "使用Python: $($PYTHON_CMD --version)"

# 检查pip是否可用
if ! command -v pip &> /dev/null && ! command -v pip3 &> /dev/null; then
    echo "错误: 未找到pip，请先安装pip"
    exit 1
fi

PIP_CMD=$(command -v pip3 || command -v pip)

# 检查是否安装了依赖
echo "检查依赖..."
if ! $PIP_CMD show streamlit &> /dev/null; then
    echo "正在安装依赖..."
    $PIP_CMD install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "错误: 依赖安装失败"
        exit 1
    fi
fi

echo
echo "启动Streamlit应用..."
echo "应用将在浏览器中自动打开: http://localhost:8501"
echo
echo "按 Ctrl+C 停止应用"
echo

$PYTHON_CMD -m streamlit run app.py
