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
            repo_path: Git仓库路径或远程URL
        """
        self.repo_path = repo_path
        self.is_remote = self._is_remote_url(repo_path)
        self.temp_dir = None
        
        try:
            if self.is_remote:
                # 处理远程仓库
                self.repo = self._handle_remote_repo(repo_path)
            else:
                # 处理本地仓库
                self.repo = git.Repo(repo_path)
        except git.exc.InvalidGitRepositoryError:
            raise ValueError(f"路径 {repo_path} 不是有效的Git仓库")
        except Exception as e:
            raise ValueError(f"无法访问仓库 {repo_path}: {str(e)}")
    
    def _is_remote_url(self, repo_path: str) -> bool:
        """判断是否是远程仓库URL"""
        repo_path = repo_path.strip().lower()
        remote_patterns = [
            'http://', 'https://', 'git://', 'ssh://',
            'git@', '.git', 'github.com', 'gitlab.com', 'bitbucket.org'
        ]
        
        for pattern in remote_patterns:
            if pattern in repo_path:
                return True
        
        # 检查简化格式
        parts = repo_path.split('/')
        if len(parts) >= 2 and not repo_path.startswith('/') and '.' not in parts[0]:
            return True
        
        return False
    
    def _normalize_remote_url(self, repo_input: str) -> str:
        """标准化远程仓库URL"""
        repo_input = repo_input.strip()
        
        if repo_input.startswith(('http://', 'https://', 'git://', 'ssh://')):
            return repo_input
        
        if repo_input.startswith('git@'):
            return repo_input
        
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
    
    def _handle_remote_repo(self, repo_url: str):
        """处理远程仓库（临时克隆）"""
        import tempfile
        import shutil
        
        # 标准化URL
        normalized_url = self._normalize_remote_url(repo_url)
        
        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp(prefix="git_analyzer_")
        
        try:
            # 克隆仓库（浅克隆以提高性能）
            repo = git.Repo.clone_from(
                normalized_url,
                self.temp_dir,
                depth=100,  # 只克隆最近100个提交
                single_branch=True  # 只克隆默认分支
            )
            return repo
        except Exception as e:
            # 清理临时目录
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
            raise e
    
    def __del__(self):
        """析构函数，清理临时目录"""
        if hasattr(self, 'temp_dir') and self.temp_dir and os.path.exists(self.temp_dir):
            import shutil
            try:
                shutil.rmtree(self.temp_dir)
            except Exception:
                pass
    
    def get_repo_info(self) -> dict:
        """
        获取仓库基本信息
        
        Returns:
            包含仓库信息的字典
        """
        repo_info = {
            'path': os.path.abspath(self.repo_path),
            'remote_urls': [],
            'current_branch': None,
            'total_branches': 0,
            'is_bare': self.repo.bare
        }
        
        try:
            # 获取当前分支
            if not self.repo.head.is_detached:
                repo_info['current_branch'] = self.repo.active_branch.name
            else:
                repo_info['current_branch'] = 'HEAD (detached)'
        except Exception:
            repo_info['current_branch'] = 'unknown'
        
        try:
            # 获取所有remote URL
            for remote in self.repo.remotes:
                for url in remote.urls:
                    repo_info['remote_urls'].append({
                        'name': remote.name,
                        'url': url
                    })
        except Exception:
            pass
        
        try:
            # 获取分支总数
            repo_info['total_branches'] = len(list(self.repo.branches))
        except Exception:
            repo_info['total_branches'] = 0
        
        return repo_info
    
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
            
            # 确保日期是datetime对象
            commit_date = commit.committed_datetime
            if hasattr(commit_date, 'replace'):
                # 移除时区信息以避免兼容性问题
                commit_date = commit_date.replace(tzinfo=None)
            
            commits_data.append({
                'hash': commit.hexsha[:8],
                'full_hash': commit.hexsha,
                'author': commit.author.name,
                'author_email': commit.author.email,
                'date': commit_date,
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
                
                # 确保日期是datetime对象
                commit_date = commit.committed_datetime
                if hasattr(commit_date, 'replace'):
                    commit_date = commit_date.replace(tzinfo=None)
                
                merge_data.append({
                    'hash': commit.hexsha[:8],
                    'full_hash': commit.hexsha,
                    'author': commit.author.name,
                    'date': commit_date,
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
                    
                    # 确保日期是datetime对象
                    commit_date = last_commit.committed_datetime
                    if hasattr(commit_date, 'replace'):
                        commit_date = commit_date.replace(tzinfo=None)
                    
                    branch_data.append({
                        'branch_name': branch.name,
                        'last_commit_hash': last_commit.hexsha[:8],
                        'last_commit_date': commit_date,
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
    
    def get_branch_graph_data(self) -> dict:
        """
        获取分支关系图数据
        
        Returns:
            包含分支关系图信息的字典
        """
        graph_data = {
            'nodes': [],
            'edges': [],
            'commits': [],
            'branches': []
        }
        
        try:
            # 获取所有分支
            branches = list(self.repo.branches)
            
            # 获取所有提交及其分支关系
            commit_branch_map = {}
            
            for branch in branches:
                try:
                    commits = list(self.repo.iter_commits(branch, max_count=50))
                    for commit in commits:
                        if commit.hexsha not in commit_branch_map:
                            commit_branch_map[commit.hexsha] = []
                        commit_branch_map[commit.hexsha].append(branch.name)
                except Exception:
                    continue
            
            # 构建节点数据
            for commit_hash, branch_names in commit_branch_map.items():
                try:
                    commit = self.repo.commit(commit_hash)
                    
                    # 确保日期是datetime对象
                    commit_date = commit.committed_datetime
                    if hasattr(commit_date, 'replace'):
                        commit_date = commit_date.replace(tzinfo=None)
                    
                    graph_data['commits'].append({
                        'hash': commit.hexsha[:8],
                        'full_hash': commit.hexsha,
                        'author': commit.author.name,
                        'date': commit_date,
                        'message': commit.message.strip()[:50] + '...' if len(commit.message.strip()) > 50 else commit.message.strip(),
                        'branches': branch_names,
                        'parents': [p.hexsha for p in commit.parents],
                        'is_merge': len(commit.parents) > 1
                    })
                except Exception:
                    continue
            
            # 按时间排序提交
            graph_data['commits'].sort(key=lambda x: x['date'], reverse=True)
            
            # 构建边数据（父子关系）
            for commit in graph_data['commits']:
                for parent_hash in commit['parents']:
                    graph_data['edges'].append({
                        'source': parent_hash[:8],
                        'target': commit['hash'],
                        'type': 'parent_child'
                    })
            
            # 分支信息
            for branch in branches:
                try:
                    last_commit = branch.commit
                    commit_count = len(list(self.repo.iter_commits(branch, max_count=100)))
                    
                    graph_data['branches'].append({
                        'name': branch.name,
                        'last_commit': last_commit.hexsha[:8],
                        'commits_count': commit_count,
                        'is_active': branch == self.repo.active_branch
                    })
                except Exception:
                    continue
                    
        except Exception:
            pass
        
        return graph_data
    
    def get_merge_direction_history(self) -> pd.DataFrame:
        """
        获取合并方向历史
        
        Returns:
            包含合并方向历史的DataFrame
        """
        merge_history = []
        
        try:
            # 获取所有合并提交
            commits = list(self.repo.iter_commits("HEAD", max_count=200))
            
            for commit in commits:
                if len(commit.parents) > 1:  # 合并提交
                    try:
                        # 分析合并信息
                        merge_info = self._analyze_merge_commit(commit)
                        if merge_info:
                            merge_history.append(merge_info)
                    except Exception:
                        continue
                        
        except Exception:
            pass
        
        return pd.DataFrame(merge_history)
    
    def _analyze_merge_commit(self, commit) -> dict:
        """
        分析合并提交的详细信息
        
        Args:
            commit: Git提交对象
            
        Returns:
            合并信息字典
        """
        try:
            # 确保日期是datetime对象
            commit_date = commit.committed_datetime
            if hasattr(commit_date, 'replace'):
                commit_date = commit_date.replace(tzinfo=None)
            
            # 解析合并消息
            message = commit.message.strip()
            source_branch = "unknown"
            target_branch = "unknown"
            
            # 尝试从提交消息中提取分支信息
            merge_patterns = [
                r"Merge branch '([^']+)' into ([^\s]+)",
                r"Merge branch '([^']+)'",
                r"Merge pull request #\d+ from ([^\s]+)",
                r"Merge ([^\s]+) into ([^\s]+)"
            ]
            
            for pattern in merge_patterns:
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    if len(match.groups()) >= 2:
                        source_branch = match.group(1)
                        target_branch = match.group(2)
                    else:
                        source_branch = match.group(1)
                        target_branch = "main"  # 默认目标分支
                    break
            
            # 获取父提交信息
            parents_info = []
            for i, parent in enumerate(commit.parents):
                parents_info.append({
                    'hash': parent.hexsha[:8],
                    'author': parent.author.name,
                    'message': parent.message.strip()[:30] + '...' if len(parent.message.strip()) > 30 else parent.message.strip()
                })
            
            # 计算合并统计
            stats = commit.stats.total
            
            return {
                'hash': commit.hexsha[:8],
                'full_hash': commit.hexsha,
                'author': commit.author.name,
                'date': commit_date,
                'message': message[:100] + '...' if len(message) > 100 else message,
                'source_branch': source_branch,
                'target_branch': target_branch,
                'parents_count': len(commit.parents),
                'parents_info': parents_info,
                'files_changed': stats['files'],
                'insertions': stats['insertions'],
                'deletions': stats['deletions'],
                'merge_type': self._classify_merge_type(message)
            }
            
        except Exception:
            return None
    
    def _classify_merge_type(self, message: str) -> str:
        """
        分类合并类型
        
        Args:
            message: 提交消息
            
        Returns:
            合并类型
        """
        message_lower = message.lower()
        
        if 'pull request' in message_lower or 'pr' in message_lower:
            return 'Pull Request'
        elif 'feature' in message_lower:
            return 'Feature Branch'
        elif 'hotfix' in message_lower or 'fix' in message_lower:
            return 'Hotfix'
        elif 'release' in message_lower:
            return 'Release Branch'
        elif 'develop' in message_lower:
            return 'Development Branch'
        else:
            return 'Regular Merge'
