"""
摄像头追踪 - 封装 MediaPipe 手部检测
"""
import cv2
import mediapipe as mp
import numpy as np

class CameraTracker:
    def __init__(self, camera_id=0):
        self.cap = cv2.VideoCapture(camera_id)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        # MediaPipe Hands
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7
        )
        self.mp_draw = mp.solutions.drawing_utils
        
    def get_frame(self):
        """获取一帧图像"""
        ret, frame = self.cap.read()
        if not ret:
            return None
        return frame
    
    def detect_hands(self, frame, screen_width=1280, screen_height=720):
        """
        检测手部并返回坐标
        返回: [{'wrist': (x,y), 'index_tip': (x,y), ...}, ...]
        """
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(frame_rgb)
        
        hands_data = []
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                landmarks = {}
                
                # 关键点位
                key_points = {
                    'wrist': self.mp_hands.HandLandmark.WRIST,
                    'thumb_tip': self.mp_hands.HandLandmark.THUMB_TIP,
                    'index_tip': self.mp_hands.HandLandmark.INDEX_FINGER_TIP,
                    'middle_tip': self.mp_hands.HandLandmark.MIDDLE_FINGER_TIP,
                    'ring_tip': self.mp_hands.HandLandmark.RING_FINGER_TIP,
                    'pinky_tip': self.mp_hands.HandLandmark.PINKY_TIP,
                }
                
                for name, idx in key_points.items():
                    lm = hand_landmarks.landmark[idx]
                    landmarks[name] = (
                        int(lm.x * screen_width),
                        int(lm.y * screen_height)
                    )
                
                hands_data.append(landmarks)
        
        return hands_data
    
    def draw_landmarks(self, frame, hands_data):
        """在图像上绘制手部标记（调试用）"""
        for hand in hands_data:
            for name, pos in hand.items():
                # 缩放回摄像头分辨率
                x = int(pos[0] * 640 / 1280)
                y = int(pos[1] * 480 / 720)
                cv2.circle(frame, (x, y), 5, (0, 255, 0), -1)
                cv2.putText(frame, name, (x+5, y), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        return frame
    
    def get_pull_gesture(self, hands_data, history=None):
        """
        检测拉弓手势
        返回: {'is_pulling': bool, 'pull_distance': float, 'hand_pos': (x,y)}
        """
        if not hands_data:
            return {'is_pulling': False, 'pull_distance': 0, 'hand_pos': None}
        
        hand = hands_data[0]
        hand_pos = hand.get('index_tip', hand.get('wrist'))
        
        # 简单的拉弓检测逻辑
        # 实际应该追踪手的移动轨迹判断是否在"拉"
        result = {
            'is_pulling': False,
            'pull_distance': 0,
            'hand_pos': hand_pos
        }
        
        if history and len(history) >= 2:
            # 检测向后移动
            prev_pos = history[-2]
            if prev_pos:
                dx = hand_pos[0] - prev_pos[0]
                # 向左移动视为拉弓（假设右手持弓）
                if dx < -10:
                    result['is_pulling'] = True
                    result['pull_distance'] = abs(dx)
        
        return result
    
    def release(self):
        """释放资源"""
        self.cap.release()
