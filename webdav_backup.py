#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
增强版WebDAV备份脚本 (Python版)
功能：自动创建WebDAV目录，将指定目录压缩后保存到本地并上传到WebDAV服务器
"""

import os
import sys
import tarfile
import datetime
import hashlib
import re
import requests
import shutil
from pathlib import Path
import time
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr

# 配置参数 - 请根据实际情况修改
SOURCE_DIR = "/path/to/source/directory"          # 要备份的源目录
WEBDAV_BASE_URL = "https://your-webdav-server.com"  # WebDAV服务器基础地址
WEBDAV_UPLOAD_DIR = "backups/docs"                # WebDAV上的上传目录（相对于基础地址）
WEBDAV_USER = "your_username"                     # WebDAV用户名
WEBDAV_PASS = "your_password"                     # WebDAV密码
LOCAL_BACKUP_DIR = "/path/to/local/backups"       # 本地备份保存目录
BACKUP_PREFIX = "backup"                          # 备份文件前缀
MAX_REMOTE_BACKUPS = 5                            # WebDAV保留的最大备份数量
MAX_LOCAL_BACKUPS = 3                             # 本地保留的最大备份数量
BACKUP_FORMAT = "tar.gz"                          # 备份文件格式，可选值: tar.gz, zip

# 文件上传参数
# 是否区分大文件和非大文件（True/False）
USE_SEPARATE_FILE_PARAMS = True                             # 设置为False则使用统一的上传参数（采用大文件参数，更稳定）

# 大文件定义（以MB为单位）- 仅在USE_SEPARATE_FILE_PARAMS=True时生效
LARGE_FILE_THRESHOLD = 100                                  # 大于此值的文件视为大文件（MB）

# 基础上传参数（适用于所有文件）
CONNECT_TIMEOUT = 30                                   # 连接超时时间（秒）

# 非大文件上传参数
SMALL_FILE_MAX_TIME = 1800                                 # 非大文件最大上传时间（秒），默认30分钟
SMALL_FILE_RATE_LIMIT = "2M"                               # 非大文件上传速度限制，格式为数字加单位（如2M=2MB/s），设为空字符串""表示无限制
                                                           # Python版本目前不支持上传速度限制功能，相关参数会被忽略 

# 大文件上传参数
LARGE_FILE_MAX_TIME = 7200                                 # 大文件最大上传时间（秒），默认2小时
LARGE_FILE_RATE_LIMIT = "1M"                               # 大文件上传速度限制，格式为数字加单位（如1M=1MB/s），设为空字符串""表示无限制
                                                           # Python版本目前不支持上传速度限制功能，相关参数会被忽略 

# 完整性检测参数
ENABLE_INTEGRITY_CHECK = True                              # 是否启用上传后的文件完整性检测（True/False）
INTEGRITY_CHECK_TIMEOUT = 300                              # 完整性检测超时时间（秒），默认5分钟
ENABLE_MD5_VERIFICATION = True                             # 是否启用MD5校验和验证（True/False）开启后会从WebDAV下载文件并计算MD5校验和以验证文件完整性
MD5_VERIFICATION_EXCLUDE_THRESHOLD = 100                   # 大于此大小的文件不进行MD5验证（MB），设为0表示所有文件都进行验证

# 邮箱通知参数
ENABLE_EMAIL_NOTIFICATION = False                          # 是否启用邮箱通知（True/False）
ENABLE_EMAIL_SUCCESS_NOTIFICATION = True                   # 是否启用成功通知邮件（True/False）
ENABLE_EMAIL_FAILURE_NOTIFICATION = True                   # 是否启用失败通知邮件（True/False）
SMTP_SERVER = "smtp.example.com"                           # SMTP服务器地址
SMTP_PORT = 587                                            # SMTP服务器端口（常用: 25, 587, 465）
SMTP_USERNAME = "your_email@example.com"                   # SMTP用户名（通常是邮箱地址）
SMTP_PASSWORD = "your_email_password"                      # SMTP密码
SMTP_USE_TLS = True                                        # 是否使用TLS加密（True/False）
EMAIL_FROM = "your_email@example.com"                      # 发件人邮箱
EMAIL_FROM_NAME = "WebDAV备份系统"                          # 发件人名称
EMAIL_TO = "recipient@example.com"                         # 收件人邮箱
EMAIL_SUBJECT_PREFIX = "服务器"                             # 邮件主题前缀，最终显示为"[服务器]WebDAV备份"


class WebDAVBackup:
    def __init__(self):
        # 初始化配置
        self.source_dir = SOURCE_DIR
        self.webdav_base_url = WEBDAV_BASE_URL.rstrip('/')
        self.webdav_upload_dir = WEBDAV_UPLOAD_DIR
        self.webdav_user = WEBDAV_USER
        self.webdav_pass = WEBDAV_PASS
        self.local_backup_dir = LOCAL_BACKUP_DIR
        self.backup_prefix = BACKUP_PREFIX
        self.max_remote_backups = MAX_REMOTE_BACKUPS
        self.max_local_backups = MAX_LOCAL_BACKUPS
        self.backup_format = BACKUP_FORMAT
        
        # 创建会话，用于保持连接
        self.session = requests.Session()
        self.session.auth = (self.webdav_user, self.webdav_pass)
        self.session.headers.update({'User-Agent': 'WebDAV-Backup-Script-Python/1.0'})
        
        # 邮箱通知参数
        self.enable_email_notification = ENABLE_EMAIL_NOTIFICATION
        self.enable_email_success_notification = ENABLE_EMAIL_SUCCESS_NOTIFICATION
        self.enable_email_failure_notification = ENABLE_EMAIL_FAILURE_NOTIFICATION
        self.smtp_server = SMTP_SERVER
        self.smtp_port = SMTP_PORT
        self.smtp_username = SMTP_USERNAME
        self.smtp_password = SMTP_PASSWORD
        self.smtp_use_tls = SMTP_USE_TLS
        self.email_from = EMAIL_FROM
        self.email_from_name = EMAIL_FROM_NAME
        self.email_to = EMAIL_TO
        self.email_subject_prefix = EMAIL_SUBJECT_PREFIX
    
    def check_source_dir(self):
        """检查源目录是否存在"""
        if not os.path.isdir(self.source_dir):
            error_msg = f"错误：源目录 {self.source_dir} 不存在！"
            print(error_msg)
            self.send_notification_email("WebDAV备份失败 - 源目录不存在", error_msg)
            sys.exit(1)
    
    def create_local_backup_dir(self):
        """创建本地备份目录（如果不存在）"""
        try:
            os.makedirs(self.local_backup_dir, exist_ok=True)
        except Exception as e:
            print(f"错误：无法创建本地备份目录 {self.local_backup_dir}！")
            print(f"详细错误：{str(e)}")
            sys.exit(1)
    
    def generate_backup_filename(self):
        """生成备份文件名（包含日期时间）"""
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"{self.backup_prefix}_{timestamp}.{self.backup_format}"
        local_backup_path = os.path.join(self.local_backup_dir, backup_filename)
        return backup_filename, local_backup_path
    
    def create_backup_file(self, local_backup_path):
        """创建压缩包"""
        print(f"正在创建备份文件: {local_backup_path}")
        try:
            source_dir_parent = os.path.dirname(self.source_dir)
            source_dir_name = os.path.basename(self.source_dir)
            
            if self.backup_format == "tar.gz":
                with tarfile.open(local_backup_path, "w:gz") as tar:
                    tar.add(os.path.join(source_dir_parent, source_dir_name), 
                            arcname=source_dir_name)
            elif self.backup_format == "zip":
                import zipfile
                import sys
                import shutil
                
                # 针对Windows平台特殊处理
                if sys.platform == 'win32':
                    # 使用shutil.make_archive替代zipfile，它能更好地处理Windows上的编码问题
                    try:
                        # 尝试使用shutil.make_archive创建zip文件
                        base_name = local_backup_path[:-4]  # 去掉.zip后缀
                        shutil.make_archive(base_name, 'zip', source_dir_parent, source_dir_name)
                    except Exception as e:
                        # 如果shutil方法失败，回退到zipfile方法但增强编码处理
                        print(f"警告：使用shutil创建zip文件失败，尝试使用替代方法: {str(e)}")
                        
                        with zipfile.ZipFile(local_backup_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                            # 遍历源目录中的所有文件和子目录
                            for root, dirs, files in os.walk(os.path.join(source_dir_parent, source_dir_name)):
                                for file in files:
                                    file_path = os.path.join(root, file)
                                    
                                    # 使用bytes路径处理特殊字符
                                    try:
                                        # 计算相对路径
                                        rel_path = os.path.relpath(file_path, source_dir_parent)
                                        
                                        # 尝试不同的编码策略
                                        try:
                                            # 策略1: 直接写入
                                            zipf.write(file_path, rel_path)
                                        except UnicodeEncodeError:
                                            # 策略2: 使用surrogateescape处理
                                            try:
                                                arcname_bytes = rel_path.encode('utf-8', 'surrogateescape')
                                                zipf.write(file_path, arcname_bytes)
                                            except Exception:
                                                # 策略3: 使用原始文件名作为arcname
                                                zipf.write(file_path)
                                    except Exception as inner_e:
                                        print(f"警告：无法添加文件 {file_path} 到备份，错误: {str(inner_e)}")
                                        # 继续处理其他文件
                                        continue
                else:
                    # 非Windows平台使用标准方式，但增强编码处理
                    with zipfile.ZipFile(local_backup_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                        # 遍历源目录中的所有文件和子目录
                        for root, dirs, files in os.walk(os.path.join(source_dir_parent, source_dir_name)):
                            for file in files:
                                try:
                                    file_path = os.path.join(root, file)
                                    arcname = os.path.relpath(file_path, source_dir_parent)
                                    
                                    try:
                                        zipf.write(file_path, arcname)
                                    except UnicodeEncodeError:
                                        # 在非Windows平台上也可能遇到编码问题
                                        arcname_safe = arcname.encode('utf-8', 'replace').decode('utf-8')
                                        zipf.write(file_path, arcname_safe)
                                except Exception as inner_e:
                                    print(f"警告：无法添加文件 {file} 到备份，错误: {str(inner_e)}")
                                    # 继续处理其他文件
                                    continue
            else:
                raise ValueError(f"不支持的备份格式: {self.backup_format}，请使用 'tar.gz' 或 'zip'")
            
        except Exception as e:
            print(f"错误：创建备份文件失败！")
            print(f"详细错误：{str(e)}")
            sys.exit(1)
    
    def create_webdav_directories(self):
        """逐级创建WebDAV目录"""
        dir_parts = self.webdav_upload_dir.split('/')
        current_path = ""
        
        for part in dir_parts:
            if part:
                current_path = f"{current_path}/{part}" if current_path else part
                webdav_url = f"{self.webdav_base_url}/{current_path}"
                
                print(f"检查/创建WebDAV目录: {webdav_url}")
                
                try:
                    # 尝试创建目录（MKCOL是WebDAV创建目录的方法）
                    response = self.session.request(
                        method='MKCOL',
                        url=webdav_url,
                        timeout=CONNECT_TIMEOUT
                    )
                    
                    # 201=创建成功，405=目录已存在（正常情况），301=重定向
                    if response.status_code not in [201, 405, 301]:
                        print(f"错误：无法创建WebDAV目录 {webdav_url} (HTTP状态码: {response.status_code})")
                        print("可能的原因：权限不足、路径错误或WebDAV服务器不支持目录创建")
                        sys.exit(1)
                    
                    # 如果是301重定向，我们假设目录已存在，继续执行
                    if response.status_code == 301:
                        print("注意：WebDAV目录可能已存在（收到301重定向），继续执行...")
                except Exception as e:
                    print(f"错误：创建WebDAV目录时发生异常！")
                    print(f"详细错误：{str(e)}")
                    sys.exit(1)
    
    def get_file_size(self, file_path):
        """获取文件大小（字节）"""
        return os.path.getsize(file_path)
    
    def get_file_size_mb(self, file_path):
        """获取文件大小（MB）"""
        return self.get_file_size(file_path) / 1024 / 1024
    
    def upload_to_webdav(self, local_backup_path, backup_filename):
        """上传到WebDAV服务器"""
        print("正在上传到WebDAV服务器...")
        
        # 构建完整的WebDAV URL
        webdav_full_url = f"{self.webdav_base_url}/{self.webdav_upload_dir}/{backup_filename}"
        
        # 检查文件大小
        file_size = self.get_file_size(local_backup_path)
        file_size_mb = self.get_file_size_mb(local_backup_path)
        print(f"文件大小: {file_size_mb:.2f} MB")
        
        # 设置上传参数
        timeout = CONNECT_TIMEOUT
        max_time = None
        limit_rate = None
        
        if USE_SEPARATE_FILE_PARAMS:
            if file_size_mb > LARGE_FILE_THRESHOLD:
                print("检测到大文件，使用大文件上传参数...")
                max_time = LARGE_FILE_MAX_TIME
                limit_rate = LARGE_FILE_RATE_LIMIT
            else:
                print("使用非大文件上传参数...")
                max_time = SMALL_FILE_MAX_TIME
                limit_rate = SMALL_FILE_RATE_LIMIT
        else:
            print("使用统一的上传参数...")
            max_time = LARGE_FILE_MAX_TIME
            limit_rate = LARGE_FILE_RATE_LIMIT
        
        # 准备请求头和参数
        headers = {}
        
        # 处理速度限制（Python requests库不直接支持限速，这里可以考虑使用第三方库如requests-toolbelt的StreamingIterator）
        if limit_rate:
            print(f"注意：Python版本暂不支持上传速度限制，参数 {limit_rate} 被忽略")
        
        # 设置请求超时
        request_timeout = (timeout, max_time if max_time else 3600)  # (connect timeout, read timeout)
        
        try:
            # 断点续传上传
            resume_header = {'Range': 'bytes=0-'}
            
            with open(local_backup_path, 'rb') as f:
                response = self.session.put(
                    url=webdav_full_url,
                    data=f,
                    headers=resume_header,
                    timeout=request_timeout
                )
            
            # 提取状态码
            status_code = response.status_code
            
            # 处理可能的HTML响应
            if not str(status_code).isdigit():
                # 尝试从响应中提取数字状态码
                match = re.search(r'^HTTP/\d+\.\d+\s+(\d{3})', response.text)
                if match:
                    status_code = int(match.group(1))
                else:
                    status_code = 400
            
            return status_code, webdav_full_url
            
        except requests.exceptions.Timeout:
            print("错误：上传超时！")
            return 408, webdav_full_url  # 408 Request Timeout
        except requests.exceptions.RequestException as e:
            print(f"错误：上传过程中发生异常！")
            print(f"详细错误：{str(e)}")
            return 500, webdav_full_url  # 500 Internal Server Error
    
    def calculate_file_md5(self, file_path):
        """计算文件的MD5校验和"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def check_integrity(self, local_backup_path, webdav_full_url):
        """执行文件完整性检测"""
        if not ENABLE_INTEGRITY_CHECK:
            return True
        
        print("正在执行文件完整性检测...")
        
        try:
            # 获取本地文件大小
            local_size = self.get_file_size(local_backup_path)
            local_size_mb = local_size / 1024 / 1024
            
            # 设置检测超时
            check_timeout = (CONNECT_TIMEOUT, INTEGRITY_CHECK_TIMEOUT)
            
            # 获取远程文件大小
            print("验证文件大小...")
            head_response = self.session.head(
                url=webdav_full_url,
                timeout=check_timeout
            )
            
            if 'Content-Length' in head_response.headers:
                remote_size = int(head_response.headers['Content-Length'])
            else:
                print("警告：无法获取远程文件大小，跳过大小验证")
                remote_size = local_size  # 假设大小相同以继续验证
            
            if local_size != remote_size:
                error_msg = f"错误：文件大小不匹配！本地:{local_size} 远程:{remote_size}"
                print(error_msg)
                self.delete_remote_file(webdav_full_url)
                self.send_notification_email("WebDAV备份失败 - 文件大小验证失败", error_msg)
                return False
            
            # 根据配置和文件大小决定是否执行MD5验证
            if ENABLE_MD5_VERIFICATION and (MD5_VERIFICATION_EXCLUDE_THRESHOLD <= 0 or local_size_mb <= MD5_VERIFICATION_EXCLUDE_THRESHOLD):
                # 计算本地文件MD5
                local_md5 = self.calculate_file_md5(local_backup_path)
                
                # 验证MD5校验和
                print("验证文件MD5校验和...")
                get_response = self.session.get(
                    url=webdav_full_url,
                    timeout=check_timeout,
                    stream=True  # 流式下载，避免大文件占用过多内存
                )
                
                # 计算远程文件的MD5
                remote_hash_md5 = hashlib.md5()
                for chunk in get_response.iter_content(chunk_size=4096):
                    if chunk:
                        remote_hash_md5.update(chunk)
                remote_md5 = remote_hash_md5.hexdigest()
                
                if local_md5 != remote_md5:
                    error_msg = f"错误：MD5校验和不匹配！本地:{local_md5} 远程:{remote_md5}"
                    print(error_msg)
                    self.delete_remote_file(webdav_full_url)
                    self.send_notification_email("WebDAV备份失败 - MD5校验失败", error_msg)
                    return False
            else:
                if not ENABLE_MD5_VERIFICATION:
                    print("跳过MD5校验和验证（已禁用）")
                else:
                    print(f"跳过MD5校验和验证（文件大小 {local_size_mb:.2f} MB 超过阈值 {MD5_VERIFICATION_EXCLUDE_THRESHOLD} MB）")
            
            print("文件完整性检测通过！")
            return True
            
        except Exception as e:
            print(f"错误：完整性检测过程中发生异常！")
            print(f"详细错误：{str(e)}")
            return False
    
    def delete_remote_file(self, webdav_file_url):
        """删除远程文件"""
        print("删除损坏的远程备份...")
        try:
            self.session.delete(webdav_file_url, timeout=CONNECT_TIMEOUT)
        except Exception as e:
            print(f"警告：删除远程文件时发生错误: {str(e)}")
    
    def clean_remote_backups(self, backup_filename):
        """清理WebDAV上的旧备份"""
        print("正在清理WebDAV上的旧备份...")
        
        webdav_dir_url = f"{self.webdav_base_url}/{self.webdav_upload_dir}/"
        
        try:
            # 获取远程文件列表
            response = self.session.get(webdav_dir_url, timeout=CONNECT_TIMEOUT)
            
            # 提取符合命名规则的备份文件 - 支持tar.gz和zip格式
            # 使用非捕获组确保返回完整文件名
            pattern = f"{self.backup_prefix}_\d{{8}}_\d{{6}}\.(?:tar\.gz|zip)"
            # 使用finditer获取完整匹配
            remote_files = [match.group(0) for match in re.finditer(pattern, response.text)]
            
            # 排序并去重
            remote_files = sorted(list(set(remote_files)))
            
            # 计算需要删除的文件数量
            files_to_delete_count = len(remote_files) - self.max_remote_backups
            
            if files_to_delete_count > 0:
                # 获取需要删除的旧文件（保留最新的）
                files_to_delete = remote_files[:files_to_delete_count]
                
                for file in files_to_delete:
                    # 跳过当前刚上传的文件
                    if file == backup_filename:
                        continue
                    
                    file_url = f"{webdav_dir_url}{file}"
                    print(f"删除WebDAV上的旧备份: {file}")
                    
                    try:
                        self.session.delete(file_url, timeout=CONNECT_TIMEOUT)
                    except Exception as e:
                        print(f"警告：删除文件 {file} 时发生错误: {str(e)}")
                        # 继续尝试删除其他文件
                        continue
        except Exception as e:
            print(f"警告：清理WebDAV旧备份时发生错误: {str(e)}")
    
    def send_notification_email(self, subject, body):
        """发送通知邮件"""
        if not self.enable_email_notification:
            return
        
        # 判断是成功通知还是失败通知
        is_success_notification = "成功" in subject
        
        # 根据对应的开关决定是否发送邮件
        if is_success_notification and not self.enable_email_success_notification:
            print(f"成功通知邮件已禁用，跳过发送：{subject}")
            return
        if not is_success_notification and not self.enable_email_failure_notification:
            print(f"失败通知邮件已禁用，跳过发送：{subject}")
            return
        
        # 添加邮件主题前缀
        original_subject = subject
        subject = f"[{self.email_subject_prefix}]{original_subject}"
        
        print(f"正在发送邮件通知：{subject}")
        
        try:
            # 添加时间戳到邮件内容
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            full_body = f"{body}\n\n时间戳: {timestamp}"
            
            # 创建邮件对象
            message = MIMEText(full_body, 'plain', 'utf-8')
            # 使用formataddr函数正确格式化发件人信息
            message['From'] = formataddr((self.email_from_name, self.email_from))
            message['To'] = Header(self.email_to)
            message['Subject'] = Header(subject)
            
            # 发送邮件
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            
            if self.smtp_use_tls:
                server.starttls()
            
            server.login(self.smtp_username, self.smtp_password)
            # 使用SMTP用户名作为实际发件地址（解决邮箱不存在的问题），但在邮件头中保持显示的发件人信息不变
            server.sendmail(self.smtp_username, [self.email_to], message.as_string())
            server.quit()
            
            print("邮件发送成功")
        except Exception as e:
            print(f"警告：发送邮件失败！错误信息: {str(e)}")
    
    def clean_local_backups(self, backup_filename):
        """清理本地旧备份"""
        print("正在清理本地旧备份...")
        
        try:
            # 获取本地备份文件列表，支持tar.gz和zip格式
            local_files = []
            
            for file in os.listdir(self.local_backup_dir):
                # 支持tar.gz和zip格式的文件
                if re.match(f"^{self.backup_prefix}_\\d{{8}}_\\d{{6}}\\.(tar\\.gz|zip)$", file):
                    local_files.append(file)
            
            # 按文件名排序（文件名包含时间戳，排序后最新的在最后）
            local_files.sort()
            
            # 计算需要删除的文件数量
            files_to_delete_count = len(local_files) - self.max_local_backups
            
            if files_to_delete_count > 0:
                # 获取需要删除的旧文件（保留最新的）
                files_to_delete = local_files[:files_to_delete_count]
                
                for file in files_to_delete:
                    # 跳过当前刚创建的文件
                    if file == backup_filename:
                        continue
                    
                    try:
                        # 处理文件路径编码
                        file_path = os.path.join(self.local_backup_dir, file)
                        print(f"删除本地旧备份: {file}")
                        
                        os.remove(file_path)
                    except UnicodeEncodeError as e:
                        # 处理文件名编码错误
                        print(f"警告：文件名字符编码错误，尝试使用原始字节路径: {str(e)}")
                        try:
                            # 尝试使用不同的编码方式处理文件路径
                            import sys
                            if sys.platform == 'win32':
                                # 在Windows上尝试使用系统默认编码
                                file_path_bytes = os.path.join(self.local_backup_dir, file).encode('mbcs', 'surrogateescape')
                                os.remove(file_path_bytes)
                            else:
                                # 在其他系统上尝试使用utf-8替换错误字符
                                file_path_safe = os.path.join(self.local_backup_dir, file.encode('utf-8', 'replace').decode('utf-8'))
                                os.remove(file_path_safe)
                        except Exception as inner_e:
                            print(f"警告：删除文件失败: {str(inner_e)}")
                            # 继续尝试删除其他文件
                            continue
                    except Exception as e:
                        print(f"警告：删除文件 {file} 时发生错误: {str(e)}")
                        # 继续尝试删除其他文件
                        continue
        except Exception as e:
            print(f"警告：清理本地旧备份时发生错误: {str(e)}")
    
    def run(self):
        """执行完整的备份流程"""
        try:
            # 检查源目录
            self.check_source_dir()
            
            # 创建本地备份目录
            self.create_local_backup_dir()
            
            # 生成备份文件名
            backup_filename, local_backup_path = self.generate_backup_filename()
            
            # 创建备份文件
            self.create_backup_file(local_backup_path)
            
            # 创建WebDAV目录
            self.create_webdav_directories()
            
            # 上传到WebDAV
            status_code, webdav_full_url = self.upload_to_webdav(local_backup_path, backup_filename)
            
            # 检查上传结果
            if status_code in [200, 201, 204]:
                print("WebDAV上传成功！")
                
                # 执行完整性检测
                if not self.check_integrity(local_backup_path, webdav_full_url):
                    print("备份任务失败！")
                    sys.exit(1)
                
                # 清理WebDAV上的旧备份
                self.clean_remote_backups(backup_filename)
            else:
                error_msg = f"错误：WebDAV上传失败 (HTTP状态码: {status_code})\n本地备份已保存，但上传到WebDAV服务器时出错"
                print(error_msg)
                self.send_notification_email("WebDAV备份失败 - 上传失败", error_msg)
            
            # 清理本地旧备份
            self.clean_local_backups(backup_filename)
            
            success_msg = f"备份任务完成！\n本地备份文件: {local_backup_path}\nWebDAV备份文件: {webdav_full_url}"
            print(success_msg)
            self.send_notification_email("WebDAV备份成功完成", success_msg)
            sys.exit(0)
            
        except KeyboardInterrupt:
            print("\n备份任务被用户中断！")
            sys.exit(1)
        except Exception as e:
            error_msg = f"错误：备份过程中发生未预期的异常！\n详细错误：{str(e)}"
            print(error_msg)
            self.send_notification_email("WebDAV备份失败 - 系统错误", error_msg)
            sys.exit(1)


if __name__ == "__main__":
    backup_script = WebDAVBackup()
    backup_script.run()