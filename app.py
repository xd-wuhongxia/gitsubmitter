"""
Git提交历史统计分析 Streamlit 应用
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import os
from pathlib import Path
import git

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


def get_recent_repos() -> list:
    """获取最近使用的仓库列表"""
    # 从session state中获取最近使用的仓库
    if 'recent_repos' not in st.session_state:
        st.session_state.recent_repos = [
            ".",
            "..",
        ]
    
    # 添加一些常见路径（如果不存在）
    common_paths = [
        os.path.expanduser("~"),
        "D:/",
        "C:/",
    ]
    
    recent_list = st.session_state.recent_repos.copy()
    for path in common_paths:
        if path not in recent_list and os.path.exists(path):
            recent_list.append(path)
    
    return recent_list[:10]  # 最多显示10个


def add_to_recent_repos(repo_path: str):
    """添加仓库到最近使用列表"""
    if 'recent_repos' not in st.session_state:
        st.session_state.recent_repos = []
    
    # 移除已存在的相同路径
    if repo_path in st.session_state.recent_repos:
        st.session_state.recent_repos.remove(repo_path)
    
    # 添加到列表开头
    st.session_state.recent_repos.insert(0, repo_path)
    
    # 保持列表长度不超过10
    st.session_state.recent_repos = st.session_state.recent_repos[:10]


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
        recent_repos = get_recent_repos()
        repo_path = st.sidebar.selectbox(
            "选择最近使用的仓库",
            recent_repos,
            help="从最近使用的仓库中选择"
        )
    
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
    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.button("🔄 刷新", help="重新加载当前仓库数据"):
            st.rerun()
    with col2:
        if st.button("🗑️ 清除历史", help="清除最近使用的仓库历史"):
            st.session_state.recent_repos = []
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
        tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
            "📝 提交分析", "👥 作者分析", "⏰ 时间分析", 
            "🔀 合并分析", "📁 文件分析", "🌳 分支分析",
            "🌐 分支关系图", "🔀 合并方向历史"
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
