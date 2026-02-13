"""
Mooer Camera API - 云台控制与智能追踪
"""
import urllib.request
import json
import time
from typing import Tuple, Optional

class MooerCameraAPI:
    """Mooer 摄像头云台控制 API"""
    
    def __init__(self, rtsp_url: str = ""):
        self.rtsp_url = rtsp_url
        
        # 从 YAML 配置或环境变量读取
        self.device_serial = self._get_config('device_serial', "BH8057272")
        self.access_token = self._get_config('access_token', 
            "at.cgowen1z38njmzt79w8au79f4b0zqthc-54yacnah4u-10ftq7j-o3tuyjnau")
        
        self.base_url = "https://open.ezvizapi.com"
        self.last_move_time = 0
        self.move_cooldown = 0.3  # 移动冷却时间（秒）
        
        # 云台位置状态
        self.pan = 0   # 水平角度
        self.tilt = 0  # 垂直角度
    
    def _get_config(self, key: str, default: str) -> str:
        """读取配置"""
        import os
        
        # 环境变量
        env_key = f"MOOER_{key.upper()}"
        if env_key in os.environ:
            return os.environ[env_key]
        
        # 尝试读取 YAML 配置
        try:
            import yaml
            config_paths = [
                "/home/albert/clawd/memory/camera-config.yaml",
                "~/.mooer-camera.yaml",
            ]
            for path in config_paths:
                expanded = os.path.expanduser(path)
                if os.path.exists(expanded):
                    with open(expanded) as f:
                        config = yaml.safe_load(f)
                        if config and 'camera' in config:
                            return config['camera'].get(key, default)
        except Exception:
            pass
        
        return default
    
    def _api_call(self, endpoint: str, params: dict) -> dict:
        """调用萤石云 API"""
        url = f"{self.base_url}{endpoint}"
        
        # 添加认证参数
        params['accessToken'] = self.access_token
        params['deviceSerial'] = self.device_serial
        
        # 构建查询字符串
        query = '&'.join([f"{k}={v}" for k, v in params.items()])
        full_url = f"{url}?{query}"
        
        try:
            req = urllib.request.Request(
                full_url,
                headers={
                    'User-Agent': 'MooerCamera/1.0',
                    'Content-Type': 'application/json'
                }
            )
            
            with urllib.request.urlopen(req, timeout=5) as response:
                return json.loads(response.read().decode('utf-8'))
        
        except Exception as e:
            print(f"API 调用失败: {e}")
            return {'code': -1, 'msg': str(e)}
    
    def move(self, direction: str, step: int = 5) -> bool:
        """
        控制云台移动
        
        Args:
            direction: 'up', 'down', 'left', 'right'
            step: 移动步长 (1-10)
        
        Returns:
            是否成功
        """
        # 冷却检查
        now = time.time()
        if now - self.last_move_time < self.move_cooldown:
            time.sleep(self.move_cooldown - (now - self.last_move_time))
        
        # 方向映射
        direction_map = {
            'up': 0,
            'down': 1,
            'left': 2,
            'right': 3
        }
        
        if direction not in direction_map:
            print(f"❌ 未知方向: {direction}")
            return False
        
        result = self._api_call('/api/lapp/device/ptz/start', {
            'channelNo': 1,
            'direction': direction_map[direction],
            'speed': min(max(step, 1), 10)
        })
        
        if result.get('code') == 200:
            self.last_move_time = time.time()
            
            # 更新位置状态
            if direction == 'left':
                self.pan -= step
            elif direction == 'right':
                self.pan += step
            elif direction == 'up':
                self.tilt += step
            elif direction == 'down':
                self.tilt -= step
            
            return True
        
        print(f"❌ 移动失败: {result.get('msg', 'Unknown error')}")
        return False
    
    def stop_move(self) -> bool:
        """停止云台移动"""
        result = self._api_call('/api/lapp/device/ptz/stop', {
            'channelNo': 1
        })
        return result.get('code') == 200
    
    def center_target(self, bbox: Tuple[int, int, int, int], 
                      frame_size: Tuple[int, int] = (1920, 1080)) -> bool:
        """
        将目标移到画面中央
        
        Args:
            bbox: (x1, y1, x2, y2) 目标框
            frame_size: (width, height) 画面尺寸
        
        Returns:
            是否成功
        """
        x1, y1, x2, y2 = bbox
        frame_w, frame_h = frame_size
        
        # 计算目标中心
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2
        
        # 计算偏移（相对于画面中心）
        offset_x = center_x - frame_w / 2
        offset_y = center_y - frame_h / 2
        
        # 转换云台步数（经验值）
        # 1920x1080 画面，水平 350 步 = 360 度
        step_x = int(offset_x / frame_w * 350)
        step_y = int(offset_y / frame_h * 200)
        
        # 执行移动
        moved = False
        
        if abs(step_x) > 3:
            direction = 'right' if step_x > 0 else 'left'
            if self.move(direction, min(abs(step_x), 10)):
                moved = True
        
        if abs(step_y) > 3:
            direction = 'down' if step_y > 0 else 'up'  # 注意 Y 轴方向
            if self.move(direction, min(abs(step_y), 10)):
                moved = True
        
        return moved
    
    def smart_track(self, bbox: Tuple[int, int, int, int], 
                   frame_size: Tuple[int, int] = (1920, 1080)) -> bool:
        """
        智能追踪 - 微调保持目标在中央区域
        
        Args:
            bbox: 目标框
            frame_size: 画面尺寸
        
        Returns:
            是否进行了调整
        """
        x1, y1, x2, y2 = bbox
        frame_w, frame_h = frame_size
        
        # 计算目标中心
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2
        
        # 定义中央区域（画面 40%）
        margin_x = frame_w * 0.3
        margin_y = frame_h * 0.3
        
        # 检查是否在中央区域
        in_center = (
            abs(center_x - frame_w / 2) < margin_x and
            abs(center_y - frame_h / 2) < margin_y
        )
        
        if in_center:
            return False  # 已经在中央，无需调整
        
        # 需要调整
        return self.center_target(bbox, frame_size)
    
    def get_status(self) -> dict:
        """获取摄像头状态"""
        result = self._api_call('/api/lapp/device/info', {
            'deviceSerial': self.device_serial
        })
        
        if result.get('code') == 200:
            data = result.get('data', {})
            return {
                'online': data.get('status') == 1,
                'name': data.get('deviceName'),
                'model': data.get('model'),
                'serial': self.device_serial
            }
        
        return {'online': False, 'error': result.get('msg')}


# ===== 便捷函数 =====

def create_mooer_camera() -> Optional[MooerCameraAPI]:
    """创建 Mooer Camera API 实例"""
    api = MooerCameraAPI()
    status = api.get_status()
    
    if status.get('online'):
        print(f"✅ Mooer Camera 已连接: {status.get('name')}")
        return api
    else:
        print(f"❌ Mooer Camera 离线: {status.get('error')}")
        return None


# ===== 测试 =====
if __name__ == "__main__":
    print("🔍 测试 Mooer Camera API...")
    
    api = create_mooer_camera()
    
    if api:
        print("\n🎮 测试云台控制")
        print("  向右移动...")
        api.move('right', 3)
        time.sleep(1)
        
        print("  向上移动...")
        api.move('up', 3)
        time.sleep(1)
        
        print("  停止")
        api.stop_move()
        
        print("\n✅ 测试完成")
    else:
        print("\n❌ 无法连接摄像头")
