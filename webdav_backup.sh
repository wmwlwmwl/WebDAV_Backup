#!/bin/bash

# 增强版WebDAV备份脚本
# 功能：自动创建WebDAV目录，将指定目录压缩后保存到本地并上传到WebDAV服务器

# 配置参数 - 请根据实际情况修改
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
SMALL_FILE_RATE_LIMIT="2M"                        # 非大文件上传速度限制，格式为数字加单位（如2M=2MB/s），设为空字符串""表示无限制

# 大文件上传参数
LARGE_FILE_MAX_TIME=7200                         # 大文件最大上传时间（秒），默认2小时
LARGE_FILE_RATE_LIMIT="1M"                        # 大文件上传速度限制，格式为数字加单位（如1M=1MB/s），设为空字符串""表示无限制

# 完整性检测参数
ENABLE_INTEGRITY_CHECK=true                      # 是否启用上传后的文件完整性检测（true/false）
INTEGRITY_CHECK_TIMEOUT=300                      # 完整性检测超时时间（秒），默认5分钟
ENABLE_MD5_VERIFICATION=true                     # 是否启用MD5校验和验证（true/false）开启后会从WebDAV下载文件并计算MD5校验和以验证文件完整性
MD5_VERIFICATION_EXCLUDE_THRESHOLD=100           # 大于此大小的文件不进行MD5验证（MB），设为0表示所有文件都进行验证

# 邮箱通知参数
ENABLE_EMAIL_NOTIFICATION=false                  # 是否启用邮箱通知（true/false）
ENABLE_EMAIL_SUCCESS_NOTIFICATION=true          # 是否启用成功通知（true/false）
ENABLE_EMAIL_FAILURE_NOTIFICATION=true          # 是否启用失败通知（true/false）
SMTP_SERVER="smtp.example.com"                   # SMTP服务器地址
SMTP_PORT=587                                    # SMTP服务器端口（常用: 25, 587, 465）
SMTP_USERNAME="your_email@example.com"           # SMTP用户名（通常是邮箱地址）
SMTP_PASSWORD="your_email_password"              # SMTP密码
SMTP_USE_TLS=true                                # 是否使用TLS加密（true/false）
EMAIL_FROM="your_email@example.com"              # 发件人邮箱
EMAIL_FROM_NAME="WebDAV备份系统"                   # 发件人名称
EMAIL_TO="recipient@example.com"                 # 收件人邮箱
EMAIL_SUBJECT_PREFIX="服务器"                     # 邮件主题前缀，最终显示为"[服务器]WebDAV备份"

# 发送通知邮件函数
send_notification_email() {
    local original_subject="$1"
    local body="$2"
    local timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
    local full_body="$body\n\n时间戳: $timestamp"
    
    # 添加邮件主题前缀
    local subject="[${EMAIL_SUBJECT_PREFIX}]${original_subject}"
    
    echo "正在发送邮件通知：$subject"
    
    # 检查是否启用了邮件通知
    if [ "$ENABLE_EMAIL_NOTIFICATION" != "true" ]; then
        echo "跳过邮件通知（未启用）"
        return 0
    fi
    
    # 检查是成功通知还是失败通知，并根据对应的开关决定是否发送
    if [[ "$original_subject" == *"成功"* ]]; then
        if [ "$ENABLE_EMAIL_SUCCESS_NOTIFICATION" != "true" ]; then
            echo "跳过成功邮件通知（未启用）"
            return 0
        fi
    else
        if [ "$ENABLE_EMAIL_FAILURE_NOTIFICATION" != "true" ]; then
            echo "跳失败邮件通知（未启用）"
            return 0
        fi
    fi
    
    # 使用curl通过SMTP服务器发送邮件（静默模式）
    if command -v curl &> /dev/null; then
        # 根据端口选择不同的协议和参数
        local protocol="smtp"
        local curl_args="--silent --show-error --connect-timeout 60 --max-time 300"
        
        # 根据端口和加密设置调整连接参数
        if [ "$SMTP_PORT" -eq 465 ]; then
            # 端口465通常使用SMTPS（SSL加密连接）
            protocol="smtps"
            curl_args+=" --ssl"
        elif [ "$SMTP_USE_TLS" = "true" ]; then
            # 端口587或其他端口使用STARTTLS
            curl_args+=" --ssl-reqd"
        fi
        
        # 构建完整的URL
        local smtp_url="$protocol://$SMTP_SERVER:$SMTP_PORT"
        
        # 执行邮件发送 - 使用curl内置的邮件发送功能（静默模式）
        
        # 创建临时邮件文件，确保所有邮件头格式正确
        MAIL_TEMP_FILE=$(mktemp)
        echo "From: $EMAIL_FROM_NAME <$EMAIL_FROM>" > $MAIL_TEMP_FILE
        echo "To: $EMAIL_TO" >> $MAIL_TEMP_FILE
        echo "Subject: $subject" >> $MAIL_TEMP_FILE
        echo "Content-Type: text/plain; charset=utf-8" >> $MAIL_TEMP_FILE
        echo "" >> $MAIL_TEMP_FILE  # 空行分隔头和正文
        echo -e "$full_body" >> $MAIL_TEMP_FILE
        
        # 发送邮件
        curl $curl_args \
            --url "$smtp_url" \
            --user "$SMTP_USERNAME:$SMTP_PASSWORD" \
            --mail-from "$EMAIL_FROM" \
            --mail-rcpt "$EMAIL_TO" \
            -T $MAIL_TEMP_FILE
        
        # 清理临时文件
        rm -f $MAIL_TEMP_FILE
        
        if [ $? -eq 0 ]; then
            echo "邮件发送成功"
            return 0
        else
            echo "错误：邮件发送失败，请检查SMTP配置是否正确"
            echo "提示：请确认SMTP服务器地址、端口、用户名和密码是否正确，以及是否启用了正确的加密方式"
            echo "提示：对于端口465，通常需要设置SMTP_USE_TLS=false并使用SMTPS协议"
            return 1
        fi
    else
        echo "错误：系统中未找到curl命令，无法发送邮件通知"
        return 1
    fi
}

# 检查源目录是否存在
if [ ! -d "$SOURCE_DIR" ]; then
    echo "错误：源目录 $SOURCE_DIR 不存在！"
    
    # 发送失败通知邮件
    if [ "$ENABLE_EMAIL_NOTIFICATION" = "true" ]; then
        send_notification_email "WebDAV备份失败：源目录不存在" "WebDAV备份失败！\n\n错误原因：源目录 $SOURCE_DIR 不存在！"
    fi
    
    exit 1
fi

# 创建本地备份目录（如果不存在）
mkdir -p "$LOCAL_BACKUP_DIR"
if [ ! -d "$LOCAL_BACKUP_DIR" ]; then
    echo "错误：无法创建本地备份目录 $LOCAL_BACKUP_DIR！"
    exit 1
fi

# 生成备份文件名（包含日期时间）
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILENAME="${BACKUP_PREFIX}_${TIMESTAMP}.${BACKUP_FORMAT}"
LOCAL_BACKUP_PATH="${LOCAL_BACKUP_DIR}/${BACKUP_FILENAME}"

# 创建压缩包
echo "正在创建备份文件: $LOCAL_BACKUP_PATH"

if [ "$BACKUP_FORMAT" = "tar.gz" ]; then
    tar -zcf "$LOCAL_BACKUP_PATH" -C "$(dirname "$SOURCE_DIR")" "$(basename "$SOURCE_DIR")"
elif [ "$BACKUP_FORMAT" = "zip" ]; then
    # 检查系统是否安装了zip命令
    if ! command -v zip &> /dev/null; then
        echo "错误：系统中未找到zip命令，无法创建zip格式的备份文件！"
        echo "请安装zip命令，例如：apt-get install zip (Ubuntu/Debian) 或 yum install zip (CentOS/RHEL)"
        exit 1
    fi
    # 使用zip命令创建压缩包 - 不使用-C选项以提高兼容性
    # 先保存当前目录
    current_dir="$(pwd)"
    # 切换到源目录的父目录
    cd "$(dirname "$SOURCE_DIR")"
    # 创建zip文件，使用相对路径，并添加静默模式选项禁用输出
    zip -rq "$LOCAL_BACKUP_PATH" "$(basename "$SOURCE_DIR")"
    # 切换回原来的目录
    cd "$current_dir"
else
    echo "错误：不支持的备份格式: $BACKUP_FORMAT，请使用 'tar.gz' 或 'zip'"
    exit 1
fi

if [ $? -ne 0 ]; then
echo "错误：创建备份文件失败！"
exit 1
fi

# 拆分目录路径以便创建
IFS='/' read -ra DIR_PARTS <<< "$WEBDAV_UPLOAD_DIR"

# 确保WebDAV基础URL不以斜杠结尾
WEBDAV_BASE_URL_CLEAN=$(echo "$WEBDAV_BASE_URL" | sed 's:/*$::')
current_path=""
WEBDAV_CURRENT_URL="$WEBDAV_BASE_URL_CLEAN"

# 逐级创建WebDAV目录
for part in "${DIR_PARTS[@]}"; do
    if [ -n "$part" ]; then
        current_path="$current_path/$part"
        # 确保URL中只有单个斜杠
        WEBDAV_CURRENT_URL="$WEBDAV_BASE_URL_CLEAN$current_path"
        
        echo "检查/创建WebDAV目录: $WEBDAV_CURRENT_URL"
        # 尝试创建目录（MKCOL是WebDAV创建目录的方法）
        response=$(curl -u "${WEBDAV_USER}:${WEBDAV_PASS}" -s -o /dev/null -w "%{http_code}" \
                  -X MKCOL "$WEBDAV_CURRENT_URL")
        
        # 201=创建成功，405=目录已存在（正常情况），301=重定向（也可能表示目录存在）
        if [ "$response" -ne 201 ] && [ "$response" -ne 405 ] && [ "$response" -ne 301 ]; then
            echo "错误：无法创建WebDAV目录 $WEBDAV_CURRENT_URL (HTTP状态码: $response)"
            echo "可能的原因：权限不足、路径错误或WebDAV服务器不支持目录创建"
            exit 1
        fi
        
        # 如果是301重定向，我们假设目录已存在，继续执行
        if [ "$response" -eq 301 ]; then
            echo "注意：WebDAV目录可能已存在（收到301重定向），继续执行..."
        fi
    fi
done

# 上传到WebDAV服务器
echo "正在上传到WebDAV服务器..."
# 确保URL中只有单个斜杠
WEBDAV_FULL_URL="${WEBDAV_BASE_URL_CLEAN}/${WEBDAV_UPLOAD_DIR}/${BACKUP_FILENAME}"

# 检查文件大小
FILE_SIZE=$(stat -c%s "$LOCAL_BACKUP_PATH" 2>/dev/null || stat -f%z "$LOCAL_BACKUP_PATH")
FILE_SIZE_MB=$((FILE_SIZE / 1024 / 1024))
echo "文件大小: $FILE_SIZE_MB MB"

# 初始化基础curl参数
curl_params=("-u" "${WEBDAV_USER}:${WEBDAV_PASS}" "-o" "/dev/null" "-w" "%{http_code}" "--connect-timeout" "$CONNECT_TIMEOUT" "-C" "-")  # 添加断点续传参数，移除进度条参数

# 根据配置决定是否区分大文件和非大文件
if [ "$USE_SEPARATE_FILE_PARAMS" = "true" ]; then
    # 根据文件大小选择不同的上传参数
    if [ "$FILE_SIZE_MB" -gt "$LARGE_FILE_THRESHOLD" ]; then
        echo "检测到大文件，使用大文件上传参数..."
        curl_params+=("--max-time" "$LARGE_FILE_MAX_TIME")
        if [ -n "$LARGE_FILE_RATE_LIMIT" ]; then
            curl_params+=("--limit-rate" "$LARGE_FILE_RATE_LIMIT")
        fi
    else
        echo "使用非大文件上传参数..."
        curl_params+=("--max-time" "$SMALL_FILE_MAX_TIME")
        if [ -n "$SMALL_FILE_RATE_LIMIT" ]; then
            curl_params+=("--limit-rate" "$SMALL_FILE_RATE_LIMIT")
        fi
    fi
else
    # 使用统一的上传参数（默认采用大文件参数，更稳定）
    echo "使用统一的上传参数..."
    curl_params+=("--max-time" "$LARGE_FILE_MAX_TIME")
    if [ -n "$LARGE_FILE_RATE_LIMIT" ]; then
        curl_params+=("--limit-rate" "$LARGE_FILE_RATE_LIMIT")
    fi
fi

# 执行上传并获取HTTP状态码
response=$(curl "${curl_params[@]}" "-T" "$LOCAL_BACKUP_PATH" "$WEBDAV_FULL_URL")

# 提取纯数字状态码（移除可能的HTML内容）
status_code=$(echo "$response" | grep -oE '^[0-9]{3}')

# 如果未提取到数字状态码，使用默认的失败状态
if [ -z "$status_code" ]; then
    status_code="400"
fi

echo

if [ "$status_code" -eq 201 ] || [ "$status_code" -eq 204 ] || [ "$status_code" -eq 200 ]; then
    echo "WebDAV上传成功！"
    
    # 完整性检测
    if [ "$ENABLE_INTEGRITY_CHECK" = "true" ]; then
        echo "正在执行文件完整性检测..."
        
        # 获取本地文件大小
        local_size=$(stat -c%s "$LOCAL_BACKUP_PATH" 2>/dev/null || stat -f%z "$LOCAL_BACKUP_PATH")
        # 使用Shell整数运算计算MB大小（避免依赖bc命令）
        local_size_mb=$((local_size / 1024 / 1024))
        
        # 获取远程文件大小
        echo "验证文件大小..."
        remote_size=$(curl -u "${WEBDAV_USER}:${WEBDAV_PASS}" --head --silent --connect-timeout "$CONNECT_TIMEOUT" --max-time "$INTEGRITY_CHECK_TIMEOUT" "$WEBDAV_FULL_URL" | grep -i Content-Length | awk '{print $2}' | tr -d '[:space:]')
        
        if [ "$local_size" != "$remote_size" ]; then
            echo "错误：文件大小不匹配！本地:$local_size 远程:$remote_size"
            echo "删除损坏的远程备份..."
                curl -u "${WEBDAV_USER}:${WEBDAV_PASS}" -X DELETE --silent "$WEBDAV_FULL_URL"
                
                # 发送失败通知邮件
                if [ "$ENABLE_EMAIL_NOTIFICATION" = "true" ]; then
                    send_notification_email "WebDAV备份失败：文件大小不匹配" "WebDAV备份失败！\n\n错误原因：文件大小不匹配\n备份文件: $BACKUP_FILENAME\n本地大小: $local_size bytes\n远程大小: $remote_size bytes"
                fi
                exit 1
        fi
        
        # 根据配置和文件大小决定是否执行MD5验证
        if [ "$ENABLE_MD5_VERIFICATION" = "true" ] && ( [ $MD5_VERIFICATION_EXCLUDE_THRESHOLD -le 0 ] || [ $local_size_mb -le $MD5_VERIFICATION_EXCLUDE_THRESHOLD ] ); then
            # 获取本地文件MD5
            local_md5=$(md5sum "$LOCAL_BACKUP_PATH" | awk '{print $1}')
            
            # 验证MD5校验和
            echo "验证文件MD5校验和..."
            remote_md5=$(curl -u "${WEBDAV_USER}:${WEBDAV_PASS}" --silent --connect-timeout "$CONNECT_TIMEOUT" --max-time "$INTEGRITY_CHECK_TIMEOUT" "$WEBDAV_FULL_URL" | md5sum | awk '{print $1}')
            
            if [ "$local_md5" != "$remote_md5" ]; then
                echo "错误：MD5校验和不匹配！本地:$local_md5 远程:$remote_md5"
                echo "删除损坏的远程备份..."
                curl -u "${WEBDAV_USER}:${WEBDAV_PASS}" -X DELETE --silent "$WEBDAV_FULL_URL"
                
                # 发送失败通知邮件
                if [ "$ENABLE_EMAIL_NOTIFICATION" = "true" ]; then
                    send_notification_email "WebDAV备份失败：MD5校验和不匹配" "WebDAV备份失败！\n\n错误原因：MD5校验和不匹配\n备份文件: $BACKUP_FILENAME\n本地MD5: $local_md5\n远程MD5: $remote_md5"
                fi
                exit 1
            fi
        else
            if [ "$ENABLE_MD5_VERIFICATION" != "true" ]; then
                echo "跳过MD5校验和验证（已禁用）"
            else
                echo "跳过MD5校验和验证（文件大小约 $local_size_mb MB 超过阈值 $MD5_VERIFICATION_EXCLUDE_THRESHOLD MB）"
            fi
        fi
        
        echo "文件完整性检测通过！"
    fi
    
    # 清理WebDAV上的旧备份
    echo "正在清理WebDAV上的旧备份..."
    # 确保URL中只有单个斜杠
    WEBDAV_DIR_URL="${WEBDAV_BASE_URL_CLEAN}/${WEBDAV_UPLOAD_DIR}"
    # 支持查找tar.gz和zip格式的文件
    REMOTE_FILES=$(curl -u "${WEBDAV_USER}:${WEBDAV_PASS}" -s "${WEBDAV_DIR_URL}/" | \
                   grep -oP "${BACKUP_PREFIX}_\d{8}_\d{6}\.(tar\.gz|zip)" | \
                   sort | uniq)
    
    REMOTE_FILE_COUNT=$(echo "$REMOTE_FILES" | wc -l)
    REMOTE_FILES_TO_DELETE=$((REMOTE_FILE_COUNT - MAX_REMOTE_BACKUPS))
    
    if [ $REMOTE_FILES_TO_DELETE -gt 0 ]; then
        OLD_REMOTE_FILES=$(echo "$REMOTE_FILES" | head -n $REMOTE_FILES_TO_DELETE)
        for file in $OLD_REMOTE_FILES; do
            echo "删除WebDAV上的旧备份: $file"
            curl -u "${WEBDAV_USER}:${WEBDAV_PASS}" -X DELETE "${WEBDAV_DIR_URL}/${file}"
        done
    fi
else
    echo "错误：WebDAV上传失败 (HTTP状态码: $status_code)"
    echo "本地备份已保存，但上传到WebDAV服务器时出错"
    
    # 发送失败通知邮件
    if [ "$ENABLE_EMAIL_NOTIFICATION" = "true" ]; then
        send_notification_email "WebDAV备份失败：上传错误 (状态码: $status_code)" "WebDAV备份失败！\n\n错误原因：上传失败 (HTTP状态码: $status_code)\n备份文件: $BACKUP_FILENAME\n源目录: $SOURCE_DIR\n本地备份路径: $LOCAL_BACKUP_PATH"
    fi
fi

# 清理本地旧备份
echo "正在清理本地旧备份..."
# 支持同时查找tar.gz和zip格式的文件
LOCAL_FILES=$(find "$LOCAL_BACKUP_DIR" -maxdepth 1 -type f -name "${BACKUP_PREFIX}_*.tar.gz" -o -name "${BACKUP_PREFIX}_*.zip" | \
              xargs -n 1 basename | sort | uniq)

LOCAL_FILE_COUNT=$(echo "$LOCAL_FILES" | wc -l)
LOCAL_FILES_TO_DELETE=$((LOCAL_FILE_COUNT - MAX_LOCAL_BACKUPS))

if [ $LOCAL_FILES_TO_DELETE -gt 0 ]; then
    OLD_LOCAL_FILES=$(echo "$LOCAL_FILES" | head -n $LOCAL_FILES_TO_DELETE)
    for file in $OLD_LOCAL_FILES; do
        echo "删除本地旧备份: $file"
        rm -f "${LOCAL_BACKUP_DIR}/${file}"
    done
fi

echo "备份任务完成！"

# 发送成功通知邮件
if [ "$ENABLE_EMAIL_NOTIFICATION" = "true" ]; then
    send_notification_email "WebDAV备份成功完成：$BACKUP_FILENAME" "WebDAV备份已成功完成！\n\n备份文件: $BACKUP_FILENAME\n源目录: $SOURCE_DIR\nWebDAV路径: $WEBDAV_FULL_URL\n本地备份路径: $LOCAL_BACKUP_PATH"
fi
exit 0
