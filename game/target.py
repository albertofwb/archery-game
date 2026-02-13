"""
靶子系统 - 绘制靶子和计分
"""
import pygame
import numpy as np

class Target:
    def __init__(self):
        self.x = 1100  # 靶子位置（右侧）
        self.y = 360
        self.rings = [
            (60, (255, 255, 255)),   # 白圈
            (50, (0, 0, 0)),         # 黑圈
            (40, (0, 0, 255)),       # 蓝圈
            (30, (255, 0, 0)),       # 红圈
            (20, (255, 255, 0)),     # 黄圈（靶心）
        ]
        self.ring_scores = [1, 2, 4, 6, 10]  # 对应分数
        self.hits = []  # 记录命中位置
        
    def draw(self, screen):
        """绘制靶子"""
        # 支架
        pygame.draw.line(screen, (139, 69, 19), 
            (self.x, self.y + 60), 
            (self.x, self.y + 200), 8)
        
        # 靶子圆环（从外到内）
        for radius, color in self.rings:
            pygame.draw.circle(screen, color, (self.x, self.y), radius)
            pygame.draw.circle(screen, (100, 100, 100), (self.x, self.y), radius, 2)
        
        # 绘制之前的命中点
        for hit_x, hit_y in self.hits:
            pygame.draw.circle(screen, (50, 50, 50), (int(hit_x), int(hit_y)), 5)
            pygame.draw.circle(screen, (0, 0, 0), (int(hit_x), int(hit_y)), 5, 2)
    
    def check_hit(self, arrow_x, arrow_y):
        """检查是否命中靶子，返回得分"""
        distance = np.sqrt((arrow_x - self.x) ** 2 + (arrow_y - self.y) ** 2)
        
        for i, (radius, _) in enumerate(self.rings):
            if distance <= radius:
                self.hits.append((arrow_x, arrow_y))
                return self.ring_scores[i]
        
        return 0  # 未命中
    
    def reset(self):
        """重置靶子"""
        self.hits.clear()
