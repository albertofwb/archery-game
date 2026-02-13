"""
弓箭系统 - 管理弓箭状态和动画
"""
import pygame
import numpy as np

class Archer:
    def __init__(self):
        self.position = (150, 360)  # 弓箭手位置
        self.bow_angle = 0
        self.pull_distance = 0
        self.max_pull = 100
        
    def update(self, hand_position, is_pulling):
        """根据手部位置更新弓箭状态"""
        if hand_position:
            dx = hand_position[0] - self.position[0]
            dy = hand_position[1] - self.position[1]
            self.bow_angle = np.degrees(np.arctan2(dy, dx))
            
            if is_pulling:
                self.pull_distance = min(
                    np.sqrt(dx**2 + dy**2),
                    self.max_pull
                )
    
    def get_arrow_velocity(self):
        """根据拉弓距离计算箭速"""
        return self.pull_distance * 0.5
    
    def reset(self):
        """重置状态"""
        self.pull_distance = 0
