# -*- coding: utf-8 -*-
"""
Cloudflare DDNS 更新脚本 (Python 2.7.3)
用于自动更新IPv4 A记录
运行环境: OpenWrt
依赖： python-mini  python-openssl

"""

import os
import re
import sys
import json
import subprocess
import urllib2

# ====== 配置区域 (根据实际情况修改) ======
CF_API_TOKEN = "你的Cloudflare_API_Token"  # Cloudflare API令牌
ZONE_ID = "你的区域ID"                     # Cloudflare区域ID
DNS_RECORD_ID = "你的DNS记录ID"           # 要更新的DNS记录ID
DNS_NAME = "你的完整域名"                  # 要更新的域名 (例如: ddns.example.com)
PROXIED = False                          # 是否启用Cloudflare代理 (True/False)
# ====== 配置结束 ======

# 系统日志标识
SYSLOG_TAG = "cloudflare-ddns"
# IP存储文件路径
IP_FILE = "/tmp/ip.txt"

def log_to_syslog(message):
    """将消息写入OpenWrt系统日志"""
    try:
        # 使用logger命令写入系统日志
        subprocess.call(["logger", "-t", SYSLOG_TAG, message])
    except Exception as e:
        # 如果logger不可用，输出到stderr
        sys.stderr.write("日志记录失败: {}\n".format(str(e)))

def get_public_ip():
    """获取当前公网IPv4地址"""
    try:
        # 执行命令获取WAN口IP地址
        cmd = "ubus call network.interface.wan status | grep -m1 '\"address\":' | grep -oE '([0-9]{1,3}\\.){3}[0-9]{1,3}'"
        output = subprocess.check_output(cmd, shell=True).strip()
        
        # 简单验证IP格式
        if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', output):
            return output
        else:
            log_to_syslog("获取到无效IP地址: {}".format(output))
            return None
    except Exception as e:
        log_to_syslog("获取公网IP失败: {}".format(str(e)))
        return None

def read_previous_ip():
    """读取之前记录的IP地址"""
    try:
        if os.path.exists(IP_FILE):
            with open(IP_FILE, 'r') as f:
                return f.read().strip()
        return None
    except Exception as e:
        log_to_syslog("读取IP文件失败: {}".format(str(e)))
        return None

def save_current_ip(ip):
    """保存当前IP到文件"""
    try:
        with open(IP_FILE, 'w') as f:
            f.write(ip)
    except Exception as e:
        log_to_syslog("保存IP文件失败: {}".format(str(e)))

def update_dns_record(ip):
    """更新Cloudflare DNS记录"""
    # 构造API请求URL
    url = "https://api.cloudflare.com/client/v4/zones/{}/dns_records/{}".format(ZONE_ID, DNS_RECORD_ID)
    
    # 构造请求数据
    data = json.dumps({
        "type": "A",
        "name": DNS_NAME,
        "content": ip,
        "ttl": 60,  # TTL设置为60秒 (最小值)
        "proxied": PROXIED
    })
    
    try:
        # 创建请求对象
        req = urllib2.Request(url, data)
        req.add_header('Authorization', 'Bearer ' + CF_API_TOKEN)
        req.add_header('Content-Type', 'application/json')
        req.get_method = lambda: 'PUT'  # 设置PUT方法
        
        # 发送请求
        response = urllib2.urlopen(req)
        result = json.loads(response.read())
        
        # 检查响应是否成功
        if result.get('success', False):
            log_to_syslog("DNS记录更新成功: {} -> {}".format(DNS_NAME, ip))
            return True
        else:
            errors = result.get('errors', [])
            error_messages = [e.get('message', '未知错误') for e in errors]
            log_to_syslog("DNS更新失败: {}".format(", ".join(error_messages)))
            return False
    except urllib2.HTTPError as e:
        log_to_syslog("HTTP错误({}): {}".format(e.code, e.reason))
        return False
    except Exception as e:
        log_to_syslog("请求异常: {}".format(str(e)))
        return False

def main():
    """主函数"""
    # 获取当前公网IP
    current_ip = get_public_ip()
    if not current_ip:
        return
    
    # 获取之前记录的IP
    previous_ip = read_previous_ip()
    
    # 检查IP是否变化
    if previous_ip == current_ip:
        # log_to_syslog("IP未变化: {}".format(current_ip))
        return
    
    # 更新DNS记录
    if update_dns_record(current_ip):
        # 只有成功时才保存新IP
        save_current_ip(current_ip)
        log_to_syslog("IP已更新: {} -> {}".format(previous_ip, current_ip))
    else:
        log_to_syslog("更新失败，保持原IP: {}".format(previous_ip or "无"))

if __name__ == "__main__":
    main()
