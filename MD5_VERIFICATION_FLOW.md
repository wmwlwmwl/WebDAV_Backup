# WebDAV备份脚本的MD5验证流程说明

本文档详细标记了WebDAV备份脚本（Shell版本和Python版本）中MD5验证的完整流程。

## Shell版本MD5验证流程

在 `webdav_backup.sh` 脚本中，MD5验证流程如下：

1. **完整性检测总开关**
   ```bash
   if [ "$ENABLE_INTEGRITY_CHECK" = "true" ]; then
       echo "正在执行文件完整性检测..."
   ```
   - 通过 `ENABLE_INTEGRITY_CHECK` 参数控制是否启用完整性检测

2. **文件大小获取与计算**
   ```bash
   # 获取本地文件大小
   local_size=$(stat -c%s "$LOCAL_BACKUP_PATH" 2>/dev/null || stat -f%z "$LOCAL_BACKUP_PATH")
   # 使用Shell整数运算计算MB大小
   local_size_mb=$((local_size / 1024 / 1024))
   ```
   - 获取本地备份文件的字节大小
   - 转换为MB（使用整数运算避免依赖bc命令）

3. **文件大小验证**
   ```bash
   # 获取远程文件大小
   echo "验证文件大小..."
   remote_size=$(curl -u "${WEBDAV_USER}:${WEBDAV_PASS}" --head --silent --connect-timeout "$CONNECT_TIMEOUT" --max-time "$INTEGRITY_CHECK_TIMEOUT" "$WEBDAV_FULL_URL" | grep -i Content-Length | awk '{print $2}' | tr -d '[:space:]')
   
   if [ "$local_size" != "$remote_size" ]; then
       echo "错误：文件大小不匹配！本地:$local_size 远程:$remote_size"
       echo "删除损坏的远程备份..."
       curl -u "${WEBDAV_USER}:${WEBDAV_PASS}" -X DELETE --silent "$WEBDAV_FULL_URL"
       exit 1
   fi
   ```
   - 通过curl HEAD请求获取远程文件大小
   - 比较本地和远程文件大小，不匹配则删除远程文件并退出

4. **MD5验证条件判断**
   ```bash
   # 根据配置和文件大小决定是否执行MD5验证
   if [ "$ENABLE_MD5_VERIFICATION" = "true" ] && ( [ $MD5_VERIFICATION_EXCLUDE_THRESHOLD -le 0 ] || [ $local_size_mb -le $MD5_VERIFICATION_EXCLUDE_THRESHOLD ] ); then
   ```
   - 检查MD5验证开关是否开启
   - 检查文件大小是否超过排除阈值

5. **本地MD5计算**
   ```bash
   # 获取本地文件MD5
   local_md5=$(md5sum "$LOCAL_BACKUP_PATH" | awk '{print $1}')
   ```
   - 使用md5sum命令计算本地文件的MD5校验和

6. **远程MD5获取**
   ```bash
   # 验证文件MD5校验和...
   remote_md5=$(curl -u "${WEBDAV_USER}:${WEBDAV_PASS}" --silent --connect-timeout "$CONNECT_TIMEOUT" --max-time "$INTEGRITY_CHECK_TIMEOUT" "$WEBDAV_FULL_URL" | md5sum | awk '{print $1}')
   ```
   - 下载远程文件内容并计算MD5校验和

7. **MD5校验和比对**
   ```bash
   if [ "$local_md5" != "$remote_md5" ]; then
       echo "错误：MD5校验和不匹配！本地:$local_md5 远程:$remote_md5"
       echo "删除损坏的远程备份..."
       curl -u "${WEBDAV_USER}:${WEBDAV_PASS}" -X DELETE --silent "$WEBDAV_FULL_URL"
       exit 1
   fi
   ```
   - 比较本地和远程文件的MD5校验和
   - 不匹配则删除远程文件并退出脚本

8. **跳过MD5验证的情况**
   ```bash
   else
       if [ "$ENABLE_MD5_VERIFICATION" != "true" ]; then
           echo "跳过MD5校验和验证（已禁用）"
       else
           echo "跳过MD5校验和验证（文件大小约 $local_size_mb MB 超过阈值 $MD5_VERIFICATION_EXCLUDE_THRESHOLD MB）"
       fi
   fi
   ```
   - 当MD5验证被禁用或文件大小超过阈值时，显示相应提示信息

## Python版本MD5验证流程

在 `webdav_backup.py` 脚本中，MD5验证流程如下：

1. **完整性检测总开关**
   ```python
   def check_integrity(self, local_backup_path, webdav_full_url):
       """执行文件完整性检测"""
       if not ENABLE_INTEGRITY_CHECK:
           return True
   
       print("正在执行文件完整性检测...")
   ```
   - 通过 `ENABLE_INTEGRITY_CHECK` 参数控制是否启用完整性检测

2. **文件大小获取与计算**
   ```python
   # 获取本地文件大小
   local_size = self.get_file_size(local_backup_path)
   local_size_mb = local_size / 1024 / 1024
   ```
   - 获取本地备份文件的字节大小
   - 转换为MB（使用浮点数计算）

3. **文件大小验证**
   ```python
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
       print(f"错误：文件大小不匹配！本地:{local_size} 远程:{remote_size}")
       self.delete_remote_file(webdav_full_url)
       return False
   ```
   - 使用requests库的head方法获取远程文件大小
   - 比较本地和远程文件大小，不匹配则删除远程文件并返回False

4. **MD5验证条件判断**
   ```python
   # 根据配置和文件大小决定是否执行MD5验证
   if ENABLE_MD5_VERIFICATION and (MD5_VERIFICATION_EXCLUDE_THRESHOLD <= 0 or local_size_mb <= MD5_VERIFICATION_EXCLUDE_THRESHOLD):
   ```
   - 检查MD5验证开关是否开启
   - 检查文件大小是否超过排除阈值

5. **本地MD5计算**
   ```python
   # 计算本地文件MD5
   local_md5 = self.calculate_file_md5(local_backup_path)
   
   # calculate_file_md5方法的实现
   def calculate_file_md5(self, file_path):
       """计算文件的MD5校验和"""
       hash_md5 = hashlib.md5()
       with open(file_path, "rb") as f:
           for chunk in iter(lambda: f.read(4096), b""):
               hash_md5.update(chunk)
       return hash_md5.hexdigest()
   ```
   - 使用hashlib库分块计算本地文件的MD5校验和
   - 分块读取避免大文件占用过多内存

6. **远程MD5获取**
   ```python
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
   ```
   - 使用requests的流式下载功能获取远程文件内容
   - 分块计算远程文件的MD5校验和，避免大文件占用过多内存

7. **MD5校验和比对**
   ```python
   if local_md5 != remote_md5:
       print(f"错误：MD5校验和不匹配！本地:{local_md5} 远程:{remote_md5}")
       self.delete_remote_file(webdav_full_url)
       return False
   ```
   - 比较本地和远程文件的MD5校验和
   - 不匹配则删除远程文件并返回False

8. **跳过MD5验证的情况**
   ```python
   else:
       if not ENABLE_MD5_VERIFICATION:
           print("跳过MD5校验和验证（已禁用）")
       else:
           print(f"跳过MD5校验和验证（文件大小 {local_size_mb:.2f} MB 超过阈值 {MD5_VERIFICATION_EXCLUDE_THRESHOLD} MB）")
   ```
   - 当MD5验证被禁用或文件大小超过阈值时，显示相应提示信息

## 配置参数说明

两个版本脚本中控制MD5验证的关键参数：

| 参数名称 | 类型 | 默认值 | 说明 |
|---------|------|--------|------|
| ENABLE_INTEGRITY_CHECK | 布尔值 | true/True | 是否启用上传后的文件完整性检测（包含文件大小和可选的MD5验证） |
| ENABLE_MD5_VERIFICATION | 布尔值 | true/True | 是否启用MD5校验和验证 |
| MD5_VERIFICATION_EXCLUDE_THRESHOLD | 数字 | 100 | 大于此大小的文件不进行MD5验证（MB），设为0表示所有文件都进行验证 |
| INTEGRITY_CHECK_TIMEOUT | 数字 | 300 | 完整性检测超时时间（秒），默认5分钟 |

## 功能特点

1. **双重控制**：通过两个独立的开关参数分别控制总完整性检测和MD5验证
2. **大文件优化**：可配置跳过大于特定大小的文件的MD5验证，提高大文件备份效率
3. **安全保障**：验证失败时自动删除损坏的远程备份，避免保留无效备份
4. **详细日志**：每个验证步骤都有明确的日志输出，便于排查问题

## 使用建议

- 对于重要数据，建议同时启用文件大小验证和MD5验证
- 对于大文件备份，可以设置合适的 `MD5_VERIFICATION_EXCLUDE_THRESHOLD` 值来平衡安全性和效率
- 对于网络稳定的环境，可以考虑降低 `INTEGRITY_CHECK_TIMEOUT` 值以提高检测速度