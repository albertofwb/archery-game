"""
物理引擎 - 箭的飞行轨迹
"""
import pygame
import numpy as np

class ArrowPhysics:
    def __init__(self):
        self.arrows = []  # 所有飞行中的箭
        self.gravity = 300  # 重力加速度
        
    def launch_arrow(self, x, y, velocity, angle):
        """发射一支箭"""
        angle_rad = np.radians(angle)
        arrow = {
            'x': x,
            'y': y,
            'vx': velocity * np.cos(angle_rad),
            'vy': velocity * np.sin(angle_rad),
            'active': True,
            'trail': [(x, y)]  # 轨迹点
        }
        self.arrows.append(arrow)
    
    def update(self, dt):
        """更新所有箭的位置"""
        for arrow in self.arrows:
            if not arrow['active']:
                continue
                
            # 应用重力
            arrow['vy'] += self.gravity * dt
            
            # 更新位置
            arrow['x'] += arrow['vx'] * dt
            arrow['y'] += arrow['vy'] * dt
            
            # 记录轨迹
            arrow['trail'].append((arrow['x'], arrow['y']))
            if len(arrow['trail']) > 20:
                arrow['trail'].pop(0)
            
            # 边界检测
            if arrow['x'] > 1280 or arrow['y'] > 720 or arrow['y'] < 0:
                arrow['active'] = False
    
    def draw_arrows(self, screen):
        """绘制所有箭"""
        for arrow in self.arrows:
            if not arrow['active'] and len(arrow['trail']) <= 1:
                continue
            
            # 绘制轨迹
            if len(arrow['trail']) > 1:
                for i in range(len(arrow['trail']) - 1):
                    alpha = int(255 * (i / len(arrow['trail'])))
                    color = (255, 255 - alpha//4, 200 - alpha//2)
                    pygame.draw.line(screen, color, 
                        (int(arrow['trail'][i][0]), int(arrow['trail'][i][1])),
                        (int(arrow['trail'][i+1][0]), int(arrow['trail'][i+1][1])), 
                        max(1, 3 - i//5))
            
            # 绘制箭
            if arrow['active']:
                angle = np.degrees(np.arctan2(arrow['vy'], arrow['vx']))
                arrow_length = 40
                end_x = arrow['x'] - arrow_length * np.cos(np.radians(angle))
                end_y = arrow['y'] - arrow_length * np.sin(np.radians(angle))
                
                pygame.draw.line(screen, (139, 69, 19), 
                    (int(end_x), int(end_y)), 
                    (int(arrow['x']), int(arrow['y'])), 4)
                # 箭头
                pygame.draw.polygon(screen, (100, 100, 100), [
                    (int(arrow['x']), int(arrow['y'])),
                    (int(arrow['x'] - 10), int(arrow['y'] - 5)),
                    (int(arrow['x'] - 10), int(arrow['y'] + 5))
                ])
    
    def clear(self):
        """清除所有箭"""
        self.arrows.clear()
