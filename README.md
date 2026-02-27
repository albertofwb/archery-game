# 🏹 Archery Game - 体感射箭游戏

基于 **MediaPipe 手势识别** + **Pygame** 的体感射箭游戏，支持 USB 摄像头、RTSP 网络流、Mooer Camera 等多种视频源。

> 💡 **项目起源**: 2026-02-13 的一次头脑风暴，将摄像头动作识别与 Steam/Linux 游戏结合的想法落地。

---

## ✨ 功能特性

### 🎮 双模控制
| 模式 | 拉弓 | 瞄准 | 放箭 |
|------|------|------|------|
| **摄像头** | 手向后拉 | 移动手 | 快速前推 |
| **鼠标** | 按住左键 | 移动鼠标 | 松开左键 |

### 📷 多源摄像头支持
- **USB 摄像头**: 即插即用，支持热插拔
- **RTSP 网络流**: IP 摄像头 / 监控设备
- **Mooer Camera**: 智能云台摄像头，支持自动追踪

### 🎯 游戏机制
- 物理引擎模拟箭的飞行轨迹（重力、抛物线）
- 动态计分系统：黄心 10 分 → 红 6 分 → 蓝 4 分 → 黑 2 分 → 白 1 分
- 10 支箭限制，R 键重置游戏

---

## 🚀 快速开始

### 环境准备

```bash
cd ~/archery-game
source .venv/bin/activate
```

### 查看可用摄像头

```bash
python main.py --list
```

示例输出：
```
🔍 检测可用摄像头...

USB 摄像头: 0 个

RTSP 流测试:
  Mooer Camera: ✅ 可用
```

### 启动游戏

```bash
# 自动检测最佳摄像头
python main.py

# 指定 Mooer Camera
python main.py --camera mooer

# 纯鼠标模式（无摄像头）
python main.py --camera mouse

# 自定义 RTSP
python main.py --camera rtsp --rtsp-url "rtsp://user:pass@192.168.1.100:554/stream"
```

---

## 🎮 操作指南

### 游戏界面
```
┌─────────────────────────────────────┐
│  [天空渐变背景]                     │
│                                     │
│   🏹           🎯                   │
│  弓箭           靶子                │
│                                     │
│  角度: -15.5°    ┌─────┐            │
│  ████████░░ 力量 │ 预览│            │
│                  │窗口 │            │
│  得分: 24        └─────┘            │
│  剩余箭: 7                          │
│                                     │
│     鼠标左键按住拉弓，移动瞄准      │
└─────────────────────────────────────┘
```

### 按键说明
| 按键 | 功能 |
|------|------|
| `R` | 重置游戏（10 支箭，分数清零） |
| `ESC` | 退出游戏 |
| `左键按住` | 拉弓蓄力 |
| `左键松开` | 放箭 |

---

## 📷 摄像头配置

### Mooer Camera（推荐）

配置方式（环境变量）：
```bash
export MOOER_CAM_USER="admin"
export MOOER_CAM_PASS="your_password"
export MOOER_CAM_IP="192.168.1.55"
```

- **RTSP**: `rtsp://admin:password@192.168.1.55:554/h264/ch1/main/av_stream`
- **云台**: 支持上下左右移动
- **追踪**: 自动将目标保持在画面中央

自定义配置（`memory/camera-config.yaml`）：
```yaml
camera:
  rtsp_url: "rtsp://your-camera-ip/stream"
  device_serial: "YOUR_SERIAL"
  access_token: "YOUR_TOKEN"
```

### USB 摄像头

自动扫描 `/dev/video0` 到 `/dev/video9`，无需额外配置。

### RTSP 通用设备

支持标准 RTSP URL：
```
rtsp://username:password@ip:port/path
```

---

## 📁 项目结构

```
archery-game/
├── main.py                    # 游戏主入口
├── game/
│   ├── __init__.py
│   ├── archer.py             # 弓箭逻辑（角度、力度计算）
│   ├── target.py             # 靶子系统（碰撞检测、计分）
│   ├── physics.py            # 物理引擎（重力、轨迹）
│   ├── camera_adapter.py     # 多源摄像头适配器 ⭐核心
│   └── mooer_api.py          # Mooer Camera 云台控制
├── hand_landmarker.task      # MediaPipe 手部检测模型 (~8MB)
├── requirements.txt
└── README.md
```

---

## 🔧 技术实现

### 手势识别（MediaPipe Hands）
```
输入: 摄像头画面 (640x480)
  ↓
MediaPipe Hands (21 个关键点)
  ↓
提取: 食指指尖坐标 (x, y)
  ↓
计算: 位移变化 → 拉弓/放箭检测
  ↓
输出: 瞄准角度 + 拉弓力度
```

### 物理引擎
```python
# 箭的运动方程
vx = velocity * cos(angle)    # 水平速度
vy = velocity * sin(angle)    # 垂直速度

# 每帧更新
vy += gravity * dt             # 重力加速度
x += vx * dt
y += vy * dt
```

### 摄像头适配器架构
```
CameraAdapter (统一接口)
    ├── USB Mode: OpenCV VideoCapture
    ├── RTSP Mode: FFmpeg/GStreamer
    └── Mooer Mode: RTSP + 云台 API
```

---

## 🐛 故障排除

### 摄像头无法打开
```bash
# 检查设备节点
ls -la /dev/video*

# 测试摄像头读取
python3 << 'EOF'
import cv2
cap = cv2.VideoCapture(0)
ret, frame = cap.read()
print(f"可用: {ret}, 分辨率: {frame.shape if ret else 'N/A'}")
cap.release()
EOF
```

### RTSP 连接失败
1. **检查网络**: `ping 192.168.1.55`
2. **验证 URL**: 用 VLC 测试 `vlc rtsp://...`
3. **防火墙**: 确保端口 554 开放
4. **编码格式**: 优先 H.264，避免 H.265

### 手势识别不灵敏
- 💡 确保手部光线充足（避免逆光）
- 💡 保持手在画面中央 60% 区域
- 💡 调整检测阈值：`min_detection_confidence=0.5`

### 游戏卡顿
```python
# 降低摄像头分辨率
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

# 减少 MediaPipe 复杂度
hands = mp.solutions.hands.Hands(
    max_num_hands=1,              # 只追踪一只手
    model_complexity=0            # 轻量模型
)
```

---

## 📝 更新日志

### 2026-02-13
- ✅ 初始版本，支持鼠标控制
- ✅ 集成 MediaPipe 手势识别
- ✅ 多源摄像头适配器（USB/RTSP/Mooer）
- ✅ Mooer Camera 云台控制 API

---

## 📄 License

MIT © 2026 Albert Wang
