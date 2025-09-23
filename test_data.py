# 测试数据文件
# 用于演示Git统计功能

def generate_sample_data():
    """生成示例数据"""
    return {
        'commits': 150,
        'authors': 5,
        'files': 25
    }

class DataGenerator:
    """数据生成器"""
    
    def __init__(self):
        self.data = []
    
    def add_sample(self, value):
        """添加样本数据"""
        self.data.append(value)
        return len(self.data)
