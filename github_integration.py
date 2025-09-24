"""
GitHub API集成模块
处理GitHub API交互，获取PR信息和pr-agent结果
"""

import os
import re
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import requests
from github import Github, GithubException
import streamlit as st


class GitHubIntegration:
    """GitHub API集成管理器"""
    
    def __init__(self, access_token: str = None):
        """
        初始化GitHub集成
        
        Args:
            access_token: GitHub Personal Access Token
        """
        self.access_token = access_token or self._get_token_from_config()
        if not self.access_token:
            raise ValueError("GitHub Access Token is required")
        
        self.github = Github(self.access_token)
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'token {self.access_token}',
            'Accept': 'application/vnd.github.v3+json'
        })
    
    def _get_token_from_config(self) -> Optional[str]:
        """从配置中获取GitHub token"""
        # 优先级：环境变量 > Streamlit secrets > 配置文件
        token = os.getenv('GITHUB_TOKEN')
        if token:
            return token
        
        try:
            if hasattr(st, 'secrets') and 'GITHUB_TOKEN' in st.secrets:
                return st.secrets['GITHUB_TOKEN']
        except:
            pass
        
        # 尝试从配置文件读取
        config_file = 'github_config.json'
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    return config.get('access_token')
            except:
                pass
        
        return None
    
    def test_connection(self) -> Tuple[bool, str]:
        """
        测试GitHub连接
        
        Returns:
            (是否成功, 消息)
        """
        try:
            user = self.github.get_user()
            return True, f"Connected as {user.login}"
        except GithubException as e:
            return False, f"GitHub API Error: {e.data.get('message', str(e))}"
        except Exception as e:
            return False, f"Connection Error: {str(e)}"
    
    def parse_repo_url(self, repo_input: str) -> Tuple[str, str]:
        """
        解析仓库输入，提取owner和repo名称
        
        Args:
            repo_input: 仓库输入（URL或owner/repo格式）
            
        Returns:
            (owner, repo)
        """
        # 清理输入
        repo_input = repo_input.strip()
        
        # 处理GitHub URL
        github_url_patterns = [
            r'https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$',
            r'git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$',
            r'^([^/]+)/([^/]+)$'  # 简单的 owner/repo 格式
        ]
        
        for pattern in github_url_patterns:
            match = re.match(pattern, repo_input)
            if match:
                owner, repo = match.groups()
                # 移除可能的.git后缀
                repo = repo.rstrip('.git')
                return owner, repo
        
        raise ValueError(f"Invalid repository format: {repo_input}")
    
    def get_repository_info(self, repo_input: str) -> Dict:
        """
        获取仓库基本信息
        
        Args:
            repo_input: 仓库输入
            
        Returns:
            仓库信息字典
        """
        try:
            owner, repo_name = self.parse_repo_url(repo_input)
            repo = self.github.get_repo(f"{owner}/{repo_name}")
            
            return {
                'full_name': repo.full_name,
                'name': repo.name,
                'owner': repo.owner.login,
                'description': repo.description,
                'url': repo.html_url,
                'default_branch': repo.default_branch,
                'private': repo.private,
                'fork': repo.fork,
                'stars': repo.stargazers_count,
                'forks': repo.forks_count,
                'open_issues': repo.open_issues_count,
                'created_at': repo.created_at.isoformat() if repo.created_at else None,
                'updated_at': repo.updated_at.isoformat() if repo.updated_at else None
            }
        except GithubException as e:
            raise Exception(f"Repository not found or access denied: {e.data.get('message', str(e))}")
        except Exception as e:
            raise Exception(f"Error getting repository info: {str(e)}")
    
    def get_pull_requests(self, repo_input: str, days: int = 30, 
                         state: str = 'all') -> List[Dict]:
        """
        获取仓库的Pull Requests
        
        Args:
            repo_input: 仓库输入
            days: 获取最近多少天的PR
            state: PR状态 ('open', 'closed', 'all')
            
        Returns:
            PR列表
        """
        try:
            owner, repo_name = self.parse_repo_url(repo_input)
            repo = self.github.get_repo(f"{owner}/{repo_name}")
            
            # 计算时间范围
            since = datetime.now() - timedelta(days=days)
            
            # 获取PR列表
            pulls = repo.get_pulls(state=state, sort='created', direction='desc')
            
            pr_list = []
            for pr in pulls:
                # 只获取指定时间范围内的PR
                if pr.created_at < since:
                    break
                
                # 获取PR统计信息
                additions = 0
                deletions = 0
                changed_files = 0
                
                try:
                    additions = pr.additions
                    deletions = pr.deletions
                    changed_files = pr.changed_files
                except:
                    # 如果无法获取统计信息，使用默认值
                    pass
                
                pr_data = {
                    'repo_url': repo.html_url,
                    'pr_number': pr.number,
                    'title': pr.title,
                    'author': pr.user.login if pr.user else 'Unknown',
                    'author_avatar': pr.user.avatar_url if pr.user else None,
                    'created_at': pr.created_at.isoformat(),
                    'updated_at': pr.updated_at.isoformat(),
                    'status': 'merged' if pr.merged else pr.state,
                    'base_branch': pr.base.ref,
                    'head_branch': pr.head.ref,
                    'pr_url': pr.html_url,
                    'description': pr.body or '',
                    'additions': additions,
                    'deletions': deletions,
                    'changed_files': changed_files,
                    'mergeable': pr.mergeable,
                    'draft': pr.draft if hasattr(pr, 'draft') else False
                }
                
                pr_list.append(pr_data)
            
            return pr_list
            
        except Exception as e:
            raise Exception(f"Error fetching pull requests: {str(e)}")
    
    def get_pr_comments(self, repo_input: str, pr_number: int) -> List[Dict]:
        """
        获取PR的评论列表
        
        Args:
            repo_input: 仓库输入
            pr_number: PR编号
            
        Returns:
            评论列表
        """
        try:
            owner, repo_name = self.parse_repo_url(repo_input)
            repo = self.github.get_repo(f"{owner}/{repo_name}")
            pr = repo.get_pull(pr_number)
            
            comments = []
            
            # 获取issue评论（PR是特殊的issue）
            for comment in pr.get_issue_comments():
                comments.append({
                    'id': comment.id,
                    'author': comment.user.login if comment.user else 'Unknown',
                    'author_avatar': comment.user.avatar_url if comment.user else None,
                    'body': comment.body,
                    'created_at': comment.created_at.isoformat(),
                    'updated_at': comment.updated_at.isoformat(),
                    'type': 'issue_comment'
                })
            
            # 获取review评论
            for comment in pr.get_review_comments():
                comments.append({
                    'id': comment.id,
                    'author': comment.user.login if comment.user else 'Unknown',
                    'author_avatar': comment.user.avatar_url if comment.user else None,
                    'body': comment.body,
                    'created_at': comment.created_at.isoformat(),
                    'updated_at': comment.updated_at.isoformat(),
                    'type': 'review_comment',
                    'path': comment.path,
                    'line': comment.line
                })
            
            # 获取reviews
            for review in pr.get_reviews():
                if review.body:  # 只包含有内容的review
                    comments.append({
                        'id': review.id,
                        'author': review.user.login if review.user else 'Unknown',
                        'author_avatar': review.user.avatar_url if review.user else None,
                        'body': review.body,
                        'created_at': review.submitted_at.isoformat() if review.submitted_at else None,
                        'updated_at': review.submitted_at.isoformat() if review.submitted_at else None,
                        'type': 'review',
                        'state': review.state
                    })
            
            # 按时间排序
            comments.sort(key=lambda x: x['created_at'] or '')
            
            return comments
            
        except Exception as e:
            raise Exception(f"Error fetching PR comments: {str(e)}")
    
    def find_pr_agent_reviews(self, comments: List[Dict]) -> List[Dict]:
        """
        从评论中找到pr-agent的review结果
        
        Args:
            comments: 评论列表
            
        Returns:
            pr-agent review结果列表
        """
        pr_agent_reviews = []
        
        # pr-agent的常见标识
        pr_agent_identifiers = [
            'pr-agent',
            'PR-Agent',
            'codium-ai',
            'CodiumAI',
            'PR Agent',
            'AI Code Review'
        ]
        
        for comment in comments:
            # 检查作者是否是pr-agent相关
            author = comment.get('author', '').lower()
            is_pr_agent = any(identifier.lower() in author for identifier in pr_agent_identifiers)
            
            # 检查评论内容是否包含pr-agent标识
            body = comment.get('body', '')
            if not is_pr_agent:
                is_pr_agent = any(identifier in body for identifier in pr_agent_identifiers)
            
            if is_pr_agent:
                # 尝试解析review结果
                review_result = self._parse_pr_agent_review(body)
                if review_result:
                    review_result.update({
                        'comment_id': comment.get('id'),
                        'author': comment.get('author'),
                        'created_at': comment.get('created_at'),
                        'raw_content': body
                    })
                    pr_agent_reviews.append(review_result)
        
        return pr_agent_reviews
    
    def _parse_pr_agent_review(self, content: str) -> Optional[Dict]:
        """
        解析pr-agent review内容，提取结构化信息
        
        Args:
            content: review内容
            
        Returns:
            解析后的review结果
        """
        result = {}
        
        # 常见的评分模式
        score_patterns = [
            r'(?:score|rating|grade)[\s:]*(\d+(?:\.\d+)?)\s*(?:/\s*(\d+))?',
            r'(\d+(?:\.\d+)?)\s*/\s*(\d+)',
            r'(?:overall|total)[\s:]*(\d+(?:\.\d+)?)'
        ]
        
        for pattern in score_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                score = float(match.group(1))
                max_score = float(match.group(2)) if match.lastindex > 1 and match.group(2) else 10
                # 标准化到10分制
                result['score'] = (score / max_score) * 10 if max_score != 10 else score
                break
        
        # 安全问题
        security_patterns = [
            r'security[\s\w]*:?\s*(\d+)',
            r'(\d+)\s*security',
            r'security issues?[\s:]*(\d+)'
        ]
        
        for pattern in security_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                result['security_issues'] = int(match.group(1))
                break
        
        # 代码质量问题
        code_patterns = [
            r'(?:code|quality)[\s\w]*issues?[\s:]*(\d+)',
            r'(\d+)\s*(?:code|quality)',
            r'bugs?[\s:]*(\d+)',
            r'issues?[\s:]*(\d+)'
        ]
        
        for pattern in code_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                result['code_issues'] = int(match.group(1))
                break
        
        # 风险等级
        risk_patterns = [
            r'risk[\s:]*(\w+)',
            r'severity[\s:]*(\w+)',
            r'priority[\s:]*(\w+)'
        ]
        
        for pattern in risk_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                risk_level = match.group(1).lower()
                if risk_level in ['low', 'medium', 'high', 'critical']:
                    result['risk_level'] = risk_level
                break
        
        # 如果没有找到任何结构化信息，但内容看起来像review，返回基本信息
        if not result and len(content) > 50:
            # 尝试从内容长度和关键词推断
            if any(word in content.lower() for word in ['review', 'analysis', 'issues', 'suggestions']):
                result = {
                    'score': None,
                    'security_issues': 0,
                    'code_issues': 0,
                    'risk_level': 'medium'
                }
        
        # 添加详细信息
        if result:
            result['details'] = {
                'summary': content[:500] + '...' if len(content) > 500 else content,
                'full_content': content
            }
        
        return result if result else None
    
    def create_github_config_file(self, access_token: str) -> str:
        """
        创建GitHub配置文件
        
        Args:
            access_token: GitHub access token
            
        Returns:
            配置文件路径
        """
        config = {
            'access_token': access_token,
            'created_at': datetime.now().isoformat()
        }
        
        config_file = 'github_config.json'
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        return config_file
