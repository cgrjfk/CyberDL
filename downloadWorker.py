import os
import shutil
import sqlite3
import tempfile

import yt_dlp
from PyQt5.QtCore import pyqtSignal, QObject

try:
    import browser_cookie3

    BROWSER_COOKIE_AVAILABLE = True
except ImportError:
    BROWSER_COOKIE_AVAILABLE = False

# 尝试导入Windows加密相关模块
try:
    from Crypto.Cipher import AES
    from Crypto.Protocol.KDF import PBKDF2

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


def _extract_domain_from_url(url):
    """从URL中提取域名"""
    try:
        # 提取主域名
        if 'youtube.com' in url or 'youtu.be' in url:
            return ['youtube.com', '.youtube.com']
        elif 'bilibili.com' in url:
            return ['bilibili.com', '.bilibili.com']
        elif 'twitter.com' in url or 'x.com' in url:
            return ['twitter.com', '.twitter.com']
        elif 'facebook.com' in url:
            return ['facebook.com', '.facebook.com']
        elif 'instagram.com' in url:
            return ['instagram.com', '.instagram.com']
        else:
            # 尝试从URL提取通用域名
            import urllib.parse
            parsed = urllib.parse.urlparse(url)
            domain = parsed.netloc
            if domain:
                return [domain, f'.{domain}']
            return None
    except:
        return None


class DownloadWorker(QObject):
    progress_signal = pyqtSignal(int)
    status_signal = pyqtSignal(str)
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)
    open_signal = pyqtSignal(str)

    # Cookie相关信号
    cookie_info_signal = pyqtSignal(str)
    cookie_warning_signal = pyqtSignal(str)
    cookie_error_signal = pyqtSignal(str)
    cookie_success_signal = pyqtSignal(str)

    def __init__(self, url, folder, language='zh', cookie_file=None, quality='best'):
        super().__init__()
        self.url = url
        self.folder = folder
        self.language = language if language in ['zh', 'en'] else 'zh'
        self.cookie_file = cookie_file
        self.quality = quality
        self.temp_cookie_file = None

    def _tr(self, zh, en):
        return zh if self.language == 'zh' else en

    def _get_chrome_cookie_manually(self):
        """手动获取Chrome Cookie（绕过加密问题）"""
        try:
            import winreg
            import shutil
            import tempfile

            # Chrome Cookie数据库路径
            chrome_paths = [
                os.path.join(os.environ['LOCALAPPDATA'], 'Google', 'Chrome', 'User Data', 'Default', 'Cookies'),
                os.path.join(os.environ['LOCALAPPDATA'], 'Google', 'Chrome', 'User Data', 'Profile 1', 'Cookies'),
                os.path.join(os.environ['LOCALAPPDATA'], 'Google', 'Chrome', 'User Data', 'Profile 2', 'Cookies'),
            ]

            cookie_db_path = None
            for path in chrome_paths:
                if os.path.exists(path):
                    cookie_db_path = path
                    break

            if not cookie_db_path:
                return None

            # 复制数据库文件
            temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
            temp_db.close()
            shutil.copy2(cookie_db_path, temp_db.name)

            # 连接到SQLite数据库
            conn = sqlite3.connect(temp_db.name)
            cursor = conn.cursor()

            # 获取域列表
            domains = _extract_domain_from_url(self.url)
            if not domains:
                return None

            # 查询相关cookie
            cookies = []
            for domain in domains:
                cursor.execute('''
                    SELECT host_key, path, secure, expires_utc, name, value, encrypted_value
                    FROM cookies 
                    WHERE host_key LIKE ? OR host_key LIKE ?
                ''', (domain, f'%{domain}'))

                for row in cursor.fetchall():
                    host_key, path, secure, expires_utc, name, value, encrypted_value = row

                    # 如果value为空但encrypted_value不为空，尝试解密
                    cookie_value = value
                    if not value and encrypted_value:
                        try:
                            # 加密则使用yt-dlp chrome此处无法解密
                            continue
                        except:
                            continue

                    cookies.append({
                        'domain': host_key,
                        'path': path,
                        'secure': bool(secure),
                        'expires': expires_utc,
                        'name': name,
                        'value': cookie_value
                    })

            conn.close()
            os.unlink(temp_db.name)

            if cookies:
                # 创建临时cookie文件
                self.temp_cookie_file = tempfile.NamedTemporaryFile(
                    mode='w',
                    suffix='.txt',
                    delete=False,
                    encoding='utf-8'
                )

                # Netscape格式
                self.temp_cookie_file.write("# Netscape HTTP Cookie File\n")
                for cookie in cookies:
                    domain = cookie['domain']
                    if domain.startswith('.'):
                        domain = domain[1:]

                    line = f"{domain}\tTRUE\t{cookie['path']}\t{str(cookie['secure']).upper()}\t{cookie['expires']}\t{cookie['name']}\t{cookie['value']}\n"
                    self.temp_cookie_file.write(line)

                self.temp_cookie_file.close()
                return self.temp_cookie_file.name

            return None

        except Exception as e:
            return None

    def _get_firefox_cookies_manually(self):
        """手动获取Firefox Cookie（通常没有加密问题）"""
        try:
            # Firefox配置文件路径
            firefox_paths = [
                os.path.join(os.environ['APPDATA'], 'Mozilla', 'Firefox', 'Profiles'),
                os.path.join(os.environ['LOCALAPPDATA'], 'Mozilla', 'Firefox', 'Profiles'),
            ]

            profiles_dir = None
            for path in firefox_paths:
                if os.path.exists(path):
                    profiles_dir = path
                    break

            if not profiles_dir:
                return None

            # 查找最新的配置文件
            profiles = []
            for item in os.listdir(profiles_dir):
                profile_path = os.path.join(profiles_dir, item)
                if os.path.isdir(profile_path):
                    # 检查是否有cookies.sqlite
                    cookie_db = os.path.join(profile_path, 'cookies.sqlite')
                    if os.path.exists(cookie_db):
                        profiles.append((profile_path, os.path.getmtime(cookie_db)))

            if not profiles:
                return None

            # 使用最新的配置文件
            profiles.sort(key=lambda x: x[1], reverse=True)
            latest_profile = profiles[0][0]
            cookie_db = os.path.join(latest_profile, 'cookies.sqlite')

            # 复制数据库文件
            temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
            temp_db.close()
            shutil.copy2(cookie_db, temp_db.name)

            # 连接到SQLite数据库
            conn = sqlite3.connect(temp_db.name)
            cursor = conn.cursor()

            # 获取域列表
            domains = _extract_domain_from_url(self.url)
            if not domains:
                return None

            # 查询相关cookie
            cookies = []
            for domain in domains:
                cursor.execute('''
                    SELECT host, path, isSecure, expiry, name, value
                    FROM moz_cookies 
                    WHERE host LIKE ? OR host LIKE ?
                ''', (domain, f'%{domain}'))

                for row in cursor.fetchall():
                    host, path, isSecure, expiry, name, value = row
                    cookies.append({
                        'domain': host,
                        'path': path,
                        'secure': bool(isSecure),
                        'expires': expiry,
                        'name': name,
                        'value': value
                    })

            conn.close()
            os.unlink(temp_db.name)

            if cookies:
                # 创建临时cookie文件
                self.temp_cookie_file = tempfile.NamedTemporaryFile(
                    mode='w',
                    suffix='.txt',
                    delete=False,
                    encoding='utf-8'
                )

                # Netscape格式
                self.temp_cookie_file.write("# Netscape HTTP Cookie File\n")
                for cookie in cookies:
                    domain = cookie['domain']
                    if domain.startswith('.'):
                        domain = domain[1:]

                    line = f"{domain}\tTRUE\t{cookie['path']}\t{str(cookie['secure']).upper()}\t{cookie['expires']}\t{cookie['name']}\t{cookie['value']}\n"
                    self.temp_cookie_file.write(line)

                self.temp_cookie_file.close()
                return self.temp_cookie_file.name

            return None

        except Exception as e:
            return None

    def _get_browser_cookies(self):
        """尝试从浏览器获取cookie（改进版）"""
        if not BROWSER_COOKIE_AVAILABLE:
            self.cookie_error_signal.emit(
                self._tr("未安装browser_cookie3库，无法自动获取浏览器Cookie",
                         "browser_cookie3 not installed, cannot auto-get browser cookies")
            )
            return None

        domain = _extract_domain_from_url(self.url)
        if not domain:
            self.cookie_warning_signal.emit(
                self._tr("无法从URL识别域名，跳过浏览器Cookie获取",
                         "Cannot recognize domain from URL, skipping browser cookie fetch")
            )
            return None

        self.cookie_info_signal.emit(
            self._tr(f"尝试从浏览器获取 {domain} 的Cookie...",
                     f"Trying to get cookies for {domain} from browser...")
        )

        # 优先尝试Firefox（通常没有加密问题）
        try:
            firefox_cookies = self._get_firefox_cookies_manually()
            if firefox_cookies:
                self.cookie_success_signal.emit(
                    self._tr(f"✅ 成功从 Firefox 获取Cookie",
                             f"✅ Successfully got cookies from Firefox")
                )
                return firefox_cookies
        except Exception as e:
            pass

        # 然后尝试标准方法
        try:
            browsers = [
                ('Firefox', browser_cookie3.firefox),
                ('Chrome', browser_cookie3.chrome),
                ('Edge', browser_cookie3.edge),
                ('Opera', browser_cookie3.opera),
                ('Brave', browser_cookie3.brave),
            ]

            tried_browsers = []

            for browser_name, browser_func in browsers:
                try:
                    self.cookie_info_signal.emit(
                        self._tr(f"尝试从 {browser_name} 获取Cookie...",
                                 f"Trying to get cookies from {browser_name}...")
                    )

                    tried_browsers.append(browser_name)

                    # 尝试获取所有cookie，然后过滤
                    cookies = browser_func()

                    if cookies:
                        # 过滤相关域名的cookie
                        filtered_cookies = []
                        for cookie in cookies:
                            cookie_domain = getattr(cookie, 'domain', '')
                            for d in domain:
                                if d in cookie_domain:
                                    filtered_cookies.append(cookie)
                                    break

                        if filtered_cookies:
                            # 创建临时cookie文件
                            self.temp_cookie_file = tempfile.NamedTemporaryFile(
                                mode='w',
                                suffix='.txt',
                                delete=False,
                                encoding='utf-8'
                            )

                            # Netscape格式
                            self.temp_cookie_file.write("# Netscape HTTP Cookie File\n")

                            cookie_count = 0
                            for cookie in filtered_cookies:
                                try:
                                    cookie_domain = getattr(cookie, 'domain', '')
                                    cookie_path = getattr(cookie, 'path', '/')
                                    cookie_secure = getattr(cookie, 'secure', False)
                                    cookie_expires = getattr(cookie, 'expires', 0)
                                    cookie_name = getattr(cookie, 'name', '')
                                    cookie_value = getattr(cookie, 'value', '')

                                    if not cookie_name or not cookie_value:
                                        continue

                                    # 处理域名
                                    if cookie_domain.startswith('.'):
                                        cookie_domain = cookie_domain[1:]

                                    line = f"{cookie_domain}\tTRUE\t{cookie_path}\t{'TRUE' if cookie_secure else 'FALSE'}\t{cookie_expires or 0}\t{cookie_name}\t{cookie_value}\n"
                                    self.temp_cookie_file.write(line)
                                    cookie_count += 1

                                except Exception as e:
                                    continue

                            self.temp_cookie_file.close()

                            if cookie_count > 0:
                                self.cookie_success_signal.emit(
                                    self._tr(f"✅ 成功从 {browser_name} 获取 {cookie_count} 个Cookie",
                                             f"✅ Successfully got {cookie_count} cookies from {browser_name}")
                                )
                                return self.temp_cookie_file.name
                            else:
                                os.unlink(self.temp_cookie_file.name)
                                self.temp_cookie_file = None
                                self.cookie_info_signal.emit(
                                    self._tr(f"从 {browser_name} 未找到相关Cookie",
                                             f"No relevant cookies found in {browser_name}")
                                )

                except Exception as e:
                    error_msg = str(e)
                    if "decryption" in error_msg.lower() or "encryption" in error_msg.lower():
                        self.cookie_info_signal.emit(
                            self._tr(f"⚠️ {browser_name} Cookie加密，无法自动解密",
                                     f"⚠️ {browser_name} cookies are encrypted, cannot auto-decrypt")
                        )
                    else:
                        self.cookie_info_signal.emit(
                            self._tr(f"{browser_name} 获取失败: {error_msg[:100]}",
                                     f"{browser_name} fetch failed: {error_msg[:100]}")
                        )
                    continue

            # 如果所有浏览器都失败了
            if tried_browsers:
                self.cookie_error_signal.emit(
                    self._tr(f"❌ 尝试了以下浏览器但都失败: {', '.join(tried_browsers)}",
                             f"❌ Tried the following browsers but all failed: {', '.join(tried_browsers)}")
                )
                self.cookie_info_signal.emit(
                    self._tr("💡 建议：请手动从浏览器导出cookie文件上传，或使用无Cookie方式下载",
                             "💡 Suggestion: Please manually export cookie file from browser or download without cookies")
                )

            return None

        except Exception as e:
            self.cookie_error_signal.emit(
                self._tr(f"获取浏览器Cookie时发生严重错误: {str(e)}",
                         f"Critical error getting browser cookies: {str(e)}")
            )
            return None

    def _cleanup_temp_cookie(self):
        """清理临时cookie文件"""
        if self.temp_cookie_file and os.path.exists(self.temp_cookie_file.name):
            try:
                os.unlink(self.temp_cookie_file.name)
                self.temp_cookie_file = None
            except:
                pass

    def run(self):
        self.status_signal.emit(self._tr("开始下载...", "Starting download..."))
        self.log_signal.emit(self._tr("开始下载: ", "Starting: ") + self.url)

        # 显示选择的清晰度
        self.log_signal.emit(self._tr(f"选择的清晰度: {self.quality}", f"Selected quality: {self.quality}"))

        # 确定使用的cookie文件
        cookie_path = None
        cookie_source = self._tr("无Cookie", "No Cookie")

        if self.cookie_file and os.path.exists(self.cookie_file):
            # 使用用户上传的cookie文件
            cookie_path = self.cookie_file
            cookie_source = self._tr(f"上传的Cookie文件: {os.path.basename(self.cookie_file)}",
                                     f"Uploaded cookie file: {os.path.basename(self.cookie_file)}")
            self.cookie_info_signal.emit(
                self._tr(f"✅ 使用上传的Cookie文件: {os.path.basename(self.cookie_file)}",
                         f"✅ Using uploaded cookie file: {os.path.basename(self.cookie_file)}")
            )
        elif self.cookie_file is None:  # 用户选择了自动获取（不是"no_cookie"）
            # 尝试从浏览器获取
            self.cookie_info_signal.emit(
                self._tr("正在尝试自动获取浏览器Cookie...",
                         "Trying to auto-get browser cookies...")
            )
            browser_cookie_path = self._get_browser_cookies()
            if browser_cookie_path:
                cookie_path = browser_cookie_path
                cookie_source = self._tr("自动获取的浏览器Cookie", "Auto-got browser cookies")
            else:
                self.cookie_warning_signal.emit(
                    self._tr("⚠️ 将使用无Cookie方式下载，某些视频可能无法访问",
                             "⚠️ Will download without cookies, some videos may be unavailable")
                )
                # 提供手动获取Cookie的指南
                self.cookie_info_signal.emit(
                    self._tr("📝 如何手动获取Cookie：",
                             "📝 How to manually get cookies:")
                )
                self.cookie_info_signal.emit(
                    self._tr("1. 安装浏览器扩展：'Get cookies.txt' (Chrome/Edge) 或 'cookies.txt' (Firefox)",
                             "1. Install browser extension: 'Get cookies.txt' (Chrome/Edge) or 'cookies.txt' (Firefox)")
                )
                self.cookie_info_signal.emit(
                    self._tr("2. 访问目标网站并登录",
                             "2. Visit the target website and log in")
                )
                self.cookie_info_signal.emit(
                    self._tr("3. 使用扩展导出cookies.txt文件",
                             "3. Use extension to export cookies.txt file")
                )
                self.cookie_info_signal.emit(
                    self._tr("4. 上传导出的文件到本程序",
                             "4. Upload exported file to this program")
                )
        else:
            # cookie_file == "no_cookie" 或 False
            self.cookie_info_signal.emit(
                self._tr("不使用Cookie下载",
                         "Downloading without cookies")
            )

        self.cookie_info_signal.emit(
            self._tr(f"Cookie来源: {cookie_source}", f"Cookie source: {cookie_source}")
        )

        ffmpeg_installed = shutil.which("ffmpeg") is not None
        if ffmpeg_installed:
            self.log_signal.emit(self._tr("✅ 已检测到 ffmpeg，启用分离流下载...",
                                          "✅ Detected ffmpeg, enabling separate stream download..."))

            # 根据清晰度选择格式
            if self.quality == 'best':
                ydl_format = 'bestvideo+bestaudio/best'
            elif self.quality == '1080':
                ydl_format = 'bestvideo[height<=1080]+bestaudio/best[height<=1080]'
            elif self.quality == '720':
                ydl_format = 'bestvideo[height<=720]+bestaudio/best[height<=720]'
            elif self.quality == '480':
                ydl_format = 'bestvideo[height<=480]+bestaudio/best[height<=480]'
            elif self.quality == '360':
                ydl_format = 'bestvideo[height<=360]+bestaudio/best[height<=360]'
            else:
                ydl_format = 'bestvideo+bestaudio/best'

            merge_format = 'mp4'
            postprocessors = [
                {'key': 'FFmpegVideoConvertor', 'preferedformat': merge_format},
                {'key': 'FFmpegEmbedSubtitle'},
                {'key': 'FFmpegMetadata'},
            ]
        else:
            self.log_signal.emit(self._tr("⚠️ 未检测到 ffmpeg，使用兼容模式...",
                                          "⚠️ ffmpeg not found, using fallback mode..."))
            # 在没有ffmpeg的情况下，使用最佳mp4格式
            ydl_format = 'best[ext=mp4]'
            postprocessors = []
            merge_format = None

        ydl_opts = {
            'format': ydl_format,
            'outtmpl': os.path.join(self.folder, '%(title)s.%(ext)s'),
            'noplaylist': True,
            'quiet': True,
            'progress_hooks': [self.yt_hook],
            'logger': self.YTDLogger(self),
            'postprocessors': postprocessors,
            'merge_output_format': merge_format,
            'prefer_ffmpeg': True,
            'postprocessor_args': ['-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k']
        }

        # 添加cookie选项（如果可用）
        if cookie_path:
            ydl_opts['cookiefile'] = cookie_path
            self.log_signal.emit(self._tr(f"✅ 使用Cookie文件: {cookie_path}",
                                          f"✅ Using cookie file: {cookie_path}"))

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])
            self.progress_signal.emit(100)
            self.status_signal.emit(self._tr("下载完成！", "Download complete!"))
            self.log_signal.emit(self._tr("下载成功！", "Downloaded successfully!"))
            self.open_signal.emit(self.folder)
            self.finished_signal.emit()
        except Exception as e:
            self.error_signal.emit(str(e))
        finally:
            # 清理临时cookie文件
            self._cleanup_temp_cookie()

    def yt_hook(self, d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes', 0)
            percent = int(downloaded * 100 / total) if total else 0
            self.progress_signal.emit(percent)
            self.status_signal.emit(
                self._tr(f"下载中：{percent}%", f"Downloading: {percent}%")
            )
        elif d['status'] == 'finished':
            self.status_signal.emit(self._tr("合并音视频中...", "Merging video and audio..."))
            self.log_signal.emit(self._tr("合并音视频中...", "Merging video and audio..."))

    class YTDLogger:
        def __init__(self, outer):
            self.outer = outer

        def debug(self, msg):
            self.outer.log_signal.emit(msg)

        def warning(self, msg):
            prefix = self.outer._tr("警告：", "Warning: ")
            self.outer.log_signal.emit(prefix + msg)

        def error(self, msg):
            prefix = self.outer._tr("错误：", "Error: ")
            self.outer.log_signal.emit(prefix + msg)