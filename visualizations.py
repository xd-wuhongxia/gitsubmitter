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
