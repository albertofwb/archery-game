"""
摄像头体感射箭游戏 - 主入口 (新版 MediaPipe)
Archery Game with Hand Tracking
"""
import sys
import cv2
import pygame
import numpy as np
import mediapipe as mp
from game.archer import Archer
from game.target import Target
from game.physics import ArrowPhysics
from game.camera_adapter import create_camera, CameraAutoDetect

# 初始化
pygame.init()

# 屏幕设置
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60

# 颜色
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (34, 139, 34)
BROWN = (139, 69, 19)
GOLD = (255, 215, 0)
RED = (220, 20, 60)
BLUE = (30, 144, 255)

class ArcheryGame:
    def __init__(self, camera_source="auto", rtsp_url=None):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("体感射箭游戏 | Hand Tracking Archery")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 48)
        self.small_font = pygame.font.Font(None, 36)
        
        # 摄像头适配器（新版多源支持）
        self.camera = None
        self.camera_available = False
        self.camera_info = "未连接"
        
        print("\n🔍 初始化摄像头...")
        print(f"   模式: {camera_source}")
        
        # 创建摄像头适配器
        if camera_source == "auto":
            self.camera = create_camera("auto")
        elif camera_source == "usb":
            self.camera = create_camera("usb", device_id=0)
        elif camera_source == "rtsp" and rtsp_url:
            self.camera = create_camera("rtsp", rtsp_url=rtsp_url)
        elif camera_source == "mooer":
            self.camera = create_camera("mooer")
        
        if self.camera:
            self.camera_available = True
            res = self.camera.get_resolution()
            self.camera_info = f"{self.camera.config.source.name} {res[0]}x{res[1]}"
            print(f"✅ 摄像头已连接: {self.camera_info}")
        else:
            print("⚠️ 使用鼠标控制模式")
        
        # MediaPipe Hands (使用传统 API，更稳定)
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
        # 游戏对象
        self.archer = Archer()
        self.target = Target()
        self.physics = ArrowPhysics()
        
        # 游戏状态
        self.score = 0
        self.arrows_left = 10
        self.game_state = "aiming"
        self.bow_power = 0
        self.max_power = 100
        self.bow_angle = 0
        
        # 手部追踪数据
        self.prev_hand_pos = None
        self.pull_start_pos = None
    
    def get_hand_data(self, frame):
        """从摄像头获取手部位置"""
        if not self.camera_available or frame is None:
            return []
        
        # 使用传统 MediaPipe API
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(frame_rgb)
        
        hands_data = []
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                # 获取关键点位
                wrist = hand_landmarks.landmark[self.mp_hands.HandLandmark.WRIST]
                index_tip = hand_landmarks.landmark[self.mp_hands.HandLandmark.INDEX_FINGER_TIP]
                middle_tip = hand_landmarks.landmark[self.mp_hands.HandLandmark.MIDDLE_FINGER_TIP]
                
                # 转换为屏幕坐标
                def to_screen(lm):
                    return (int(lm.x * SCREEN_WIDTH), int(lm.y * SCREEN_HEIGHT))
                
                hands_data.append({
                    'wrist': to_screen(wrist),
                    'index_tip': to_screen(index_tip),
                    'middle_tip': to_screen(middle_tip)
                })
        
        return hands_data
    
    def calculate_bow_state(self, hands_data):
        """根据手部位置计算弓的状态"""
        if len(hands_data) < 1:
            return None, 0, 0
        
        hand = hands_data[0]
        hand_pos = hand['index_tip']
        
        if self.game_state == "aiming":
            if self.prev_hand_pos:
                dx = hand_pos[0] - self.prev_hand_pos[0]
                dy = hand_pos[1] - self.prev_hand_pos[1]
                
                if dx < -20 and self.arrows_left > 0:
                    self.game_state = "pulling"
                    self.pull_start_pos = self.prev_hand_pos
            
            center_x = SCREEN_WIDTH // 2
            center_y = SCREEN_HEIGHT // 2
            dx = hand_pos[0] - center_x
            dy = hand_pos[1] - center_y
            self.bow_angle = np.degrees(np.arctan2(dy, dx))
            
        elif self.game_state == "pulling":
            if self.pull_start_pos:
                pull_distance = np.sqrt(
                    (hand_pos[0] - self.pull_start_pos[0]) ** 2 +
                    (hand_pos[1] - self.pull_start_pos[1]) ** 2
                )
                self.bow_power = min(pull_distance / 3, self.max_power)
                
                if self.prev_hand_pos:
                    dx = hand_pos[0] - self.prev_hand_pos[0]
                    if dx > 30:
                        self.release_arrow()
        
        self.prev_hand_pos = hand_pos
        return hand_pos, self.bow_power, self.bow_angle
    
    def release_arrow(self):
        """放箭"""
        if self.bow_power > 10:
            velocity = self.bow_power * 0.3
            self.physics.launch_arrow(
                x=100,
                y=SCREEN_HEIGHT // 2,
                velocity=velocity,
                angle=self.bow_angle
            )
            self.arrows_left -= 1
            self.game_state = "released"
            self.bow_power = 0
    
    def draw_camera_preview(self, frame, hands_data):
        """绘制摄像头预览"""
        if frame is None:
            return
        
        # 镜像翻转
        frame = cv2.flip(frame, 1)
        
        # 获取实际帧尺寸
        h, w = frame.shape[:2]
        
        # 绘制手部标记（在实际帧上）
        if hands_data:
            for hand in hands_data:
                # 从屏幕坐标映射回帧坐标
                screen_x, screen_y = hand['index_tip']
                x = int(screen_x * w / SCREEN_WIDTH)
                y = int(screen_y * h / SCREEN_HEIGHT)
                cv2.circle(frame, (x, y), 15, (0, 255, 0), -1)
                cv2.circle(frame, (x, y), 15, (255, 255, 255), 3)
        
        # 转换为 pygame surface
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # 等比例缩放到预览窗口
        preview_w, preview_h = 320, 240
        scale = min(preview_w / w, preview_h / h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        
        frame_small = cv2.resize(frame_rgb, (new_w, new_h))
        
        # 创建 surface
        frame_surface = pygame.surfarray.make_surface(
            np.transpose(frame_small, (1, 0, 2))
        )
        
        # 居中显示
        x_offset = SCREEN_WIDTH - 340 + (preview_w - new_w) // 2
        y_offset = 20 + (preview_h - new_h) // 2
        self.screen.blit(frame_surface, (x_offset, y_offset))
        
        # 边框
        pygame.draw.rect(self.screen, WHITE, (SCREEN_WIDTH - 340, 20, 320, 240), 2)
        
        # 显示摄像头信息
        info_text = self.small_font.render(self.camera_info, True, WHITE)
        self.screen.blit(info_text, (SCREEN_WIDTH - 340, 265))
    
    def draw_game(self, hand_pos):
        """绘制游戏画面"""
        self.screen.fill((50, 50, 50))
        
        for i in range(SCREEN_HEIGHT):
            color = (135 - i//10, 206 - i//10, 235 - i//10)
            pygame.draw.line(self.screen, color, (0, i), (SCREEN_WIDTH, i))
        
        pygame.draw.rect(self.screen, GREEN, (0, SCREEN_HEIGHT - 100, SCREEN_WIDTH, 100))
        
        self.target.draw(self.screen)
        
        bow_x, bow_y = 150, SCREEN_HEIGHT // 2
        
        bow_color = BROWN if self.game_state != "released" else (150, 150, 150)
        pygame.draw.arc(self.screen, bow_color, 
            (bow_x - 50, bow_y - 80, 100, 160), 
            np.radians(-60), np.radians(60), 6)
        
        if self.game_state in ["aiming", "pulling"]:
            string_pull = int(self.bow_power * 2)
            pygame.draw.line(self.screen, WHITE, 
                (bow_x, bow_y - 70), 
                (bow_x + 30 - string_pull, bow_y), 2)
            pygame.draw.line(self.screen, WHITE, 
                (bow_x, bow_y + 70), 
                (bow_x + 30 - string_pull, bow_y), 2)
            
            arrow_x = bow_x + 30 - string_pull
            pygame.draw.line(self.screen, GOLD, 
                (arrow_x, bow_y), 
                (arrow_x + 60, bow_y), 3)
        
        angle_text = self.small_font.render(f"角度: {self.bow_angle:.1f} deg", True, WHITE)
        self.screen.blit(angle_text, (20, 20))
        
        power_width = 200
        power_height = 20
        power_fill = (self.bow_power / self.max_power) * power_width
        pygame.draw.rect(self.screen, WHITE, (20, 60, power_width, power_height), 2)
        pygame.draw.rect(self.screen, RED, (20, 60, power_fill, power_height))
        
        power_text = self.small_font.render(f"力量: {int(self.bow_power)}", True, WHITE)
        self.screen.blit(power_text, (20, 85))
        
        score_text = self.font.render(f"得分: {self.score}", True, GOLD)
        self.screen.blit(score_text, (20, SCREEN_HEIGHT - 120))
        
        arrows_text = self.small_font.render(f"剩余箭: {self.arrows_left}", True, WHITE)
        self.screen.blit(arrows_text, (20, SCREEN_HEIGHT - 60))
        
        if self.camera_available:
            if self.game_state == "aiming":
                hint = "举起手，向后拉弓"
            elif self.game_state == "pulling":
                hint = "拉满后快速前推放箭！"
            elif self.game_state == "released":
                hint = "箭已射出..."
            else:
                hint = ""
        else:
            if self.game_state == "aiming":
                hint = "鼠标左键按住拉弓，移动瞄准，松开放箭"
            elif self.game_state == "pulling":
                hint = "拖动鼠标调整力度和角度，松开左键放箭"
            elif self.game_state == "released":
                hint = "箭已射出..."
            else:
                hint = ""
        
        hint_text = self.font.render(hint, True, BLUE)
        hint_rect = hint_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 50))
        self.screen.blit(hint_text, hint_rect)
        
        self.physics.draw_arrows(self.screen)
    
    def check_collisions(self):
        """检测箭与靶子的碰撞"""
        for arrow in self.physics.arrows:
            if arrow['active']:
                points = self.target.check_hit(arrow['x'], arrow['y'])
                if points > 0:
                    self.score += points
                    arrow['active'] = False
    
    def run(self):
        """主游戏循环"""
        running = True
        mouse_pos = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
        
        while running:
            dt = self.clock.tick(FPS) / 1000.0
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_r:
                        self.arrows_left = 10
                        self.score = 0
                        self.game_state = "aiming"
                        self.physics.arrows.clear()
                
                elif not self.camera_available:
                    if event.type == pygame.MOUSEMOTION:
                        mouse_pos = event.pos
                    elif event.type == pygame.MOUSEBUTTONDOWN:
                        if event.button == 1:
                            self.pull_start_pos = mouse_pos
                            self.game_state = "pulling"
                    elif event.type == pygame.MOUSEBUTTONUP:
                        if event.button == 1 and self.game_state == "pulling":
                            self.release_arrow()
            
            frame = None
            hands_data = []
            hand_pos = None
            
            if self.camera_available and self.camera:
                # 使用新的摄像头适配器获取帧
                frame = self.camera.get_frame_safe()
                if frame is not None:
                    hands_data = self.get_hand_data(frame)
                    hand_pos, power, angle = self.calculate_bow_state(hands_data)
            else:
                # 鼠标控制模式
                if self.game_state == "pulling" and self.pull_start_pos:
                    dx = mouse_pos[0] - self.pull_start_pos[0]
                    dy = mouse_pos[1] - self.pull_start_pos[1]
                    self.bow_power = min(np.sqrt(dx**2 + dy**2) / 3, self.max_power)
                    self.bow_angle = np.degrees(np.arctan2(dy, dx))
                hand_pos = mouse_pos
            
            self.physics.update(dt)
            self.check_collisions()
            
            if self.game_state == "released" and not any(a['active'] for a in self.physics.arrows):
                self.game_state = "aiming"
                self.bow_power = 0
                self.pull_start_pos = None
            
            self.draw_game(hand_pos)
            if self.camera_available and frame is not None:
                self.draw_camera_preview(frame, hands_data)
            
            pygame.display.flip()
        
        # 清理
        if self.camera:
            self.camera.stop()
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    print("启动体感射箭游戏...")
    print("控制方式：")
    print("  - 摄像头: 举手向后拉拉弓，前推放箭")
    print("  - 鼠标: 左键按住拉弓，移动瞄准，松开放箭")
    print("  - R: 重置游戏")
    print("  - ESC: 退出")
    print()
    
    game = ArcheryGame()
    game.run()
