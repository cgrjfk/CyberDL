import json
import os
import webbrowser

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor, QBrush
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QHBoxLayout, QPushButton,
    QMessageBox, QMenu, QFileDialog, QApplication, QAbstractItemView
)

HISTORY_FILE = "download_history.json"  # 历史记录保存文件
MAX_VISIBLE = 15  # 可视化的最多条数
QSS_FILE = "history.qss"  # CSS样式文件


# ============================
# HistoryManager
# ----------------------------
# 下载历史管理组件
#
# 功能概述：
# - 展示下载 URL 与状态的历史记录
# - 支持搜索、分页加载、右键操作
# - 支持历史导出与多语言切换
# - 使用外部 QSS 文件统一样式
#
# 设计特点：
# - 数据与 UI 解耦
# - 表格按比例自适应
# - 所有修改均持久化到 JSON
# ============================
class HistoryManager(QWidget):

    # ----------------------------
    # 初始化历史管理界面
    #
    # 参数：
    # - translations: 多语言字典
    # - lang: 当前语言标识
    # ----------------------------
    def __init__(self, translations, lang):
        super().__init__()
        self.translations = translations
        self.current_language = lang

        # 加载CSS样式
        self._load_stylesheet()

        # ===== 标题 =====
        self.history_label = QLabel(self.translations['history_label'][self.current_language])
        self.history_label.setObjectName("historyLabel")

        # ===== 搜索栏 =====
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search history links or status")
        self.search_bar.setObjectName("searchBar")
        self.search_bar.textChanged.connect(self.refresh_history_list)

        # ===== 按钮 =====
        # 清空按钮
        self.clear_btn = QPushButton(self.translations.get("clear_btn", {}).get(lang, "清空全部"))
        self.clear_btn.setFixedWidth(150)
        self.clear_btn.setObjectName("clearButton")
        self.clear_btn.clicked.connect(self.clear_history)

        # 导出按钮
        self.export_btn = QPushButton(self.translations.get("export_history", {}).get(lang, "导出历史"))
        self.export_btn.setFixedWidth(150)
        self.export_btn.setObjectName("exportButton")
        self.export_btn.clicked.connect(self.export_history)

        # 加载更多按钮
        self.load_more_btn = QPushButton(self.translations.get("load_more", {}).get(lang, "加载更多"))
        self.load_more_btn.setObjectName("loadMoreButton")
        self.load_more_btn.clicked.connect(self.show_more_history)

        # ===== 空状态提示 =====
        self.empty_label = QLabel(self.translations.get("empty_history", {}).get(lang, "暂无下载历史"))
        self.empty_label.setObjectName("emptyLabel")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.hide()

        # ===== 历史表格 =====
        self.table = QTableWidget()
        self.table.setObjectName("historyTable")
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(['URL', "Status"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setWordWrap(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.table_right_click)

        # ===== 布局 =====
        top_row = QHBoxLayout()
        top_row.addWidget(self.history_label)
        top_row.addStretch()
        top_row.addWidget(self.export_btn)
        top_row.addWidget(self.clear_btn)

        layout = QVBoxLayout(self)
        layout.addLayout(top_row)
        layout.addWidget(self.search_bar)
        layout.addWidget(self.table)
        layout.addWidget(self.empty_label)
        layout.addWidget(self.load_more_btn, alignment=Qt.AlignCenter)
        self.setLayout(layout)
        self.setMinimumWidth(1270)
        self.setMinimumHeight(600)

        # ===== 数据 =====
        self.history = []
        self.display_count = MAX_VISIBLE
        self.load_history()

    # ----------------------------
    # 加载外部 QSS 样式表
    # ----------------------------
    def _load_stylesheet(self):
        try:
            if os.path.exists(QSS_FILE):
                with open(QSS_FILE, 'r', encoding='utf-8') as f:
                    self.setStyleSheet(f.read())
        except Exception as e:
            print(f"加载CSS样式表失败: {e}")

    # ----------------------------
    # 设置表格列宽比例（URL:状态 = 7:3）
    # ----------------------------
    def set_table_col_stretch(self):
        total = self.table.viewport().width()
        self.table.setColumnWidth(0, int(total * 0.7))
        self.table.setColumnWidth(1, int(total * 0.3))

    # ----------------------------
    # 窗口尺寸变化时自适应列宽
    # ----------------------------
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.set_table_col_stretch()

    # ----------------------------
    # 从本地 JSON 文件加载历史记录
    # ----------------------------
    def load_history(self):
        self.history = []
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    self.history = json.load(f)
            except Exception:
                self.history = []
        self.display_count = MAX_VISIBLE
        self.refresh_history_list()

    # ----------------------------
    # 将当前历史记录保存到本地
    # ----------------------------
    def save_history(self):
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ----------------------------
    # 根据搜索条件刷新表格内容
    # ----------------------------
    def refresh_history_list(self):
        self.table.setRowCount(0)
        query = self.search_bar.text().strip().lower()
        show_items = self.history[-self.display_count:][::-1]
        if query:
            show_items = [
                item for item in show_items
                if query in item.get("url", "").lower()
                or query in item.get("status", "").lower()
            ]
        if not show_items:
            self.empty_label.show()
            self.load_more_btn.hide()
            return

        self.empty_label.hide()
        for item in show_items:
            row = self.table.rowCount()
            self.table.insertRow(row)

            url_item = QTableWidgetItem(item.get("url", ""))
            url_item.setToolTip(item.get("url", ""))
            url_item.setFont(QFont("Arial", 10))
            url_item.setForeground(QBrush(QColor("#ffffff")))
            url_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

            status_item = QTableWidgetItem(item.get("status", ""))
            status_item.setFont(QFont("Arial", 11, QFont.Bold))
            status_item.setTextAlignment(Qt.AlignCenter)

            status_color = {
                "完成！": "#4CAF50",
                "Complete!": "#4CAF50",
                "下载失败": "#FF5252",
                "Download Failed": "#FF5252"
            }.get(item.get("status", ""), "#00BCD4")
            status_item.setForeground(QBrush(QColor(status_color)))

            self.table.setItem(row, 0, url_item)
            self.table.setItem(row, 1, status_item)

        self.set_table_col_stretch()
        self.table.resizeRowsToContents()
        self.load_more_btn.setVisible(self.display_count < len(self.history) and not query)

    # ----------------------------
    # 分页加载更多历史记录
    # ----------------------------
    def show_more_history(self):
        self.display_count += MAX_VISIBLE
        self.refresh_history_list()

    # ----------------------------
    # 清空全部历史记录（带确认）
    # ----------------------------
    def clear_history(self):
        reply = QMessageBox.question(
            self,
            self.translations['history_label'][self.current_language],
            self.translations.get("clear_confirm", {}).get(self.current_language, "确定要清空所有历史记录吗？"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.history = []
            self.save_history()
            self.refresh_history_list()

    # ----------------------------
    # 删除指定视图索引对应的历史记录
    # ----------------------------
    def delete_callback(self, view_idx):
        query = self.search_bar.text().strip().lower()
        show_items = self.history[-self.display_count:][::-1]
        if query:
            show_items = [
                item for item in show_items
                if query in item.get("url", "").lower()
                or query in item.get("status", "").lower()
            ]
        if 0 <= view_idx < len(show_items):
            to_del = show_items[view_idx]
            for i, h in enumerate(self.history):
                if h.get("url") == to_del.get("url") and h.get("status") == to_del.get("status"):
                    self.history.pop(i)
                    break
            self.save_history()
            self.display_count = min(self.display_count, len(self.history))
            self.refresh_history_list()

    # ----------------------------
    # 向历史记录中追加一条新记录
    # ----------------------------
    def add_to_history(self, url, status):
        self.history.append({"url": url, "status": status})
        self.save_history()
        self.display_count = min(self.display_count + 1, len(self.history))
        self.refresh_history_list()

    # ----------------------------
    # 切换界面语言
    # ----------------------------
    def set_language(self, lang):
        self.current_language = lang
        self.history_label.setText(self.translations['history_label'][lang])
        self.clear_btn.setText(self.translations.get("clear_btn", {}).get(lang, "清空全部"))
        self.export_btn.setText(self.translations.get("export_history", {}).get(lang, "导出历史"))
        self.load_more_btn.setText(self.translations.get("load_more", {}).get(lang, "加载更多"))
        self.empty_label.setText(self.translations.get("empty_history", {}).get(lang, "暂无下载历史"))
        self.search_bar.setPlaceholderText(
            self.translations.get("search_text", {}).get(lang, "搜索历史链接或状态")
        )
        self.refresh_history_list()

    # ----------------------------
    # 导出历史记录到文本文件
    # ----------------------------
    def export_history(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "导出历史", "download_history.txt", "Text Files (*.txt)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                for item in self.history:
                    f.write(f"URL: {item.get('url', '')}\nStatus: {item.get('status', '')}\n\n")
            QMessageBox.information(self, "导出成功", f"历史已导出到: {path}")
        except Exception as e:
            QMessageBox.warning(self, "导出失败", f"导出历史失败: {str(e)}")

    # ----------------------------
    # 显示 Toast 风格的提示消息
    # ----------------------------
    def show_toast_message(self, message, duration=2000):
        toast = QLabel(message, self)
        toast.setObjectName("toastLabel")
        toast.setAlignment(Qt.AlignCenter)
        toast.adjustSize()
        toast.move(self.width() // 2 - toast.width() // 2, self.height() - 100)
        toast.show()
        QTimer.singleShot(duration, toast.hide)

    # ----------------------------
    # 表格右键菜单处理
    # ----------------------------
    def table_right_click(self, pos):
        idx = self.table.indexAt(pos)
        if not idx.isValid():
            return
        row = idx.row()
        url = self.table.item(row, 0).text()

        menu = QMenu(self)
        menu.addAction(
            self.translations.get('copy_action', {}).get(self.current_language, "复制链接"),
            lambda: QApplication.clipboard().setText(url)
        )
        menu.addAction(
            self.translations.get('delete_action', {}).get(self.current_language, "删除记录"),
            lambda: self.delete_callback(row)
        )
        menu.addAction(
            self.translations.get('open_in_browser', {}).get(self.current_language, "浏览器打开"),
            lambda: webbrowser.open(url)
        )
        menu.exec_(self.table.viewport().mapToGlobal(pos))
