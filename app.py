"""
Git提交历史统计分析 Streamlit 应用
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import os
from pathlib import Path

# 导入自定义模块
from git_analyzer import GitAnalyzer
from visualizations import GitVisualizer


def init_page_config():
    """初始化页面配置"""
    st.set_page_config(
        page_title="Git统计分析仪表板",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )


def load_custom_css():
    """加载自定义CSS样式"""
    st.markdown("""
    <style>
    .main-header {
        font-size: 3rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
        font-weight: bold;
    }
    
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #1f77b4;
        margin: 0.5rem 0;
    }
    
    .sidebar-section {
        margin: 1rem 0;
        padding: 1rem;
        background-color: #f8f9fa;
        border-radius: 8px;
    }
    
    .info-box {
        background-color: #e7f3ff;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #2196F3;
        margin: 1rem 0;
    }
    
    .warning-box {
        background-color: #fff3cd;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #ffc107;
        margin: 1rem 0;
    }
    </style>
    """, unsafe_allow_html=True)


def sidebar_controls():
    """侧边栏控件"""
    st.sidebar.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
    st.sidebar.markdown("### 🔧 分析配置")
    
    # Git仓库路径选择
    repo_path = st.sidebar.text_input(
        "Git仓库路径",
        value=".",
        help="输入Git仓库的路径，默认为当前目录"
    )
    
    # 日期范围选择
    st.sidebar.markdown("#### 📅 时间范围")
    
    # 预设时间范围
    time_range = st.sidebar.selectbox(
        "选择时间范围",
        ["全部时间", "最近7天", "最近30天", "最近90天", "最近一年", "自定义"]
    )
    
    # 根据选择设置日期
    end_date = datetime.now().date()
    if time_range == "最近7天":
        start_date = end_date - timedelta(days=7)
    elif time_range == "最近30天":
        start_date = end_date - timedelta(days=30)
    elif time_range == "最近90天":
        start_date = end_date - timedelta(days=90)
    elif time_range == "最近一年":
        start_date = end_date - timedelta(days=365)
    elif time_range == "自定义":
        col1, col2 = st.sidebar.columns(2)
        with col1:
            start_date = st.date_input("开始日期", value=end_date - timedelta(days=30))
        with col2:
            end_date = st.date_input("结束日期", value=end_date)
    else:  # 全部时间
        start_date = None
        end_date = None
    
    # 分支选择
    branch = st.sidebar.text_input("分析分支", value="HEAD", help="要分析的Git分支")
    
    # 分析选项
    st.sidebar.markdown("#### ⚙️ 分析选项")
    show_merge_commits = st.sidebar.checkbox("包含合并提交", value=True)
    show_file_stats = st.sidebar.checkbox("显示文件统计", value=True)
    
    st.sidebar.markdown('</div>', unsafe_allow_html=True)
    
    return {
        'repo_path': repo_path,
        'start_date': start_date,
        'end_date': end_date,
        'branch': branch,
        'show_merge_commits': show_merge_commits,
        'show_file_stats': show_file_stats
    }


def display_overview_metrics(analyzer: GitAnalyzer, config: dict):
    """显示概览指标"""
    st.markdown("## 📈 统计概览")
    
    try:
        # 获取基础统计
        commits_df = analyzer.get_commit_stats(
            since_date=datetime.combine(config['start_date'], datetime.min.time()) if config['start_date'] else None,
            until_date=datetime.combine(config['end_date'], datetime.min.time()) if config['end_date'] else None,
            branch=config['branch']
        )
        
        author_stats = analyzer.get_author_stats(
            since_date=datetime.combine(config['start_date'], datetime.min.time()) if config['start_date'] else None,
            until_date=datetime.combine(config['end_date'], datetime.min.time()) if config['end_date'] else None
        )
        
        # 显示关键指标
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                label="📝 总提交数",
                value=len(commits_df) if not commits_df.empty else 0
            )
        
        with col2:
            st.metric(
                label="👥 活跃作者数",
                value=len(author_stats) if not author_stats.empty else 0
            )
        
        with col3:
            total_lines = commits_df['lines_changed'].sum() if not commits_df.empty else 0
            st.metric(
                label="📊 代码行变更",
                value=f"{total_lines:,}"
            )
        
        with col4:
            total_files = commits_df['files_changed'].sum() if not commits_df.empty else 0
            st.metric(
                label="📁 文件变更",
                value=f"{total_files:,}"
            )
        
        return commits_df, author_stats
        
    except Exception as e:
        st.error(f"获取统计数据时出错: {str(e)}")
        return pd.DataFrame(), pd.DataFrame()


def display_commit_analysis(commits_df: pd.DataFrame, visualizer: GitVisualizer):
    """显示提交分析"""
    st.markdown("## 🔍 提交分析")
    
    if commits_df.empty:
        st.warning("暂无提交数据可供分析")
        return
    
    # 提交时间线
    st.markdown("### 提交时间线")
    timeline_fig = visualizer.plot_commit_timeline(commits_df)
    st.plotly_chart(timeline_fig, use_container_width=True)
    
    # 最近提交列表
    st.markdown("### 最近提交")
    recent_commits = commits_df.head(10)[['hash', 'author', 'date', 'message', 'files_changed', 'lines_changed']]
    recent_commits['date'] = recent_commits['date'].dt.strftime('%Y-%m-%d %H:%M')
    st.dataframe(recent_commits, use_container_width=True)


def display_author_analysis(author_stats: pd.DataFrame, visualizer: GitVisualizer):
    """显示作者分析"""
    st.markdown("## 👥 作者分析")
    
    if author_stats.empty:
        st.warning("暂无作者数据可供分析")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        # 作者贡献饼图
        st.markdown("### 提交贡献分布")
        contrib_fig = visualizer.plot_author_contributions(author_stats)
        st.plotly_chart(contrib_fig, use_container_width=True)
    
    with col2:
        # 作者统计表
        st.markdown("### 作者详细统计")
        display_stats = author_stats[[
            'author', 'commits_count', 'total_lines_changed', 
            'avg_lines_per_commit', 'active_days'
        ]].round(2)
        st.dataframe(display_stats, use_container_width=True)


def display_time_analysis(analyzer: GitAnalyzer, config: dict, visualizer: GitVisualizer):
    """显示时间分析"""
    st.markdown("## ⏰ 时间分析")
    
    try:
        # 获取时间序列数据
        time_series = analyzer.get_time_series_stats(
            period='D',
            since_date=datetime.combine(config['start_date'], datetime.min.time()) if config['start_date'] else None,
            until_date=datetime.combine(config['end_date'], datetime.min.time()) if config['end_date'] else None
        )
        
        if time_series.empty:
            st.warning("暂无时间序列数据可供分析")
            return
        
        # 代码变更趋势
        st.markdown("### 代码变更趋势")
        trend_fig = visualizer.plot_lines_trend(time_series)
        st.plotly_chart(trend_fig, use_container_width=True)
        
    except Exception as e:
        st.error(f"时间分析出错: {str(e)}")


def display_merge_analysis(analyzer: GitAnalyzer, config: dict, visualizer: GitVisualizer):
    """显示合并分析"""
    if not config['show_merge_commits']:
        return
    
    st.markdown("## 🔀 合并分析")
    
    try:
        merge_stats = analyzer.get_merge_stats(
            since_date=datetime.combine(config['start_date'], datetime.min.time()) if config['start_date'] else None,
            until_date=datetime.combine(config['end_date'], datetime.min.time()) if config['end_date'] else None
        )
        
        if merge_stats.empty:
            st.info("在指定时间范围内未发现合并提交")
            return
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("🔀 合并次数", len(merge_stats))
            
        with col2:
            unique_authors = merge_stats['author'].nunique()
            st.metric("👥 参与合并的作者", unique_authors)
        
        # 合并频率图
        merge_freq_fig = visualizer.plot_merge_frequency(merge_stats)
        st.plotly_chart(merge_freq_fig, use_container_width=True)
        
        # 最近合并列表
        st.markdown("### 最近合并")
        recent_merges = merge_stats.head(10)[['hash', 'author', 'date', 'source_branch', 'target_branch']]
        recent_merges['date'] = recent_merges['date'].dt.strftime('%Y-%m-%d %H:%M')
        st.dataframe(recent_merges, use_container_width=True)
        
    except Exception as e:
        st.error(f"合并分析出错: {str(e)}")


def display_file_analysis(analyzer: GitAnalyzer, config: dict, visualizer: GitVisualizer):
    """显示文件分析"""
    if not config['show_file_stats']:
        return
    
    st.markdown("## 📁 文件分析")
    
    try:
        file_stats = analyzer.get_file_stats(
            since_date=datetime.combine(config['start_date'], datetime.min.time()) if config['start_date'] else None,
            until_date=datetime.combine(config['end_date'], datetime.min.time()) if config['end_date'] else None
        )
        
        if file_stats.empty:
            st.warning("暂无文件统计数据")
            return
        
        # 文件类型分布
        st.markdown("### 文件类型修改分布")
        file_dist_fig = visualizer.plot_file_changes_distribution(file_stats)
        st.plotly_chart(file_dist_fig, use_container_width=True)
        
        # 最常修改的文件
        st.markdown("### 最常修改的文件")
        top_files = file_stats.nlargest(20, 'modifications')[
            ['file_path', 'modifications', 'total_changes', 'authors_count']
        ]
        st.dataframe(top_files, use_container_width=True)
        
    except Exception as e:
        st.error(f"文件分析出错: {str(e)}")


def display_branch_analysis(analyzer: GitAnalyzer, visualizer: GitVisualizer):
    """显示分支分析"""
    st.markdown("## 🌳 分支分析")
    
    try:
        branch_stats = analyzer.get_branch_stats()
        
        if branch_stats.empty:
            st.warning("暂无分支数据")
            return
        
        # 分支活跃度
        branch_activity_fig = visualizer.plot_branch_activity(branch_stats)
        st.plotly_chart(branch_activity_fig, use_container_width=True)
        
        # 分支详情
        st.markdown("### 分支详情")
        display_branches = branch_stats[[
            'branch_name', 'commits_count', 'last_commit_date', 'last_author', 'is_active'
        ]]
        display_branches['last_commit_date'] = display_branches['last_commit_date'].dt.strftime('%Y-%m-%d %H:%M')
        st.dataframe(display_branches, use_container_width=True)
        
    except Exception as e:
        st.error(f"分支分析出错: {str(e)}")


def main():
    """主函数"""
    # 初始化页面
    init_page_config()
    load_custom_css()
    
    # 页面标题
    st.markdown('<h1 class="main-header">📊 Git统计分析仪表板</h1>', unsafe_allow_html=True)
    
    # 侧边栏控件
    config = sidebar_controls()
    
    # 初始化分析器
    try:
        analyzer = GitAnalyzer(config['repo_path'])
        visualizer = GitVisualizer()
        
        # 显示仓库信息
        st.markdown(f"""
        <div class="info-box">
        <strong>📁 分析仓库:</strong> {os.path.abspath(config['repo_path'])}<br>
        <strong>🌿 分析分支:</strong> {config['branch']}<br>
        <strong>📅 时间范围:</strong> {config['start_date'] or '开始'} 至 {config['end_date'] or '结束'}
        </div>
        """, unsafe_allow_html=True)
        
        # 显示各种分析
        commits_df, author_stats = display_overview_metrics(analyzer, config)
        
        # 创建选项卡
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "📝 提交分析", "👥 作者分析", "⏰ 时间分析", 
            "🔀 合并分析", "📁 文件分析", "🌳 分支分析"
        ])
        
        with tab1:
            display_commit_analysis(commits_df, visualizer)
        
        with tab2:
            display_author_analysis(author_stats, visualizer)
        
        with tab3:
            display_time_analysis(analyzer, config, visualizer)
        
        with tab4:
            display_merge_analysis(analyzer, config, visualizer)
        
        with tab5:
            display_file_analysis(analyzer, config, visualizer)
        
        with tab6:
            display_branch_analysis(analyzer, visualizer)
            
    except ValueError as e:
        st.error(f"❌ {str(e)}")
        st.markdown("""
        <div class="warning-box">
        <strong>💡 提示:</strong><br>
        1. 请确保指定的路径是有效的Git仓库<br>
        2. 检查路径是否正确<br>
        3. 确保有访问仓库的权限
        </div>
        """, unsafe_allow_html=True)
        
    except Exception as e:
        st.error(f"❌ 应用运行出错: {str(e)}")
        st.markdown("""
        <div class="warning-box">
        <strong>🔧 故障排除:</strong><br>
        1. 检查Git仓库是否可访问<br>
        2. 确保所有依赖已正确安装<br>
        3. 查看控制台获取详细错误信息
        </div>
        """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
