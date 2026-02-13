# Archery Game - 摄像头体感射箭游戏

## 项目结构
```
archery-game/
├── main.py          # 游戏主入口
├── game/            # 游戏核心逻辑
│   ├── __init__.py
│   ├── archer.py    # 弓箭手/弓箭逻辑
│   ├── target.py    # 靶子系统
│   ├── physics.py   # 物理引擎（箭的飞行）
│   └── camera.py    # 摄像头与手势识别
├── assets/          # 资源文件
│   ├── images/
│   └── sounds/
└── requirements.txt # 依赖
```

## 核心玩法
1. **拉弓**：手往后拉，检测拉弓距离
2. **瞄准**：移动手调整角度
3. **放箭**：手快速前推或松开
4. **计分**：命中靶心得分

## 依赖
- opencv-python
- mediapipe
- pygame
- numpy

## 启动
```bash
cd ~/archery-game
python main.py
```
