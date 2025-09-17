# WebDAV备份脚本

## 简介
这是一个用于将指定目录备份到WebDAV服务器的脚本集合，包含Shell和Python两个版本。它们能够创建本地备份、上传到WebDAV服务器、管理远程和本地备份文件数量，并支持大文件上传和完整性检测功能。

## WebDAV注册推荐
如果您需要WebDAV存储服务，可以考虑使用以下服务：
- **InfiniCloud**：注册即可获得20GB存储空间，填写推荐码`QXPSY`额外获得5GB，总共25GB空间
- 注册地址：https://infini-cloud.net/

## 环境要求
### Shell版本
- 支持Bash的操作系统（Linux、macOS、Windows Subsystem for Linux等）
- `curl` 命令行工具（推荐版本7.19.0或更高，以支持断点续传等功能）
- `tar` 命令行工具（当使用tar.gz格式时需要）
- `zip` 命令行工具（当使用zip格式时需要）
- 有访问权限的WebDAV服务器

### Python版本
- Python 3.6或更高版本
- 安装所需依赖：`pip install requests`
- Python标准库已包含`smtplib`和`email`模块，无需额外安装
- 有访问权限的WebDAV服务器

## 配置参数
在使用前，请根据您的实际情况修改脚本开头的配置参数：

```bash
SOURCE_DIR="/path/to/source/directory"          # 要备份的源目录
WEBDAV_BASE_URL="https://your-webdav-server.com" # WebDAV服务器基础地址
WEBDAV_UPLOAD_DIR="backups/docs"                # WebDAV上的上传目录（相对于基础地址）
WEBDAV_USER="your_username"                     # WebDAV用户名
WEBDAV_PASS="your_password"                     # WebDAV密码
LOCAL_BACKUP_DIR="/path/to/local/backups"       # 本地备份保存目录
BACKUP_PREFIX="backup"                          # 备份文件前缀
MAX_REMOTE_BACKUPS=5                            # WebDAV保留的最大备份数量
MAX_LOCAL_BACKUPS=3                             # 本地保留的最大备份数量
BACKUP_FORMAT="tar.gz"                          # 备份文件格式，可选值: tar.gz, zip

# 文件上传参数
# 是否区分大文件和非大文件（true/false）
USE_SEPARATE_FILE_PARAMS=true                     # 设置为false则使用统一的上传参数（采用大文件参数，更稳定）

# 大文件定义（以MB为单位）- 仅在USE_SEPARATE_FILE_PARAMS=true时生效
LARGE_FILE_THRESHOLD=100                          # 大于此值的文件视为大文件（MB）

# 基础上传参数（适用于所有文件）
CONNECT_TIMEOUT=30                               # 连接超时时间（秒）

# 非大文件上传参数
SMALL_FILE_MAX_TIME=1800                         # 非大文件最大上传时间（秒），默认30分钟
SMALL_FILE_RATE_LIMIT="2M"                        # 非大文件上传速度限制，格式为数字加单位（如1M=1MB/s），设为空字符串""表示无限制

# 大文件上传参数
LARGE_FILE_MAX_TIME=7200                         # 大文件最大上传时间（秒），默认2小时
LARGE_FILE_RATE_LIMIT="1M"                        # 大文件上传速度限制，格式为数字加单位（如1M=1MB/s），设为空字符串""表示无限制

# 完整性检测参数
ENABLE_INTEGRITY_CHECK=true                      # 是否启用上传后的文件完整性检测（true/false）
INTEGRITY_CHECK_TIMEOUT=300                      # 完整性检测超时时间（秒），默认5分钟
ENABLE_MD5_VERIFICATION=true                     # 是否启用MD5校验和验证（true/false）
MD5_VERIFICATION_EXCLUDE_THRESHOLD=100           # 大于此大小的文件不进行MD5验证（MB），设为0表示所有文件都进行验证

# 邮箱通知参数（两个版本均支持）
ENABLE_EMAIL_NOTIFICATION=false                  # 是否启用邮箱通知（true/false）
ENABLE_EMAIL_SUCCESS_NOTIFICATION=true           # 是否启用成功通知邮件（true/false）
ENABLE_EMAIL_FAILURE_NOTIFICATION=true           # 是否启用失败通知邮件（true/false）
SMTP_SERVER="smtp.example.com"                   # SMTP服务器地址
SMTP_PORT=587                                    # SMTP服务器端口（常用: 25, 587, 465）
SMTP_USERNAME="your_email@example.com"           # SMTP用户名（通常是邮箱地址）
SMTP_PASSWORD="your_email_password"              # SMTP密码
SMTP_USE_TLS=true                                # 是否使用TLS加密（true/false）
EMAIL_FROM="your_email@example.com"              # 发件人邮箱
EMAIL_FROM_NAME="WebDAV备份系统"                  # 发件人名称
EMAIL_TO="recipient@example.com"                 # 收件人邮箱
EMAIL_SUBJECT_PREFIX="服务器"                     # 邮件主题前缀，最终显示为"[服务器]WebDAV备份"
```

## 使用方法
### Shell版本
1. 根据上述说明修改脚本的配置参数
2. 给脚本添加执行权限：
   ```bash
   chmod +x webdav_backup.sh
   ```
3. 运行脚本：
   ```bash
   ./webdav_backup.sh
   ```
4. 也可以将脚本添加到cron任务中实现定期自动备份：
   ```bash
   # 每天凌晨2点执行备份
   0 2 * * * /path/to/webdav_backup.sh >> /path/to/backup.log 2>&1
   ```
   
   要直接将任务添加到crontab中，可以使用以下命令：
   ```bash
   # 打开crontab编辑器
   crontab -e
   
   # 在编辑器中添加上述cron表达式，然后保存退出
   # 或者使用以下命令直接添加（替换为实际路径）
   (crontab -l 2>/dev/null; echo "0 2 * * * /path/to/webdav_backup.sh >> /path/to/backup.log 2>&1") | crontab -
   ```

### Python版本
1. 安装所需依赖：
   ```bash
   pip install requests
   ```
2. 根据上述说明修改脚本的配置参数（Python版本的参数与Shell版本基本相同）
3. 运行脚本：
   ```bash
   python webdav_backup.py
   ```
4. 也可以将Python脚本添加到定期任务中：
   ```bash
   # 每天凌晨2点执行备份
   0 2 * * * python /path/to/webdav_backup.py >> /path/to/backup.log 2>&1
   ```

## 脚本功能
- 创建源目录的压缩备份文件（tar.gz格式）
- 上传备份文件到WebDAV服务器，支持根据文件大小自动选择上传参数
- 可配置是否区分大文件和非大文件处理（通过USE_SEPARATE_FILE_PARAMS参数）
- 所有文件上传均支持：断点续传功能、可配置超时和速度限制
- 可选启用上传后完整性检测（文件大小比对+可选的MD5校验和验证），自动删除损坏文件
- 支持独立控制MD5验证开关和基于文件大小的MD5验证控制（可设置大于特定大小的文件不进行MD5验证）
- 详见 `MD5_VERIFICATION_FLOW.md` 文件了解完整的MD5验证流程说明
- 自动清理WebDAV服务器上的旧备份文件，保留指定数量的最新备份
- 自动清理本地旧备份文件，保留指定数量的最新备份
- 支持选择备份文件格式（tar.gz 或 zip）
- 两个版本均支持邮件通知功能（可选择开启/关闭所有通知，或单独控制成功/失败通知）
- 两个版本均支持自定义发件人名称和邮件主题前缀

## 工作流程
1. 检查源目录是否存在
2. 创建本地备份目录（如果不存在）
3. 创建带时间戳的备份压缩文件
4. 检查WebDAV目录结构并创建（如果不存在）
5. 根据文件大小选择合适的上传参数上传备份文件
6. 清理WebDAV服务器上的旧备份
7. 清理本地旧备份

## 常见问题与解决方案

### 1. 备份文件过大
**问题描述**：备份文件太大，导致上传时间过长或上传失败

**解决方案**：
- 减小备份源目录的大小，排除不必要的文件
- 调整MAX_REMOTE_BACKUPS和MAX_LOCAL_BACKUPS参数，减少保留的备份数量
- 调整脚本顶部配置部分的文件上传参数：
  - 如不需要区分大文件和非大文件处理，可将`USE_SEPARATE_FILE_PARAMS`设置为`false`
  - 修改`LARGE_FILE_THRESHOLD`值来定义多大的文件被视为大文件
  - 增加`LARGE_FILE_MAX_TIME`值以延长大文件的最大上传时间
  - 调整`LARGE_FILE_RATE_LIMIT`值以更改大文件上传速度限制，格式为数字加单位（如1M=1MB/s），设为空字符串""表示无限制
  - 调整`SMALL_FILE_MAX_TIME`值以优化非大文件的上传超时时间
  - 调整`SMALL_FILE_RATE_LIMIT`值以优化非大文件上传速度限制，格式为数字加单位（如1M=1MB/s），设为空字符串""表示无限制
  - 如遇网络不稳定，所有文件上传均支持断点续传功能，中断后再次运行脚本会从断点处继续上传

### 2. 上传进度条不显示
**问题描述**：使用脚本上传文件时，没有显示上传进度条

**解决方案**：

### 3. Python版本特有说明
**注意事项**：
- Python版本目前不支持上传速度限制功能，相关参数会被忽略
- 如需要严格控制上传速度，请使用Shell版本的脚本
- Python版本在处理大文件时会使用流式上传和下载，减少内存占用
- Python版本的错误处理更加完善，可以提供更详细的错误信息
- Python版本和Shell版本均支持邮件通知功能，可灵活配置通知类型
- 确保您的curl版本支持进度条功能（curl通常默认支持此功能）
- 某些终端环境可能无法正确显示进度条，这是正常现象

### 3. WebDAV目录创建失败
**问题描述**：脚本无法创建WebDAV目录结构

**解决方案**：
- 检查WebDAV服务器地址和登录凭据是否正确
- 确认您有在WebDAV服务器上创建目录的权限
- 检查WebDAV路径是否正确，避免特殊字符

## 安全注意事项
- 脚本中包含明文的WebDAV用户名和密码，请妥善保管脚本文件
- 建议设置适当的文件权限，防止未授权访问：
  ```bash
  chmod 600 webdav_backup.sh
  ```

## 更新日志
- 添加了HTTP 301状态码处理逻辑，解决目录已存在导致的错误
- 修复了WebDAV URL中可能出现的双斜杠问题
- 优化了大文件上传功能，增加了断点续传、可配置超时和速度限制（格式为数字加单位，如1M=1MB/s）
- 优化了Shell版本的zip命令使用，移除了不兼容的'-C'选项，改用目录切换方法提高跨系统兼容性
- 为Shell版本的zip命令添加了静默模式（-q选项），隐藏压缩过程输出
- 修复了Python版本邮件发送问题：使用SMTP用户名作为实际发件地址，解决邮箱不存在无法发送邮件的问题
- 更新了Shell版本的环境要求说明，明确指出使用zip格式时需要安装zip命令
- 实现了根据文件大小自动选择不同上传参数的功能，区分大文件和非大文件