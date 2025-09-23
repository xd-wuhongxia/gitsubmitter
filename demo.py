#!/usr/bin/env python3
"""
Git统计分析仪表板演示脚本
快速展示应用的主要功能
"""

import os
import sys
from git_analyzer import GitAnalyzer

def main():
    """主演示函数"""
    print("🚀 Git统计分析仪表板演示")
    print("=" * 50)
    
    # 检查当前目录是否为Git仓库
    try:
        analyzer = GitAnalyzer(".")
        print("✅ 成功连接到Git仓库")
    except ValueError as e:
        print(f"❌ 错误: {e}")
        return
    
    # 显示仓库信息
    repo_info = analyzer.get_repo_info()
    print(f"\n📁 仓库信息:")
    print("-" * 30)
    print(f"📍 路径: {repo_info['path']}")
    print(f"🌿 当前分支: {repo_info['current_branch']}")
    print(f"📊 总分支数: {repo_info['total_branches']}")
    
    if repo_info['remote_urls']:
        print("🔗 Remote URLs:")
        for remote in repo_info['remote_urls']:
            print(f"   • {remote['name']}: {remote['url']}")
    else:
        print("🔗 Remote URLs: 无远程仓库")
    
    # 获取基本统计信息
    print("\n📊 基本统计信息:")
    print("-" * 30)
    
    try:
        # 提交统计
        commits_df = analyzer.get_commit_stats()
        print(f"📝 总提交数: {len(commits_df)}")
        
        # 作者统计
        author_stats = analyzer.get_author_stats()
        print(f"👥 活跃作者数: {len(author_stats)}")
        
        if not commits_df.empty:
            total_lines = commits_df['lines_changed'].sum()
            total_files = commits_df['files_changed'].sum()
            print(f"📊 总代码行变更: {total_lines:,}")
            print(f"📁 总文件变更: {total_files:,}")
        
        # 最新提交信息
        if not commits_df.empty:
            latest = commits_df.iloc[0]
            print(f"\n🔥 最新提交:")
            print(f"   Hash: {latest['hash']}")
            print(f"   作者: {latest['author']}")
            print(f"   时间: {latest['date'].strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   消息: {latest['message'][:50]}...")
        
        # 作者贡献排行
        if not author_stats.empty:
            print(f"\n🏆 作者贡献排行:")
            top_authors = author_stats.nlargest(5, 'commits_count')
            for i, (_, author) in enumerate(top_authors.iterrows(), 1):
                print(f"   {i}. {author['author']}: {author['commits_count']} 提交")
        
        # 分支信息
        branch_stats = analyzer.get_branch_stats()
        if not branch_stats.empty:
            print(f"\n🌳 分支信息:")
            for _, branch in branch_stats.iterrows():
                status = "🟢 当前" if branch['is_active'] else "⭕ 其他"
                print(f"   {status} {branch['branch_name']}: {branch['commits_count']} 提交")
        
    except Exception as e:
        print(f"❌ 分析过程中出错: {e}")
        return
    
    print("\n" + "=" * 50)
    print("🎯 要查看完整的交互式分析，请运行:")
    print("   streamlit run app.py")
    print("或者使用启动脚本:")
    print("   Windows: run.bat")
    print("   Linux/Mac: ./run.sh")

if __name__ == "__main__":
    main()
