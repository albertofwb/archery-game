"""
摄像头体感射箭游戏 - 主入口 (新版 MediaPipe)
Archery Game with Hand Tracking
"""
import sys
import cv2
import pygame
import numpy as np
import mediapipe as mp
from pathlib import Path
from typing import Any
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

# 双手拉弓参数
PULL_START_THRESHOLD = 25
RELEASE_DISTANCE_DELTA = 18
POWER_DISTANCE_SCALE = 2.5

# 颜色
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (34, 139, 34)
BROWN = (139, 69, 19)
GOLD = (255, 215, 0)
RED = (220, 20, 60)
BLUE = (30, 144, 255)

# 中文字体配置 - 按优先级排列
CHINESE_FONT_PATHS = [
    "/usr/share/fonts/truetype/arphic/ukai.ttc",  # AR PL UKai
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",  # Noto Sans CJK
    "/usr/share/fonts/truetype/arphic/uming.ttc",  # AR PL UMing
]
CHINESE_FONT_SIZE = 36
CHINESE_FONT_SMALL = 28

def load_chinese_font():
    """尝试加载中文字体，返回 (font, small_font, 成功标志)"""
    import os
    
    print(f"\n🔤 加载中文字体...", flush=True)
    
    for font_path in CHINESE_FONT_PATHS:
        print(f"   尝试: {font_path}", flush=True)
        
        # 检查文件是否存在
        if not os.path.exists(font_path):
            print(f"   ❌ 文件不存在", flush=True)
            continue
        
        try:
            font = pygame.font.Font(font_path, CHINESE_FONT_SIZE)
            small_font = pygame.font.Font(font_path, CHINESE_FONT_SMALL)
            
            # 测试渲染
            test_surface = font.render("中文测试", True, (255, 255, 255))
            print(f"   ✅ 加载成功，测试渲染尺寸: {test_surface.get_size()}", flush=True)
            
            return font, small_font, True
        except Exception as e:
            print(f"   ⚠️ 加载失败: {e}", flush=True)
            continue
    
    print("❌ 所有中文字体加载失败，使用默认字体", flush=True)
    return pygame.font.Font(None, 48), pygame.font.Font(None, 36), False

class ArcheryGame:
    def __init__(self, camera_source="auto", rtsp_url=None):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("体感射箭游戏 | Hand Tracking Archery")
        self.clock = pygame.time.Clock()
        
        # 加载中文字体
        self.font, self.small_font, self.font_loaded = load_chinese_font()
        
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
        
        # MediaPipe Hands（兼容 solutions / tasks 两种 API）
        self.mp_hands: Any = None
        self.hands = None
        self.hand_tracking_mode = "none"
        self._video_timestamp_ms = 0
        self._init_hand_tracker()
        
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
        self.neutral_hand_distance = None
        self.prev_hand_distance = None

    def _init_hand_tracker(self):
        """初始化 MediaPipe 手势识别，优先使用传统 solutions API。"""
        mp_solutions = getattr(mp, "solutions", None)
        mp_hands_module = getattr(mp_solutions, "hands", None)

        if mp_hands_module is not None:
            self.mp_hands = mp_hands_module
            self.hands = self.mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=2,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )
            self.hand_tracking_mode = "solutions"
            print("✅ MediaPipe Hands 初始化成功: solutions API")
            return

        try:
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision

            model_candidates = [
                Path(__file__).resolve().parent / "hand_landmarker.task",
                Path.cwd() / "hand_landmarker.task",
            ]
            model_path = next((p for p in model_candidates if p.exists()), None)
            if model_path is None:
                raise FileNotFoundError("未找到 hand_landmarker.task 模型文件")

            options = vision.HandLandmarkerOptions(
                base_options=mp_python.BaseOptions(model_asset_path=str(model_path)),
                running_mode=vision.RunningMode.VIDEO,
                num_hands=2,
                min_hand_detection_confidence=0.5,
                min_hand_presence_confidence=0.5,
                min_tracking_confidence=0.5,
            )
            self.hands = vision.HandLandmarker.create_from_options(options)
            self.hand_tracking_mode = "tasks"
            print(f"✅ MediaPipe Hands 初始化成功: tasks API ({model_path.name})")
        except Exception as e:
            print(f"⚠️ MediaPipe 手势识别不可用，回退到鼠标模式: {e}")
            if self.camera:
                self.camera.stop()
                self.camera = None
            self.camera_available = False
            self.camera_info = "鼠标控制"
    
    def get_hand_data(self, frame):
        """从摄像头获取手部位置"""
        if not self.camera_available or frame is None or self.hands is None:
            return []

        hands_data = []

        if self.hand_tracking_mode == "solutions" and self.mp_hands is not None:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.hands.process(frame_rgb)
            if results.multi_hand_landmarks:
                handedness_list = results.multi_handedness or []
                for i, hand_landmarks in enumerate(results.multi_hand_landmarks):
                    wrist = hand_landmarks.landmark[self.mp_hands.HandLandmark.WRIST]
                    index_tip = hand_landmarks.landmark[self.mp_hands.HandLandmark.INDEX_FINGER_TIP]
                    middle_tip = hand_landmarks.landmark[self.mp_hands.HandLandmark.MIDDLE_FINGER_TIP]

                    handedness = "Unknown"
                    if i < len(handedness_list):
                        cls = handedness_list[i].classification
                        if cls:
                            handedness = cls[0].label

                    def to_screen(lm):
                        return (int(lm.x * SCREEN_WIDTH), int(lm.y * SCREEN_HEIGHT))

                    hands_data.append({
                        'wrist': to_screen(wrist),
                        'index_tip': to_screen(index_tip),
                        'middle_tip': to_screen(middle_tip),
                        'handedness': handedness
                    })

        elif self.hand_tracking_mode == "tasks":
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
            self._video_timestamp_ms += 16
            results = self.hands.detect_for_video(mp_image, self._video_timestamp_ms)
            for i, landmarks in enumerate(results.hand_landmarks):
                wrist = landmarks[0]
                index_tip = landmarks[8]
                middle_tip = landmarks[12]

                handedness = "Unknown"
                if i < len(results.handedness) and results.handedness[i]:
                    category = results.handedness[i][0]
                    handedness = getattr(category, "category_name", None) or getattr(category, "display_name", None) or "Unknown"

                def to_screen(lm):
                    return (int(lm.x * SCREEN_WIDTH), int(lm.y * SCREEN_HEIGHT))

                hands_data.append({
                    'wrist': to_screen(wrist),
                    'index_tip': to_screen(index_tip),
                    'middle_tip': to_screen(middle_tip),
                    'handedness': handedness
                })
        
        return hands_data

    def _select_bow_and_string_hands(self, hands_data):
        """优先按左右手识别角色；失败时按 x 坐标兜底。"""
        if len(hands_data) < 2:
            return None, None

        left_hand = next((h for h in hands_data if h.get('handedness') == "Left"), None)
        right_hand = next((h for h in hands_data if h.get('handedness') == "Right"), None)

        if left_hand and right_hand:
            return left_hand, right_hand

        ordered = sorted(hands_data, key=lambda h: h['index_tip'][0])
        return ordered[0], ordered[-1]
    
    def calculate_bow_state(self, hands_data):
        """双手状态机：一只手持弓，一只手拉弦。"""
        if len(hands_data) < 2:
            if self.game_state == "pulling":
                self.game_state = "aiming"
                self.bow_power = 0
            self.prev_hand_distance = None
            return None, 0, 0

        bow_hand, string_hand = self._select_bow_and_string_hands(hands_data)
        if not bow_hand or not string_hand:
            return None, self.bow_power, self.bow_angle

        bow_pos = bow_hand['index_tip']
        string_pos = string_hand['index_tip']

        dx = string_pos[0] - bow_pos[0]
        dy = string_pos[1] - bow_pos[1]
        current_distance = float(np.hypot(dx, dy))

        if self.neutral_hand_distance is None:
            self.neutral_hand_distance = current_distance

        # 保证箭总体向右飞行，同时使用双手相对高度控制角度
        aim_dx = max(abs(dx), 1)
        aim_dy = bow_pos[1] - string_pos[1]
        self.bow_angle = float(np.degrees(np.arctan2(aim_dy, aim_dx)))

        if self.game_state == "aiming":
            # 在瞄准阶段更新自然间距基线，用于抵抗不同站位与身材差异
            self.neutral_hand_distance = self.neutral_hand_distance * 0.9 + current_distance * 0.1
            pull_delta = current_distance - self.neutral_hand_distance

            if pull_delta > PULL_START_THRESHOLD and self.arrows_left > 0:
                self.game_state = "pulling"

        elif self.game_state == "pulling":
            pull_delta = max(0.0, current_distance - self.neutral_hand_distance)
            self.bow_power = min(pull_delta * POWER_DISTANCE_SCALE, self.max_power)

            if self.prev_hand_distance is not None:
                release_delta = self.prev_hand_distance - current_distance
                if release_delta > RELEASE_DISTANCE_DELTA:
                    self.release_arrow()

        self.prev_hand_distance = current_distance
        self.prev_hand_pos = bow_pos
        return bow_pos, self.bow_power, self.bow_angle
    
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
                hint = "双手入镜：一手持弓，一手向后拉"
            elif self.game_state == "pulling":
                hint = "保持拉弓，拉弦手快速前送放箭！"
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
        if self.hands and hasattr(self.hands, "close"):
            self.hands.close()
        if self.camera:
            self.camera.stop()
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='体感射箭游戏')
    parser.add_argument('--camera', '-c', choices=['auto', 'usb', 'rtsp', 'mooer', 'mouse'],
                       default='auto', help='摄像头源 (默认: auto)')
    parser.add_argument('--rtsp-url', '-u', type=str,
                       help='RTSP 流地址 (例如: rtsp://user:pass@ip:554/stream)')
    parser.add_argument('--list', '-l', action='store_true',
                       help='列出可用摄像头并退出')
    
    args = parser.parse_args()
    
    # 列出可用摄像头
    if args.list:
        print("🔍 检测可用摄像头...\n")
        
        # USB 摄像头
        usb_cams = CameraAutoDetect.detect_usb_cameras()
        print(f"USB 摄像头: {len(usb_cams)} 个")
        for cam in usb_cams:
            print(f"  /dev/video{cam['id']}: {cam['resolution']}")
        
        # RTSP 测试
        print("\nRTSP 流测试:")
        # 从环境变量读取摄像头配置
        mooer_user = os.getenv('MOOER_CAM_USER', 'admin')
        mooer_pass = os.getenv('MOOER_CAM_PASS', 'password')
        mooer_ip = os.getenv('MOOER_CAM_IP', '192.168.1.55')
        mooer_url = f"rtsp://{mooer_user}:{mooer_pass}@{mooer_ip}:554/h264/ch1/main/av_stream"
        test_urls = [
            ("Mooer Camera", mooer_url),
        ]
        if args.rtsp_url:
            test_urls.append(("自定义", args.rtsp_url))
        
        for name, url in test_urls:
            print(f"  {name}: ", end="", flush=True)
            if CameraAutoDetect.test_rtsp(url, timeout=3.0):
                print("✅ 可用")
            else:
                print("❌ 不可用")
        
        sys.exit(0)
    
    # 启动游戏
    print("\n🏹 启动体感射箭游戏...")
    print("=" * 40)
    print("控制方式:")
    print("  摄像头: 举手向后拉拉弓，前推放箭")
    print("  鼠标:   左键按住拉弓，移动瞄准，松开放箭")
    print("=" * 40)
    print()
    
    # 选择摄像头源
    camera_source = args.camera
    rtsp_url = args.rtsp_url
    
    if camera_source == "mouse":
        # 纯鼠标模式，跳过摄像头检测
        print("🖱️  纯鼠标控制模式")
        game = ArcheryGame.__new__(ArcheryGame)
        game.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("体感射箭游戏 | 鼠标模式")
        game.clock = pygame.time.Clock()
        
        # 加载中文字体（关键修复）
        game.font, game.small_font, game.font_loaded = load_chinese_font()
        
        game.camera = None
        game.camera_available = False
        game.camera_info = "鼠标控制"
        game.mp_hands = None
        game.hands = None
        game.hand_tracking_mode = "none"
        game._video_timestamp_ms = 0
        game.archer = Archer()
        game.target = Target()
        game.physics = ArrowPhysics()
        game.score = 0
        game.arrows_left = 10
        game.game_state = "aiming"
        game.bow_power = 0
        game.max_power = 100
        game.bow_angle = 0
        game.prev_hand_pos = None
        game.pull_start_pos = None
        game.neutral_hand_distance = None
        game.prev_hand_distance = None
    else:
        game = ArcheryGame(camera_source=camera_source, rtsp_url=rtsp_url)
    
    game.run()
