# Archery Game - 项目活文档

> 本文档记录项目背景、规则、踩坑经验和重要决策。
> 与代码一起演进，保持精简有效。

## 项目概述

**项目名称**: Archery Game（体感射箭游戏）
**技术栈**: Python + OpenCV + MediaPipe + Pygame
**核心玩法**: 通过摄像头捕捉手势，模拟拉弓射箭动作

## 目录结构

```
~/archery-game/
├── main.py              # 游戏主入口
├── game/                # 游戏核心逻辑
│   ├── __init__.py
│   ├── archer.py        # 弓箭手/弓箭逻辑
│   ├── target.py        # 靶子系统
│   ├── physics.py       # 物理引擎（箭的飞行）
│   └── camera.py        # 摄像头与手势识别
├── assets/              # 资源文件
│   ├── images/
│   └── sounds/
├── requirements.txt     # 依赖
├── README.md           # 项目说明
└── CLAUDE.md           # 本文件
```

## 开发规范

### 环境设置
```bash
cd ~/archery-game
# 使用项目自带的 .venv 或创建新的
source .venv/bin/activate  # 如果存在
```

### Git 工作流
1. 原子化提交：先说明计划，验证后再 commit/push
2. 不跟踪的文件：.venv/, *.task, __pycache__/, IDE配置等（见 .gitignore）
3. 提交前检查：`git status` 确认只提交了相关文件

### 代码规范
- 使用有意义的变量名
- 核心游戏逻辑添加注释
- 手势识别参数可调（拉弓阈值、灵敏度等）

## 核心机制

### 手势识别流程
1. **检测手**: MediaPipe Hands 检测手部关键点
2. **拉弓动作**: 检测手往后拉的移动距离
3. **瞄准**: 通过手的位置调整射箭角度
4. **放箭**: 手快速前推或特定手势触发

### 物理系统
- 箭的抛物线轨迹
- 重力影响
- 风速（可选扩展）

### 计分规则
- 靶心得分最高
- 根据命中环数计算得分
- 连击/ combo 系统（可选）

## 已知问题 & 待办

### 当前状态
- [ ] 需要验证手势识别的准确度
- [ ] 调整拉弓灵敏度参数
- [ ] 添加游戏音效

### 未来扩展
- [ ] 多人对战模式
- [ ] 不同难度级别
- [ ] 保存最高分记录

## 重要决策记录

| 日期 | 决策 | 原因 |
|------|------|------|
| 2026-02-13 | 使用 MediaPipe 进行手势识别 | 准确度高，易于集成 |

## 调试技巧

### 手势识别调试
- 在画面上显示手部关键点（调试用）
- 输出拉弓距离数值到控制台
- 使用 `debug=True` 模式运行

### 性能优化
- MediaPipe 模型文件较大（~7MB），不纳入 Git
- 降低摄像头分辨率可提高帧率
- 只在需要时运行手势检测

## 参考资源

- [MediaPipe Hands](https://developers.google.com/mediapipe/solutions/vision/gesture_recognizer)
- [Pygame 文档](https://www.pygame.org/docs/)
- [OpenCV Python](https://docs.opencv.org/4.x/d6/d00/tutorial_py_root.html)
