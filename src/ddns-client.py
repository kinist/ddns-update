#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import yaml
import subprocess
import requests
import logging
import smtplib
import hashlib
import argparse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from urllib.parse import urlencode

def setup_logging(work_dir):
    """配置日志"""
    log_file = os.path.join(work_dir, 'run.log')
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    logging.info(f"程序工作目录: {work_dir}")

class DDNSClient:
    def __init__(self, config_file='config.yaml', work_dir=None):
        self.work_dir = work_dir or os.getcwd()
        self.config_file = os.path.join(self.work_dir, config_file)
        self.current_ip = None
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
                    self.username = self.ddns_config.get('username')
                    self.password = self.ddns_config.get('password')
                    self.domains = self.ddns_config.get('domains', [])
                    self.cached_ip = self.ddns_config.get('last_ip', '127.0.0.1')
                    self.smtp_config = self.config.get('smtp', {})
                logging.info(f"成功加载配置文件: {self.config_file}")
                logging.info(f"配置的域名数量: {len(self.domains)}")
            else:
                # 自动生成配置文件模板
                self.config = {
                    'ddns': {
                        'server': 'api-ipv4.dynu.com',
                        'port': 8245,
                        'protocol': 'http',
                        'path': '/nic/update',
                        'username': 'username',
                        'password': 'password',
                        'domains': [
                            'yourname1.dynudomain.com',
                            'yourname2.dynudomain.com',
                            'yourname3.dynudomain.com',
                            'yourname4.dynudomain.com'
                        ],
                        'last_ip': '127.0.0.1'
                    },
                    'smtp': {
                        'server': 'mail.qq.com',
                        'port': 465,
                        'username': 'yourname@qq.com',
                        'password': 'password',
                        'sender': 'yourname@sender.com',
                        'receiver': 'yourname@receiver.com',
                        'use_tls': False
                    }
                }
                with open(self.config_file, 'w', encoding='utf-8', newline='\n') as f:
                    yaml.dump(self.config, f, allow_unicode=True, sort_keys=False)
                logging.info(f"配置文件不存在，已自动生成模板: {self.config_file}")
                # 重新加载一次
                self.load_config()
        except Exception as e:
            error_msg = f"加载配置文件时出错: {e}"
            logging.error(error_msg)
            raise

    def save_config(self):
        """保存配置文件"""
        try:
            # 更新配置中的IP地址
            self.ddns_config['last_ip'] = self.cached_ip
            self.config['ddns'] = self.ddns_config
            
            with open(self.config_file, 'w', encoding='utf-8', newline='\n') as f:
                yaml.dump(self.config, f, allow_unicode=True, sort_keys=False)
            logging.info(f"配置文件已更新: {self.config_file}")
        except Exception as e:
            logging.error(f"保存配置文件时出错: {e}")

    def send_email(self, subject, content):
        """发送邮件通知"""
        if not self.smtp_config:
            logging.warning("未配置SMTP信息，跳过邮件发送")
            return False

        try:
            # 记录SMTP配置信息（密码除外）
            smtp_info = self.smtp_config.copy()
            if 'password' in smtp_info:
                smtp_info['password'] = '******'
            logging.info(f"SMTP配置信息: {smtp_info}")

            msg = MIMEMultipart()
            msg['From'] = self.smtp_config['sender']
            msg['To'] = self.smtp_config['receiver']
            msg['Subject'] = subject

            msg.attach(MIMEText(content, 'plain', 'utf-8'))

            logging.info(f"正在连接SMTP服务器: {self.smtp_config['server']}:{self.smtp_config['port']}")
            
            # 根据端口选择连接方式
            if self.smtp_config['port'] == 465:
                # 465端口使用SSL
                server = smtplib.SMTP_SSL(self.smtp_config['server'], self.smtp_config['port'])
            else:
                # 其他端口使用普通SMTP
                server = smtplib.SMTP(self.smtp_config['server'], self.smtp_config['port'])
                if self.smtp_config.get('use_tls', True):
                    logging.info("启用TLS加密连接")
                    server.starttls()

            logging.info("正在登录SMTP服务器")
            server.login(self.smtp_config['username'], self.smtp_config['password'])
            logging.info("正在发送邮件")
            server.send_message(msg)
            server.quit()

            logging.info("邮件发送成功")
            return True
        except smtplib.SMTPAuthenticationError as e:
            logging.error(f"SMTP认证失败: {e}")
            return False
        except smtplib.SMTPConnectError as e:
            logging.error(f"连接SMTP服务器失败: {e}")
            return False
        except smtplib.SMTPException as e:
            logging.error(f"SMTP错误: {e}")
            return False
        except Exception as e:
            logging.error(f"发送邮件时出错: {e}")
            return False

    def get_public_ip(self):
        """获取公网IP地址，支持两种方式"""
        # 方式1：使用 oray 的接口
        try:
            result = subprocess.run(['curl', '-s', 'http://ddns.oray.com/checkip'], 
                                 capture_output=True, text=True)
            if result.returncode == 0:
                match = re.search(r'Current IP Address: (\d+\.\d+\.\d+\.\d+)', result.stdout)
                if match:
                    self.current_ip = match.group(1)
                    logging.info(f"通过 oray 接口获取到当前公网IP: {self.current_ip}")
                    return True
        except Exception as e:
            logging.warning(f"通过 oray 接口获取IP失败: {e}")

        # 方式2：使用 ipip.net 的接口
        try:
            result = subprocess.run(['curl', '-s', 'https://myip.ipip.net'], 
                                 capture_output=True, text=True)
            if result.returncode == 0:
                match = re.search(r'当前 IP：(\d+\.\d+\.\d+\.\d+)', result.stdout)
                if match:
                    self.current_ip = match.group(1)
                    logging.info(f"通过 ipip.net 接口获取到当前公网IP: {self.current_ip}")
                    return True
        except Exception as e:
            logging.warning(f"通过 ipip.net 接口获取IP失败: {e}")

        # 两种方式都失败，发送邮件通知
        error_msg = "所有获取IP的方式都失败了"
        logging.error(error_msg)
        self.send_email("获取公网IP失败通知", error_msg)
        return False

    def _md5_password(self, password):
        """对密码进行MD5加密"""
        return hashlib.md5(password.encode()).hexdigest()

    def update_ddns(self, domain):
        """更新单个域名的DDNS记录"""
        try:
            # 对密码进行MD5加密
            md5_password = self._md5_password(self.password)
            logging.info("密码已进行MD5加密")
            
            params = {
                'username': self.username,
                'password': md5_password,  # 使用MD5加密后的密码
                'hostname': domain,
                'myip': self.current_ip
            }
            # 构建完整的URL并记录到日志
            full_url = f"{self.api_url}?{urlencode(params)}"
            logging.info(f"DDNS更新URL: {full_url}")
            
            # 使用GET方法发送请求
            logging.info(f"使用GET方法发送DDNS更新请求")
            response = requests.get(self.api_url, params=params)
            response.raise_for_status()
            
            response_text = response.text.strip()
            logging.info(f"DDNS服务器响应: {response_text}")
            
            if response_text.startswith('good'):
                logging.info(f"域名 {domain} DDNS更新成功")
                return True
            elif response_text.startswith('nochg'):
                logging.info(f"域名 {domain} IP地址未变化")
                return True
            elif response_text.startswith('badauth'):
                error_msg = f"域名 {domain} 认证失败，请检查用户名和密码"
                logging.error(error_msg)
                return False
            elif response_text.startswith('911'):
                error_msg = f"域名 {domain} 服务器维护中，10分钟后重试"
                logging.error(error_msg)
                return False
            elif response_text.startswith('notfqdn'):
                error_msg = f"域名 {domain} 格式无效"
                logging.error(error_msg)
                return False
            elif response_text.startswith('nohost'):
                error_msg = f"域名 {domain} 未找到"
                logging.error(error_msg)
                return False
            elif response_text.startswith('dnserr'):
                error_msg = f"域名 {domain} DNS服务器错误"
                logging.error(error_msg)
                return False
            else:
                error_msg = f"域名 {domain} DDNS更新失败: {response_text}"
                logging.error(error_msg)
                return False
        except Exception as e:
            error_msg = f"更新域名 {domain} DDNS时出错: {e}"
            logging.error(error_msg)
            return False

    def update_all_domains(self):
        """更新所有域名的DDNS记录"""
        # 检查域名数量
        if len(self.domains) > 20:
            error_msg = "域名数量超过20个，无法一次性更新"
            logging.error(error_msg)
            self.send_email("DDNS更新失败通知", error_msg)
            return False

        success_count = 0
        failed_domains = []

        for domain in self.domains:
            if self.update_ddns(domain):
                success_count += 1
            else:
                failed_domains.append(domain)

        # 如果有失败的域名，发送邮件通知
        if failed_domains:
            error_msg = (
                f"以下域名DDNS更新失败：\n"
                f"{', '.join(failed_domains)}\n"
                f"当前IP: {self.current_ip}"
            )
            self.send_email("DDNS更新失败通知", error_msg)

        return success_count == len(self.domains)

    def run(self):
        """运行DDNS客户端"""
        logging.info("DDNS客户端启动")
        
        # 检查是否有配置域名
        if not self.domains:
            logging.error("未配置任何域名")
            return
        
        # 获取当前公网IP
        if not self.get_public_ip():
            return
        
        # 比较IP是否发生变化
        if self.current_ip == self.cached_ip:
            logging.info("IP地址未发生变化，无需更新")
            return
        
        # 更新所有域名的DDNS
        if self.update_all_domains():
            logging.info("所有域名DDNS更新完成")
            # 发送更新成功通知邮件
            email_subject = "DDNS更新成功通知"
            email_content = (
                f"DDNS更新成功！\n\n"
                f"更新前IP地址: {self.cached_ip}\n"
                f"更新后IP地址: {self.current_ip}\n"
                f"更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"更新的域名列表：\n"
            )
            for domain in self.domains:
                email_content += f"- {domain}\n"
            
            if self.send_email(email_subject, email_content):
                logging.info("DDNS更新成功通知邮件发送成功")
            else:
                logging.error("DDNS更新成功通知邮件发送失败")
            
            # 更新配置文件中的IP
            self.cached_ip = self.current_ip
            self.save_config()
        else:
            logging.error("部分域名DDNS更新失败")

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description='DDNS客户端程序',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('-d', '--directory', help='set working directory', default=None)
    args = parser.parse_args()

    # 设置工作目录
    work_dir = args.directory if args.directory else os.getcwd()
    if not os.path.exists(work_dir):
        print(f"错误：指定的目录 '{work_dir}' 不存在")
        return

    # 切换到工作目录
    os.chdir(work_dir)
    
    # 设置日志
    setup_logging(work_dir)
    
    try:
        # 创建并运行DDNS客户端
        client = DDNSClient(work_dir=work_dir)
        client.run()
    except FileNotFoundError as e:
        logging.error(str(e))
        return
    except Exception as e:
        logging.error(f"程序运行出错: {e}")
        return

if __name__ == '__main__':
    main() 