"""
Merge Request 数据库管理模块
处理PR数据存储、review结果和操作历史
"""

import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import os


class MRDatabase:
    """Merge Request 数据库管理器"""
    
    def __init__(self, db_path: str = "mr_data.db"):
        """
        初始化数据库连接
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """初始化数据库表结构"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 创建pull_requests表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pull_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    repo_url TEXT NOT NULL,
                    pr_number INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    author TEXT NOT NULL,
                    author_avatar TEXT,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('open', 'closed', 'merged')),
                    base_branch TEXT NOT NULL,
                    head_branch TEXT NOT NULL,
                    pr_url TEXT NOT NULL,
                    description TEXT,
                    additions INTEGER DEFAULT 0,
                    deletions INTEGER DEFAULT 0,
                    changed_files INTEGER DEFAULT 0,
                    last_fetched TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(repo_url, pr_number)
                )
            ''')
            
            # 创建review_results表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS review_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pr_id INTEGER NOT NULL,
                    score REAL,
                    security_issues INTEGER DEFAULT 0,
                    code_issues INTEGER DEFAULT 0,
                    performance_issues INTEGER DEFAULT 0,
                    risk_level TEXT CHECK (risk_level IN ('low', 'medium', 'high', 'critical')),
                    review_details TEXT, -- JSON格式存储详细结果
                    reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    reviewer_type TEXT DEFAULT 'pr-agent', -- pr-agent, manual, etc.
                    FOREIGN KEY (pr_id) REFERENCES pull_requests (id) ON DELETE CASCADE
                )
            ''')
            
            # 创建operation_history表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS operation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pr_id INTEGER NOT NULL,
                    operation TEXT NOT NULL CHECK (operation IN ('approve', 'reject', 'view', 'comment')),
                    operator TEXT NOT NULL,
                    operation_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    comments TEXT,
                    additional_data TEXT, -- JSON格式存储额外信息
                    FOREIGN KEY (pr_id) REFERENCES pull_requests (id) ON DELETE CASCADE
                )
            ''')
            
            # 创建索引以提高查询性能
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_pr_repo_status ON pull_requests(repo_url, status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_pr_created_at ON pull_requests(created_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_review_pr_id ON review_results(pr_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_operation_pr_id ON operation_history(pr_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_operation_time ON operation_history(operation_time)')
            
            conn.commit()
    
    def insert_or_update_pr(self, pr_data: Dict) -> int:
        """
        插入或更新PR数据
        
        Args:
            pr_data: PR数据字典
            
        Returns:
            PR的数据库ID
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 尝试更新现有记录
            cursor.execute('''
                UPDATE pull_requests 
                SET title=?, author=?, author_avatar=?, updated_at=?, status=?, 
                    description=?, additions=?, deletions=?, changed_files=?, 
                    last_fetched=CURRENT_TIMESTAMP
                WHERE repo_url=? AND pr_number=?
            ''', (
                pr_data['title'], pr_data['author'], pr_data.get('author_avatar'),
                pr_data['updated_at'], pr_data['status'], pr_data.get('description'),
                pr_data.get('additions', 0), pr_data.get('deletions', 0), 
                pr_data.get('changed_files', 0), pr_data['repo_url'], pr_data['pr_number']
            ))
            
            if cursor.rowcount == 0:
                # 插入新记录
                cursor.execute('''
                    INSERT INTO pull_requests 
                    (repo_url, pr_number, title, author, author_avatar, created_at, 
                     updated_at, status, base_branch, head_branch, pr_url, description, 
                     additions, deletions, changed_files)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    pr_data['repo_url'], pr_data['pr_number'], pr_data['title'],
                    pr_data['author'], pr_data.get('author_avatar'), pr_data['created_at'],
                    pr_data['updated_at'], pr_data['status'], pr_data['base_branch'],
                    pr_data['head_branch'], pr_data['pr_url'], pr_data.get('description'),
                    pr_data.get('additions', 0), pr_data.get('deletions', 0),
                    pr_data.get('changed_files', 0)
                ))
            
            # 获取PR ID
            cursor.execute('SELECT id FROM pull_requests WHERE repo_url=? AND pr_number=?',
                          (pr_data['repo_url'], pr_data['pr_number']))
            pr_id = cursor.fetchone()[0]
            
            conn.commit()
            return pr_id
    
    def insert_review_result(self, pr_id: int, review_data: Dict) -> int:
        """
        插入review结果
        
        Args:
            pr_id: PR数据库ID
            review_data: review数据字典
            
        Returns:
            review结果的数据库ID
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO review_results 
                (pr_id, score, security_issues, code_issues, performance_issues, 
                 risk_level, review_details, reviewer_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                pr_id, review_data.get('score'), review_data.get('security_issues', 0),
                review_data.get('code_issues', 0), review_data.get('performance_issues', 0),
                review_data.get('risk_level'), json.dumps(review_data.get('details', {})),
                review_data.get('reviewer_type', 'pr-agent')
            ))
            
            review_id = cursor.lastrowid
            conn.commit()
            return review_id
    
    def record_operation(self, pr_id: int, operation: str, operator: str, 
                        comments: str = None, additional_data: Dict = None) -> int:
        """
        记录操作历史
        
        Args:
            pr_id: PR数据库ID
            operation: 操作类型
            operator: 操作人
            comments: 备注
            additional_data: 额外数据
            
        Returns:
            操作记录的数据库ID
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO operation_history (pr_id, operation, operator, comments, additional_data)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                pr_id, operation, operator, comments,
                json.dumps(additional_data) if additional_data else None
            ))
            
            operation_id = cursor.lastrowid
            conn.commit()
            return operation_id
    
    def get_recent_prs(self, repo_url: str = None, days: int = 30, 
                      status: str = None) -> List[Dict]:
        """
        获取最近的PR列表
        
        Args:
            repo_url: 仓库URL筛选
            days: 天数范围
            status: 状态筛选
            
        Returns:
            PR列表
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = '''
                SELECT pr.*, 
                       rv.score, rv.security_issues, rv.code_issues, rv.performance_issues,
                       rv.risk_level, rv.reviewed_at,
                       COUNT(oh.id) as operation_count,
                       MAX(oh.operation_time) as last_operation_time
                FROM pull_requests pr
                LEFT JOIN review_results rv ON pr.id = rv.pr_id
                LEFT JOIN operation_history oh ON pr.id = oh.pr_id
                WHERE pr.created_at >= datetime('now', '-{} days')
            '''.format(days)
            
            params = []
            
            if repo_url:
                query += ' AND pr.repo_url = ?'
                params.append(repo_url)
            
            if status:
                query += ' AND pr.status = ?'
                params.append(status)
            
            query += '''
                GROUP BY pr.id
                ORDER BY pr.created_at DESC
            '''
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return [dict(row) for row in rows]
    
    def get_pr_details(self, pr_id: int) -> Optional[Dict]:
        """
        获取PR详细信息，包括review结果和操作历史
        
        Args:
            pr_id: PR数据库ID
            
        Returns:
            PR详细信息
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 获取PR基本信息
            cursor.execute('SELECT * FROM pull_requests WHERE id = ?', (pr_id,))
            pr_row = cursor.fetchone()
            
            if not pr_row:
                return None
            
            pr_data = dict(pr_row)
            
            # 获取review结果
            cursor.execute('''
                SELECT * FROM review_results 
                WHERE pr_id = ? 
                ORDER BY reviewed_at DESC
            ''', (pr_id,))
            review_rows = cursor.fetchall()
            pr_data['reviews'] = [dict(row) for row in review_rows]
            
            # 获取操作历史
            cursor.execute('''
                SELECT * FROM operation_history 
                WHERE pr_id = ? 
                ORDER BY operation_time DESC
            ''', (pr_id,))
            operation_rows = cursor.fetchall()
            pr_data['operations'] = [dict(row) for row in operation_rows]
            
            return pr_data
    
    def get_operation_history(self, limit: int = 50) -> List[Dict]:
        """
        获取最近的操作历史
        
        Args:
            limit: 返回记录数限制
            
        Returns:
            操作历史列表
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT oh.*, pr.title as pr_title, pr.pr_number, pr.repo_url
                FROM operation_history oh
                JOIN pull_requests pr ON oh.pr_id = pr.id
                ORDER BY oh.operation_time DESC
                LIMIT ?
            ''', (limit,))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def cleanup_old_data(self, days: int = 90):
        """
        清理旧数据
        
        Args:
            days: 保留天数
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 删除旧的PR记录（会级联删除相关的review和operation记录）
            cursor.execute('''
                DELETE FROM pull_requests 
                WHERE created_at < datetime('now', '-{} days')
            '''.format(days))
            
            conn.commit()
            
            # 执行VACUUM以回收空间
            cursor.execute('VACUUM')
