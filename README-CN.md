
<div align="center">

<h1>🎬 VideoMergeX</h1>

<p><strong>具有赛博朋克美学的现代化 GUI 视频下载工具，基于 yt-dlp 构建</strong></p>

<p>
<a href="./README.md">English</a> |
<a href="./README-CN.md">简体中文</a>
</p>

<p>
<img src="https://img.shields.io/badge/Python-3.11+-blue.svg" />
<img src="https://img.shields.io/badge/GUI-PyQt5-009688" />
<img src="https://img.shields.io/badge/Powered%20by-yt--dlp-red" />
<img src="https://img.shields.io/badge/Platform-Windows-lightgrey" />
<img src="https://img.shields.io/badge/License-MIT-green" />
</p>

</div>

---

## ✨ 项目概述

**VideoMergeX** 是一款基于 **yt-dlp** 构建的现代桌面级视频下载工具，  
旨在通过简洁直观的 GUI 界面，提供**稳定、可控、完全本地化**的视频下载体验。

本项目重点关注：
- 稳定性与透明性
- 对下载行为的精细化控制
- 相比浏览器工具更实用的桌面级使用体验

适用于普通用户以及需要批量处理、Cookie 管理和多清晰度下载的高级用户。

---

## 📸 界面截图

### 批量下载模式
![批量下载](batch_main.png)

### 单视频下载模式
![单视频模式](single_main.png)

### 历史记录
![历史记录](history.png)

---

## 📋 功能特性

### 🎯 核心功能
- **多平台支持**  
  基于 yt-dlp，支持 YouTube、TikTok、Bilibili 等多个主流视频网站
- **智能 Cookie 管理**  
  自动从浏览器提取 Cookie  
  支持手动导入 Cookie 文件
- **多清晰度选择**  
  支持 `best / 1080p / 720p / 480p / 360p`
- **批量下载**  
  支持同时添加多个 URL 并行处理
- **实时进度监控**  
  表格化任务管理，清晰展示任务状态
- **下载历史记录**  
  自动保存下载历史，便于后续查看与管理
- **多语言界面**  
  支持中英文一键切换

---

## 📁 项目结构

```

VideoDownloader/
├── main.py                   # 主程序入口
├── downloadWorker.py         # 下载工作线程
├── historyManager.py         # 历史记录管理
├── logSyntaxHighlighter.py   # 日志语法高亮
├── translate_data.py         # 多语言翻译数据
├── style.qss                 # 主界面样式表
├── history.qss               # 历史样式表
├── icon.ico                  # 应用程序图标
├── cookies/                  # Cookie 文件存储目录
├── requirements.txt          # Python 依赖列表
├── README-CN.md              # 中文项目说明文档
└── README.md                 # 项目说明文档

````

---

## 🚀 快速开始

### 环境要求
- **Python 3.11+**
- **Windows 10 / 11**（Linux / macOS 需自行测试）
- **磁盘空间**：至少 100MB 可用空间

### 安装与运行

```bash
# 1. 克隆仓库
git clone https://github.com/yourusername/VideoDownloader.git
cd VideoDownloader

# 2. 创建并激活 conda 环境（推荐）
conda create -n VidMergeX python=3.11
conda activate VidMergeX

# 3. 安装依赖
pip install -r requirements.txt

# 4. 运行程序
python main.py
````

---

### 打包为可执行文件

```bash
pyinstaller --onefile --windowed --clean --icon=icon.ico --name VideoDownloader main.py
```

---

## 🍪 如何获取 Cookie

### 方法一：浏览器插件（推荐）

1. 使用浏览器登录目标视频网站（确保拥有合法访问权限）
2. 安装 Cookie 导出插件，例如：
   Chrome / Edge：*Get cookies.txt*
   Firefox：*cookies.txt*

3. 打开目标视频网站页面
4. 通过插件导出 `cookies.txt` 文件
5. 在程序中手动导入该 Cookie 文件

该方式具有**最高的兼容性和稳定性**，强烈推荐。

---

### 方法二：自动从浏览器获取（可选）

程序可尝试自动从支持的浏览器中提取 Cookie。
该方式需要以**管理员权限**运行程序，且是否成功取决于浏览器版本。

若自动获取失败，程序将**自动切换至无 Cookie 下载模式**。

---

## 🛠️ Cookie 使用说明

为确保能够稳定下载会员或受限内容，**强烈建议使用手动导入 Cookie 的方式**。
虽然以管理员权限运行程序可以启用自动从浏览器获取 Cookie 的功能，但由于浏览器安全机制限制，该功能通常仅在部分较低版本浏览器中可用。若自动获取失败，程序将自动回退至**无 Cookie 模式**进行下载。
### ⚠️声明
本项目仅用于学习与个人用途。

作者不鼓励也不支持在未获得授权的情况下下载受版权保护的内容。

用户需对其使用本软件的行为自行承担全部责任，并确保遵守当地法律法规以及目标平台的服务条款。

对于因使用本项目而产生的任何不当使用、数据丢失或法律问题，作者不承担任何责任。


