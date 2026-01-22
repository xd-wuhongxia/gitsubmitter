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
            
            # 设置Git配置以正确处理UTF-8编码
            try:
                with self.repo.config_writer() as git_config:
                    git_config.set_value('i18n', 'commitEncoding', 'utf-8')
                    git_config.set_value('i18n', 'logOutputEncoding', 'utf-8')
            except Exception:
                # 如果配置写入失败，继续执行（某些只读仓库可能会失败）
                pass
                
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
            # 尝试浅克隆（更深的历史以减少统计错误）
            try:
                repo = git.Repo.clone_from(
                    normalized_url,
                    self.temp_dir,
                    depth=500,  # 增加到500个提交以获得更完整的统计
                    single_branch=True
                )
                return repo
            except git.exc.GitCommandError:
                # 如果浅克隆失败，尝试完整克隆
                import shutil
                if os.path.exists(self.temp_dir):
                    shutil.rmtree(self.temp_dir)
                self.temp_dir = tempfile.mkdtemp(prefix="git_analyzer_full_")
                
                repo = git.Repo.clone_from(
                    normalized_url,
                    self.temp_dir
                    # 不使用depth参数，进行完整克隆
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
        # 对于远程仓库，显示原始URL而不是临时路径
        if self.is_remote:
            display_path = self._normalize_remote_url(self.repo_path)
        else:
            display_path = os.path.abspath(self.repo_path)
            
        repo_info = {
            'path': display_path,
            'original_path': self.repo_path,  # 保存原始输入
            'is_remote': self.is_remote,
            'temp_dir': self.temp_dir if self.is_remote else None,
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
            try:
                # 获取提交统计 - 对于浅克隆需要特殊处理
                stats = commit.stats.total
            except git.exc.GitCommandError as e:
                # 浅克隆中可能无法访问某些提交的统计信息
                if "bad object" in str(e) or "fatal:" in str(e):
                    stats = {'files': 0, 'insertions': 0, 'deletions': 0}
                else:
                    raise e
            except Exception:
                # 其他统计获取错误，使用默认值
                stats = {'files': 0, 'insertions': 0, 'deletions': 0}
            
            # 确保日期是datetime对象
            commit_date = commit.committed_datetime
            if hasattr(commit_date, 'replace'):
                # 移除时区信息以避免兼容性问题
                commit_date = commit_date.replace(tzinfo=None)
            
            # 处理commit message的编码
            try:
                # 尝试获取正确编码的message
                if isinstance(commit.message, bytes):
                    message = commit.message.decode('utf-8', errors='replace').strip()
                else:
                    message = commit.message.strip()
            except Exception:
                message = str(commit.message).strip()
            
            commits_data.append({
                'hash': commit.hexsha[:8],
                'full_hash': commit.hexsha,
                'author': commit.author.name,
                'author_email': commit.author.email,
                'date': commit_date,
                'message': message,
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
                # 处理commit message的编码
                try:
                    if isinstance(commit.message, bytes):
                        message = commit.message.decode('utf-8', errors='replace').strip()
                    else:
                        message = commit.message.strip()
                except Exception:
                    message = str(commit.message).strip()
                
                # 解析合并信息
                merge_pattern = r"Merge.*?(\w+).*?into.*?(\w+)"
                match = re.search(merge_pattern, message, re.IGNORECASE)
                
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
                    'message': message,
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
                # 获取每个提交的文件变更 - 处理浅克隆问题
                try:
                    files_stats = commit.stats.files
                except git.exc.GitCommandError as e:
                    if "bad object" in str(e) or "fatal:" in str(e):
                        continue  # 跳过无法访问的提交
                    else:
                        raise e
                
                for file_path, stats in files_stats.items():
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
                    
                    # 处理commit message的编码
                    try:
                        if isinstance(commit.message, bytes):
                            message = commit.message.decode('utf-8', errors='replace').strip()
                        else:
                            message = commit.message.strip()
                    except Exception:
                        message = str(commit.message).strip()
                    
                    # 截断长消息
                    display_message = message[:50] + '...' if len(message) > 50 else message
                    
                    graph_data['commits'].append({
                        'hash': commit.hexsha[:8],
                        'full_hash': commit.hexsha,
                        'author': commit.author.name,
                        'date': commit_date,
                        'message': display_message,
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
            
            # 处理commit message的编码
            try:
                if isinstance(commit.message, bytes):
                    message = commit.message.decode('utf-8', errors='replace').strip()
                else:
                    message = commit.message.strip()
            except Exception:
                message = str(commit.message).strip()
            
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
                # 处理父提交message的编码
                try:
                    if isinstance(parent.message, bytes):
                        parent_message = parent.message.decode('utf-8', errors='replace').strip()
                    else:
                        parent_message = parent.message.strip()
                except Exception:
                    parent_message = str(parent.message).strip()
                
                display_parent_message = parent_message[:30] + '...' if len(parent_message) > 30 else parent_message
                
                parents_info.append({
                    'hash': parent.hexsha[:8],
                    'author': parent.author.name,
                    'message': display_parent_message
                })
            
            # 计算合并统计 - 处理浅克隆问题
            try:
                stats = commit.stats.total
            except git.exc.GitCommandError as e:
                if "bad object" in str(e) or "fatal:" in str(e):
                    stats = {'files': 0, 'insertions': 0, 'deletions': 0}
                else:
                    raise e
            except Exception:
                stats = {'files': 0, 'insertions': 0, 'deletions': 0}
            
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
    
    def get_file_tree(self, branch: str = "HEAD") -> Dict:
        """
        获取仓库文件树结构
        
        Args:
            branch: 分支名称
            
        Returns:
            树形结构字典，包含文件和目录信息
        """
        try:
            commit = self.repo.commit(branch)
            tree = commit.tree
            
            def build_tree(tree_obj, path=""):
                """递归构建文件树"""
                result = {
                    "name": os.path.basename(path) if path else "/",
                    "path": path or "/",
                    "type": "directory",
                    "children": []
                }
                
                for item in tree_obj:
                    item_path = f"{path}/{item.name}" if path else item.name
                    
                    if item.type == "tree":
                        # 目录
                        child = build_tree(item, item_path)
                        result["children"].append(child)
                    else:
                        # 文件
                        file_info = {
                            "name": item.name,
                            "path": item_path,
                            "type": "file",
                            "size": item.size,
                            "extension": os.path.splitext(item.name)[1] or "no_ext",
                            "mode": oct(item.mode)
                        }
                        result["children"].append(file_info)
                
                # 排序：目录在前，文件在后，各自按名称排序
                result["children"].sort(key=lambda x: (0 if x["type"] == "directory" else 1, x["name"].lower()))
                
                return result
            
            return build_tree(tree)
            
        except Exception as e:
            return {"name": "/", "path": "/", "type": "directory", "children": [], "error": str(e)}
    
    def get_all_files(self, branch: str = "HEAD") -> List[Dict]:
        """
        获取仓库中所有文件的扁平列表
        
        Args:
            branch: 分支名称
            
        Returns:
            文件信息列表
        """
        files = []
        
        try:
            commit = self.repo.commit(branch)
            tree = commit.tree
            
            def traverse_tree(tree_obj, path=""):
                for item in tree_obj:
                    item_path = f"{path}/{item.name}" if path else item.name
                    
                    if item.type == "tree":
                        traverse_tree(item, item_path)
                    else:
                        files.append({
                            "name": item.name,
                            "path": item_path,
                            "size": item.size,
                            "extension": os.path.splitext(item.name)[1] or "no_ext",
                            "directory": path or "/"
                        })
            
            traverse_tree(tree)
            
        except Exception as e:
            pass
        
        return files
    
    def get_file_history(self, file_path: str, max_commits: int = 50, 
                         since_date: Optional[datetime] = None,
                         until_date: Optional[datetime] = None) -> List[Dict]:
        """
        获取指定文件的提交历史
        
        Args:
            file_path: 文件路径
            max_commits: 最大返回提交数
            since_date: 开始日期
            until_date: 结束日期
            
        Returns:
            提交历史列表
        """
        history = []
        
        try:
            # 构建git log参数
            kwargs = {'paths': file_path, 'max_count': max_commits}
            if since_date:
                kwargs['since'] = since_date
            if until_date:
                kwargs['until'] = until_date
            
            commits = list(self.repo.iter_commits("HEAD", **kwargs))
            
            for commit in commits:
                # 处理commit message的编码
                try:
                    if isinstance(commit.message, bytes):
                        message = commit.message.decode('utf-8', errors='replace').strip()
                    else:
                        message = commit.message.strip()
                except Exception:
                    message = str(commit.message).strip()
                
                # 获取该提交中此文件的变更统计
                file_stats = {'insertions': 0, 'deletions': 0, 'lines': 0}
                try:
                    stats = commit.stats.files.get(file_path, {})
                    file_stats['insertions'] = stats.get('insertions', 0)
                    file_stats['deletions'] = stats.get('deletions', 0)
                    file_stats['lines'] = stats.get('lines', file_stats['insertions'] + file_stats['deletions'])
                except Exception:
                    pass
                
                # 确保日期是datetime对象
                commit_date = commit.committed_datetime
                if hasattr(commit_date, 'replace'):
                    commit_date = commit_date.replace(tzinfo=None)
                
                history.append({
                    'hash': commit.hexsha[:8],
                    'full_hash': commit.hexsha,
                    'author': commit.author.name,
                    'author_email': commit.author.email,
                    'date': commit_date,
                    'message': message,
                    'insertions': file_stats['insertions'],
                    'deletions': file_stats['deletions'],
                    'lines_changed': file_stats['lines']
                })
                
        except Exception as e:
            pass
        
        return history
    
    def get_file_content(self, file_path: str, commit_hash: str = "HEAD") -> Optional[str]:
        """
        获取指定提交中文件的内容
        
        Args:
            file_path: 文件路径
            commit_hash: 提交哈希值
            
        Returns:
            文件内容字符串，如果无法获取则返回None
        """
        try:
            commit = self.repo.commit(commit_hash)
            blob = commit.tree / file_path
            
            # 尝试解码文件内容
            try:
                content = blob.data_stream.read().decode('utf-8', errors='replace')
                return content
            except Exception:
                return None
                
        except Exception:
            return None
    
    def get_directory_stats(self, branch: str = "HEAD") -> List[Dict]:
        """
        获取目录级别的统计信息
        
        Args:
            branch: 分支名称
            
        Returns:
            目录统计列表
        """
        dir_stats = defaultdict(lambda: {
            'file_count': 0,
            'total_size': 0,
            'extensions': Counter()
        })
        
        files = self.get_all_files(branch)
        
        for file_info in files:
            directory = file_info['directory']
            dir_stats[directory]['file_count'] += 1
            dir_stats[directory]['total_size'] += file_info.get('size', 0)
            dir_stats[directory]['extensions'][file_info['extension']] += 1
        
        result = []
        for dir_path, stats in dir_stats.items():
            result.append({
                'directory': dir_path,
                'file_count': stats['file_count'],
                'total_size': stats['total_size'],
                'top_extensions': dict(stats['extensions'].most_common(5))
            })
        
        return sorted(result, key=lambda x: x['file_count'], reverse=True)
