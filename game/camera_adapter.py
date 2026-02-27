"""
多源摄像头适配器 - 支持 USB/RTSP/Mooer Camera
"""
import cv2
import numpy as np
import os
import subprocess
import threading
import queue
import time
from typing import Optional, Tuple, Callable
from dataclasses import dataclass
from enum import Enum, auto

class CameraSource(Enum):
    """摄像头来源类型"""
    USB = auto()       # USB 摄像头
    RTSP = auto()      # RTSP 网络流
    MOOER = auto()     # Mooer 智能摄像头
    FILE = auto()      # 视频文件（测试用）

@dataclass
class CameraConfig:
    """摄像头配置"""
    source: CameraSource
    device_id: int = 0          # USB 摄像头 ID
    rtsp_url: str = ""          # RTSP 地址
    width: int = 640
    height: int = 480
    fps: int = 30
    buffer_size: int = 1        # 减少延迟

class CameraAdapter:
    """通用摄像头适配器"""
    
    def __init__(self, config: CameraConfig):
        self.config = config
        self.cap = None
        self.frame_queue = queue.Queue(maxsize=2)
        self.is_running = False
        self.capture_thread = None
        self.last_frame = None
        self.frame_time = 0
        
        # Mooer Camera 特殊处理
        self.mooer_api = None
        if config.source == CameraSource.MOOER:
            from .mooer_api import MooerCameraAPI
            self.mooer_api = MooerCameraAPI(config.rtsp_url)
    
    def start(self) -> bool:
        """启动摄像头"""
        if self.config.source == CameraSource.USB:
            return self._start_usb()
        elif self.config.source in [CameraSource.RTSP, CameraSource.MOOER]:
            return self._start_rtsp()
        return False
    
    def _start_usb(self) -> bool:
        """启动 USB 摄像头"""
        self.cap = cv2.VideoCapture(self.config.device_id)
        
        # 设置缓冲区大小（减少延迟）
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, self.config.buffer_size)
        
        # 设置分辨率
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
        
        # 设置 FPS
        self.cap.set(cv2.CAP_PROP_FPS, self.config.fps)
        
        if not self.cap.isOpened():
            print(f"❌ 无法打开 USB 摄像头 {self.config.device_id}")
            return False
        
        # 读取一帧测试
        ret, frame = self.cap.read()
        if not ret:
            print("❌ USB 摄像头无法读取画面")
            return False
        
        self.is_running = True
        self._start_capture_thread()
        print(f"✅ USB 摄像头已启动: {self.config.device_id}")
        return True
    
    def _start_rtsp(self) -> bool:
        """启动 RTSP 流"""
        url = self.config.rtsp_url
        
        # 优先使用 ffmpeg 后端（更稳定）
        # OpenCV 的 RTSP 支持：CAP_FFMPEG 或 GStreamer
        
        # 尝试 FFmpeg 后端
        self.cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        
        if not self.cap.isOpened():
            # 尝试 GStreamer（Linux 上效果更好）
            gst_pipeline = (
                f'rtspsrc location={url} latency=0 ! '
                f'rtph264depay ! h264parse ! avdec_h264 ! '
                f'videoconvert ! appsink'
            )
            self.cap = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)
        
        if not self.cap.isOpened():
            print(f"❌ 无法打开 RTSP 流: {url}")
            return False
        
        # 设置低延迟
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        self.is_running = True
        self._start_capture_thread()
        print(f"✅ RTSP 流已连接: {url}")
        return True
    
    def _start_capture_thread(self):
        """启动后台采集线程"""
        def capture_loop():
            while self.is_running:
                if self.cap is None:
                    time.sleep(0.01)
                    continue
                
                ret, frame = self.cap.read()
                if ret:
                    self.last_frame = frame
                    self.frame_time = time.time()
                    
                    # 非阻塞放入队列
                    try:
                        self.frame_queue.put_nowait(frame)
                    except queue.Full:
                        # 丢弃旧帧，保持最新
                        try:
                            self.frame_queue.get_nowait()
                            self.frame_queue.put_nowait(frame)
                        except queue.Empty:
                            pass
                else:
                    # 读取失败，短暂等待
                    time.sleep(0.001)
        
        self.capture_thread = threading.Thread(target=capture_loop, daemon=True)
        self.capture_thread.start()
    
    def get_frame(self, timeout: float = 1.0) -> Optional[np.ndarray]:
        """获取最新帧"""
        if not self.is_running:
            return None
        
        # 优先从队列获取
        try:
            return self.frame_queue.get(timeout=timeout)
        except queue.Empty:
            # 如果队列空，返回最后一帧
            return self.last_frame
    
    def get_frame_safe(self) -> Optional[np.ndarray]:
        """获取帧（线程安全，非阻塞）"""
        return self.last_frame
    
    def is_active(self) -> bool:
        """检查摄像头是否活跃"""
        if not self.is_running:
            return False
        
        # 检查最后帧时间（超过 3 秒无新帧视为断开）
        if time.time() - self.frame_time > 3.0:
            return False
        
        return True
    
    def get_fps(self) -> float:
        """获取实际 FPS"""
        if self.cap:
            return self.cap.get(cv2.CAP_PROP_FPS)
        return 0.0
    
    def get_resolution(self) -> Tuple[int, int]:
        """获取实际分辨率"""
        if self.cap:
            w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            return (w, h)
        return (0, 0)
    
    # ===== Mooer Camera 特有功能 =====
    
    def move_ptz(self, direction: str, step: int = 5) -> bool:
        """控制云台移动（仅 Mooer Camera）"""
        if self.mooer_api:
            return self.mooer_api.move(direction, step)
        return False
    
    def center_on_person(self, bbox: Tuple[int, int, int, int]) -> bool:
        """将人移到画面中央（仅 Mooer Camera）"""
        if self.mooer_api:
            return self.mooer_api.center_target(bbox)
        return False
    
    def stop(self):
        """停止摄像头"""
        self.is_running = False
        
        if self.capture_thread:
            self.capture_thread.join(timeout=1.0)
        
        if self.cap:
            self.cap.release()
            self.cap = None
        
        # 清空队列
        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
            except queue.Empty:
                break
        
        print("✅ 摄像头已停止")
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False


class CameraAutoDetect:
    """自动检测可用摄像头"""
    
    @staticmethod
    def detect_usb_cameras(max_id: int = 10) -> list:
        """检测可用的 USB 摄像头"""
        available = []
        for i in range(max_id):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    available.append({
                        'id': i,
                        'resolution': f"{w}x{h}"
                    })
                cap.release()
        return available
    
    @staticmethod
    def test_rtsp(url: str, timeout: float = 5.0) -> bool:
        """测试 RTSP 流是否可用"""
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        start = time.time()
        while time.time() - start < timeout:
            ret, frame = cap.read()
            if ret:
                cap.release()
                return True
            time.sleep(0.1)
        
        cap.release()
        return False
    
    @staticmethod
    def create_default_camera() -> Optional[CameraAdapter]:
        """创建默认摄像头（自动检测）"""
        # 1. 尝试 USB 摄像头
        usb_cams = CameraAutoDetect.detect_usb_cameras()
        if usb_cams:
            print(f"✅ 发现 {len(usb_cams)} 个 USB 摄像头")
            config = CameraConfig(
                source=CameraSource.USB,
                device_id=usb_cams[0]['id']
            )
            adapter = CameraAdapter(config)
            if adapter.start():
                return adapter
        
        # 2. 尝试 Mooer Camera RTSP
        # 从环境变量读取摄像头配置，默认使用示例地址
        mooer_user = os.getenv('MOOER_CAM_USER', 'admin')
        mooer_pass = os.getenv('MOOER_CAM_PASS', 'password')
        mooer_ip = os.getenv('MOOER_CAM_IP', '192.168.1.55')
        mooer_url = f"rtsp://{mooer_user}:{mooer_pass}@{mooer_ip}:554/h264/ch1/main/av_stream"
        print("🔍 尝试连接 Mooer Camera...")
        if CameraAutoDetect.test_rtsp(mooer_url, timeout=3.0):
            config = CameraConfig(
                source=CameraSource.MOOER,
                rtsp_url=mooer_url
            )
            adapter = CameraAdapter(config)
            if adapter.start():
                return adapter
        
        print("❌ 未检测到可用摄像头")
        return None


# ===== 便捷函数 =====

def create_camera(source_type: str = "auto", **kwargs) -> Optional[CameraAdapter]:
    """
    创建摄像头适配器
    
    Args:
        source_type: "auto", "usb", "rtsp", "mooer"
        **kwargs: 
            - device_id: USB 摄像头 ID
            - rtsp_url: RTSP 地址
            - width, height, fps
    
    Returns:
        CameraAdapter 实例 或 None
    """
    if source_type == "auto":
        return CameraAutoDetect.create_default_camera()
    
    elif source_type == "usb":
        config = CameraConfig(
            source=CameraSource.USB,
            device_id=kwargs.get('device_id', 0),
            width=kwargs.get('width', 640),
            height=kwargs.get('height', 480),
            fps=kwargs.get('fps', 30)
        )
    
    elif source_type == "rtsp":
        config = CameraConfig(
            source=CameraSource.RTSP,
            rtsp_url=kwargs.get('rtsp_url', ''),
            width=kwargs.get('width', 1920),
            height=kwargs.get('height', 1080)
        )
    
    elif source_type == "mooer":
        # 从环境变量读取摄像头配置
        mooer_user = os.getenv('MOOER_CAM_USER', 'admin')
        mooer_pass = os.getenv('MOOER_CAM_PASS', 'password')
        mooer_ip = os.getenv('MOOER_CAM_IP', '192.168.1.55')
        default_url = f"rtsp://{mooer_user}:{mooer_pass}@{mooer_ip}:554/h264/ch1/main/av_stream"
        url = kwargs.get('rtsp_url', default_url)
        config = CameraConfig(
            source=CameraSource.MOOER,
            rtsp_url=url
        )
    
    else:
        raise ValueError(f"未知的摄像头类型: {source_type}")
    
    adapter = CameraAdapter(config)
    if adapter.start():
        return adapter
    return None


# ===== 测试 =====
if __name__ == "__main__":
    print("🔍 检测可用摄像头...")
    
    # 显示所有 USB 摄像头
    usb_cams = CameraAutoDetect.detect_usb_cameras()
    print(f"\nUSB 摄像头: {len(usb_cams)} 个")
    for cam in usb_cams:
        print(f"  - /dev/video{cam['id']}: {cam['resolution']}")
    
    # 尝试自动连接
    print("\n🎥 尝试连接...")
    cam = create_camera("auto")
    
    if cam:
        print(f"✅ 已连接: {cam.config.source.name}")
        print(f"   分辨率: {cam.get_resolution()}")
        
        # 显示预览
        cv2.namedWindow("Camera Preview", cv2.WINDOW_NORMAL)
        
        try:
            while True:
                frame = cam.get_frame(timeout=0.1)
                if frame is not None:
                    cv2.imshow("Camera Preview", frame)
                
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
        finally:
            cam.stop()
            cv2.destroyAllWindows()
    else:
        print("❌ 无法连接任何摄像头")
