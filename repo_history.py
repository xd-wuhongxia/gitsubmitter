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
        初始化仓库历史管理器
        
        Args:
            config_file: 配置文件路径
            max_records: 最大记录数量
        """
        self.config_file = config_file
        self.max_records = max_records
        self.history_data = self._load_history()
    
    def _load_history(self) -> Dict:
        """从文件加载历史记录"""
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
        """保存历史记录到文件"""
        self.history_data["last_updated"] = datetime.now().isoformat()
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.history_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存仓库历史失败: {e}")
    
    def _detect_repo_type(self, repo_path: str) -> str:
        """
        检测仓库类型
        
        Args:
            repo_path: 仓库路径
            
        Returns:
            'local' 或 'remote'
        """
        # First check if path exists on disk (highest priority for local detection)
        if os.path.exists(repo_path) or os.path.isdir(repo_path):
            return 'local'
        
        # Check if it's clearly a filesystem path (absolute, starts with '.', or contains os.path.sep)
        if os.path.isabs(repo_path) or repo_path.startswith('.') or os.path.sep in repo_path:
            return 'local'
        
        # Check if it's a remote URL format
        remote_patterns = [
            r'^https?://',  # HTTP/HTTPS URLs
            r'^git@',  # SSH URLs
            r'^ssh://',  # SSH protocol URLs
        ]
        
        for pattern in remote_patterns:
            if re.match(pattern, repo_path):
                return 'remote'
        
        # Check for owner/repo format (GitHub shorthand) - only if it doesn't look like a local path
        # Must have exactly one slash and no path separators
        if re.match(r'^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$', repo_path):
            # Additional check: if it looks like a relative path that could exist, treat as local
            if not os.path.sep == '/' or '/' not in repo_path.replace('/', '', 1):
                return 'remote'
        
        # Default to local
        return 'local'
    
    def _extract_repo_name(self, repo_path: str, repo_type: str) -> str:
        """
        提取仓库名称
        
        Args:
            repo_path: 仓库路径
            repo_type: 仓库类型
            
        Returns:
            仓库名称
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
        生成仓库描述
        
        Args:
            repo_path: 仓库路径
            repo_type: 仓库类型
            
        Returns:
            仓库描述
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
    
    def _normalize_path(self, repo_path: str, repo_type: str) -> str:
        """
        Normalize path for consistent storage and comparison.
        
        Args:
            repo_path: Repository path
            repo_type: Repository type ('local' or 'remote')
            
        Returns:
            Normalized path string
        """
        if repo_type == 'local':
            # Resolve to absolute path and normalize
            try:
                normalized = Path(repo_path).resolve().as_posix()
                return normalized
            except (OSError, ValueError):
                # Fallback to original path if resolution fails
                return repo_path
        else:
            # For remote repos, just return as-is (already normalized)
            return repo_path
    
    def add_repo(self, repo_path: str) -> bool:
        """
        添加仓库到历史记录
        
        Args:
            repo_path: 仓库路径
            
        Returns:
            是否添加成功
        """
        if not repo_path or not repo_path.strip():
            return False
        
        repo_path = repo_path.strip()
        repo_type = self._detect_repo_type(repo_path)
        
        # Normalize path to prevent duplicates (e.g., "." vs "/abs/path")
        normalized_path = self._normalize_path(repo_path, repo_type)
        
        repo_name = self._extract_repo_name(repo_path, repo_type)
        description = self._generate_description(normalized_path, repo_type)
        
        # Check for existing entry using normalized path comparison
        existing_index = -1
        for i, repo in enumerate(self.history_data["recent_repos"]):
            stored_path = repo["path"]
            stored_type = repo.get("type", self._detect_repo_type(stored_path))
            stored_normalized = self._normalize_path(stored_path, stored_type)
            if stored_normalized == normalized_path:
                existing_index = i
                break
        
        repo_record = {
            "path": normalized_path,
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
        获取最近使用的仓库列表
        
        Args:
            limit: 返回数量限制
            
        Returns:
            仓库列表
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
            except (ValueError, KeyError, TypeError):
                # If date parsing fails, keep the record but update the time
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
        删除指定的仓库记录
        
        Args:
            repo_path: 仓库路径
            
        Returns:
            是否删除成功
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
        清空所有历史记录
        
        Returns:
            是否清空成功
        """
        self.history_data["recent_repos"] = []
        self._save_history()
        return True
    
    def get_repos_by_type(self, repo_type: str) -> List[Dict]:
        """
        按类型获取仓库列表
        
        Args:
            repo_type: 'local' 或 'remote'
            
        Returns:
            指定类型的仓库列表
        """
        return [
            repo for repo in self.get_recent_repos()
            if repo.get("type") == repo_type
        ]
    
    def get_stats(self) -> Dict:
        """
        获取历史记录统计信息
        
        Returns:
            统计信息字典
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
        格式化仓库显示名称
        
        Args:
            repo: 仓库记录
            
        Returns:
            格式化的显示名称
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
