"""
Git仓库分析模块
提供Git提交历史、合并历史等统计分析功能
"""

import git
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import re
from typing import Dict, List, Tuple, Optional
import os


class GitAnalyzer:
    """Git仓库分析器"""
    
    def __init__(self, repo_path: str = "."):
        """
        初始化Git分析器
        
        Args:
            repo_path: Git仓库路径
        """
        try:
            self.repo = git.Repo(repo_path)
        except git.exc.InvalidGitRepositoryError:
            raise ValueError(f"路径 {repo_path} 不是有效的Git仓库")
        
        self.repo_path = repo_path
    
    def get_commit_stats(self, 
                        since_date: Optional[datetime] = None,
                        until_date: Optional[datetime] = None,
                        branch: str = "HEAD") -> pd.DataFrame:
        """
        获取提交统计信息
        
        Args:
            since_date: 开始日期
            until_date: 结束日期  
            branch: 分析的分支
            
        Returns:
            包含提交信息的DataFrame
        """
        commits_data = []
        
        # 设置时间范围
        kwargs = {}
        if since_date:
            kwargs['since'] = since_date
        if until_date:
            kwargs['until'] = until_date
            
        try:
            commits = list(self.repo.iter_commits(branch, **kwargs))
        except git.exc.GitCommandError:
            commits = []
        
        for commit in commits:
            # 获取提交统计
            stats = commit.stats.total
            
            commits_data.append({
                'hash': commit.hexsha[:8],
                'full_hash': commit.hexsha,
                'author': commit.author.name,
                'author_email': commit.author.email,
                'date': commit.committed_datetime,
                'message': commit.message.strip(),
                'files_changed': stats['files'],
                'insertions': stats['insertions'],
                'deletions': stats['deletions'],
                'lines_changed': stats['insertions'] + stats['deletions']
            })
        
        return pd.DataFrame(commits_data)
    
    def get_merge_stats(self, 
                       since_date: Optional[datetime] = None,
                       until_date: Optional[datetime] = None) -> pd.DataFrame:
        """
        获取合并统计信息
        
        Args:
            since_date: 开始日期
            until_date: 结束日期
            
        Returns:
            包含合并信息的DataFrame
        """
        merge_data = []
        
        # 设置时间范围
        kwargs = {}
        if since_date:
            kwargs['since'] = since_date
        if until_date:
            kwargs['until'] = until_date
        
        try:
            commits = list(self.repo.iter_commits("HEAD", **kwargs))
        except git.exc.GitCommandError:
            commits = []
        
        for commit in commits:
            # 检查是否是合并提交（有多个父提交）
            if len(commit.parents) > 1:
                # 解析合并信息
                merge_pattern = r"Merge.*?(\w+).*?into.*?(\w+)"
                match = re.search(merge_pattern, commit.message, re.IGNORECASE)
                
                source_branch = "unknown"
                target_branch = "unknown"
                
                if match:
                    source_branch = match.group(1)
                    target_branch = match.group(2)
                
                merge_data.append({
                    'hash': commit.hexsha[:8],
                    'full_hash': commit.hexsha,
                    'author': commit.author.name,
                    'date': commit.committed_datetime,
                    'message': commit.message.strip(),
                    'source_branch': source_branch,
                    'target_branch': target_branch,
                    'parents_count': len(commit.parents)
                })
        
        return pd.DataFrame(merge_data)
    
    def get_author_stats(self, 
                        since_date: Optional[datetime] = None,
                        until_date: Optional[datetime] = None) -> pd.DataFrame:
        """
        获取作者统计信息
        
        Args:
            since_date: 开始日期
            until_date: 结束日期
            
        Returns:
            包含作者统计的DataFrame
        """
        commits_df = self.get_commit_stats(since_date, until_date)
        
        if commits_df.empty:
            return pd.DataFrame()
        
        author_stats = commits_df.groupby('author').agg({
            'hash': 'count',
            'files_changed': 'sum',
            'insertions': 'sum',
            'deletions': 'sum',
            'lines_changed': 'sum',
            'date': ['min', 'max']
        }).round(2)
        
        # 重命名列
        author_stats.columns = [
            'commits_count', 'total_files_changed', 'total_insertions',
            'total_deletions', 'total_lines_changed', 'first_commit', 'last_commit'
        ]
        
        # 计算活跃天数
        author_stats['active_days'] = (
            author_stats['last_commit'] - author_stats['first_commit']
        ).dt.days + 1
        
        # 计算平均每次提交的变更
        author_stats['avg_lines_per_commit'] = (
            author_stats['total_lines_changed'] / author_stats['commits_count']
        ).round(2)
        
        return author_stats.reset_index()
    
    def get_file_stats(self, 
                      since_date: Optional[datetime] = None,
                      until_date: Optional[datetime] = None) -> pd.DataFrame:
        """
        获取文件修改统计
        
        Args:
            since_date: 开始日期
            until_date: 结束日期
            
        Returns:
            包含文件统计的DataFrame
        """
        file_changes = defaultdict(lambda: {
            'modifications': 0,
            'insertions': 0,
            'deletions': 0,
            'authors': set()
        })
        
        # 设置时间范围
        kwargs = {}
        if since_date:
            kwargs['since'] = since_date
        if until_date:
            kwargs['until'] = until_date
        
        try:
            commits = list(self.repo.iter_commits("HEAD", **kwargs))
        except git.exc.GitCommandError:
            commits = []
        
        for commit in commits:
            try:
                # 获取每个提交的文件变更
                for file_path, stats in commit.stats.files.items():
                    file_changes[file_path]['modifications'] += 1
                    file_changes[file_path]['insertions'] += stats['insertions']
                    file_changes[file_path]['deletions'] += stats['deletions']
                    file_changes[file_path]['authors'].add(commit.author.name)
            except Exception:
                continue
        
        # 转换为DataFrame
        file_data = []
        for file_path, stats in file_changes.items():
            file_data.append({
                'file_path': file_path,
                'modifications': stats['modifications'],
                'insertions': stats['insertions'],
                'deletions': stats['deletions'],
                'total_changes': stats['insertions'] + stats['deletions'],
                'authors_count': len(stats['authors']),
                'file_extension': os.path.splitext(file_path)[1] or 'no_ext'
            })
        
        return pd.DataFrame(file_data)
    
    def get_branch_stats(self) -> pd.DataFrame:
        """
        获取分支统计信息
        
        Returns:
            包含分支信息的DataFrame
        """
        branch_data = []
        
        try:
            # 获取所有分支
            branches = list(self.repo.branches)
            
            for branch in branches:
                try:
                    # 获取分支的最后提交
                    last_commit = branch.commit
                    
                    # 计算分支的提交数量
                    commit_count = len(list(self.repo.iter_commits(branch)))
                    
                    branch_data.append({
                        'branch_name': branch.name,
                        'last_commit_hash': last_commit.hexsha[:8],
                        'last_commit_date': last_commit.committed_datetime,
                        'last_author': last_commit.author.name,
                        'commits_count': commit_count,
                        'is_active': branch == self.repo.active_branch
                    })
                except Exception:
                    continue
                    
        except Exception:
            pass
        
        return pd.DataFrame(branch_data)
    
    def get_time_series_stats(self, 
                             period: str = 'D',
                             since_date: Optional[datetime] = None,
                             until_date: Optional[datetime] = None) -> pd.DataFrame:
        """
        获取时间序列统计
        
        Args:
            period: 时间周期 ('D'=天, 'W'=周, 'M'=月)
            since_date: 开始日期
            until_date: 结束日期
            
        Returns:
            包含时间序列统计的DataFrame
        """
        commits_df = self.get_commit_stats(since_date, until_date)
        
        if commits_df.empty:
            return pd.DataFrame()
        
        # 设置日期索引
        commits_df['date'] = pd.to_datetime(commits_df['date'])
        commits_df.set_index('date', inplace=True)
        
        # 按时间周期聚合
        time_stats = commits_df.resample(period).agg({
            'hash': 'count',
            'files_changed': 'sum',
            'insertions': 'sum',
            'deletions': 'sum',
            'lines_changed': 'sum',
            'author': lambda x: len(set(x))
        })
        
        # 重命名列
        time_stats.columns = [
            'commits', 'files_changed', 'insertions', 
            'deletions', 'lines_changed', 'unique_authors'
        ]
        
        return time_stats.reset_index()
