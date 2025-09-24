"""
测试评论功能修复
"""

from mr_database import MRDatabase
from datetime import datetime

def test_comment_functionality():
    """测试完整的评论功能流程"""
    
    print("🧪 开始测试评论功能修复...")
    
    # 初始化数据库
    db = MRDatabase()
    
    # 模拟GitHub PR数据
    github_pr_data = {
        'repo_url': 'https://github.com/example/test-repo',
        'pr_number': 456,
        'title': 'Fix comment functionality',
        'author': 'developer',
        'created_at': '2024-01-01T10:00:00Z',
        'updated_at': '2024-01-01T11:00:00Z',
        'status': 'open',
        'base_branch': 'main',
        'head_branch': 'fix/comments',
        'pr_url': 'https://github.com/example/test-repo/pull/456',
        'description': 'This PR fixes the comment functionality in MR management'
    }
    
    print(f"📝 插入PR数据: #{github_pr_data['pr_number']} - {github_pr_data['title']}")
    
    # 1. 插入PR数据到数据库
    pr_db_id = db.insert_or_update_pr(github_pr_data)
    print(f"✅ PR数据库ID: {pr_db_id}")
    
    # 2. 模拟从GitHub数据获取数据库ID的过程
    retrieved_id = db.get_pr_id_by_number(
        github_pr_data['repo_url'], 
        github_pr_data['pr_number']
    )
    print(f"✅ 通过repo_url和pr_number获取的ID: {retrieved_id}")
    
    # 3. 验证ID匹配
    assert pr_db_id == retrieved_id, f"ID不匹配: {pr_db_id} != {retrieved_id}"
    print("✅ ID匹配验证通过")
    
    # 4. 测试添加评论
    test_comments = [
        "这个PR看起来不错，代码质量很高",
        "建议添加更多的单元测试",
        "LGTM! 可以合并了"
    ]
    
    operation_ids = []
    for i, comment in enumerate(test_comments):
        operation_id = db.record_operation(
            pr_db_id,
            'comment',
            f'TestUser{i+1}',
            comment
        )
        operation_ids.append(operation_id)
        print(f"✅ 添加评论 #{operation_id}: {comment[:30]}...")
    
    # 5. 测试approve和reject操作
    approve_id = db.record_operation(pr_db_id, 'approve', 'Reviewer1', '代码审查通过')
    print(f"✅ 添加approve操作 #{approve_id}")
    
    reject_id = db.record_operation(pr_db_id, 'reject', 'Reviewer2', '需要修复安全问题')
    print(f"✅ 添加reject操作 #{reject_id}")
    
    # 6. 获取并验证操作历史
    history = db.get_operation_history(limit=10)
    print(f"\n📜 操作历史 (共{len(history)}条记录):")
    
    for record in history[:5]:  # 显示最新的5条记录
        print(f"  • {record['operation_time'][:19]} | {record['operation']:8} | {record['operator']:10} | {record['comments'][:40]}...")
    
    # 7. 测试获取PR详情
    pr_details = db.get_pr_details(pr_db_id)
    print(f"\n📋 PR详情:")
    print(f"  • 标题: {pr_details['title']}")
    print(f"  • 状态: {pr_details['status']}")
    print(f"  • 操作记录数: {len(pr_details['operations'])}")
    
    # 8. 验证数据完整性
    expected_operations = len(test_comments) + 2  # 3个评论 + 1个approve + 1个reject
    actual_operations = len(pr_details['operations'])
    
    if actual_operations >= expected_operations:
        print(f"✅ 数据完整性验证通过: {actual_operations} >= {expected_operations}")
    else:
        print(f"❌ 数据完整性验证失败: {actual_operations} < {expected_operations}")
        return False
    
    print("\n🎉 所有测试通过！评论功能修复验证成功！")
    return True

if __name__ == "__main__":
    test_comment_functionality()
