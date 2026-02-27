# CLAUDE.md - 项目上下文

## 项目概述

**项目名称**: Archery Game（体感射箭游戏）  
**类型**: Pygame + OpenCV + MediaPipe 体感游戏  
**创建日期**: 2026-02-13  
**作者**: Albert Wang (@albertofwb)  
**位置**: `~/archery-game/`

---

## 核心需求

1. **体感控制**: 通过摄像头捕捉手势实现射箭动作
2. **多源摄像头**: 支持 USB / RTSP / Mooer Camera
3. **游戏性**: 物理引擎、计分系统、流畅体验
4. **跨平台**: 优先 Linux，兼容 Windows/macOS

---

## 技术栈

| 组件 | 用途 | 版本 |
|------|------|------|
| **Python** | 主语言 | 3.13 |
| **Pygame** | 游戏引擎、渲染 | 2.6.1 |
| **OpenCV** | 摄像头接入、图像处理 | 4.13 |
| **MediaPipe** | 手势识别（21 关键点） | 0.10.x |
| **NumPy** | 数值计算 | 2.4 |

---

## 文件职责

### 核心文件

| 文件 | 职责 | 关键函数 |
|------|------|----------|
| `main.py` | 游戏主循环、事件处理 | `ArcheryGame.run()` |
| `game/archer.py` | 弓箭状态管理 | `Archer.update()` |
| `game/target.py` | 靶子绘制、碰撞检测 | `Target.check_hit()` |
| `game/physics.py` | 箭的物理运动 | `ArrowPhysics.update()` |
| `game/camera_adapter.py` | 多源摄像头适配 ⭐ | `create_camera()` |
| `game/mooer_api.py` | 云台控制 API | `MooerCameraAPI.move()` |

### 配置文件

| 文件 | 用途 |
|------|------|
| `requirements.txt` | Python 依赖 |
| `hand_landmarker.task` | MediaPipe 模型 (~8MB) |
| `memory/camera-config.yaml` | Mooer Camera 凭据 |

---

## 手势识别流程

```
摄像头帧 (BGR)
    ↓
cv2.cvtColor() → RGB
    ↓
MediaPipe Hands.process()
    ↓
提取 INDEX_FINGER_TIP (8) 坐标
    ↓
映射到屏幕坐标 (1280x720)
    ↓
位移计算 → 拉弓/放箭检测
```

### 关键阈值

```python
# 拉弓触发：手向左移动 > 20px
PULL_THRESHOLD = 20

# 放箭触发：手向右快速移动 > 30px
RELEASE_THRESHOLD = 30

# 最小放箭力度
MIN_POWER = 10
```

---

## 摄像头适配器

### 架构

```
CameraAdapter
├── CameraConfig (source, url, resolution)
├── 采集线程 (background capture)
└── 帧队列 (Queue, maxsize=2)
```

### 支持的源

| 源类型 | 标识 | 实现 |
|--------|------|------|
| USB | `CameraSource.USB` | OpenCV VideoCapture |
| RTSP | `CameraSource.RTSP` | FFmpeg/GStreamer |
| Mooer | `CameraSource.MOOER` | RTSP + 云台 API |

### 自动检测优先级

1. USB 摄像头 (`/dev/video0-9`)
2. Mooer Camera RTSP
3. 回退到鼠标模式

---

## 物理引擎参数

```python
GRAVITY = 300          # px/s²
MAX_POWER = 100        # 最大拉弓力度
VELOCITY_SCALE = 0.3   # 力度→速度转换系数
ARROW_LENGTH = 40      # 箭长 (px)
TRAIL_LENGTH = 20      # 轨迹点数量
```

### 运动方程

```python
# 初始化
vx = power * VELOCITY_SCALE * cos(angle)
vy = power * VELOCITY_SCALE * sin(angle)

# 每帧更新
dt = 1/60  # 假设 60 FPS
vy += GRAVITY * dt
x += vx * dt
y += vy * dt
```

---

## 计分规则

```
黄心 (r=20):  10 分
红圈 (r=30):   6 分
蓝圈 (r=40):   4 分
黑圈 (r=50):   2 分
白圈 (r=60):   1 分
未命中:        0 分
```

---

## Mooer Camera 集成

### 萤石云 API

```python
base_url = "https://open.ezvizapi.com"
endpoints = {
    "ptz_start": "/api/lapp/device/ptz/start",
    "ptz_stop": "/api/lapp/device/ptz/stop",
    "device_info": "/api/lapp/device/info"
}
```

### 云台控制

| 方向 | API 参数 |
|------|----------|
| 上 | `direction=0` |
| 下 | `direction=1` |
| 左 | `direction=2` |
| 右 | `direction=3` |

### 智能追踪

```python
# 将目标框 (bbox) 移到画面中央
center_target(bbox, frame_size)
    ↓
计算中心偏移
    ↓
转换为云台步数
    ↓
调用 move() API
```

---

## 命令行接口

```bash
# 列出摄像头
python main.py --list

# 自动检测
python main.py
python main.py --camera auto

# 指定源
python main.py --camera usb
python main.py --camera mooer
python main.py --camera rtsp --rtsp-url URL

# 纯鼠标
python main.py --camera mouse
```

---

## 开发笔记

### 常见问题

1. **MediaPipe 版本兼容性**: 新版 API (`mp.tasks`) 与传统 API (`mp.solutions`) 差异大，本项目使用传统 API 更稳定。

2. **RTSP 延迟**: 使用 `CAP_FFMPEG` 后端 + `set(CAP_PROP_BUFFERSIZE, 1)` 降低延迟。

3. **摄像头权限**: Linux 需要用户加入 `video` 组。

4. **手势抖动**: 添加移动平均滤波或提高检测阈值。

### 优化方向

- [ ] 添加音效（拉弓、放箭、命中）
- [ ] 多人对战模式
- [ ] 风力影响
- [ ] 移动靶
- [ ] 箭的旋转动画

---

## 依赖安装

```bash
# 使用 uv（推荐）
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt

# 或使用 pip
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 运行环境

- **OS**: Ubuntu 24.04 / Linux 6.17
- **GPU**: 可选（MediaPipe 默认 CPU）
- **摄像头**: USB 免驱 或 RTSP 网络流
- **输入**: 鼠标（必需），摄像头（可选）

---

## 参考资料

- [MediaPipe Hands](https://developers.google.com/mediapipe/solutions/vision/hand_landmarker)
- [Pygame Documentation](https://www.pygame.org/docs/)
- [OpenCV VideoCapture](https://docs.opencv.org/4.x/d8/dfe/classcv_1_1VideoCapture.html)
- [萤石云 OpenAPI](https://open.ys7.com/doc/zh/book/index/abstract.html)
