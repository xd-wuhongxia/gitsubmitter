"""
Git提交历史统计分析 Streamlit 应用
"""

import json
import logging
import os
import re
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Dict, List, Optional

import git
import numpy as np
import pandas as pd
import streamlit as st

# 导入自定义模块
from git_analyzer import GitAnalyzer
from visualizations import GitVisualizer
from mr_database import MRDatabase
from github_integration import GitHubIntegration
from repo_history import RepoHistoryManager


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


def is_remote_repo_url(repo_path: str) -> bool:
    """
    判断是否是远程仓库URL
    
    Args:
        repo_path: 仓库路径或URL
        
    Returns:
        是否是远程URL
    """
    repo_path = repo_path.strip().lower()
    remote_patterns = [
        'http://', 'https://', 'git://', 'ssh://',
        'git@', '.git', 'github.com', 'gitlab.com', 'bitbucket.org'
    ]
    
    # 检查是否包含远程仓库的特征
    for pattern in remote_patterns:
        if pattern in repo_path:
            return True
    
    # 检查是否是简化的GitHub格式 (如: user/repo 或 m/user/repo)
    parts = repo_path.split('/')
    if len(parts) >= 2 and not repo_path.startswith('/') and '.' not in parts[0]:
        return True
    
    return False


def normalize_remote_url(repo_input: str) -> str:
    """
    标准化远程仓库URL
    
    Args:
        repo_input: 用户输入的仓库地址
        
    Returns:
        标准化的GitHub URL
    """
    repo_input = repo_input.strip()
    
    # 如果已经是完整的URL，直接返回
    if repo_input.startswith(('http://', 'https://', 'git://', 'ssh://')):
        return repo_input
    
    # 处理git@格式
    if repo_input.startswith('git@'):
        return repo_input
    
    # 处理简化格式
    if '/' in repo_input:
        parts = repo_input.split('/')
        
        # 处理 m/user/repo 格式
        if len(parts) == 3 and parts[0] == 'm':
            user, repo = parts[1], parts[2]
            repo = repo.replace('.git', '')  # 移除可能存在的.git后缀
            return f"https://github.com/{user}/{repo}.git"
        
        # 处理 user/repo 格式
        elif len(parts) == 2:
            user, repo = parts[0], parts[1]
            repo = repo.replace('.git', '')  # 移除可能存在的.git后缀
            return f"https://github.com/{user}/{repo}.git"
    
    return repo_input


def validate_git_repo(repo_path: str) -> tuple[bool, str]:
    """
    验证Git仓库路径（支持本地和远程）
    
    Args:
        repo_path: 仓库路径或URL
        
    Returns:
        (是否有效, 错误消息)
    """
    try:
        if not repo_path or repo_path.strip() == "":
            return False, "请输入仓库路径"
        
        repo_path = repo_path.strip()
        
        # 检查是否是远程仓库URL
        if is_remote_repo_url(repo_path):
            return True, f"🌐 远程Git仓库: {normalize_remote_url(repo_path)}"
        
        # 本地仓库验证逻辑
        # 检查路径是否存在
        if not os.path.exists(repo_path):
            return False, f"本地路径不存在: {repo_path}"
        
        # 检查是否是目录
        if not os.path.isdir(repo_path):
            return False, f"路径不是目录: {repo_path}"
        
        # 检查是否是Git仓库
        try:
            test_repo = git.Repo(repo_path)
            return True, "✅ 本地Git仓库"
        except git.exc.InvalidGitRepositoryError:
            return False, f"不是有效的Git仓库: {repo_path}"
        except Exception as e:
            return False, f"访问仓库时出错: {str(e)}"
            
    except Exception as e:
        return False, f"验证路径时出错: {str(e)}"


def get_repo_history_manager() -> RepoHistoryManager:
    """获取仓库历史管理器实例"""
    if 'repo_history_manager' not in st.session_state:
        st.session_state.repo_history_manager = RepoHistoryManager()
    return st.session_state.repo_history_manager


def get_code_review_config() -> Dict:
    """获取Code Review配置"""
    if 'code_review_config' not in st.session_state:
        config_file = 'code_review_config.json'
        default_config = {
            'keywords': ['pr-agent', 'codiumai-pr-agent', 'github-actions[bot]'],
            'enabled': True
        }
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                st.session_state.code_review_config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, IOError, OSError) as e:
            logging.warning(f"Failed to load code review config: {e}")
            st.session_state.code_review_config = default_config
    return st.session_state.code_review_config


def save_code_review_config(config: Dict) -> bool:
    """保存Code Review配置"""
    try:
        config_file = 'code_review_config.json'
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        st.session_state.code_review_config = config
        return True
    except (IOError, OSError) as e:
        st.error(f"保存配置失败: {e}")
        return False


def get_recent_repos() -> list:
    """获取最近使用的仓库列表"""
    history_manager = get_repo_history_manager()
    recent_repos = history_manager.get_recent_repos()
    
    # 如果没有历史记录，添加一些默认选项
    if not recent_repos:
        # 添加当前目录作为默认选项
        history_manager.add_repo(".")
        recent_repos = history_manager.get_recent_repos()
    
    return [repo["path"] for repo in recent_repos]


def add_to_recent_repos(repo_path: str):
    """添加仓库到最近使用列表"""
    history_manager = get_repo_history_manager()
    history_manager.add_repo(repo_path)


def sidebar_controls():
    """侧边栏控件"""
    st.sidebar.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
    st.sidebar.markdown("### 📁 Git仓库选择")
    
    # 仓库路径选择方式
    input_method = st.sidebar.radio(
        "选择输入方式",
        ["📝 手动输入", "📋 最近使用", "📂 浏览选择"],
        help="选择Git仓库路径的输入方式"
    )
    
    repo_path = "."
    
    if input_method == "📝 手动输入":
        repo_path = st.sidebar.text_input(
            "Git仓库路径或URL",
            value=".",
            help="支持本地路径和远程仓库URL",
            placeholder="本地: . 或 /path/to/repo\n远程: user/repo 或 https://github.com/user/repo.git"
        )
        
        st.sidebar.markdown("""
        <div style="font-size: 0.8em; color: #666; margin-top: 5px;">
        <strong>支持格式:</strong><br>
        • 本地路径: <code>.</code> 或 <code>/path/to/repo</code><br>
        • GitHub简化: <code>user/repo</code><br>
        • 完整URL: <code>https://github.com/user/repo.git</code>
        </div>
        """, unsafe_allow_html=True)
    
    elif input_method == "📋 最近使用":
        history_manager = get_repo_history_manager()
        recent_repos = history_manager.get_recent_repos()
        
        if recent_repos:
            # 创建显示选项
            display_options = []
            repo_paths = []
            
            for repo in recent_repos:
                display_name = history_manager.format_repo_display(repo)
                display_options.append(display_name)
                repo_paths.append(repo["path"])
            
            # 显示统计信息
            stats = history_manager.get_stats()
            st.sidebar.markdown(f"""
            <div style="font-size: 0.8em; color: #666; margin-bottom: 10px;">
            📊 共 {stats['total']} 个仓库 (📁 {stats['local']} 本地 + 🌐 {stats['remote']} 远程)
            </div>
            """, unsafe_allow_html=True)
            
            # 选择框
            selected_index = st.sidebar.selectbox(
                "选择最近使用的仓库",
                range(len(display_options)),
                format_func=lambda i: display_options[i],
                help="从最近使用的仓库中选择"
            )
            
            repo_path = repo_paths[selected_index]
            
            # 管理按钮
            col1, col2 = st.sidebar.columns(2)
            with col1:
                if st.button("🗑️ 删除", key="remove_repo", help="删除选中的仓库记录"):
                    if history_manager.remove_repo(repo_path):
                        st.success("✅ 已删除仓库记录")
                        st.rerun()
                    else:
                        st.error("❌ 删除失败")
            
            with col2:
                if st.button("🧹 清空", key="clear_history", help="清空所有仓库历史"):
                    if history_manager.clear_history():
                        st.success("✅ 已清空历史记录")
                        st.rerun()
                    else:
                        st.error("❌ 清空失败")
        else:
            st.sidebar.info("📭 暂无最近使用的仓库")
            st.sidebar.markdown("💡 使用其他方式选择仓库后，会自动添加到历史记录中")
            repo_path = "."
    
    elif input_method == "📂 浏览选择":
        st.sidebar.info("💡 在下方输入框中输入要分析的仓库路径")
        repo_path = st.sidebar.text_input(
            "仓库路径",
            value=".",
            help="输入要分析的Git仓库路径"
        )
    
    # 实时验证仓库路径
    is_valid, validation_msg = validate_git_repo(repo_path)
    
    if is_valid:
        st.sidebar.success(validation_msg)
    else:
        st.sidebar.error(validation_msg)
        # 如果路径无效，回退到当前目录
        if repo_path != ".":
            st.sidebar.warning("⚠️ 将使用当前目录作为备选")
            fallback_valid, _ = validate_git_repo(".")
            if fallback_valid:
                repo_path = "."
            else:
                st.sidebar.error("❌ 当前目录也不是有效的Git仓库")
    
    # 显示仓库信息预览
    if is_valid:
        if is_remote_repo_url(repo_path):
            # 远程仓库预览
            st.sidebar.markdown("#### 🌐 远程仓库预览")
            normalized_url = normalize_remote_url(repo_path)
            st.sidebar.markdown(f"**仓库URL**: `{normalized_url}`")
            st.sidebar.info("💡 远程仓库将在分析时临时克隆")
            st.sidebar.markdown("**克隆设置**:")
            st.sidebar.markdown("• 优先模式: 浅克隆（500个提交）")
            st.sidebar.markdown("• 备用模式: 完整克隆（如需要）")
            st.sidebar.markdown("• 分支: 默认分支")
            st.sidebar.markdown("• 自动清理: 分析完成后删除临时文件")
        else:
            # 本地仓库预览
            try:
                preview_analyzer = GitAnalyzer(repo_path)
                repo_info = preview_analyzer.get_repo_info()
                
                st.sidebar.markdown("#### 📊 本地仓库预览")
                st.sidebar.markdown(f"**路径**: `{repo_info['path']}`")
                st.sidebar.markdown(f"**当前分支**: `{repo_info['current_branch']}`")
                st.sidebar.markdown(f"**分支总数**: {repo_info['total_branches']}")
                
                if repo_info['remote_urls']:
                    st.sidebar.markdown("**Remote URLs**:")
                    for remote in repo_info['remote_urls'][:2]:  # 最多显示2个
                        url_display = remote['url']
                        if len(url_display) > 30:
                            url_display = url_display[:27] + "..."
                        st.sidebar.markdown(f"• `{remote['name']}`: {url_display}")
                    if len(repo_info['remote_urls']) > 2:
                        st.sidebar.markdown(f"• ... 还有 {len(repo_info['remote_urls']) - 2} 个")
                else:
                    st.sidebar.markdown("**Remote URLs**: 无")
                    
            except Exception as e:
                st.sidebar.warning(f"获取仓库预览失败: {str(e)}")
    
    # 快速操作按钮
    # 刷新按钮
    if st.sidebar.button("🔄 刷新", help="重新加载当前仓库数据"):
        st.rerun()
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### ⚙️ 分析配置")
    
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


@st.cache_data(ttl=300)  # 缓存5分钟
def get_cached_commit_stats(repo_path: str, start_date, end_date, branch: str):
    """缓存的提交统计获取"""
    analyzer = GitAnalyzer(repo_path)
    return analyzer.get_commit_stats(
        since_date=datetime.combine(start_date, datetime.min.time()) if start_date else None,
        until_date=datetime.combine(end_date, datetime.min.time()) if end_date else None,
        branch=branch
    )

@st.cache_data(ttl=300)  # 缓存5分钟  
def get_cached_author_stats(repo_path: str, start_date, end_date):
    """缓存的作者统计获取"""
    analyzer = GitAnalyzer(repo_path)
    return analyzer.get_author_stats(
        since_date=datetime.combine(start_date, datetime.min.time()) if start_date else None,
        until_date=datetime.combine(end_date, datetime.min.time()) if end_date else None
    )


def display_overview_metrics(analyzer: GitAnalyzer, config: dict):
    """显示概览指标"""
    st.markdown("## 📈 统计概览")
    
    try:
        # 使用缓存获取基础统计
        commits_df = get_cached_commit_stats(
            config['repo_path'],
            config['start_date'],
            config['end_date'], 
            config['branch']
        )
        
        author_stats = get_cached_author_stats(
            config['repo_path'],
            config['start_date'],
            config['end_date']
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
        st.plotly_chart(timeline_fig, width='stretch')
    
    # 最近提交列表
    st.markdown("### 最近提交")
    recent_commits = commits_df.head(10)[['hash', 'author', 'date', 'message', 'files_changed', 'lines_changed']].copy()
    recent_commits['date'] = recent_commits['date'].dt.strftime('%Y-%m-%d %H:%M')
    # 清理message中的emoji字符
    recent_commits['message'] = recent_commits['message'].apply(clean_message_for_display)
    st.dataframe(recent_commits, width='stretch')


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
        st.plotly_chart(contrib_fig, width='stretch')
    
    with col2:
        # 作者统计表
        st.markdown("### 作者详细统计")
        display_stats = author_stats[[
            'author', 'commits_count', 'total_lines_changed', 
            'avg_lines_per_commit', 'active_days'
        ]].round(2)
        st.dataframe(display_stats, width='stretch')


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
        st.plotly_chart(trend_fig, width='stretch')
        
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
        st.plotly_chart(merge_freq_fig, width='stretch')
        
        # 最近合并列表
        st.markdown("### 最近合并")
        recent_merges = merge_stats.head(10)[['hash', 'author', 'date', 'source_branch', 'target_branch']].copy()
        recent_merges['date'] = recent_merges['date'].dt.strftime('%Y-%m-%d %H:%M')
        st.dataframe(recent_merges, width='stretch')
        
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
        st.plotly_chart(file_dist_fig, width='stretch')
        
        # 最常修改的文件
        st.markdown("### 最常修改的文件")
        top_files = file_stats.nlargest(20, 'modifications')[
            ['file_path', 'modifications', 'total_changes', 'authors_count']
        ]
        st.dataframe(top_files, width='stretch')
        
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
        st.plotly_chart(branch_activity_fig, width='stretch')
        
        # 分支详情
        st.markdown("### 分支详情")
        display_branches = branch_stats[[
            'branch_name', 'commits_count', 'last_commit_date', 'last_author', 'is_active'
        ]].copy()
        display_branches['last_commit_date'] = display_branches['last_commit_date'].dt.strftime('%Y-%m-%d %H:%M')
        st.dataframe(display_branches, width='stretch')
        
    except Exception as e:
        st.error(f"分支分析出错: {str(e)}")


def display_branch_graph_analysis(analyzer: GitAnalyzer, visualizer: GitVisualizer):
    """显示分支关系图分析"""
    st.markdown("## 🌐 分支关系图")
    
    try:
        # 获取分支关系图数据
        graph_data = analyzer.get_branch_graph_data()
        
        if not graph_data['commits']:
            st.warning("暂无分支关系数据")
            return
        
        # 显示概览统计
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📊 提交节点", len(graph_data['commits']))
        
        with col2:
            st.metric("🔗 关系连接", len(graph_data['edges']))
        
        with col3:
            merge_commits = sum(1 for commit in graph_data['commits'] if commit['is_merge'])
            st.metric("🔀 合并提交", merge_commits)
        
        with col4:
            st.metric("🌿 分支数量", len(graph_data['branches']))
        
        # 分支网络关系图
        st.markdown("### 分支网络关系图")
        st.markdown("""
        <div class="info-box">
        💡 <strong>图表说明:</strong><br>
        • 🔵 圆形节点 = 普通提交<br>
        • 💎 菱形节点 = 合并提交<br>
        • 不同颜色 = 不同分支<br>
        • 连线显示提交的父子关系
        </div>
        """, unsafe_allow_html=True)
        
        network_fig = visualizer.plot_branch_network_graph(graph_data)
        st.plotly_chart(network_fig, width='stretch')
        
        # 分支提交详情
        st.markdown("### 最近提交节点")
        commits_df = pd.DataFrame(graph_data['commits'][:20])
        if not commits_df.empty:
            display_commits = commits_df[['hash', 'author', 'date', 'message', 'branches', 'is_merge']].copy()
            display_commits['date'] = pd.to_datetime(display_commits['date']).dt.strftime('%Y-%m-%d %H:%M')
            display_commits['branches'] = display_commits['branches'].apply(lambda x: ', '.join(x))
            display_commits['type'] = display_commits['is_merge'].apply(lambda x: '🔀 合并' if x else '📝 普通')
            display_commits = display_commits.drop('is_merge', axis=1)
            st.dataframe(display_commits, width='stretch')
        
    except Exception as e:
        st.error(f"分支关系图分析出错: {str(e)}")


def clean_message_for_display(message: str) -> str:
    """清理消息中的emoji和特殊Unicode字符，确保在所有环境下正确显示"""
    if not isinstance(message, str):
        message = str(message)
    
    # 移除emoji和其他特殊Unicode字符 (U+1F000 到 U+1FFFF范围)
    # 保留常见的中文、英文、标点符号等
    cleaned = re.sub(r'[\U00010000-\U0010ffff]', '', message)
    
    # 移除其他常见的装饰性Unicode字符
    cleaned = re.sub(r'[\u2600-\u27BF]', '', cleaned)  # 各种符号
    cleaned = re.sub(r'[\uE000-\uF8FF]', '', cleaned)  # 私有使用区
    cleaned = re.sub(r'[\uFE00-\uFE0F]', '', cleaned)  # 变体选择符
    
    # 移除零宽字符
    cleaned = re.sub(r'[\u200B-\u200D\uFEFF]', '', cleaned)
    
    # 清理多余的空格和换行
    cleaned = ' '.join(cleaned.split())
    
    return cleaned.strip()


def display_code_review_analysis(analyzer: GitAnalyzer, config: dict):
    """显示Code Review统计分析"""
    st.markdown("## 🔍 Code Review 统计")
    
    # 获取Code Review配置
    cr_config = get_code_review_config()
    
    # 配置部分
    with st.expander("⚙️ Code Review 配置", expanded=False):
        st.markdown("### 🤖 机器人关键词配置")
        st.markdown("配置用于识别自动化Code Review的关键词（如机器人名称）")
        
        # 启用/禁用开关
        enabled = st.checkbox(
            "启用Code Review统计",
            value=cr_config.get('enabled', True),
            help="是否启用Code Review统计功能"
        )
        
        # 关键词输入
        keywords_text = st.text_area(
            "关键词列表（每行一个）",
            value='\n'.join(cr_config.get('keywords', [])),
            height=100,
            help="输入用于识别Code Review的关键词，如机器人名称、用户名等"
        )
        
        # 示例关键词
        st.markdown("""
        **常见机器人关键词示例：**
        - `pr-agent` - PR Agent 机器人
        - `codiumai-pr-agent` - CodiumAI PR Agent
        - `github-actions[bot]` - GitHub Actions 机器人
        - `codecov` - Codecov 机器人
        - `sonarcloud[bot]` - SonarCloud 机器人
        """)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 保存配置", type="primary"):
                keywords = [k.strip() for k in keywords_text.split('\n') if k.strip()]
                new_config = {
                    'keywords': keywords,
                    'enabled': enabled
                }
                if save_code_review_config(new_config):
                    st.success("✅ 配置已保存！")
                    st.rerun()
        
        with col2:
            if st.button("🔄 重置为默认"):
                default_config = {
                    'keywords': ['pr-agent', 'codiumai-pr-agent', 'github-actions[bot]'],
                    'enabled': True
                }
                if save_code_review_config(default_config):
                    st.success("✅ 已重置为默认配置！")
                    st.rerun()
    
    if not cr_config.get('enabled', True):
        st.info("💡 Code Review统计功能已禁用，请在配置中启用")
        return
    
    keywords = cr_config.get('keywords', [])
    if not keywords:
        st.warning("⚠️ 未配置任何关键词，请在配置中添加")
        return
    
    try:
        # 获取commit历史
        commits_df = get_cached_commit_stats(
            config['repo_path'],
            config['start_date'],
            config['end_date'],
            config['branch']
        )
        
        if commits_df.empty:
            st.warning("暂无提交数据可供分析")
            return
        
        # 分析commit message中的关键词
        st.markdown("### 📊 统计概览")
        st.markdown(f"**监控关键词**: {', '.join([f'`{k}`' for k in keywords])}")
        
        # 统计包含关键词的commit
        review_stats = {
            'total_commits': len(commits_df),
            'reviewed_commits': 0,
            'review_rate': 0.0,
            'keyword_counts': {k: 0 for k in keywords},
            'reviews_by_author': {},
            'reviews_over_time': []
        }
        
        # 分析每个commit
        for _, commit in commits_df.iterrows():
            message = str(commit.get('message', '')).lower()
            author = commit.get('author', 'Unknown')
            date = commit.get('date')
            
            # 检查是否包含任何关键词
            has_review = False
            for keyword in keywords:
                if keyword.lower() in message:
                    review_stats['keyword_counts'][keyword] += 1
                    has_review = True
            
            if has_review:
                review_stats['reviewed_commits'] += 1
                
                # 按作者统计
                if author not in review_stats['reviews_by_author']:
                    review_stats['reviews_by_author'][author] = 0
                review_stats['reviews_by_author'][author] += 1
                
                # 时间序列统计
                review_stats['reviews_over_time'].append({
                    'date': date,
                    'author': author,
                    'message': commit.get('message', '')[:100]
                })
        
        # 计算review率
        if review_stats['total_commits'] > 0:
            review_stats['review_rate'] = (review_stats['reviewed_commits'] / review_stats['total_commits']) * 100
        
        # 显示关键指标
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                label="📝 总提交数",
                value=review_stats['total_commits']
            )
        
        with col2:
            st.metric(
                label="✅ 已Review提交",
                value=review_stats['reviewed_commits']
            )
        
        with col3:
            st.metric(
                label="📈 Review覆盖率",
                value=f"{review_stats['review_rate']:.1f}%"
            )
        
        with col4:
            total_reviews = sum(review_stats['keyword_counts'].values())
            st.metric(
                label="🔍 Review总数",
                value=total_reviews
            )
        
        # 关键词统计
        st.markdown("### 🤖 关键词出现次数")
        keyword_df = pd.DataFrame([
            {'关键词': k, '出现次数': v, '占比': f"{(v/total_reviews*100):.1f}%" if total_reviews > 0 else "0%"}
            for k, v in review_stats['keyword_counts'].items()
        ]).sort_values('出现次数', ascending=False)
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # 使用bar chart显示
            if not keyword_df.empty and total_reviews > 0:
                st.bar_chart(keyword_df.set_index('关键词')['出现次数'])
        
        with col2:
            st.dataframe(keyword_df, use_container_width=True, hide_index=True)
        
        # 按作者统计
        if review_stats['reviews_by_author']:
            st.markdown("### 👥 作者Review统计")
            author_df = pd.DataFrame([
                {'作者': author, 'Review次数': count}
                for author, count in sorted(
                    review_stats['reviews_by_author'].items(),
                    key=lambda x: x[1],
                    reverse=True
                )
            ])
            
            st.dataframe(author_df, use_container_width=True, hide_index=True)
        
        # 最近Review记录
        if review_stats['reviews_over_time']:
            st.markdown("### 📜 最近Review记录")
            recent_reviews = sorted(
                review_stats['reviews_over_time'],
                key=lambda x: x['date'],
                reverse=True
            )[:20]
            
            review_display_df = pd.DataFrame([
                {
                    '时间': r['date'].strftime('%Y-%m-%d %H:%M') if hasattr(r['date'], 'strftime') else str(r['date']),
                    '作者': r['author'],
                    '提交信息': clean_message_for_display(r['message'])
                }
                for r in recent_reviews
            ])
            
            st.dataframe(review_display_df, use_container_width=True, hide_index=True)
        
        # 趋势分析
        if len(review_stats['reviews_over_time']) > 1:
            st.markdown("### 📈 Review趋势分析")
            st.info("💡 基于commit message中的关键词统计Review活动趋势")
            
            # 按日期聚合
            review_dates = pd.DataFrame(review_stats['reviews_over_time'])
            if not review_dates.empty and 'date' in review_dates.columns:
                review_dates['date_only'] = pd.to_datetime(review_dates['date']).dt.date
                daily_reviews = review_dates.groupby('date_only').size().reset_index(name='review_count')
                daily_reviews.columns = ['日期', 'Review数量']
                
                st.line_chart(daily_reviews.set_index('日期'))
        
    except Exception as e:
        st.error(f"Code Review分析出错: {str(e)}")
        import traceback
        st.code(traceback.format_exc())


def display_merge_direction_analysis(analyzer: GitAnalyzer, visualizer: GitVisualizer):
    """显示合并方向历史分析"""
    st.markdown("## 🔀 合并方向历史")
    
    try:
        # 获取合并历史数据
        merge_history = analyzer.get_merge_direction_history()
        
        if merge_history.empty:
            st.info("在当前仓库中未发现合并提交")
            return
        
        # 显示合并概览统计
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("🔀 总合并次数", len(merge_history))
        
        with col2:
            unique_authors = merge_history['author'].nunique()
            st.metric("👥 参与作者数", unique_authors)
        
        with col3:
            unique_branches = len(set(merge_history['source_branch'].tolist() + merge_history['target_branch'].tolist()))
            st.metric("🌿 涉及分支数", unique_branches)
        
        with col4:
            avg_files = int(merge_history['files_changed'].mean()) if not merge_history.empty else 0
            st.metric("📁 平均文件变更", avg_files)
        
        # 合并方向流程图
        st.markdown("### 分支合并流向图")
        st.markdown("""
        <div class="info-box">
        💡 <strong>桑基图说明:</strong> 显示分支间的合并流向和频率，线条粗细代表合并次数
        </div>
        """, unsafe_allow_html=True)
        
        flow_fig = visualizer.plot_merge_direction_flow(merge_history)
        st.plotly_chart(flow_fig, width='stretch')
        
        # 合并时间线
        st.markdown("### 合并历史时间线")
        timeline_fig = visualizer.plot_merge_timeline(merge_history)
        st.plotly_chart(timeline_fig, width='stretch')
        
        # 合并统计总览
        st.markdown("### 合并统计总览")
        stats_fig = visualizer.plot_merge_statistics(merge_history)
        st.plotly_chart(stats_fig, width='stretch')
        
        # 最近合并详情
        st.markdown("### 最近合并记录")
        recent_merges = merge_history.head(15).copy()
        if not recent_merges.empty:
            display_merges = recent_merges[[
                'hash', 'author', 'date', 'source_branch', 'target_branch', 
                'merge_type', 'files_changed', 'insertions', 'deletions'
            ]].copy()
            display_merges['date'] = display_merges['date'].dt.strftime('%Y-%m-%d %H:%M')
            display_merges['code_changes'] = display_merges.apply(
                lambda row: f"+{row['insertions']} -{row['deletions']}", axis=1
            )
            display_merges = display_merges.drop(['insertions', 'deletions'], axis=1)
            st.dataframe(display_merges, width='stretch')
        
    except Exception as e:
        st.error(f"合并方向分析出错: {str(e)}")


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
        # 验证仓库路径
        is_valid, validation_msg = validate_git_repo(config['repo_path'])
        
        if not is_valid:
            st.error(f"❌ 仓库路径无效: {validation_msg}")
            st.markdown("""
            <div class="warning-box">
            <strong>💡 解决方案:</strong><br>
            1. 检查侧边栏中的仓库路径是否正确<br>
            2. 确保该路径是有效的Git仓库<br>
            3. 检查是否有访问该仓库的权限<br>
            4. 尝试使用其他仓库路径
            </div>
            """, unsafe_allow_html=True)
            return
        
        # 添加到最近使用列表
        add_to_recent_repos(config['repo_path'])
        
        # 检查是否是远程仓库，显示加载进度
        if is_remote_repo_url(config['repo_path']):
            with st.spinner('🌐 正在克隆远程仓库，请稍候...'):
                progress_info = st.empty()
                progress_info.info(f"正在从 {normalize_remote_url(config['repo_path'])} 克隆仓库（浅克隆模式）")
                
                try:
                    analyzer = GitAnalyzer(config['repo_path'])
                    progress_info.success("✅ 远程仓库克隆完成！")
                    
                    # 添加浅克隆提示
                    if hasattr(analyzer, 'temp_dir') and analyzer.temp_dir:
                        st.info("""
                        📋 **远程仓库分析说明**：
                        • 使用浅克隆技术以提高性能
                        • 如遇到统计数据不完整，属正常现象
                        • 临时文件将在分析完成后自动清理
                        """)
                        
                except Exception as e:
                    progress_info.error(f"❌ 克隆失败: {str(e)}")
                    st.markdown("""
                    <div class="warning-box">
                    <strong>💡 可能的解决方案:</strong><br>
                    1. 检查仓库URL是否正确<br>
                    2. 确认仓库是公开的或您有访问权限<br>
                    3. 检查网络连接是否正常<br>
                    4. 尝试使用完整的GitHub URL格式
                    </div>
                    """, unsafe_allow_html=True)
                    return
        else:
            analyzer = GitAnalyzer(config['repo_path'])
        
        visualizer = GitVisualizer()
        
        # 获取并显示仓库信息
        repo_info = analyzer.get_repo_info()
        
        remote_info = ""
        # 对于远程仓库，显示原始URL而不是克隆后的remote信息
        if repo_info.get('is_remote', False):
            remote_info = f"<br><strong>🔗 原始URL:</strong> <code>{repo_info.get('original_path', 'unknown')}</code>"
        elif repo_info['remote_urls']:
            remote_info = "<br><strong>🔗 Remote URLs:</strong><br>"
            for remote in repo_info['remote_urls']:
                # 简化显示长URL
                display_url = remote['url']
                if len(display_url) > 60:
                    display_url = display_url[:57] + "..."
                remote_info += f"&nbsp;&nbsp;• {remote['name']}: <code>{display_url}</code><br>"
        else:
            remote_info = "<br><strong>🔗 Remote URLs:</strong> 无远程仓库"
        
        # 先获取数据用于状态显示
        commits_df, author_stats = display_overview_metrics(analyzer, config)
        
        # 添加仓库状态指示器
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            # 根据是否是远程仓库调整显示内容
            if repo_info.get('is_remote', False):
                repo_type_info = f"🌐 <strong>远程仓库:</strong> {repo_info['path']}<br>"
                if repo_info.get('temp_dir'):
                    repo_type_info += f"📁 <strong>临时路径:</strong> {repo_info['temp_dir']}<br>"
            else:
                repo_type_info = f"📁 <strong>本地仓库:</strong> {repo_info['path']}<br>"
            
            st.markdown(f"""
            <div class="info-box">
            {repo_type_info}
            <strong>🌿 当前分支:</strong> {repo_info['current_branch']}<br>
            <strong>🔍 分析分支:</strong> {config['branch']}<br>
            <strong>📊 总分支数:</strong> {repo_info['total_branches']}{remote_info}<br>
            <strong>📅 时间范围:</strong> {config['start_date'] or '开始'} 至 {config['end_date'] or '结束'}
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            # 根据仓库类型显示不同的状态
            if repo_info.get('is_remote', False):
                status_value = "🌐 已克隆"
                status_delta = "远程仓库"
            else:
                status_value = "✅ 已连接"
                status_delta = "本地仓库"
                
            st.metric(
                label="🔄 仓库状态",
                value=status_value,
                delta=status_delta
            )
        
        with col3:
            # 显示数据状态
            total_commits = len(commits_df) if not commits_df.empty else 0
            st.metric(
                label="📊 数据状态", 
                value=f"{total_commits} 提交",
                delta="数据已加载"
            )
        
        # 创建选项卡
        tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10 = st.tabs([
            "📝 提交分析", "👥 作者分析", "⏰时间分析", 
            "🔀 合并分析", "📁 文件分析", "🌳 分支分析",
            "🌐 分支关系图", "🔀 合并方向历史", "🔍 Code Review统计", "🔄 MR管理"
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
        
        with tab7:
            display_branch_graph_analysis(analyzer, visualizer)
        
        with tab8:
            display_merge_direction_analysis(analyzer, visualizer)
        
        with tab9:
            display_code_review_analysis(analyzer, config)
        
        with tab10:
            display_mr_management(analyzer, config)
            
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


def display_mr_management(analyzer, config):
    """显示MR管理页面"""
    st.markdown("### 🔄 Merge Request 管理")
    
    # GitHub配置检查
    github_token = st.session_state.get('github_token')
    
    if not github_token:
        st.info("🔑 请先配置GitHub访问令牌以使用MR管理功能")
        
        with st.expander("⚙️ GitHub配置", expanded=True):
            st.markdown("""
            **获取GitHub Personal Access Token:**
            1. 访问 [GitHub Settings > Personal access tokens](https://github.com/settings/tokens)
            2. 点击 "Generate new token (classic)"
            3. 选择适当的权限范围 (至少需要 `repo` 权限)
            4. 复制生成的token
            """)
            
            token_input = st.text_input(
                "GitHub Access Token",
                type="password",
                help="输入您的GitHub Personal Access Token"
            )
            
            if st.button("保存配置"):
                if token_input:
                    st.session_state['github_token'] = token_input
                    st.success("✅ GitHub配置已保存！")
                    st.rerun()
                else:
                    st.error("请输入有效的token")
        return  # 只有在没有token时才返回
    
    # 初始化GitHub集成
    try:
        github_client = GitHubIntegration(github_token)
        success, message = github_client.test_connection()
        
        if not success:
            st.error(f"❌ GitHub连接失败: {message}")
            
            # 显示常见问题解决方案
            with st.expander("🔧 故障排除", expanded=True):
                st.markdown("""
                **常见问题及解决方案：**
                
                **1. Token格式错误**
                - 确保token以 `ghp_` 开头（Personal Access Token）
                - 检查token是否完整复制（通常40-50个字符）
                
                **2. Token权限不足**
                - 访问 [GitHub Token设置](https://github.com/settings/tokens)
                - 确保勾选了以下权限：
                  - `repo` (访问私有仓库) 或 `public_repo` (访问公开仓库)
                  - `user` (读取用户信息)
                
                **3. Token已过期**
                - 检查token的过期时间
                - 如已过期，请生成新的token
                
                **4. 网络连接问题**
                - 检查网络连接是否正常
                - 确认可以访问 github.com
                """)
            
            if st.button("🔄 重新配置Token"):
                del st.session_state['github_token']
                st.rerun()
            return
        
        st.success(f"✅ GitHub连接成功: {message}")
        
        # 检查token权限
        perm_success, perm_message, permissions = github_client.check_token_permissions()
        
        if perm_success:
            with st.expander("🔐 Token权限信息", expanded=False):
                st.markdown(f"**权限检查结果:** {perm_message}")
                if permissions:
                    st.markdown("**检测到的权限:**")
                    for perm in permissions:
                        st.markdown(f"- ✅ `{perm}`")
                else:
                    st.warning("⚠️ 未检测到明确的权限信息")
        else:
            st.warning(f"⚠️ {perm_message}")
        
        # 显示连接成功后的提示
        with st.expander("💡 使用提示", expanded=False):
            st.markdown("""
            **GitHub连接已建立，现在您可以：**
            1. 在下方输入要管理的仓库地址
            2. 设置时间范围和PR状态筛选
            3. 点击"刷新PR数据"获取数据
            
            **热门仓库示例：**
            - `microsoft/vscode` - Visual Studio Code
            - `facebook/react` - React JavaScript库
            - `tensorflow/tensorflow` - TensorFlow机器学习
            - `kubernetes/kubernetes` - Kubernetes容器编排
            
            **权限说明：**
            - 公开仓库需要 `public_repo` 权限
            - 私有仓库需要 `repo` 权限
            - 某些功能可能需要 `user` 权限
            """)
        
    except Exception as e:
        st.error(f"❌ GitHub集成初始化失败: {str(e)}")
        
        with st.expander("🐛 调试信息", expanded=False):
            st.code(f"""
错误类型: {type(e).__name__}
错误消息: {str(e)}
Token长度: {len(github_token) if github_token else 0}
Token前缀: {github_token[:10] + '...' if github_token and len(github_token) > 10 else github_token}
            """)
        
        if st.button("🔄 重新配置Token"):
            del st.session_state['github_token']
            st.rerun()
        return
    
    # 用户设置
    if 'user_name' not in st.session_state:
        st.session_state['user_name'] = 'Unknown User'
    
    with st.expander("👤 用户设置"):
        user_name = st.text_input(
            "操作人名称",
            value=st.session_state.get('user_name', 'Unknown User'),
            help="设置您的名称，将记录在操作历史中"
        )
        if st.button("保存用户设置"):
            st.session_state['user_name'] = user_name
            st.success(f"✅ 用户名已设置为: {user_name}")
    
    # 仓库选择和配置
    st.markdown("#### 📁 仓库设置")
    
    # 仓库输入方式选择
    col_method, col_input = st.columns([1, 3])
    
    with col_method:
        mr_input_method = st.selectbox(
            "输入方式",
            ["手动输入", "最近使用"],
            key="mr_input_method",
            help="选择仓库输入方式"
        )
    
    with col_input:
        if mr_input_method == "手动输入":
            repo_input = st.text_input(
                "GitHub仓库",
                value="",
                placeholder="例如: owner/repo 或 https://github.com/owner/repo",
                help="输入要管理的GitHub仓库",
                key="mr_repo_input"
            )
        else:  # 最近使用
            history_manager = get_repo_history_manager()
            recent_repos = history_manager.get_repos_by_type("remote")  # 只显示远程仓库
            
            if recent_repos:
                display_options = []
                repo_paths = []
                
                for repo in recent_repos:
                    display_name = f"🌐 {repo['name']} - {repo['path']}"
                    display_options.append(display_name)
                    repo_paths.append(repo["path"])
                
                selected_index = st.selectbox(
                    "选择远程仓库",
                    range(len(display_options)),
                    format_func=lambda i: display_options[i],
                    help="从最近使用的远程仓库中选择",
                    key="mr_recent_select"
                )
                
                repo_input = repo_paths[selected_index]
            else:
                st.info("📭 暂无最近使用的远程仓库")
                repo_input = st.text_input(
                    "GitHub仓库",
                    value="",
                    placeholder="例如: owner/repo",
                    help="输入GitHub仓库地址",
                    key="mr_repo_fallback"
                )
    
    col2, col3 = st.columns([1, 1])
    
    with col2:
        days_range = st.number_input(
            "时间范围（天）",
            min_value=1,
            max_value=90,
            value=30,
            help="获取最近多少天的PR"
        )
    
    with col3:
        pr_state = st.selectbox(
            "PR状态",
            options=["all", "open", "closed"],
            index=0,
            help="筛选PR状态"
        )
    
    if not repo_input:
        st.info("💡 请输入要管理的GitHub仓库地址")
        st.markdown("#### 🚀 快速开始")
        st.markdown("""
        **设置完成后，请按以下步骤操作：**
        1. ✅ GitHub Token 已配置
        2. 📝 在上方输入要管理的仓库地址
        3. 🔄 点击"刷新PR数据"获取数据
        4. 📋 查看和管理Pull Requests
        
        **支持的仓库地址格式：**
        - `owner/repo` (例如: `microsoft/vscode`)
        - `https://github.com/owner/repo`
        - `https://github.com/owner/repo.git`
        """)
        return
    
    # 获取PR数据
    if st.button("🔄 刷新PR数据") or 'mr_data' not in st.session_state:
        progress_container = st.container()
        
        with st.spinner("📥 正在获取PR数据..."):
            try:
                # 步骤1: 获取仓库信息
                progress_container.info("🔍 正在验证仓库访问权限...")
                try:
                    repo_info = github_client.get_repository_info(repo_input)
                    st.session_state['current_repo_info'] = repo_info
                    progress_container.success(f"✅ 仓库验证成功: {repo_info['full_name']}")
                    
                    # 添加到仓库历史记录
                    add_to_recent_repos(repo_input)
                except Exception as e:
                    progress_container.error(f"❌ 仓库访问失败: {str(e)}")
                    
                    # 显示详细的故障排除信息
                    with st.expander("🔧 仓库访问故障排除", expanded=True):
                        st.markdown(f"""
                        **仓库地址:** `{repo_input}`
                        **错误信息:** {str(e)}
                        
                        **可能的原因：**
                        1. **仓库不存在**: 请检查仓库名称是否正确
                        2. **权限不足**: 
                           - 公开仓库需要 `public_repo` 权限
                           - 私有仓库需要 `repo` 权限
                        3. **仓库地址格式错误**: 
                           - 正确格式: `owner/repo`
                           - 示例: `microsoft/vscode`
                        4. **网络问题**: 检查网络连接
                        
                        **解决方案：**
                        - 检查token权限设置
                        - 确认仓库名称正确
                        - 尝试访问公开仓库进行测试
                        """)
                    return
                
                # 步骤2: 获取PR列表
                progress_container.info(f"📋 正在获取最近 {days_range} 天的 {pr_state} 状态PR...")
                try:
                    prs = github_client.get_pull_requests(repo_input, days=days_range, state=pr_state)
                    st.session_state['mr_data'] = prs
                    progress_container.success(f"✅ 成功获取 {len(prs)} 个PR")
                except Exception as e:
                    progress_container.error(f"❌ 获取PR列表失败: {str(e)}")
                    
                    # 显示PR获取故障排除信息
                    with st.expander("🔧 PR获取故障排除", expanded=True):
                        st.markdown(f"""
                        **错误详情:** {str(e)}
                        
                        **常见问题：**
                        1. **权限不足**: Token缺少访问PR的权限
                        2. **API限制**: GitHub API调用频率限制
                        3. **仓库无PR**: 该时间范围内可能没有PR
                        
                        **建议操作：**
                        - 检查token是否有 `repo` 或 `public_repo` 权限
                        - 尝试增加时间范围
                        - 检查仓库是否有PR存在
                        - 稍后重试（可能是API限制）
                        """)
                    return
                
                # 步骤3: 处理PR数据和pr-agent结果
                if prs:
                    progress_container.info("💾 正在处理PR数据和pr-agent结果...")
                    
                    # 初始化数据库
                    db = MRDatabase()
                    
                    processed_count = 0
                    pr_agent_count = 0
                    
                    # 存储PR数据到数据库
                    for pr in prs:
                        try:
                            pr_id = db.insert_or_update_pr(pr)
                            processed_count += 1
                            
                            # 获取PR评论以查找pr-agent结果
                            try:
                                comments = github_client.get_pr_comments(repo_input, pr['pr_number'])
                                pr_agent_reviews = github_client.find_pr_agent_reviews(comments)
                                
                                # 存储review结果
                                for review in pr_agent_reviews:
                                    db.insert_review_result(pr_id, review)
                                    pr_agent_count += 1
                            except Exception as comment_e:
                                # 评论获取失败不影响主流程
                                st.warning(f"⚠️ PR #{pr['pr_number']} 评论获取失败: {str(comment_e)}")
                                
                        except Exception as pr_e:
                            st.warning(f"⚠️ PR #{pr.get('pr_number', 'Unknown')} 处理失败: {str(pr_e)}")
                    
                    progress_container.success(f"✅ 数据处理完成!")
                    
                    # 显示处理结果摘要
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("📋 PR总数", len(prs))
                    with col2:
                        st.metric("💾 已处理", processed_count)
                    with col3:
                        st.metric("🤖 pr-agent结果", pr_agent_count)
                else:
                    progress_container.info("📭 该时间范围内没有找到PR")
                    st.info(f"💡 尝试增加时间范围或检查仓库 '{repo_input}' 是否有PR")
                
            except Exception as e:
                progress_container.error(f"❌ 数据获取过程中发生未知错误: {str(e)}")
                
                # 显示详细的调试信息
                with st.expander("🐛 详细错误信息", expanded=False):
                    st.code(f"""
错误类型: {type(e).__name__}
错误消息: {str(e)}
仓库地址: {repo_input}
时间范围: {days_range} 天
PR状态: {pr_state}
Token状态: {'已配置' if github_token else '未配置'}
                    """)
                return
    
    # 显示仓库信息
    if 'current_repo_info' in st.session_state:
        repo_info = st.session_state['current_repo_info']
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("⭐ Stars", repo_info.get('stars', 0))
        with col2:
            st.metric("🍴 Forks", repo_info.get('forks', 0))
        with col3:
            st.metric("🐛 Issues", repo_info.get('open_issues', 0))
        with col4:
            st.metric("📝 PRs", len(st.session_state.get('mr_data', [])))
    
    # 显示PR列表
    if 'mr_data' in st.session_state and st.session_state['mr_data']:
        st.markdown("#### 📋 Pull Request 列表")
        
        # 创建PR数据表格
        mr_data = st.session_state['mr_data']
        
        # 准备表格数据
        table_data = []
        db = MRDatabase()  # 在循环外创建数据库连接
        
        for pr in mr_data:
            # 通过repo_url和pr_number获取数据库中的PR ID
            pr_id = db.get_pr_id_by_number(pr['repo_url'], pr['pr_number'])
            
            review_score = "N/A"
            security_issues = 0
            code_issues = 0
            risk_level = "Unknown"
            
            if pr_id:
                # 获取数据库中的review结果
                pr_details = db.get_pr_details(pr_id)
                
                if pr_details and pr_details.get('reviews'):
                    latest_review = pr_details['reviews'][0]  # 最新的review
                    review_score = f"{latest_review.get('score', 0):.1f}/10" if latest_review.get('score') else "N/A"
                    security_issues = latest_review.get('security_issues', 0)
                    code_issues = latest_review.get('code_issues', 0)
                    risk_level = latest_review.get('risk_level', 'Unknown').title()
                
                # 将数据库ID添加到PR数据中，供后续操作使用
                pr['db_id'] = pr_id
            
            table_data.append({
                'PR#': pr['pr_number'],
                '标题': pr['title'][:50] + '...' if len(pr['title']) > 50 else pr['title'],
                '作者': pr['author'],
                '状态': pr['status'],
                '创建时间': pr['created_at'][:10],
                'Review评分': review_score,
                '安全问题': security_issues,
                '代码问题': code_issues,
                '风险等级': risk_level,
                'URL': pr['pr_url']
            })
        
        # 显示表格
        if table_data:
            df = pd.DataFrame(table_data)
            
            # 使用颜色标记风险等级
            def highlight_risk(val):
                if val == 'Critical':
                    return 'background-color: #ffebee; color: #c62828'
                elif val == 'High':
                    return 'background-color: #fff3e0; color: #ef6c00'
                elif val == 'Medium':
                    return 'background-color: #f3e5f5; color: #7b1fa2'
                elif val == 'Low':
                    return 'background-color: #e8f5e8; color: #2e7d32'
                return ''
            
            styled_df = df.style.applymap(highlight_risk, subset=['风险等级'])
            
            st.dataframe(
                styled_df,
                width='stretch',
                height=400,
                use_container_width=True
            )
            
            # PR详情和操作
            st.markdown("#### 🔍 PR详细操作")
            
            selected_pr_num = st.selectbox(
                "选择要操作的PR",
                options=[pr['pr_number'] for pr in mr_data],
                format_func=lambda x: f"#{x} - {next(pr['title'] for pr in mr_data if pr['pr_number'] == x)[:30]}..."
            )
            
            if selected_pr_num:
                selected_pr = next(pr for pr in mr_data if pr['pr_number'] == selected_pr_num)
                
                with st.expander(f"📄 PR #{selected_pr_num} 详细信息", expanded=True):
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.markdown(f"**标题:** {selected_pr['title']}")
                        st.markdown(f"**作者:** {selected_pr['author']}")
                        st.markdown(f"**分支:** `{selected_pr['head_branch']}` → `{selected_pr['base_branch']}`")
                        st.markdown(f"**状态:** {selected_pr['status']}")
                        st.markdown(f"**创建时间:** {selected_pr['created_at']}")
                        
                        if selected_pr.get('description'):
                            st.markdown("**描述:**")
                            st.markdown(selected_pr['description'][:500] + '...' if len(selected_pr['description']) > 500 else selected_pr['description'])
                    
                    with col2:
                        st.markdown("**统计信息:**")
                        st.metric("➕ 新增行", selected_pr.get('additions', 0))
                        st.metric("➖ 删除行", selected_pr.get('deletions', 0))
                        st.metric("📁 变更文件", selected_pr.get('changed_files', 0))
                
                # 操作按钮
                if selected_pr['status'] == 'open':
                    col1, col2, col3 = st.columns([1, 1, 2])
                    
                    # 获取当前选中PR的数据库ID
                    db = MRDatabase()
                    selected_pr_db_id = selected_pr.get('db_id') or db.get_pr_id_by_number(selected_pr['repo_url'], selected_pr['pr_number'])
                    
                    if not selected_pr_db_id:
                        st.warning(f"⚠️ 无法找到PR #{selected_pr_num} 的数据库记录，请先刷新PR数据")
                    else:
                        col1, col2, col3 = st.columns([1, 1, 2])
                        
                        with col1:
                            if st.button("✅ Approve", type="primary", key=f"approve_{selected_pr_num}"):
                                # 记录approve操作
                                operation_id = db.record_operation(
                                    selected_pr_db_id, 
                                    'approve', 
                                    st.session_state.get('user_name', 'Unknown User'),
                                    f"通过Streamlit界面批准PR #{selected_pr_num}"
                                )
                                st.success(f"✅ 已批准PR #{selected_pr_num} (操作ID: {operation_id})")
                                # 清除操作历史缓存，强制刷新
                                if 'operation_history' in st.session_state:
                                    del st.session_state['operation_history']
                        
                        with col2:
                            if st.button("❌ Reject", type="secondary", key=f"reject_{selected_pr_num}"):
                                # 记录reject操作
                                operation_id = db.record_operation(
                                    selected_pr_db_id,
                                    'reject',
                                    st.session_state.get('user_name', 'Unknown User'),
                                    f"通过Streamlit界面拒绝PR #{selected_pr_num}"
                                )
                                st.error(f"❌ 已拒绝PR #{selected_pr_num} (操作ID: {operation_id})")
                                # 清除操作历史缓存，强制刷新
                                if 'operation_history' in st.session_state:
                                    del st.session_state['operation_history']
                        
                        with col3:
                            # 使用session state来管理评论输入
                            comment_key = f"comment_{selected_pr_num}"
                            comment = st.text_input(
                                "添加评论", 
                                placeholder="可选：添加操作备注",
                                key=comment_key
                            )
                            
                            if st.button("💬 添加评论", key=f"add_comment_{selected_pr_num}"):
                                if comment and comment.strip():
                                    operation_id = db.record_operation(
                                        selected_pr_db_id,
                                        'comment',
                                        st.session_state.get('user_name', 'Unknown User'),
                                        comment.strip()
                                    )
                                    st.success(f"💬 已添加评论到PR #{selected_pr_num} (操作ID: {operation_id})")
                                    # 清空评论输入框
                                    st.session_state[comment_key] = ""
                                    # 清除操作历史缓存，强制刷新
                                    if 'operation_history' in st.session_state:
                                        del st.session_state['operation_history']
                                    # 重新运行页面以更新显示
                                    st.rerun()
                                else:
                                    st.warning("请输入评论内容")
                else:
                    st.info(f"ℹ️ PR #{selected_pr_num} 状态为 {selected_pr['status']}，无法进行approve/reject操作")
        else:
            st.info("📭 暂无PR数据")
    
    # 操作历史
    st.markdown("#### 📜 操作历史")
    
    if st.button("🔄 刷新操作历史"):
        db = MRDatabase()
        operation_history = db.get_operation_history(limit=20)
        st.session_state['operation_history'] = operation_history
    
    if 'operation_history' in st.session_state:
        history = st.session_state['operation_history']
        
        if history:
            history_df = pd.DataFrame(history)
            history_df['operation_time'] = pd.to_datetime(history_df['operation_time']).dt.strftime('%Y-%m-%d %H:%M')
            
            st.dataframe(
                history_df[['operation_time', 'operation', 'operator', 'pr_title', 'comments']].rename(columns={
                    'operation_time': '操作时间',
                    'operation': '操作类型',
                    'operator': '操作人',
                    'pr_title': 'PR标题',
                    'comments': '备注'
                }),
                width='stretch'
            )
        else:
            st.info("📭 暂无操作历史")


if __name__ == "__main__":
    main()
