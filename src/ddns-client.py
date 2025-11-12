#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import yaml
import requests
import smtplib
import hashlib
import time
import shutil
from loguru import logger
from croniter import croniter
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib.parse import urlencode

# 固定目录
CONFIG_DIR = '/etc/ddns-update'
LOG_DIR = '/var/log/ddns-update'
CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.yaml')
CONFIG_EXAMPLE = os.path.join(CONFIG_DIR, 'config.yaml.example')
# 应用目录中的示例文件（用于初始化）
APP_CONFIG_EXAMPLE = '/app/config.yaml.example'
# 健康检查标记文件
HEALTH_CHECK_FILE = '/tmp/ddns-update.health'

def setup_logging():
    """配置日志 - 使用loguru，仅输出到文件，按日期切割，保留7天"""
    # 确保日志目录存在
    os.makedirs(LOG_DIR, exist_ok=True)
    
    # 移除默认的控制台输出
    logger.remove()
    
    # 添加文件日志处理器
    log_file = os.path.join(LOG_DIR, 'ddns-update.log')
    logger.add(
        log_file,
        rotation='00:00',  # 每天午夜轮转
        retention='7 days',  # 保留7天
        encoding='utf-8',
        format='{time:YYYY-MM-DD HH:mm:ss} - {level} - {message}',
        level='INFO'
    )
    
    logger.info("日志系统初始化完成")
    logger.info(f"日志目录: {LOG_DIR}")

def init_config_dir():
    """初始化配置目录，如果config.yaml不存在则复制example文件"""
    try:
        # 确保配置目录存在
        os.makedirs(CONFIG_DIR, exist_ok=True)
        
        # 如果config.yaml不存在，尝试从多个位置复制example文件
        if not os.path.exists(CONFIG_FILE):
            # 优先使用配置目录中的example文件
            if os.path.exists(CONFIG_EXAMPLE):
                shutil.copy2(CONFIG_EXAMPLE, CONFIG_FILE)
                logger.info(f"配置文件不存在，已从配置目录的示例文件复制: {CONFIG_FILE}")
            # 如果配置目录中没有，尝试从应用目录复制
            elif os.path.exists(APP_CONFIG_EXAMPLE):
                shutil.copy2(APP_CONFIG_EXAMPLE, CONFIG_FILE)
                # 同时复制example文件到配置目录，方便后续使用
                shutil.copy2(APP_CONFIG_EXAMPLE, CONFIG_EXAMPLE)
                logger.info(f"配置文件不存在，已从应用目录的示例文件复制: {CONFIG_FILE}")
            else:
                logger.warning(f"配置文件不存在且无示例文件: {CONFIG_FILE}")
    except Exception as e:
        logger.error(f"初始化配置目录时出错: {e}")

def write_health_check():
    """写入健康检查标记"""
    try:
        with open(HEALTH_CHECK_FILE, 'w') as f:
            f.write(str(int(datetime.now().timestamp())))
    except Exception as e:
        logger.warning(f"写入健康检查文件失败: {e}")

class DDNSClient:
    def __init__(self):
        self.config_file = CONFIG_FILE
        self.current_ip = None
        self.cached_ip = None
        self.schedule = None
        self.cron = None
        self.load_config()
        self._build_api_url()

    def _build_api_url(self):
        """构建API URL"""
        ddns_config = self.config.get('ddns', {})
        protocol = ddns_config.get('protocol', 'http')
        server = ddns_config.get('server', 'api-ipv4.dynu.com')
        port = ddns_config.get('port', 8245)
        path = ddns_config.get('path', '/nic/update')
        self.api_url = f"{protocol}://{server}:{port}{path}"

    def load_config(self):
        """加载配置文件"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = yaml.safe_load(f)
                    self.ddns_config = self.config.get('ddns', {})
                    self.users = self.ddns_config.get('users', [])
                    self.cached_ip = self.ddns_config.get('last_ip', '0.0.0.0')
                    self.schedule = self.ddns_config.get('schedule', '*/5 * * * *')
                    self.smtp_config = self.config.get('smtp', {})
                
                # 验证并初始化crontab表达式
                try:
                    self.cron = croniter(self.schedule, datetime.now())
                    logger.info(f"成功加载配置文件: {self.config_file}")
                    logger.info(f"配置的用户数量: {len(self.users)}")
                    logger.info(f"更新计划: {self.schedule}")
                except Exception as e:
                    error_msg = f"crontab表达式无效: {self.schedule}, 错误: {e}"
                    logger.error(error_msg)
                    raise ValueError(error_msg)
            else:
                error_msg = f"配置文件不存在: {self.config_file}"
                logger.error(error_msg)
                raise FileNotFoundError(error_msg)
        except Exception as e:
            error_msg = f"加载配置文件时出错: {e}"
            logger.error(error_msg)
            raise

    def save_config(self):
        """保存配置文件"""
        try:
            # 更新配置中的IP地址
            self.ddns_config['last_ip'] = self.cached_ip
            self.config['ddns'] = self.ddns_config
            
            with open(self.config_file, 'w', encoding='utf-8', newline='\n') as f:
                yaml.dump(self.config, f, allow_unicode=True, sort_keys=False)
            logger.info(f"配置文件已更新: {self.config_file}")
        except Exception as e:
            logger.error(f"保存配置文件时出错: {e}")

    def send_email(self, subject, content):
        """发送邮件通知"""
        if not self.smtp_config:
            logger.warning("未配置SMTP信息，跳过邮件发送")
            return False

        try:
            msg = MIMEMultipart()
            msg['From'] = self.smtp_config['sender']
            msg['To'] = self.smtp_config['receiver']
            msg['Subject'] = subject
            msg.attach(MIMEText(content, 'plain', 'utf-8'))

            logger.info(f"正在连接SMTP服务器: {self.smtp_config['server']}:{self.smtp_config['port']}")
            
            # 根据端口选择连接方式
            if self.smtp_config['port'] == 465:
                server = smtplib.SMTP_SSL(self.smtp_config['server'], self.smtp_config['port'], timeout=30)
            else:
                server = smtplib.SMTP(self.smtp_config['server'], self.smtp_config['port'], timeout=30)
                if self.smtp_config.get('use_tls', True):
                    logger.info("启用TLS加密连接")
                    server.starttls()

            server.login(self.smtp_config['username'], self.smtp_config['password'])
            server.send_message(msg)
            server.quit()

            logger.info("邮件发送成功")
            return True
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP认证失败: {e}")
            return False
        except smtplib.SMTPConnectError as e:
            logger.error(f"连接SMTP服务器失败: {e}")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"SMTP错误: {e}")
            return False
        except Exception as e:
            logger.error(f"发送邮件时出错: {e}")
            return False

    def get_public_ip(self):
        """获取公网IP地址，使用requests库"""
        # 方式1：使用 oray 的接口
        try:
            response = requests.get('http://ddns.oray.com/checkip', timeout=30)
            if response.status_code == 200:
                match = re.search(r'Current IP Address: (\d+\.\d+\.\d+\.\d+)', response.text)
                if match:
                    self.current_ip = match.group(1)
                    logger.info(f"通过 oray 接口获取到当前公网IP: {self.current_ip}")
                    return True
        except Exception as e:
            logger.warning(f"通过 oray 接口获取IP失败: {e}")

        # 方式2：使用 ipip.net 的接口
        try:
            response = requests.get('https://myip.ipip.net', timeout=30)
            if response.status_code == 200:
                match = re.search(r'当前 IP：(\d+\.\d+\.\d+\.\d+)', response.text)
                if match:
                    self.current_ip = match.group(1)
                    logger.info(f"通过 ipip.net 接口获取到当前公网IP: {self.current_ip}")
                    return True
        except Exception as e:
            logger.warning(f"通过 ipip.net 接口获取IP失败: {e}")

        # 两种方式都失败，发送邮件通知
        error_msg = "所有获取IP的方式都失败了"
        logger.error(error_msg)
        self.send_email("获取公网IP失败通知", error_msg)
        return False

    def _md5_password(self, password):
        """对密码进行MD5加密"""
        return hashlib.md5(password.encode()).hexdigest()

    def update_ddns_for_user(self, username, password):
        """更新单个用户的所有域名（不带hostname参数）"""
        try:
            md5_password = self._md5_password(password)
            
            params = {
                'username': username,
                'password': md5_password,
                'myip': self.current_ip
                # 注意：不包含hostname参数，这样会更新该用户下的所有域名
            }
            
            full_url = f"{self.api_url}?{urlencode(params)}"
            logger.info(f"DDNS更新URL (用户: {username}): {full_url.replace(md5_password, '******')}")
            
            response = requests.get(self.api_url, params=params, timeout=30)
            response.raise_for_status()
            
            response_text = response.text.strip()
            logger.info(f"DDNS服务器响应 (用户: {username}): {response_text}")
            
            if response_text.startswith('good'):
                logger.info(f"用户 {username} 的所有域名DDNS更新成功")
                return True
            elif response_text.startswith('nochg'):
                logger.info(f"用户 {username} 的IP地址未变化")
                return True
            elif response_text.startswith('badauth'):
                error_msg = f"用户 {username} 认证失败，请检查用户名和密码"
                logger.error(error_msg)
                return False
            elif response_text.startswith('911'):
                error_msg = f"用户 {username} 服务器维护中，10分钟后重试"
                logger.error(error_msg)
                return False
            else:
                error_msg = f"用户 {username} DDNS更新失败: {response_text}"
                logger.error(error_msg)
                return False
        except Exception as e:
            error_msg = f"更新用户 {username} DDNS时出错: {e}"
            logger.error(error_msg)
            return False

    def update_all_users(self):
        """更新所有用户的DDNS记录"""
        if not self.users:
            logger.error("未配置任何用户")
            return False

        success_count = 0
        failed_users = []

        for user in self.users:
            username = user.get('username')
            password = user.get('password')
            
            if not username or not password:
                logger.warning(f"用户配置不完整，跳过: {user}")
                continue
                
            if self.update_ddns_for_user(username, password):
                success_count += 1
            else:
                failed_users.append(username)

        # 如果有失败的用户，发送邮件通知
        if failed_users:
            error_msg = (
                f"以下用户DDNS更新失败：\n"
                f"{', '.join(failed_users)}\n"
                f"当前IP: {self.current_ip}"
            )
            self.send_email("DDNS更新失败通知", error_msg)

        return success_count == len(self.users)

    def run_once(self):
        """执行一次更新流程"""
        # 开始执行时更新健康检查标记
        write_health_check()
        
        # 获取当前公网IP
        if not self.get_public_ip():
            write_health_check()  # 即使失败也更新标记
            return False
        
        # 比较IP是否发生变化
        if self.current_ip == self.cached_ip:
            logger.info("IP地址未发生变化，无需更新")
            write_health_check()  # 更新标记
            return True
        
        # 更新所有用户的DDNS
        if self.update_all_users():
            logger.info("所有用户DDNS更新完成")
            # 发送更新成功通知邮件
            email_subject = "DDNS更新成功通知"
            email_content = (
                f"DDNS更新成功！\n\n"
                f"更新前IP地址: {self.cached_ip}\n"
                f"更新后IP地址: {self.current_ip}\n"
                f"更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"更新的用户数量: {len(self.users)}"
            )
            
            if self.send_email(email_subject, email_content):
                logger.info("DDNS更新成功通知邮件发送成功")
            else:
                logger.error("DDNS更新成功通知邮件发送失败")
            
            # 更新配置文件中的IP
            self.cached_ip = self.current_ip
            self.save_config()
            write_health_check()  # 更新标记
            return True
        else:
            logger.error("部分用户DDNS更新失败")
            write_health_check()  # 即使失败也更新标记
            return False

    def run(self):
        """运行DDNS客户端 - 基于crontab的定时更新模式"""
        logger.info("=" * 50)
        logger.info("DDNS客户端启动")
        logger.info(f"更新计划: {self.schedule}")
        logger.info(f"配置目录: {CONFIG_DIR}")
        logger.info(f"日志目录: {LOG_DIR}")
        logger.info("=" * 50)
        
        # 检查是否有配置用户
        if not self.users:
            logger.error("未配置任何用户，程序退出")
            return
        
        try:
            # 首次启动时立即执行一次
            logger.info("首次启动，立即执行一次更新")
            write_health_check()  # 启动时写入健康检查标记
            self.run_once()
            
            while True:
                # 计算下次执行时间
                next_time = self.cron.get_next(datetime)
                wait_seconds = (next_time - datetime.now()).total_seconds()
                
                if wait_seconds > 0:
                    logger.info(f"下次执行时间: {next_time.strftime('%Y-%m-%d %H:%M:%S')}")
                    logger.info(f"等待 {int(wait_seconds)} 秒...")
                    time.sleep(wait_seconds)
                
                # 执行更新
                self.run_once()
                
        except KeyboardInterrupt:
            logger.info("收到退出信号，程序正常退出")
        except Exception as e:
            logger.error(f"程序运行出错: {e}")
            raise

def main():
    # 初始化配置目录
    init_config_dir()
    
    # 设置日志（使用loguru，仅输出到文件）
    setup_logging()
    
    try:
        # 创建并运行DDNS客户端
        client = DDNSClient()
        client.run()
    except FileNotFoundError as e:
        logger.error(str(e))
        return
    except ValueError as e:
        logger.error(str(e))
        return
    except Exception as e:
        logger.error(f"程序运行出错: {e}")
        return

if __name__ == '__main__':
    main()
