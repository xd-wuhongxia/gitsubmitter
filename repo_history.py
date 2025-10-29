"""
仓库历史管理模块
支持本地和远程仓库的历史记录管理
"""

import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path
import re


class RepoHistoryManager:
    """仓库历史记录管理器"""
    
    def __init__(self, config_file: str = "repo_history.json", max_records: int = 15):
        """
        Create a RepoHistoryManager and initialize its persisted history.
        
        Parameters:
            config_file (str): Path to the JSON file used to persist repository history.
            max_records (int): Maximum number of repository entries to retain; older entries are removed when this limit is exceeded.
        
        Notes:
            The instance's `history_data` is populated by loading the configured file (or a default structure if loading fails).
        """
        self.config_file = config_file
        self.max_records = max_records
        self.history_data = self._load_history()
    
    def _load_history(self) -> Dict:
        """
        Load repository history from the configured JSON file, falling back to a default structure when the file is missing or cannot be parsed.
        
        Returns:
            dict: History object with keys:
                - "recent_repos" (list): List of repository records (empty list when no history).
                - "last_updated" (str): ISO 8601 timestamp of the last update (current time when falling back).
        """
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        
        # 返回默认结构
        return {
            "recent_repos": [],
            "last_updated": datetime.now().isoformat()
        }
    
    def _save_history(self):
        """
        Persist the in-memory repository history to the configured JSON file.
        
        Updates `history_data["last_updated"]` to the current ISO timestamp and writes `history_data` to `self.config_file` as UTF-8 JSON. If the write operation fails, an error message is printed and the exception is suppressed.
        """
        self.history_data["last_updated"] = datetime.now().isoformat()
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.history_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存仓库历史失败: {e}")
    
    def _detect_repo_type(self, repo_path: str) -> str:
        """
        Determine whether a repository path refers to a local or remote repository.
        
        Returns:
            'local' if the path is identified as a local repository path, 'remote' if it is identified as a remote repository.
        """
        # 检查是否是本地路径
        if os.path.isabs(repo_path) or repo_path.startswith('.'):
            return 'local'
        
        # 检查是否是远程URL格式
        remote_patterns = [
            r'^https?://github\.com/',
            r'^git@github\.com:',
            r'^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$'  # owner/repo格式
        ]
        
        for pattern in remote_patterns:
            if re.match(pattern, repo_path):
                return 'remote'
        
        # 默认判断为本地
        return 'local'
    
    def _extract_repo_name(self, repo_path: str, repo_type: str) -> str:
        """
        Extracts the repository name from the given path.
        
        Parameters:
            repo_path (str): Local filesystem path or remote repository identifier (URL or "owner/repo").
            repo_type (str): Either "local" or "remote", which selects the extraction strategy.
        
        Returns:
            str: The repository name (for local paths, the basename; for remote identifiers, the last path segment with any trailing ".git" removed).
        """
        if repo_type == 'local':
            return os.path.basename(os.path.abspath(repo_path))
        else:
            # 远程仓库
            if '/' in repo_path:
                # 提取最后的仓库名
                parts = repo_path.rstrip('/').split('/')
                return parts[-1].replace('.git', '')
            return repo_path
    
    def _generate_description(self, repo_path: str, repo_type: str) -> str:
        """
        Generate a human-readable description for a repository path.
        
        For local paths, indicates whether the path exists as a Git repository or is a plain filesystem path.
        For remote paths, distinguishes HTTP(S) URLs from GitHub-style identifiers.
        
        Parameters:
            repo_path (str): The repository path or remote identifier.
            repo_type (str): The repository type, expected to be "local" or "remote".
        
        Returns:
            str: A concise description of the repository suitable for display.
        """
        if repo_type == 'local':
            if os.path.exists(repo_path):
                return f"本地Git仓库 ({repo_path})"
            else:
                return f"本地路径 ({repo_path})"
        else:
            if repo_path.startswith('http'):
                return f"远程仓库 ({repo_path})"
            else:
                return f"GitHub仓库 ({repo_path})"
    
    def add_repo(self, repo_path: str) -> bool:
        """
        Add or refresh a repository entry in the history, placing it at the front and enforcing the maximum record limit.
        
        Parameters:
            repo_path (str): Repository path or identifier (local path, URL, or owner/repo); empty or whitespace-only values are rejected.
        
        Returns:
            bool: `True` if the repository was added or refreshed, `False` if the provided `repo_path` was empty or invalid.
        """
        if not repo_path or not repo_path.strip():
            return False
        
        repo_path = repo_path.strip()
        repo_type = self._detect_repo_type(repo_path)
        repo_name = self._extract_repo_name(repo_path, repo_type)
        description = self._generate_description(repo_path, repo_type)
        
        # 检查是否已存在，如果存在则更新时间
        existing_index = -1
        for i, repo in enumerate(self.history_data["recent_repos"]):
            if repo["path"] == repo_path:
                existing_index = i
                break
        
        repo_record = {
            "path": repo_path,
            "type": repo_type,
            "name": repo_name,
            "description": description,
            "last_used": datetime.now().isoformat()
        }
        
        if existing_index >= 0:
            # 更新现有记录并移到最前面
            self.history_data["recent_repos"].pop(existing_index)
        
        # 添加到最前面
        self.history_data["recent_repos"].insert(0, repo_record)
        
        # 限制记录数量
        if len(self.history_data["recent_repos"]) > self.max_records:
            self.history_data["recent_repos"] = self.history_data["recent_repos"][:self.max_records]
        
        self._save_history()
        return True
    
    def get_recent_repos(self, limit: Optional[int] = None) -> List[Dict]:
        """
        Return the list of recently used repositories, pruning entries last used more than 90 days ago.
        
        Prunes any entries whose `last_used` is older than 90 days; entries with unparseable `last_used` timestamps are updated to the current time and retained. If pruning or timestamp fixes occur, the history is persisted to disk. The returned list preserves recency order (most recent first).
        
        Parameters:
            limit (Optional[int]): If provided, limits the number of returned entries to this value.
        
        Returns:
            List[Dict]: Repository records (dictionaries) ordered from most to least recent, possibly truncated by `limit`.
        """
        repos = self.history_data.get("recent_repos", [])
        
        # 清理过期记录（超过90天）
        cutoff_date = datetime.now() - timedelta(days=90)
        valid_repos = []
        
        for repo in repos:
            try:
                last_used = datetime.fromisoformat(repo["last_used"])
                if last_used >= cutoff_date:
                    valid_repos.append(repo)
            except:
                # 如果日期解析失败，保留记录但更新时间
                repo["last_used"] = datetime.now().isoformat()
                valid_repos.append(repo)
        
        # 如果清理了记录，保存更新
        if len(valid_repos) != len(repos):
            self.history_data["recent_repos"] = valid_repos
            self._save_history()
        
        if limit:
            return valid_repos[:limit]
        return valid_repos
    
    def remove_repo(self, repo_path: str) -> bool:
        """
        Remove a repository entry matching the given path from the history.
        
        Parameters:
            repo_path (str): Path or identifier of the repository to remove.
        
        Returns:
            bool: `True` if an entry was removed and the history was saved, `False` otherwise.
        """
        original_count = len(self.history_data["recent_repos"])
        self.history_data["recent_repos"] = [
            repo for repo in self.history_data["recent_repos"] 
            if repo["path"] != repo_path
        ]
        
        if len(self.history_data["recent_repos"]) < original_count:
            self._save_history()
            return True
        return False
    
    def clear_history(self) -> bool:
        """
        Clear all stored repository history and persist the empty state.
        
        Returns:
            bool: `True` if the in-memory history was cleared and a save was attempted.
        """
        self.history_data["recent_repos"] = []
        self._save_history()
        return True
    
    def get_repos_by_type(self, repo_type: str) -> List[Dict]:
        """
        Filter repository records by type.
        
        Parameters:
        	repo_type (str): Repository type to filter by — expected values are "local" or "remote".
        
        Returns:
        	List[Dict]: Repository entries whose "type" field equals the provided `repo_type`.
        """
        return [
            repo for repo in self.get_recent_repos()
            if repo.get("type") == repo_type
        ]
    
    def get_stats(self) -> Dict:
        """
        Produce summary statistics for the current repository history.
        
        Returns:
            dict: A mapping with keys:
                - "total" (int): Number of recent repository entries.
                - "local" (int): Count of entries classified as local.
                - "remote" (int): Count of entries classified as remote.
                - "last_updated" (str | None): Timestamp of the last history update from stored data.
        """
        repos = self.get_recent_repos()
        local_count = sum(1 for repo in repos if repo.get("type") == "local")
        remote_count = sum(1 for repo in repos if repo.get("type") == "remote")
        
        return {
            "total": len(repos),
            "local": local_count,
            "remote": remote_count,
            "last_updated": self.history_data.get("last_updated")
        }
    
    def format_repo_display(self, repo: Dict) -> str:
        """
        Format a repository record into a short display string containing an icon, repository name, type label, and a human-readable relative last-used time.
        
        Parameters:
            repo (Dict): Repository record expected to contain at least the keys `"type"` (either `"local"` or `"remote"`), `"name"`, and `"last_used"` (ISO-8601 timestamp).
        
        Returns:
            str: A single-line formatted display string, e.g. "🌐 repo-name (远程) - 3天前".
        """
        icon = "🌐" if repo.get("type") == "remote" else "📁"
        name = repo.get("name", "Unknown")
        repo_type = "远程" if repo.get("type") == "remote" else "本地"
        
        # 计算相对时间
        try:
            last_used = datetime.fromisoformat(repo["last_used"])
            time_diff = datetime.now() - last_used
            
            if time_diff.days > 0:
                time_str = f"{time_diff.days}天前"
            elif time_diff.seconds > 3600:
                hours = time_diff.seconds // 3600
                time_str = f"{hours}小时前"
            elif time_diff.seconds > 60:
                minutes = time_diff.seconds // 60
                time_str = f"{minutes}分钟前"
            else:
                time_str = "刚刚"
        except:
            time_str = "未知"
        
        return f"{icon} {name} ({repo_type}) - {time_str}"