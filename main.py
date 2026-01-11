import ctypes
import os
import shutil
import sys
from datetime import datetime

import qdarkstyle
from PyQt5.QtCore import (Qt, QThread, QPropertyAnimation,
                          QEasingCurve, QParallelAnimationGroup)
from PyQt5.QtGui import QColor, QIcon, QTextCursor
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QHBoxLayout, QTextEdit, QFrame, QGraphicsDropShadowEffect,
    QTabWidget, QPlainTextEdit, QTableWidget, QTableWidgetItem, QProgressBar,
    QComboBox, QGroupBox
)

# 导入功能类
from downloadWorker import DownloadWorker
from historyManager import HistoryManager
from logSyntaxHighlighter import LogSyntaxHighlighter
from translate_data import translations

# 设置应用程序ID
appId = "VidMergeX"
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(appId)


class HDDownloader(QWidget):
    """
    高清视频下载器主窗口类

    这是一个基于PyQt5的视频下载器应用程序，支持单URL和批量下载，
    提供下载进度监控、日志记录和历史记录功能，支持中英文双语界面。
    """

    def __init__(self):
        """
        初始化HDDownloader类

        设置窗口基础属性，初始化变量，构建UI界面，加载样式表。
        """
        super().__init__()

        self.current_language = 'en'  # 当前语言设置，默认英文
        self.translations = translations  # 多语言翻译数据

        self.workers = []  # 存储工作线程对象
        self.worker_threads = []  # 存储线程对象
        self.cookie_files = []  # 存储Cookie文件信息
        self.current_cookie_file = None  # 当前选中的Cookie文件

        # 窗口基础尺寸设置
        self.base_width = 1400
        self.base_height = 1050
        self.log_width = 400  # 日志边栏宽度
        self.log_expanded = False  # 日志边栏是否展开
        self.log_animating = False  # 动画执行状态锁

        # 设置窗口标题
        self.setWindowTitle(self.translations['window_title'][self.current_language])

        def resource_path(relative_path):
            """
            获取资源文件的绝对路径

            Args:
                relative_path (str): 相对路径

            Returns:
                str: 资源的绝对路径
            """
            try:
                base_path = os.path.dirname(sys.argv[0])
            except Exception:
                base_path = os.path.abspath(".")
            return os.path.join(base_path, relative_path)

        # 设置窗口图标
        self.setWindowIcon(QIcon(resource_path("icon.ico")))

        # 设置窗口固定大小（不包含侧边栏）
        self.setFixedSize(self.base_width, self.base_height)

        # ===== 主布局 =====
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ===== 左侧主内容区域 =====
        self.left_container = QWidget()
        self.setup_left_content()

        # ===== 右侧日志边栏 =====
        self.setup_right_log()

        # ===== 添加到主布局 =====
        main_layout.addWidget(self.left_container)
        # 注意：侧边栏初始不添加到布局中

        # 创建浮动侧边栏按钮
        self.create_sidebar_button()

        self.batch_mode = False  # 批量模式标志
        self.load_cookie_files()  # 加载已有的Cookie文件
        self.update_language()  # 更新界面语言

        # 加载QSS样式表
        self.load_styles()

    def load_styles(self):
        """
        加载QSS样式表

        从外部文件加载CSS样式，为应用程序提供自定义外观。
        如果样式文件不存在或加载失败，会打印警告信息。
        """
        try:
            with open("style.qss", "r", encoding="utf-8") as f:
                qss_content = f.read()
                self.setStyleSheet(qss_content)
        except FileNotFoundError:
            print("警告: 未找到 style_test.qss 文件")
        except Exception as e:
            print(f"加载样式表出错: {e}")

    def setup_left_content(self):
        """
        设置左侧主内容区域

        构建主界面布局，包括：
        - 标题区域
        - URL输入区域
        - 文件夹选择区域
        - Cookie文件选择区域
        - 操作按钮区域
        - 任务表区域
        - 选项卡（下载/历史记录）
        """
        # 外层布局
        outer_layout = QVBoxLayout(self.left_container)
        outer_layout.setAlignment(Qt.AlignCenter)

        # 主框架
        frame = QFrame()
        frame.setFixedSize(1300, 950)
        frame.setObjectName("main_frame")

        # 添加阴影效果
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(0, 4)
        frame.setGraphicsEffect(shadow)

        # 选项卡控件
        self.tabs = QTabWidget()
        self.tabs.setObjectName("main_tabs")

        # ================= 下载页 =================
        download_tab = QWidget()
        download_tab.setObjectName("download_tab")
        download_layout = QVBoxLayout(download_tab)

        # ---- 标题 ----
        self.title_label = QLabel()
        self.title_label.setObjectName("title_label")
        self.title_label.setAlignment(Qt.AlignCenter)
        download_layout.addWidget(self.title_label)

        # ---- URL 输入 ----
        self.url_label = QLabel()
        self.url_label.setObjectName("url_label")
        self.url_input = QLineEdit()
        self.url_input.setObjectName("url_input")
        self.url_input.setMaximumHeight(50)

        # 多行URL输入框（批量模式使用）
        self.url_input_multiline = QPlainTextEdit()
        self.url_input_multiline.setObjectName("url_input_multiline")
        self.url_input_multiline.setMaximumHeight(500)
        self.url_input_multiline.setVisible(False)

        download_layout.addWidget(self.url_label)
        download_layout.addWidget(self.url_input)
        download_layout.addWidget(self.url_input_multiline)

        # ---- 文件夹选择 ----
        self.folder_label = QLabel()
        self.folder_label.setObjectName("folder_label")
        folder_row = QHBoxLayout()

        self.folder_path = QLineEdit()
        self.folder_path.setObjectName("folder_path")
        self.folder_path.setMaximumHeight(50)
        self.folder_button = QPushButton()
        self.folder_button.setObjectName("folder_button")
        self.folder_button.clicked.connect(self.choose_folder)

        folder_row.addWidget(self.folder_path)
        folder_row.addWidget(self.folder_button)

        download_layout.addWidget(self.folder_label)
        download_layout.addLayout(folder_row)

        # ---- Cookie设置区域 ----
        cookie_group = QGroupBox()
        cookie_group.setObjectName("cookie_group")
        cookie_layout = QVBoxLayout(cookie_group)

        # 创建一个水平布局，将所有控件放在同一行
        control_row = QHBoxLayout()
        control_row.setSpacing(15)  # 设置控件之间的间距

        # Cookie下拉框
        self.cookie_combo = QComboBox()
        self.cookie_combo.setObjectName("cookie_combo")
        self.cookie_combo.setMaximumHeight(50)
        self.cookie_combo.setMinimumWidth(100)
        self.cookie_combo.currentIndexChanged.connect(self.on_cookie_selected)

        # Cookie上传按钮
        self.cookie_upload_button = QPushButton()
        self.cookie_upload_button.setObjectName("cookie_upload_button")
        self.cookie_upload_button.setMaximumHeight(50)
        self.cookie_upload_button.clicked.connect(self.upload_cookie_file)

        # Cookie删除按钮
        self.cookie_delete_button = QPushButton()
        self.cookie_delete_button.setObjectName("cookie_delete_button")
        self.cookie_delete_button.setMaximumHeight(50)
        self.cookie_delete_button.setEnabled(False)
        self.cookie_delete_button.clicked.connect(self.delete_cookie_file)

        # 清晰度标签
        self.quality_label = QLabel()
        self.quality_label.setObjectName("quality_label")

        # 清晰度下拉框
        self.quality_combo = QComboBox()
        self.quality_combo.setObjectName("quality_combo")
        self.quality_combo.setMaximumHeight(50)

        # 添加清晰度选项
        self.quality_combo.addItem("best", "best")
        self.quality_combo.addItem("1080", "1080")
        self.quality_combo.addItem("720", "720")
        self.quality_combo.addItem("480", "480")
        self.quality_combo.addItem("360", "360")

        # 将控件添加到水平布局
        control_row.addWidget(self.cookie_combo)
        control_row.addWidget(self.cookie_upload_button)
        control_row.addWidget(self.cookie_delete_button)
        control_row.addWidget(self.quality_label)
        control_row.addWidget(self.quality_combo)

        # 设置控件拉伸因子，均匀分布
        control_row.setStretch(0, 4)  # Cookie下拉框占4份
        control_row.setStretch(1, 2)  # 上传按钮占2份
        control_row.setStretch(2, 2)  # 删除按钮占2份
        control_row.setStretch(3, 1)  # 标签占1份
        control_row.setStretch(4, 2)  # 清晰度下拉框占2份

        cookie_layout.addLayout(control_row)

        download_layout.addWidget(cookie_group)

        # ================= 操作按钮区（统一风格） =================
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        # 中英文切换按钮
        self.lang_button = QPushButton("EN")
        self.lang_button.setObjectName("lang_button")
        self.lang_button.setFixedSize(260, 80)
        self.lang_button.setCursor(Qt.PointingHandCursor)
        self.lang_button.clicked.connect(self.toggle_language)

        # 开始下载（主按钮）
        self.download_button = QPushButton()
        self.download_button.setObjectName("downloadButton")
        self.download_button.setFixedSize(260, 80)
        self.download_button.setCursor(Qt.PointingHandCursor)
        self.download_button.clicked.connect(self.download_video)

        # 批量下载按钮
        self.batch_button = QPushButton("batch_button")
        self.batch_button.setObjectName("batch_button")
        self.batch_button.setFixedSize(260, 80)
        self.batch_button.setCursor(Qt.PointingHandCursor)
        self.batch_button.clicked.connect(self.toggle_batch_mode)

        # 按钮间距
        button_spacing = 220
        btn_row.addWidget(self.lang_button)
        btn_row.addSpacing(button_spacing)
        btn_row.addWidget(self.download_button)
        btn_row.addSpacing(button_spacing)
        btn_row.addWidget(self.batch_button)
        btn_row.addStretch()
        download_layout.addLayout(btn_row)

        # ================= 任务表 =================
        self.task_table = QTableWidget(0, 4)
        self.task_table.setObjectName("task_table")
        self.task_table.setHorizontalHeaderLabels(
            ["Task", "Status", "Progress", "Result"]
        )
        self.task_table.verticalHeader().setVisible(False)
        self.task_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.task_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.task_table.setAlternatingRowColors(True)
        self.task_table.setFixedHeight(330)
        self.task_table.setColumnWidth(0, 420)
        self.task_table.setColumnWidth(1, 120)
        self.task_table.setColumnWidth(2, 420)
        self.task_table.horizontalHeader().setStretchLastSection(True)
        download_layout.addWidget(self.task_table)

        # ================= 历史页 =================
        self.history_manager = HistoryManager(self.translations, self.current_language)

        # 添加选项卡
        self.tabs.addTab(download_tab, "")
        self.tabs.addTab(self.history_manager, "")

        # 将选项卡添加到框架
        frame_layout = QVBoxLayout(frame)
        frame_layout.addWidget(self.tabs)

        # 将框架添加到外层布局
        outer_layout.addWidget(frame)

    def setup_right_log(self):
        """
        设置右侧日志边栏

        构建可折叠的日志边栏，包括：
        - 日志标题栏
        - 日志显示文本框
        - 清空日志按钮
        - 关闭按钮
        """
        self.log_container = QFrame()
        self.log_container.setObjectName("log_container")
        self.log_container.setFixedWidth(0)  # 初始宽度为0

        # 添加阴影效果 - 与主界面阴影一致
        self.sidebar_shadow = QGraphicsDropShadowEffect(self.log_container)
        self.sidebar_shadow.setBlurRadius(40)
        self.sidebar_shadow.setColor(QColor(0, 0, 0, 180))
        self.sidebar_shadow.setOffset(-5, 0)
        self.log_container.setGraphicsEffect(self.sidebar_shadow)

        # 日志边栏布局
        log_layout = QVBoxLayout(self.log_container)
        log_layout.setContentsMargins(10, 10, 10, 10)
        log_layout.setSpacing(8)

        # 侧边栏头部 - 高度降低，添加装饰线
        header_widget = QFrame()
        header_widget.setObjectName("log_header")
        header_widget.setFixedHeight(45)

        # 创建装饰线效果
        header_widget.setGraphicsEffect(self.create_header_shadow())

        # 标题栏布局
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(15, 8, 15, 8)
        header_layout.setSpacing(10)

        # 侧边栏标题
        self.log_title_label = QLabel("📋 下载日志")
        self.log_title_label.setObjectName("log_title_label")
        self.log_title_label.setAlignment(Qt.AlignCenter)

        # 关闭按钮 - 风格与主界面一致，位置调整
        self.sidebar_close_button = QPushButton("✕")
        self.sidebar_close_button.setObjectName("sidebar_close_button")
        self.sidebar_close_button.setFixedSize(28, 28)
        self.sidebar_close_button.clicked.connect(self.collapse_log)
        self.sidebar_close_button.hide()

        # 左侧占位 + 标题居中 + 右侧关闭按钮
        header_layout.addStretch()
        header_layout.addWidget(self.log_title_label, 0, Qt.AlignCenter)
        header_layout.addStretch()
        header_layout.addWidget(self.sidebar_close_button)

        # 日志文本框 - 与主界面表格风格一致
        self.output_box = QTextEdit()
        self.output_box.setObjectName("output_box")
        self.output_box.setReadOnly(True)
        self.output_box.setFixedHeight(860)
        self.output_box.hide()

        # 添加语法高亮器
        self.highlighter = LogSyntaxHighlighter(self.output_box.document())

        # 清空日志按钮 - 改为透明红色样式
        self.clear_log_button = QPushButton()
        self.clear_log_button.setObjectName("clear_log_button")
        self.clear_log_button.setFixedHeight(38)
        self.clear_log_button.hide()
        self.clear_log_button.clicked.connect(self.clear_log)

        # 将所有控件添加到布局
        log_layout.addWidget(header_widget)
        log_layout.addWidget(self.output_box, 1)
        log_layout.addWidget(self.clear_log_button)

    def create_sidebar_button(self):
        """
        创建与主界面风格一致的侧边栏触发按钮

        创建浮动在窗口右侧的按钮，用于展开/折叠日志边栏。
        """
        self.sidebar_toggle_button = QPushButton("📋")
        self.sidebar_toggle_button.setObjectName("sidebar_toggle_button")
        self.sidebar_toggle_button.setFixedSize(45, 45)

        # 添加按钮阴影 - 与主界面阴影一致
        button_shadow = QGraphicsDropShadowEffect(self.sidebar_toggle_button)
        button_shadow.setBlurRadius(15)
        button_shadow.setColor(QColor(0, 0, 0, 100))
        button_shadow.setOffset(0, 2)
        self.sidebar_toggle_button.setGraphicsEffect(button_shadow)

        # 连接按钮点击事件
        self.sidebar_toggle_button.clicked.connect(self.toggle_sidebar)

        # 将按钮添加到窗口
        self.sidebar_toggle_button.setParent(self)
        self.sidebar_toggle_button.raise_()

        # 定位按钮到窗口右侧边缘，垂直居中
        button_x = self.width() - 55
        button_y = self.height() // 2 - 22
        self.sidebar_toggle_button.move(button_x, button_y)

    def toggle_sidebar(self):
        """
        切换侧边栏状态

        根据当前侧边栏状态，展开或折叠日志边栏。
        防止在动画执行过程中重复触发。
        """
        if self.log_animating:
            return

        if self.log_expanded:
            self.collapse_log()
        else:
            self.expand_log()

    def expand_log(self):
        """
        展开侧边栏

        使用动画效果展开日志边栏，显示日志内容和相关控件。
        包括侧边栏宽度动画、窗口宽度动画和阴影动画。
        """
        if self.log_animating or self.log_expanded:
            return

        self.log_animating = True
        self.log_expanded = True

        # 隐藏浮动按钮
        self.sidebar_toggle_button.hide()

        # 显示侧边栏内容
        self.sidebar_close_button.show()
        self.output_box.show()
        self.clear_log_button.show()

        # 将侧边栏添加到布局
        self.layout().addWidget(self.log_container)

        # 创建动画组
        self.animation_group = QParallelAnimationGroup()

        # 1. 侧边栏宽度动画
        width_animation = QPropertyAnimation(self.log_container, b"minimumWidth")
        width_animation.setDuration(400)
        width_animation.setStartValue(0)
        width_animation.setEndValue(self.log_width)
        width_animation.setEasingCurve(QEasingCurve.OutCubic)

        # 2. 窗口宽度动画
        window_animation = QPropertyAnimation(self, b"minimumWidth")
        window_animation.setDuration(400)
        window_animation.setStartValue(self.base_width)
        window_animation.setEndValue(self.base_width + self.log_width)
        window_animation.setEasingCurve(QEasingCurve.OutCubic)

        # 3. 侧边栏阴影动画（从无到有）
        shadow_animation = QPropertyAnimation(self.sidebar_shadow, b"color")
        shadow_animation.setDuration(250)
        shadow_animation.setStartValue(QColor(0, 0, 0, 0))
        shadow_animation.setEndValue(QColor(0, 0, 0, 180))
        shadow_animation.setEasingCurve(QEasingCurve.OutCubic)

        # 添加动画到动画组
        self.animation_group.addAnimation(width_animation)
        self.animation_group.addAnimation(window_animation)
        self.animation_group.addAnimation(shadow_animation)

        # 动画完成回调
        self.animation_group.finished.connect(self.on_expand_finished)
        self.animation_group.start()

    def on_expand_finished(self):
        """
        展开动画完成回调

        动画执行完成后，更新动画状态锁并设置窗口最终大小。
        """
        self.log_animating = False
        self.setFixedSize(self.base_width + self.log_width, self.base_height)

    def collapse_log(self):
        """
        折叠侧边栏

        使用动画效果折叠日志边栏，隐藏日志内容和相关控件。
        包括侧边栏宽度动画、窗口宽度动画和阴影动画。
        """
        if self.log_animating or not self.log_expanded:
            return

        self.log_animating = True
        self.log_expanded = False

        # 创建动画组
        self.animation_group = QParallelAnimationGroup()

        # 1. 侧边栏宽度动画
        width_animation = QPropertyAnimation(self.log_container, b"minimumWidth")
        width_animation.setDuration(350)
        width_animation.setStartValue(self.log_width)
        width_animation.setEndValue(0)
        width_animation.setEasingCurve(QEasingCurve.InCubic)

        # 2. 窗口宽度动画
        window_animation = QPropertyAnimation(self, b"minimumWidth")
        window_animation.setDuration(350)
        window_animation.setStartValue(self.base_width + self.log_width)
        window_animation.setEndValue(self.base_width)
        window_animation.setEasingCurve(QEasingCurve.InCubic)

        # 3. 侧边栏阴影动画（从有到无）
        shadow_animation = QPropertyAnimation(self.sidebar_shadow, b"color")
        shadow_animation.setDuration(200)
        shadow_animation.setStartValue(QColor(0, 0, 0, 180))
        shadow_animation.setEndValue(QColor(0, 0, 0, 0))
        shadow_animation.setEasingCurve(QEasingCurve.InCubic)

        # 添加动画到动画组
        self.animation_group.addAnimation(width_animation)
        self.animation_group.addAnimation(window_animation)
        self.animation_group.addAnimation(shadow_animation)

        # 动画完成回调
        self.animation_group.finished.connect(self.on_collapse_finished)
        self.animation_group.start()

    def on_collapse_finished(self):
        """
        折叠动画完成回调

        动画执行完成后，隐藏侧边栏内容，从布局中移除侧边栏，
        显示浮动按钮并重新定位，恢复窗口原始大小。
        """
        self.log_animating = False

        # 隐藏侧边栏内容
        self.sidebar_close_button.hide()
        self.output_box.hide()
        self.clear_log_button.hide()

        # 从布局中移除侧边栏
        self.layout().removeWidget(self.log_container)

        # 显示浮动按钮并重新定位
        self.sidebar_toggle_button.show()
        self.reposition_toggle_button()

        # 确保窗口大小正确
        self.setFixedSize(self.base_width, self.base_height)

    def reposition_toggle_button(self):
        """
        重新定位浮动按钮

        根据当前窗口大小重新计算并定位侧边栏触发按钮的位置，
        确保按钮始终位于窗口右侧边缘中间位置。
        """
        if hasattr(self, 'sidebar_toggle_button') and self.sidebar_toggle_button:
            button_x = self.width() - 55
            button_y = self.height() // 2 - 22
            self.sidebar_toggle_button.move(button_x, button_y)

    def resizeEvent(self, event):
        """
        窗口大小变化事件处理

        当窗口大小改变时，重新定位侧边栏触发按钮的位置。

        Args:
            event: QResizeEvent对象，包含窗口大小变化信息
        """
        super().resizeEvent(event)
        self.reposition_toggle_button()

    def append_log_with_color(self, msg, color=None):
        """
        添加带颜色的日志消息

        Args:
            msg (str): 日志消息内容
            color (str, optional): HTML颜色值，如"#FF0000"
        """
        if color:
            # 使用HTML格式设置颜色
            colored_msg = f'<span style="color:{color};">{msg}</span>'
            self.output_box.append(colored_msg)
        else:
            # 使用语法高亮器自动着色
            self.output_box.append(msg)

        # 滚动到底部
        self.output_box.moveCursor(QTextCursor.End)

    def append_log(self, msg):
        """
        增加日志方法 - 现在输出到右侧边栏，支持多种颜色

        使用语法高亮器自动为不同类型的日志消息着色。

        Args:
            msg (str): 日志消息内容
        """
        # 使用语法高亮器自动着色
        self.output_box.append(msg)

        # 滚动到底部
        self.output_box.moveCursor(QTextCursor.End)

    def show_cookie_message(self, message, message_type="info"):
        """
        显示Cookie相关信息到日志框

        Args:
            message (str): 消息文本
            message_type (str): 消息类型，可以是 "info", "warning", "error", "success"
        """
        # 如果侧边栏未展开，自动展开它
        if not self.log_expanded:
            self.expand_log()

        # 根据消息类型设置颜色和前缀
        if message_type == "warning":
            color = "#FFA726"
            prefix = "⚠️ "
        elif message_type == "error":
            color = "#FF5252"
            prefix = "❌ "
        elif message_type == "success":
            color = "#4CAF50"
            prefix = "✅ "
        else:  # info
            color = "#2196F3"
            prefix = "ℹ️ "

        # 添加时间戳
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        full_message = f"{timestamp} {prefix}{message}"

        # 记录到日志
        self.append_log_with_color(full_message, color)

    @staticmethod
    def set_status_color(item, status):
        """
        根据状态设置状态列的颜色

        Args:
            item (QTableWidgetItem): 表格项对象
            status (str): 状态字符串
        """
        status = status.lower() if status else ""

        if "waiting" in status:
            item.setForeground(QColor("#FFC107"))  # 黄色
        elif "succeed" in status or "success" in status or "complete" in status or "完成" in status:
            item.setForeground(QColor("#4CAF50"))  # 绿色
        elif "failed" in status or "error" in status or "失败" in status:
            item.setForeground(QColor("#FF5252"))  # 红色
        elif "downloading" in status or "processing" in status or "下载中" in status:
            item.setForeground(QColor("#2196F3"))  # 蓝色
        else:
            item.setForeground(QColor("#E2E8F0"))  # 默认白色

    @staticmethod
    def create_header_shadow():
        """
        创建标题栏阴影效果

        Returns:
            QGraphicsDropShadowEffect: 配置好的阴影效果对象
        """
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 229, 255, 80))  # 青色阴影
        shadow.setOffset(0, 2)
        return shadow

    # ================= 任务表操作 =================
    def add_task_row(self, url):
        """
        在任务表中添加新任务行

        Args:
            url (str): 视频URL地址

        Returns:
            tuple: (行索引, 进度条对象)
        """
        row = self.task_table.rowCount()
        self.task_table.insertRow(row)

        # 添加任务URL
        self.task_table.setItem(row, 0, QTableWidgetItem(url))

        # 添加状态列（默认等待中）
        status_item = QTableWidgetItem("Waiting")
        status_item.setTextAlignment(Qt.AlignCenter)
        self.set_status_color(status_item, "Waiting")
        self.task_table.setItem(row, 1, status_item)

        # 添加进度条
        progress = QProgressBar()
        progress.setValue(0)
        self.task_table.setCellWidget(row, 2, progress)

        # 添加结果列（默认占位符）
        result_item = QTableWidgetItem("—")
        result_item.setTextAlignment(Qt.AlignCenter)
        self.task_table.setItem(row, 3, result_item)

        return row, progress

    # ================= Cookie文件管理 =================
    def load_cookie_files(self):
        """加载已有的Cookie文件"""
        self.cookie_files = []
        self.cookie_combo.clear()

        # 添加自动获取选项
        self.cookie_combo.addItem(self._tr("自动获取浏览器Cookie", "Auto-get browser cookies"), None)

        # 添加无Cookie选项
        self.cookie_combo.addItem(self._tr("不使用Cookie", "No Cookie"), "no_cookie")

        # 检查cookies目录
        cookie_dir = os.path.join(os.getcwd(), "cookies")
        if not os.path.exists(cookie_dir):
            os.makedirs(cookie_dir)

        # 加载目录中的cookie文件
        for file_name in os.listdir(cookie_dir):
            if file_name.endswith('.txt'):
                file_path = os.path.join(cookie_dir, file_name)
                if os.path.getsize(file_path) > 10:  # 只加载非空文件
                    file_size = os.path.getsize(file_path)
                    modified_time = datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d')

                    file_info = {
                        'name': file_name,
                        'path': file_path,
                        'size': file_size,
                        'modified': modified_time
                    }
                    self.cookie_files.append(file_info)

                    # 添加到下拉框
                    display_text = f"{file_name} ({file_size}字节, {modified_time})"
                    self.cookie_combo.addItem(display_text, file_path)

    def _tr(self, zh, en):
        """翻译辅助函数"""
        return zh if self.current_language == 'zh' else en

    def on_cookie_selected(self, index):
        """Cookie文件选择改变"""
        if index > 1:
            file_path = self.cookie_combo.itemData(index)
            self.current_cookie_file = file_path
            self.cookie_delete_button.setEnabled(True)

            # 显示选择信息到日志框
            file_name = os.path.basename(file_path)
            self.show_cookie_message(
                self._tr(f"已选择Cookie文件: {file_name}", f"Selected cookie file: {file_name}"),
                "info"
            )
        elif index == 0:  # 自动获取浏览器Cookie
            self.current_cookie_file = None
            self.cookie_delete_button.setEnabled(False)

            # 显示选择信息到日志框
            self.show_cookie_message(
                self._tr("已选择自动获取浏览器Cookie", "Selected auto-get browser cookies"),
                "info"
            )
        elif index == 1:  # 不使用Cookie
            self.current_cookie_file = "no_cookie"
            self.cookie_delete_button.setEnabled(False)

            # 显示选择信息到日志框
            self.show_cookie_message(
                self._tr("已选择不使用Cookie", "Selected no cookie"),
                "info"
            )

    def upload_cookie_file(self):
        """上传Cookie文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self._tr("选择Cookie文件", "Select Cookie File"),
            "",
            self._tr("Cookie文件 (*.txt);;所有文件 (*.*)", "Cookie Files (*.txt);;All Files (*.*)")
        )

        if file_path:
            try:
                # 验证文件内容
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if not content:
                        self.show_cookie_message(
                            self._tr("Cookie文件内容为空", "Cookie file is empty"),
                            "error"
                        )
                        return

                # 创建cookies目录
                cookie_dir = os.path.join(os.getcwd(), "cookies")
                if not os.path.exists(cookie_dir):
                    os.makedirs(cookie_dir)

                # 复制文件到cookies目录
                file_name = os.path.basename(file_path)
                dest_path = os.path.join(cookie_dir, file_name)

                # 如果文件已存在，添加时间戳避免冲突
                if os.path.exists(dest_path):
                    base_name, ext = os.path.splitext(file_name)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    file_name = f"{base_name}_{timestamp}{ext}"
                    dest_path = os.path.join(cookie_dir, file_name)

                shutil.copy2(file_path, dest_path)

                # 重新加载Cookie文件
                self.load_cookie_files()

                # 选择新上传的文件
                for i in range(self.cookie_combo.count()):
                    if self.cookie_combo.itemData(i) == dest_path:
                        self.cookie_combo.setCurrentIndex(i)
                        break

                self.show_cookie_message(
                    self._tr(f"Cookie文件上传成功: {file_name}", f"Cookie file uploaded successfully: {file_name}"),
                    "success"
                )

            except Exception as e:
                self.show_cookie_message(
                    self._tr(f"上传Cookie文件失败: {str(e)}", f"Failed to upload cookie file: {str(e)}"),
                    "error"
                )

    def delete_cookie_file(self):
        """删除选中的Cookie文件"""
        if not self.current_cookie_file or self.current_cookie_file in [None, "no_cookie"]:
            return

        file_name = os.path.basename(self.current_cookie_file)

        # 显示确认信息
        self.show_cookie_message(
            self._tr(f"确认删除Cookie文件 '{file_name}'？", f"Confirm delete cookie file '{file_name}'?"),
            "warning"
        )

        try:
            os.remove(self.current_cookie_file)
            self.load_cookie_files()  # 重新加载
            self.cookie_combo.setCurrentIndex(0)  # 选择"自动获取浏览器Cookie"

            self.show_cookie_message(
                self._tr(f"Cookie文件已删除: {file_name}", f"Cookie file deleted: {file_name}"),
                "success"
            )
        except Exception as e:
            self.show_cookie_message(
                self._tr(f"删除Cookie文件失败: {str(e)}", f"Failed to delete cookie file: {str(e)}"),
                "error"
            )

    # ================= 下载逻辑 =================
    def download_video(self):
        """
        下载视频主入口

        根据当前模式（单URL或批量）获取URL列表，
        验证输入有效性后启动下载任务。
        """
        folder = self.folder_path.text().strip()
        if not folder:
            self.show_cookie_message(
                self.translations['error_empty_fields'][self.current_language],
                "error"
            )
            return

        # 获取清晰度选择
        quality = self.quality_combo.currentData()

        # 根据模式获取URL列表
        if self.batch_mode:
            urls = [
                u.strip() for u in self.url_input_multiline.toPlainText().splitlines()
                if u.strip()
            ]
        else:
            urls = [self.url_input.text().strip()] if self.url_input.text().strip() else []

        # 验证URL列表
        if not urls:
            self.show_cookie_message(
                self.translations['error_empty_fields'][self.current_language],
                "error"
            )
            return

        # 显示清晰度选择信息
        self.show_cookie_message(
            self._tr(f"已选择清晰度: {quality}", f"Selected quality: {quality}"),
            "info"
        )

        # 启动每个URL的下载任务
        for url in urls:
            self.start_download_task(url, folder, quality)

    def start_download_task(self, url, folder, quality):
        """
        启动单个下载任务

        Args:
            url (str): 视频URL地址
            folder (str): 保存文件夹路径
            quality (str): 视频清晰度
        """
        # 添加任务到表格
        row, progress_bar = self.add_task_row(url)

        # 确定要使用的cookie文件
        cookie_file = None
        if self.current_cookie_file:
            if self.current_cookie_file != "no_cookie":
                cookie_file = self.current_cookie_file

        # 创建工作线程（传递cookie_file和quality参数）
        worker = DownloadWorker(url, folder, self.current_language, cookie_file, quality)
        thread = QThread()

        # 将工作线程移动到新线程
        worker.moveToThread(thread)

        # 连接信号和槽
        worker.progress_signal.connect(progress_bar.setValue)

        def update_status(status):
            """更新状态并设置颜色"""
            item = self.task_table.item(row, 1)
            if item:
                item.setText(status)
                self.set_status_color(item, status)

        worker.status_signal.connect(update_status)
        worker.log_signal.connect(self.append_log)

        # 连接Cookie相关信号
        worker.cookie_info_signal.connect(lambda msg: self.show_cookie_message(msg, "info"))
        worker.cookie_warning_signal.connect(lambda msg: self.show_cookie_message(msg, "warning"))
        worker.cookie_error_signal.connect(lambda msg: self.show_cookie_message(msg, "error"))
        worker.cookie_success_signal.connect(lambda msg: self.show_cookie_message(msg, "success"))

        # 连接完成信号
        def on_finished():
            thread.quit()
            self.task_table.item(row, 3).setText("Succeed")
            self.add_to_history(
                url, self.translations['status_complete'][self.current_language]
            )

        worker.finished_signal.connect(on_finished)

        # 连接错误信号
        def on_error(msg):
            update_status("Failed")
            self.show_cookie_message(
                self._tr(f"下载失败: {msg}", f"Download failed: {msg}"),
                "error"
            )

        worker.error_signal.connect(on_error)

        # 启动线程
        thread.started.connect(worker.run)
        thread.start()

        # 保存工作线程和线程对象引用
        self.workers.append(worker)
        self.worker_threads.append(thread)

    # ================= 语言 & UI =================
    def toggle_batch_mode(self):
        """
        切换批量下载模式

        在单URL输入和多行URL输入之间切换，并同步输入内容。
        """
        self.batch_mode = not self.batch_mode
        self.url_input.setVisible(not self.batch_mode)
        self.url_input_multiline.setVisible(self.batch_mode)

        # 同步输入内容
        if self.batch_mode:
            self.url_input_multiline.setPlainText(self.url_input.text())
            self.show_cookie_message(
                self._tr("已切换到批量下载模式", "Switched to batch download mode"),
                "info"
            )
        else:
            text = self.url_input_multiline.toPlainText().strip().split("\n")[0]
            self.url_input.setText(text)
            self.show_cookie_message(
                self._tr("已切换到单URL下载模式", "Switched to single URL download mode"),
                "info"
            )

    def toggle_language(self):
        """
        切换界面语言

        在中英文之间切换，更新界面文本和按钮状态。
        """
        self.current_language = 'en' if self.current_language == 'cn' else 'cn'
        self.lang_button.setText("EN" if self.current_language == 'cn' else "CN")
        self.update_language()
        self.history_manager.set_language(self.current_language)

    def update_language(self):
        """
        更新界面文本

        根据当前语言设置更新所有界面元素的文本内容。
        """
        lang = self.current_language

        # 更新窗口标题
        self.setWindowTitle(self.translations['window_title'][lang])

        # 更新主界面文本
        self.title_label.setText(self.translations['title'][lang])
        self.url_label.setText(self.translations['url_label'][lang])
        self.folder_label.setText(self.translations['folder_label'][lang])
        self.folder_button.setText(self.translations['folder_button'][lang])
        self.download_button.setText(self.translations['download_button'][lang])
        self.log_title_label.setText(self.translations['output_label'][lang])
        self.clear_log_button.setText(self.translations['clear_log'][lang])
        self.batch_button.setText(self.translations['batch_import'][lang])

        # 更新清晰度标签
        self.quality_label.setText(self.translations['quality_label'][lang])

        # 更新Cookie相关文本
        self.cookie_upload_button.setText(self.translations['cookie_upload'][lang])
        self.cookie_delete_button.setText(self.translations['cookie_delete'][lang])

        # 更新下拉框的前两个选项
        if self.cookie_combo.count() > 1:
            self.cookie_combo.setItemText(0, self.translations['auto_cookie'][lang])
            self.cookie_combo.setItemText(1, self.translations['no_cookie'][lang])

        # 更新选项卡文本
        self.tabs.setTabText(0, self.translations['title'][lang])
        self.tabs.setTabText(1, self.translations['history_label'][lang])

    # ================= 工具 =================
    def choose_folder(self):
        """
        选择保存文件夹

        打开文件夹选择对话框，让用户选择视频保存位置。
        """
        folder = QFileDialog.getExistingDirectory(
            self, self.translations['folder_button'][self.current_language]
        )
        if folder:
            self.folder_path.setText(folder)
            self.show_cookie_message(
                self._tr(f"已选择保存文件夹: {folder}", f"Selected save folder: {folder}"),
                "info"
            )

    def add_to_history(self, url, status):
        """
        添加任务到历史记录

        Args:
            url (str): 视频URL地址
            status (str): 任务完成状态
        """
        self.history_manager.add_to_history(url, status)

    def clear_log(self):
        """
        清空日志

        清空右侧边栏中的所有日志内容。
        """
        self.output_box.clear()
        self.show_cookie_message(
            self._tr("日志已清空", "Log cleared"),
            "info"
        )


if __name__ == '__main__':

    # 创建应用程序实例
    app = QApplication(sys.argv)

    # 设置全局样式（使用qdarkstyle）
    app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())

    # 创建主窗口并显示
    window = HDDownloader()
    window.show()

    # 启动事件循环
    sys.exit(app.exec_())

    # pyinstaller --onefile --windowed --clean --icon=icon.ico --name VideoDownloader main.py
