"""
数据可视化组件模块
提供各种图表和可视化功能
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


class GitVisualizer:
    """Git数据可视化器"""
    
    def __init__(self):
        """初始化可视化器"""
        self.color_palette = px.colors.qualitative.Set3
    
    def plot_commit_timeline(self, commits_df: pd.DataFrame) -> go.Figure:
        """
        绘制提交时间线图
        
        Args:
            commits_df: 提交数据DataFrame
            
        Returns:
            Plotly图表对象
        """
        if commits_df.empty:
            return self._empty_figure("暂无提交数据")
        
        fig = px.scatter(
            commits_df,
            x='date',
            y='lines_changed',
            color='author',
            size='files_changed',
            hover_data=['hash', 'message'],
            title='提交时间线 - 代码变更量',
            labels={
                'date': '提交日期',
                'lines_changed': '代码行变更数',
                'author': '作者',
                'files_changed': '文件变更数'
            }
        )
        
        fig.update_layout(
            xaxis_title="提交日期",
            yaxis_title="代码行变更数",
            height=500
        )
        
        return fig
    
    def plot_author_contributions(self, author_stats_df: pd.DataFrame) -> go.Figure:
        """
        绘制作者贡献饼图
        
        Args:
            author_stats_df: 作者统计DataFrame
            
        Returns:
            Plotly图表对象
        """
        if author_stats_df.empty:
            return self._empty_figure("暂无作者数据")
        
        fig = px.pie(
            author_stats_df,
            values='commits_count',
            names='author',
            title='作者提交贡献分布',
            color_discrete_sequence=self.color_palette
        )
        
        fig.update_traces(textposition='inside', textinfo='percent+label')
        fig.update_layout(height=500)
        
        return fig
    
    def plot_commit_heatmap(self, time_series_df: pd.DataFrame) -> go.Figure:
        """
        绘制提交活跃度热力图
        
        Args:
            time_series_df: 时间序列DataFrame
            
        Returns:
            Plotly图表对象
        """
        if time_series_df.empty:
            return self._empty_figure("暂无时间序列数据")
        
        # 添加星期和小时信息
        df = time_series_df.copy()
        df['date'] = pd.to_datetime(df['date'])
        df['weekday'] = df['date'].dt.day_name()
        df['hour'] = df['date'].dt.hour
        
        # 创建热力图数据
        heatmap_data = df.groupby(['weekday', 'hour'])['commits'].sum().reset_index()
        
        # 重新排列星期顺序
        weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        heatmap_pivot = heatmap_data.pivot(index='weekday', columns='hour', values='commits').fillna(0)
        heatmap_pivot = heatmap_pivot.reindex(weekday_order)
        
        fig = px.imshow(
            heatmap_pivot,
            labels=dict(x="小时", y="星期", color="提交次数"),
            title="提交活跃度热力图",
            aspect="auto"
        )
        
        fig.update_layout(height=400)
        
        return fig
    
    def plot_lines_trend(self, time_series_df: pd.DataFrame) -> go.Figure:
        """
        绘制代码行数变化趋势图
        
        Args:
            time_series_df: 时间序列DataFrame
            
        Returns:
            Plotly图表对象
        """
        if time_series_df.empty:
            return self._empty_figure("暂无时间序列数据")
        
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            subplot_titles=('代码行数变化', '提交数量'),
            vertical_spacing=0.1
        )
        
        # 添加代码行数变化
        fig.add_trace(
            go.Scatter(
                x=time_series_df['date'],
                y=time_series_df['insertions'],
                mode='lines+markers',
                name='新增行数',
                line=dict(color='green')
            ),
            row=1, col=1
        )
        
        fig.add_trace(
            go.Scatter(
                x=time_series_df['date'],
                y=time_series_df['deletions'],
                mode='lines+markers',
                name='删除行数',
                line=dict(color='red')
            ),
            row=1, col=1
        )
        
        # 添加提交数量
        fig.add_trace(
            go.Bar(
                x=time_series_df['date'],
                y=time_series_df['commits'],
                name='提交次数',
                marker_color='lightblue'
            ),
            row=2, col=1
        )
        
        fig.update_layout(
            title="代码变更趋势分析",
            height=600,
            showlegend=True
        )
        
        return fig
    
    def plot_file_changes_distribution(self, file_stats_df: pd.DataFrame) -> go.Figure:
        """
        绘制文件修改分布图
        
        Args:
            file_stats_df: 文件统计DataFrame
            
        Returns:
            Plotly图表对象
        """
        if file_stats_df.empty:
            return self._empty_figure("暂无文件统计数据")
        
        # 按文件扩展名分组
        ext_stats = file_stats_df.groupby('file_extension').agg({
            'modifications': 'sum',
            'total_changes': 'sum',
            'file_path': 'count'
        }).rename(columns={'file_path': 'file_count'}).reset_index()
        
        fig = px.treemap(
            ext_stats,
            path=['file_extension'],
            values='total_changes',
            title='文件类型修改分布',
            color='modifications',
            hover_data=['file_count'],
            color_continuous_scale='Viridis'
        )
        
        fig.update_layout(height=500)
        
        return fig
    
    def plot_merge_frequency(self, merge_stats_df: pd.DataFrame) -> go.Figure:
        """
        绘制合并频率图
        
        Args:
            merge_stats_df: 合并统计DataFrame
            
        Returns:
            Plotly图表对象
        """
        if merge_stats_df.empty:
            return self._empty_figure("暂无合并数据")
        
        # 按日期聚合合并次数
        merge_daily = merge_stats_df.copy()
        merge_daily['date'] = pd.to_datetime(merge_daily['date']).dt.date
        daily_merges = merge_daily.groupby('date').size().reset_index(name='merge_count')
        daily_merges['date'] = pd.to_datetime(daily_merges['date'])
        
        fig = px.bar(
            daily_merges,
            x='date',
            y='merge_count',
            title='合并频率统计',
            labels={'date': '日期', 'merge_count': '合并次数'}
        )
        
        fig.update_layout(height=400)
        
        return fig
    
    def plot_branch_activity(self, branch_stats_df: pd.DataFrame) -> go.Figure:
        """
        绘制分支活跃度图
        
        Args:
            branch_stats_df: 分支统计DataFrame
            
        Returns:
            Plotly图表对象
        """
        if branch_stats_df.empty:
            return self._empty_figure("暂无分支数据")
        
        # 按提交数量排序
        branch_stats_sorted = branch_stats_df.sort_values('commits_count', ascending=True)
        
        fig = px.bar(
            branch_stats_sorted,
            x='commits_count',
            y='branch_name',
            orientation='h',
            title='分支活跃度 (提交数量)',
            labels={'commits_count': '提交次数', 'branch_name': '分支名称'},
            color='commits_count',
            color_continuous_scale='Blues'
        )
        
        fig.update_layout(height=max(400, len(branch_stats_sorted) * 30))
        
        return fig
    
    def plot_author_activity_matrix(self, commits_df: pd.DataFrame) -> go.Figure:
        """
        绘制作者活跃度矩阵
        
        Args:
            commits_df: 提交数据DataFrame
            
        Returns:
            Plotly图表对象
        """
        if commits_df.empty:
            return self._empty_figure("暂无提交数据")
        
        # 准备数据
        df = commits_df.copy()
        df['date'] = pd.to_datetime(df['date'])
        df['week'] = df['date'].dt.isocalendar().week
        df['year'] = df['date'].dt.year
        df['year_week'] = df['year'].astype(str) + '-W' + df['week'].astype(str).str.zfill(2)
        
        # 创建作者-周活跃度矩阵
        activity_matrix = df.groupby(['author', 'year_week']).size().reset_index(name='commits')
        
        fig = px.density_heatmap(
            activity_matrix,
            x='year_week',
            y='author',
            z='commits',
            title='作者活跃度矩阵',
            labels={'year_week': '年-周', 'author': '作者', 'commits': '提交次数'}
        )
        
        fig.update_layout(height=max(400, len(df['author'].unique()) * 40))
        
        return fig
    
    def plot_branch_network_graph(self, graph_data: dict) -> go.Figure:
        """
        绘制分支网络关系图
        
        Args:
            graph_data: 分支关系图数据
            
        Returns:
            Plotly图表对象
        """
        if not graph_data['commits']:
            return self._empty_figure("暂无分支关系数据")
        
        # 创建网络图
        fig = go.Figure()
        
        # 为每个分支分配颜色
        branch_colors = {}
        colors = px.colors.qualitative.Set3
        for i, branch_info in enumerate(graph_data['branches']):
            branch_colors[branch_info['name']] = colors[i % len(colors)]
        
        # 创建节点位置布局
        commits = graph_data['commits'][:30]  # 限制显示数量
        node_positions = self._calculate_node_positions(commits, graph_data['edges'])
        
        # 绘制边（连接线）
        for edge in graph_data['edges']:
            source_pos = node_positions.get(edge['source'])
            target_pos = node_positions.get(edge['target'])
            
            if source_pos and target_pos:
                fig.add_trace(go.Scatter(
                    x=[source_pos[0], target_pos[0], None],
                    y=[source_pos[1], target_pos[1], None],
                    mode='lines',
                    line=dict(color='lightgray', width=1),
                    hoverinfo='none',
                    showlegend=False
                ))
        
        # 绘制节点（提交）
        for commit in commits:
            pos = node_positions.get(commit['hash'])
            if not pos:
                continue
                
            # 确定节点颜色（基于主要分支）
            primary_branch = commit['branches'][0] if commit['branches'] else 'unknown'
            node_color = branch_colors.get(primary_branch, 'gray')
            
            # 节点大小基于是否为合并提交
            node_size = 15 if commit['is_merge'] else 10
            
            fig.add_trace(go.Scatter(
                x=[pos[0]],
                y=[pos[1]],
                mode='markers',
                marker=dict(
                    size=node_size,
                    color=node_color,
                    line=dict(width=2, color='white'),
                    symbol='diamond' if commit['is_merge'] else 'circle'
                ),
                text=f"<b>{commit['hash']}</b><br>" +
                     f"作者: {commit['author']}<br>" +
                     f"分支: {', '.join(commit['branches'])}<br>" +
                     f"消息: {commit['message']}<br>" +
                     f"日期: {commit['date'].strftime('%Y-%m-%d %H:%M')}" +
                     f"<br>{'🔀 合并提交' if commit['is_merge'] else '📝 普通提交'}",
                hovertemplate='%{text}<extra></extra>',
                name=primary_branch,
                showlegend=primary_branch not in [trace.name for trace in fig.data if hasattr(trace, 'name')]
            ))
        
        fig.update_layout(
            title="Git分支关系网络图",
            xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
            yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
            height=600,
            showlegend=True,
            legend=dict(title="分支"),
            hovermode='closest'
        )
        
        return fig
    
    def plot_merge_direction_flow(self, merge_history_df: pd.DataFrame) -> go.Figure:
        """
        绘制合并方向流程图
        
        Args:
            merge_history_df: 合并历史DataFrame
            
        Returns:
            Plotly图表对象
        """
        if merge_history_df.empty:
            return self._empty_figure("暂无合并历史数据")
        
        # 创建桑基图显示合并流向
        fig = go.Figure()
        
        # 统计分支间的合并流向
        merge_flows = merge_history_df.groupby(['source_branch', 'target_branch']).size().reset_index(name='count')
        
        # 获取所有唯一的分支
        all_branches = list(set(merge_flows['source_branch'].tolist() + merge_flows['target_branch'].tolist()))
        branch_indices = {branch: i for i, branch in enumerate(all_branches)}
        
        # 准备桑基图数据
        source_indices = [branch_indices[branch] for branch in merge_flows['source_branch']]
        target_indices = [branch_indices[branch] for branch in merge_flows['target_branch']]
        values = merge_flows['count'].tolist()
        
        fig.add_trace(go.Sankey(
            node=dict(
                pad=15,
                thickness=20,
                line=dict(color="black", width=0.5),
                label=all_branches,
                color="lightblue"
            ),
            link=dict(
                source=source_indices,
                target=target_indices,
                value=values,
                color="lightgray"
            )
        ))
        
        fig.update_layout(
            title="分支合并流向图",
            height=500
        )
        
        return fig
    
    def plot_merge_timeline(self, merge_history_df: pd.DataFrame) -> go.Figure:
        """
        绘制合并时间线图
        
        Args:
            merge_history_df: 合并历史DataFrame
            
        Returns:
            Plotly图表对象
        """
        if merge_history_df.empty:
            return self._empty_figure("暂无合并历史数据")
        
        # 按合并类型分组
        merge_types = merge_history_df['merge_type'].unique()
        colors = px.colors.qualitative.Set3
        
        fig = go.Figure()
        
        for i, merge_type in enumerate(merge_types):
            type_data = merge_history_df[merge_history_df['merge_type'] == merge_type]
            
            fig.add_trace(go.Scatter(
                x=type_data['date'],
                y=[merge_type] * len(type_data),
                mode='markers',
                marker=dict(
                    size=12,
                    color=colors[i % len(colors)],
                    symbol='diamond'
                ),
                name=merge_type,
                text=[
                    f"<b>{row['hash']}</b><br>" +
                    f"作者: {row['author']}<br>" +
                    f"从 {row['source_branch']} 合并到 {row['target_branch']}<br>" +
                    f"文件变更: {row['files_changed']}<br>" +
                    f"代码行: +{row['insertions']} -{row['deletions']}<br>" +
                    f"消息: {row['message'][:50]}..."
                    for _, row in type_data.iterrows()
                ],
                hovertemplate='%{text}<extra></extra>'
            ))
        
        fig.update_layout(
            title="合并历史时间线",
            xaxis_title="时间",
            yaxis_title="合并类型",
            height=500,
            hovermode='closest'
        )
        
        return fig
    
    def plot_merge_statistics(self, merge_history_df: pd.DataFrame) -> go.Figure:
        """
        绘制合并统计图表
        
        Args:
            merge_history_df: 合并历史DataFrame
            
        Returns:
            Plotly图表对象
        """
        if merge_history_df.empty:
            return self._empty_figure("暂无合并统计数据")
        
        # 创建子图
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('合并类型分布', '合并作者统计', '合并代码变更', '分支合并频率'),
            specs=[[{"type": "pie"}, {"type": "bar"}],
                   [{"type": "scatter"}, {"type": "bar"}]]
        )
        
        # 合并类型分布饼图
        merge_type_counts = merge_history_df['merge_type'].value_counts()
        fig.add_trace(
            go.Pie(
                labels=merge_type_counts.index,
                values=merge_type_counts.values,
                name="合并类型"
            ),
            row=1, col=1
        )
        
        # 合并作者统计柱状图
        author_counts = merge_history_df['author'].value_counts().head(10)
        fig.add_trace(
            go.Bar(
                x=author_counts.index,
                y=author_counts.values,
                name="作者合并次数"
            ),
            row=1, col=2
        )
        
        # 合并代码变更散点图
        fig.add_trace(
            go.Scatter(
                x=merge_history_df['insertions'],
                y=merge_history_df['deletions'],
                mode='markers',
                marker=dict(
                    size=merge_history_df['files_changed'],
                    color=merge_history_df['files_changed'],
                    colorscale='Viridis',
                    showscale=True
                ),
                name="代码变更",
                text=[f"Hash: {row['hash']}<br>文件: {row['files_changed']}" 
                      for _, row in merge_history_df.iterrows()],
                hovertemplate='新增: %{x}<br>删除: %{y}<br>%{text}<extra></extra>'
            ),
            row=2, col=1
        )
        
        # 分支合并频率
        branch_merge_counts = merge_history_df['source_branch'].value_counts().head(10)
        fig.add_trace(
            go.Bar(
                x=branch_merge_counts.index,
                y=branch_merge_counts.values,
                name="分支合并频率"
            ),
            row=2, col=2
        )
        
        fig.update_layout(
            title="合并统计总览",
            height=800,
            showlegend=False
        )
        
        return fig
    
    def _calculate_node_positions(self, commits: list, edges: list) -> dict:
        """
        计算节点位置（简单的层次布局）
        
        Args:
            commits: 提交列表
            edges: 边列表
            
        Returns:
            节点位置字典
        """
        positions = {}
        
        # 按时间排序
        sorted_commits = sorted(commits, key=lambda x: x['date'])
        
        # 简单的网格布局
        cols = 5
        for i, commit in enumerate(sorted_commits):
            row = i // cols
            col = i % cols
            positions[commit['hash']] = (col * 2, -row * 2)
        
        return positions
    
    def _empty_figure(self, message: str) -> go.Figure:
        """
        创建空图表
        
        Args:
            message: 显示消息
            
        Returns:
            空的Plotly图表
        """
        fig = go.Figure()
        fig.add_annotation(
            text=message,
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            xanchor='center', yanchor='middle',
            showarrow=False,
            font=dict(size=16)
        )
        fig.update_layout(
            xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
            yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
            height=400
        )
        return fig
