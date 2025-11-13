#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sys
import signal
import yaml
import requests
import smtplib
import hashlib
import time
import shutil
import socket
from typing import Optional, List, Dict, Any
from loguru import logger
from croniter import croniter  # type: ignore
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

# 常量定义
REQUEST_TIMEOUT = 30
SMTP_TIMEOUT = 30
MIN_CRON_INTERVAL_MINUTES = 1  # 最小更新间隔（分钟）
IP_V4_PATTERN = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')

# IP检测服务列表（优先使用中国境内可访问的服务）
IP_CHECK_SERVICES = [
    {'url': 'http://ddns.oray.com/checkip', 'pattern': r'Current IP Address: (\d+\.\d+\.\d+\.\d+)'},
    {'url': 'https://myip.ipip.net', 'pattern': r'当前 IP：(\d+\.\d+\.\d+\.\d+)'},
    {'url': 'http://ip.3322.net', 'pattern': r'^(\d+\.\d+\.\d+\.\d+)$'},  # 备用服务（中国境内可用）
]

def is_valid_ipv4(ip: str) -> bool:
    """验证IPv4地址格式"""
    if not ip or not IP_V4_PATTERN.match(ip):
        return False
    try:
        parts = ip.split('.')
        return all(0 <= int(part) <= 255 for part in parts)
    except ValueError:
        return False

def init_config_dir() -> None:
    """初始化配置目录，如果config.yaml不存在则从应用目录复制example文件
    
    Raises:
        FileNotFoundError: 当配置文件不存在且示例文件也不存在时
        PermissionError: 当没有权限创建目录或复制文件时
        RuntimeError: 当其他初始化错误发生时
    """
    try:
        # 确保配置目录存在
        os.makedirs(CONFIG_DIR, exist_ok=True)
    except PermissionError as e:
        error_msg = f"没有权限创建配置目录 {CONFIG_DIR}: {e}"
        print(f"错误: {error_msg}", flush=True)
        raise PermissionError(error_msg) from e
    except OSError as e:
        error_msg = f"创建配置目录失败 {CONFIG_DIR}: {e}"
        print(f"错误: {error_msg}", flush=True)
        raise RuntimeError(error_msg) from e
    
    # 如果config.yaml不存在，从应用目录复制example文件
    if not os.path.exists(CONFIG_FILE):
        if not os.path.exists(APP_CONFIG_EXAMPLE):
            error_msg = (
                f"配置文件不存在: {CONFIG_FILE}\n"
                f"且示例文件也不存在: {APP_CONFIG_EXAMPLE}\n"
                f"请确保示例文件存在于应用目录中"
            )
            raise FileNotFoundError(error_msg)
        
        try:
            shutil.copy2(APP_CONFIG_EXAMPLE, CONFIG_FILE)
            # 注意：此时日志系统可能还未初始化，使用print并立即刷新
            print(f"配置文件不存在，已从示例文件复制到: {CONFIG_FILE}", flush=True)
        except PermissionError as e:
            error_msg = f"没有权限复制配置文件到 {CONFIG_FILE}: {e}"
            print(f"错误: {error_msg}", flush=True)
            raise PermissionError(error_msg) from e
        except OSError as e:
            error_msg = f"复制配置文件失败: {e}"
            print(f"错误: {error_msg}", flush=True)
            raise RuntimeError(error_msg) from e

def setup_logging():
    """配置日志 - 使用loguru，仅输出到文件，按日期切割，保留7天"""
    try:
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
            level='INFO',
            enqueue=True,  # 异步写入，提高性能
            backtrace=True,  # 记录异常堆栈
            diagnose=True  # 显示变量值
        )
        
        logger.info("日志系统初始化完成")
        logger.info(f"日志目录: {LOG_DIR}")
    except Exception as e:
        # 如果日志初始化失败，至少输出到控制台
        print(f"警告: 日志系统初始化失败: {e}")

def write_health_check():
    """写入健康检查标记"""
    try:
        with open(HEALTH_CHECK_FILE, 'w') as f:
            f.write(str(int(datetime.now().timestamp())))
    except Exception as e:
        logger.warning(f"写入健康检查文件失败: {e}")

def validate_cron_schedule(schedule: str) -> bool:
    """验证crontab表达式并检查最小间隔"""
    try:
        cron = croniter(schedule, datetime.now())
        # 计算下次执行时间
        next_time = cron.get_next(datetime)
        current_time = datetime.now()
        minutes_diff = (next_time - current_time).total_seconds() / 60
        
        # 检查最小间隔
        if minutes_diff < MIN_CRON_INTERVAL_MINUTES:
            logger.warning(f"更新间隔过短: {minutes_diff:.1f}分钟，建议至少{MIN_CRON_INTERVAL_MINUTES}分钟")
        
        return True
    except Exception:
        return False

class DDNSClient:
    def __init__(self):
        self.config_file = CONFIG_FILE
        self.current_ip: Optional[str] = None
        self.cached_ip: Optional[str] = None
        self.schedule: Optional[str] = None
        self.cron: Optional[Any] = None
        self.config: Dict[str, Any] = {}
        self.ddns_config: Dict[str, Any] = {}
        self.users: List[Dict[str, str]] = []
        self.smtp_config: Dict[str, Any] = {}
        self.api_url: str = ''
        self.load_config()
        self._build_api_url()
        self._validate_config()

    def _build_api_url(self) -> None:
        """构建API URL"""
        ddns_config = self.config.get('ddns', {})
        protocol = ddns_config.get('protocol', 'http')
        server = ddns_config.get('server', 'api-ipv4.dynu.com')
        port = ddns_config.get('port', 8245)
        path = ddns_config.get('path', '/nic/update')
        self.api_url = f"{protocol}://{server}:{port}{path}"

    def _validate_config(self) -> None:
        """验证配置的完整性和有效性
        
        Raises:
            ValueError: 当配置验证失败时
        """
        # 验证用户配置
        if not self.users:
            raise ValueError("配置文件中未找到任何用户，请至少配置一个用户")
        
        for idx, user in enumerate(self.users):
            username = user.get('username')
            password = user.get('password')
            if not username or not password:
                raise ValueError(f"用户配置不完整 (索引 {idx}): 缺少用户名或密码")
            if not isinstance(username, str) or not isinstance(password, str):
                raise ValueError(f"用户配置格式错误 (索引 {idx}): 用户名和密码必须是字符串")
            if not username.strip() or not password.strip():
                raise ValueError(f"用户配置无效 (索引 {idx}): 用户名和密码不能为空")
        
        # 验证crontab表达式
        if not self.schedule:
            raise ValueError("配置文件中缺少schedule字段，请配置更新计划")
        if not validate_cron_schedule(self.schedule):
            raise ValueError(f"无效的crontab表达式: {self.schedule}")
        
        # 验证DDNS服务器配置
        if not self.ddns_config.get('server'):
            raise ValueError("配置文件中缺少DDNS服务器地址")
        if not self.ddns_config.get('port'):
            raise ValueError("配置文件中缺少DDNS服务器端口")
        
        # 验证缓存的IP地址格式
        if self.cached_ip and self.cached_ip != '0.0.0.0':
            if not is_valid_ipv4(self.cached_ip):
                logger.warning(f"配置文件中缓存的IP地址格式无效: {self.cached_ip}，将重置为0.0.0.0")
                self.cached_ip = '0.0.0.0'
                self.ddns_config['last_ip'] = '0.0.0.0'
                try:
                    self.save_config()
                except Exception as e:
                    logger.warning(f"重置缓存IP时保存配置失败: {e}")

    def load_config(self) -> None:
        """加载配置文件
        
        Raises:
            FileNotFoundError: 当配置文件不存在时
            ValueError: 当配置文件格式错误或内容无效时
            RuntimeError: 当加载配置文件时发生其他错误时
        """
        try:
            if not os.path.exists(self.config_file):
                error_msg = f"配置文件不存在: {self.config_file}"
                logger.error(error_msg)
                raise FileNotFoundError(error_msg)
            
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
                if not self.config:
                    raise ValueError("配置文件为空或格式错误")
                
                self.ddns_config = self.config.get('ddns', {})
                if not self.ddns_config:
                    raise ValueError("配置文件中缺少ddns配置段")
                
                self.users = self.ddns_config.get('users', [])
                if not isinstance(self.users, list):
                    raise ValueError("users配置必须是列表类型")
                
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
        except (FileNotFoundError, ValueError) as e:
            raise
        except yaml.YAMLError as e:
            error_msg = f"配置文件YAML格式错误: {e}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e
        except Exception as e:
            error_msg = f"加载配置文件时出错: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def save_config(self) -> None:
        """保存配置文件
        
        Raises:
            PermissionError: 当没有权限写入配置文件时
            OSError: 当文件操作失败时
        """
        try:
            # 更新配置中的IP地址
            self.ddns_config['last_ip'] = self.cached_ip
            self.config['ddns'] = self.ddns_config
            
            # 使用临时文件确保原子性写入
            temp_file = f"{self.config_file}.tmp"
            try:
                with open(temp_file, 'w', encoding='utf-8', newline='\n') as f:
                    yaml.dump(self.config, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
                
                # 原子性替换
                shutil.move(temp_file, self.config_file)
                logger.info(f"配置文件已更新: {self.config_file}")
            except PermissionError:
                # 清理临时文件
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except OSError:
                        pass
                raise PermissionError(f"没有权限写入配置文件: {self.config_file}")
            except OSError as e:
                # 清理临时文件
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except OSError:
                        pass
                raise OSError(f"保存配置文件失败: {e}") from e
        except (PermissionError, OSError):
            raise
        except Exception as e:
            logger.error(f"保存配置文件时出错: {e}")
            # 清理临时文件
            temp_file = f"{self.config_file}.tmp"
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except OSError:
                    pass
            raise RuntimeError(f"保存配置文件时发生未知错误: {e}") from e

    def send_email(self, subject: str, content: str) -> bool:
        """发送邮件通知"""
        if not self.smtp_config:
            logger.warning("未配置SMTP信息，跳过邮件发送")
            return False

        # 验证SMTP配置
        required_fields = ['server', 'port', 'username', 'password', 'sender', 'receiver']
        for field in required_fields:
            if field not in self.smtp_config:
                logger.error(f"SMTP配置缺少必需字段: {field}")
                return False

        try:
            msg = MIMEMultipart()
            msg['From'] = self.smtp_config['sender']
            msg['To'] = self.smtp_config['receiver']
            msg['Subject'] = subject
            msg.attach(MIMEText(content, 'plain', 'utf-8'))

            logger.info(f"正在连接SMTP服务器: {self.smtp_config['server']}:{self.smtp_config['port']}")
            
            # 根据端口选择连接方式，使用上下文管理器确保资源正确释放
            if self.smtp_config['port'] == 465:
                with smtplib.SMTP_SSL(
                    self.smtp_config['server'], 
                    self.smtp_config['port'], 
                    timeout=SMTP_TIMEOUT
                ) as server:
                    server.login(self.smtp_config['username'], self.smtp_config['password'])
                    server.send_message(msg)
            else:
                with smtplib.SMTP(
                    self.smtp_config['server'], 
                    self.smtp_config['port'], 
                    timeout=SMTP_TIMEOUT
                ) as server:
                    if self.smtp_config.get('use_tls', True):
                        logger.info("启用TLS加密连接")
                        server.starttls()
                    server.login(self.smtp_config['username'], self.smtp_config['password'])
                    server.send_message(msg)

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
        except (socket.timeout, socket.error) as e:
            logger.error(f"网络连接错误: {e}")
            return False
        except Exception as e:
            logger.error(f"发送邮件时出错: {e}")
            return False

    def get_public_ip(self) -> bool:
        """获取公网IP地址，使用多个服务进行容错
        
        Returns:
            bool: 成功获取IP返回True，失败返回False
            
        Note:
            失败时会发送邮件通知，但不会抛出异常（允许程序继续运行）
        """
        for service in IP_CHECK_SERVICES:
            try:
                response = requests.get(service['url'], timeout=REQUEST_TIMEOUT)
                if response.status_code == 200:
                    match = re.search(service['pattern'], response.text.strip())
                    if match:
                        ip = match.group(1)
                        # 验证IP地址格式
                        if is_valid_ipv4(ip):
                            self.current_ip = ip
                            logger.info(f"通过 {service['url']} 获取到当前公网IP: {self.current_ip}")
                            return True
                        else:
                            logger.warning(f"从 {service['url']} 获取的IP地址格式无效: {ip}")
            except requests.exceptions.Timeout:
                logger.warning(f"从 {service['url']} 获取IP超时")
            except requests.exceptions.RequestException as e:
                logger.warning(f"从 {service['url']} 获取IP失败: {e}")
            except Exception as e:
                logger.warning(f"从 {service['url']} 获取IP时发生未知错误: {e}")

        # 所有方式都失败，发送邮件通知
        error_msg = "所有获取IP的方式都失败了，请检查网络连接"
        logger.error(error_msg)
        self.send_email("获取公网IP失败通知", error_msg)
        return False

    def _md5_password(self, password: str) -> str:
        """对密码进行MD5加密"""
        return hashlib.md5(password.encode('utf-8')).hexdigest()
    
    def update_ddns_for_user(self, username: str, password: str) -> tuple[bool, str]:
        """更新单个用户的所有域名（不带hostname参数）
        
        返回: (是否成功, 错误信息)
        """
        try:
            if not self.current_ip:
                error_msg = f"当前IP地址为空，无法更新"
                logger.error(f"用户 {username}: {error_msg}")
                return (False, error_msg)
            
            if not is_valid_ipv4(self.current_ip):
                error_msg = f"IP地址格式无效: {self.current_ip}"
                logger.error(f"用户 {username}: {error_msg}")
                return (False, error_msg)
            
            md5_password = self._md5_password(password)
            
            params = {
                'username': username,
                'password': md5_password,
                'myip': self.current_ip
                # 注意：不包含hostname参数，这样会更新该用户下的所有域名
            }
            
            full_url = f"{self.api_url}?{urlencode(params)}"
            logger.info(f"DDNS更新URL (用户: {username}): {full_url.replace(md5_password, '******')}")
            
            response = requests.get(self.api_url, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            
            response_text = response.text.strip()
            logger.info(f"DDNS服务器响应 (用户: {username}): {response_text}")
            
            if response_text.startswith('good'):
                logger.info(f"用户 {username} 的所有域名DDNS更新成功")
                return (True, "")
            elif response_text.startswith('nochg'):
                logger.info(f"用户 {username} 的IP地址未变化")
                return (True, "")
            elif response_text.startswith('badauth'):
                error_msg = f"认证失败，请检查用户名和密码"
                logger.error(f"用户 {username}: {error_msg}")
                return (False, error_msg)
            elif response_text.startswith('911'):
                error_msg = f"服务器维护中，10分钟后重试"
                logger.error(f"用户 {username}: {error_msg}")
                return (False, error_msg)
            elif response_text.startswith('notfqdn'):
                error_msg = f"域名格式无效"
                logger.error(f"用户 {username}: {error_msg}")
                return (False, error_msg)
            elif response_text.startswith('nohost'):
                error_msg = f"域名未找到"
                logger.error(f"用户 {username}: {error_msg}")
                return (False, error_msg)
            elif response_text.startswith('dnserr'):
                error_msg = f"DNS服务器错误"
                logger.error(f"用户 {username}: {error_msg}")
                return (False, error_msg)
            else:
                error_msg = f"DDNS更新失败: {response_text}"
                logger.error(f"用户 {username}: {error_msg}")
                return (False, error_msg)
        except requests.exceptions.Timeout:
            error_msg = f"请求超时"
            logger.error(f"更新用户 {username} DDNS时{error_msg}")
            return (False, error_msg)
        except requests.exceptions.RequestException as e:
            error_msg = f"网络错误: {e}"
            logger.error(f"更新用户 {username} DDNS时{error_msg}")
            return (False, error_msg)
        except Exception as e:
            error_msg = f"未知错误: {e}"
            logger.error(f"更新用户 {username} DDNS时{error_msg}")
            return (False, error_msg)

    def update_all_users(self) -> dict[str, Any]:
        """更新所有用户的DDNS记录
        
        返回: {
            'all_success': bool,  # 是否所有用户都成功
            'success_users': list,  # 成功用户列表
            'failed_users': list,  # 失败用户列表，每个元素为 {'username': str, 'error': str}
            'skipped_count': int   # 跳过的用户数量
        }
        """
        result = {
            'all_success': False,
            'success_users': [],
            'failed_users': [],
            'skipped_count': 0
        }
        
        if not self.users:
            logger.error("未配置任何用户")
            return result

        for user in self.users:
            username = user.get('username')
            password = user.get('password')
            
            if not username or not password:
                logger.warning(f"用户配置不完整，跳过: {user}")
                result['skipped_count'] += 1
                continue
                
            success, error_msg = self.update_ddns_for_user(username, password)
            if success:
                result['success_users'].append(username)
            else:
                result['failed_users'].append({
                    'username': username,
                    'error': error_msg
                })

        total_valid_users = len(self.users) - result['skipped_count']
        result['all_success'] = (len(result['success_users']) == total_valid_users and total_valid_users > 0)
        
        return result

    def run_once(self) -> bool:
        """执行一次更新流程
        
        Returns:
            bool: 更新成功返回True，失败返回False
            
        Note:
            获取IP失败或IP格式无效时不会退出程序，只返回False并记录日志
        """
        # 开始执行时更新健康检查标记
        write_health_check()
        
        # 获取当前公网IP
        if not self.get_public_ip():
            error_msg = "无法获取公网IP地址，跳过本次更新"
            logger.error(error_msg)
            write_health_check()  # 即使失败也更新标记
            return False
        
        # 验证获取到的IP地址（双重验证，确保安全）
        if not self.current_ip or not is_valid_ipv4(self.current_ip):
            error_msg = f"获取到的IP地址格式无效: {self.current_ip}，跳过本次更新"
            logger.error(error_msg)
            write_health_check()
            return False
        
        # 比较IP是否发生变化
        if self.current_ip == self.cached_ip:
            logger.info(f"IP地址未发生变化 ({self.current_ip})，无需更新")
            write_health_check()  # 更新标记
            return True
        
        # 更新所有用户的DDNS
        update_result = self.update_all_users()
        
        # 构建汇总邮件内容
        email_content_parts = [
            f"更新后IP地址: {self.current_ip}",
            f"更新前IP地址: {self.cached_ip}",
            f"更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            ""
        ]
        
        # 添加成功用户信息
        if update_result['success_users']:
            email_content_parts.append(f"✅ 更新成功的用户 ({len(update_result['success_users'])} 个):")
            for username in update_result['success_users']:
                email_content_parts.append(f"  - {username}")
            email_content_parts.append("")
        
        # 添加失败用户信息
        if update_result['failed_users']:
            email_content_parts.append(f"❌ 更新失败的用户 ({len(update_result['failed_users'])} 个):")
            for failed_user in update_result['failed_users']:
                email_content_parts.append(f"  - {failed_user['username']}: {failed_user['error']}")
            email_content_parts.append("")
        
        # 添加跳过的用户信息
        if update_result['skipped_count'] > 0:
            email_content_parts.append(f"⚠️  跳过的用户: {update_result['skipped_count']} 个（配置不完整）")
            email_content_parts.append("")
        
        # 确定邮件主题
        if update_result['all_success']:
            email_subject = "DDNS更新成功通知"
            email_content_parts.insert(0, "DDNS更新成功！\n")
            logger.info("所有用户DDNS更新完成")
        else:
            email_subject = "DDNS更新结果通知"
            email_content_parts.insert(0, "DDNS更新完成（部分用户失败）\n")
            logger.error("部分用户DDNS更新失败")
        
        email_content = "\n".join(email_content_parts)
        
        # 发送汇总邮件
        if self.send_email(email_subject, email_content):
            logger.info("DDNS更新结果通知邮件发送成功")
        else:
            logger.error("DDNS更新结果通知邮件发送失败")
        
        # 如果所有用户都成功，更新配置文件中的IP
        if update_result['all_success']:
            self.cached_ip = self.current_ip
            try:
                self.save_config()
            except Exception as e:
                logger.error(f"保存配置失败，但更新已成功: {e}")
        
        write_health_check()  # 更新标记
        return update_result['all_success']

    def run(self) -> None:
        """运行DDNS客户端 - 基于crontab的定时更新模式
        
        Note:
            此方法会持续运行，直到收到退出信号或发生致命错误
        """
        logger.info("=" * 50)
        logger.info("DDNS客户端启动")
        logger.info(f"更新计划: {self.schedule}")
        logger.info(f"配置目录: {CONFIG_DIR}")
        logger.info(f"日志目录: {LOG_DIR}")
        logger.info("=" * 50)
        
        # 检查是否有配置用户（此检查已在_validate_config中完成，这里作为双重保险）
        if not self.users:
            error_msg = "未配置任何用户，程序退出"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # 输出启动完成信息到控制台（立即刷新以确保在Docker中可见）
        print("=" * 60, flush=True)
        print("DDNS Update Client - System Started Successfully", flush=True)
        print("=" * 60, flush=True)
        print(f"Configuration loaded: {len(self.users)} user(s) configured", flush=True)
        print(f"Update schedule: {self.schedule}", flush=True)
        print(f"Configuration directory: {CONFIG_DIR}", flush=True)
        print(f"Log directory: {LOG_DIR}", flush=True)
        print("=" * 60, flush=True)
        print("System is running normally. Domain updates will begin according to the schedule.", flush=True)
        print("=" * 60, flush=True)
        
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
            logger.error(f"程序运行出错: {e}", exc_info=True)
            raise

def signal_handler(signum: int, frame: Any) -> None:
    """信号处理器，用于优雅退出"""
    try:
        signal_name = signal.Signals(signum).name
        logger.info(f"收到信号 {signal_name} ({signum})，准备退出...")
    except:
        # 如果日志系统未初始化，直接退出
        pass
    sys.exit(0)

def main() -> int:
    """主函数
    
    Returns:
        int: 退出码，0表示成功，非0表示失败
    """
    # 注册信号处理器，用于优雅退出
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # 初始化配置目录（在日志系统之前，使用print输出）
        init_config_dir()
        
        # 设置日志（使用loguru，仅输出到文件）
        setup_logging()
        
        # 创建并运行DDNS客户端
        # 注意：配置验证失败会在DDNSClient.__init__中抛出异常，导致程序退出
        client = DDNSClient()
        client.run()
        
        return 0
    except (FileNotFoundError, PermissionError) as e:
        # 配置文件或权限错误，直接退出
        error_msg = str(e)
        try:
            logger.error(error_msg)
        except:
            print(f"错误: {error_msg}", flush=True)
        return 1
    except ValueError as e:
        # 配置验证失败，直接退出
        error_msg = f"配置验证失败: {e}"
        try:
            logger.error(error_msg)
        except:
            print(f"错误: {error_msg}", flush=True)
        return 1
    except RuntimeError as e:
        # 运行时错误，直接退出
        error_msg = f"运行时错误: {e}"
        try:
            logger.error(error_msg, exc_info=True)
        except:
            print(f"错误: {error_msg}", flush=True)
        return 1
    except KeyboardInterrupt:
        # 用户中断，正常退出
        try:
            logger.info("收到键盘中断信号，程序退出")
        except:
            pass
        return 0
    except Exception as e:
        # 其他未预期的错误
        error_msg = f"程序运行出错: {e}"
        try:
            logger.error(error_msg, exc_info=True)
        except:
            print(error_msg, flush=True)
        return 1

if __name__ == '__main__':
    exit(main())
