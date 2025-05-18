#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import yaml
import smtplib
import argparse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def load_config(config_file='config.yaml'):
    """加载配置文件"""
    if os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            return config.get('smtp', {})
    return {}

def test_email(smtp_config):
    """测试邮件发送"""
    try:
        # 创建邮件
        msg = MIMEMultipart()
        msg['From'] = smtp_config['sender']
        msg['To'] = smtp_config['receiver']
        msg['Subject'] = '邮件发送测试'
        
        content = '这是一封测试邮件，用于验证SMTP配置是否正确。'
        msg.attach(MIMEText(content, 'plain', 'utf-8'))
        
        print(f"正在连接SMTP服务器: {smtp_config['server']}:{smtp_config['port']}")
        
        # 根据端口选择连接方式
        if smtp_config['port'] == 465:
            # 465端口使用SSL
            server = smtplib.SMTP_SSL(smtp_config['server'], smtp_config['port'])
        else:
            # 其他端口使用普通SMTP
            server = smtplib.SMTP(smtp_config['server'], smtp_config['port'])
            if smtp_config.get('use_tls', True):
                print("启用TLS加密连接")
                server.starttls()
        
        print("正在登录SMTP服务器")
        server.login(smtp_config['username'], smtp_config['password'])
        
        print("正在发送测试邮件")
        server.send_message(msg)
        server.quit()
        
        print("测试邮件发送成功！")
        return True
    except Exception as e:
        print(f"发送测试邮件时出错: {e}")
        return False

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='SMTP邮件发送测试程序')
    parser.add_argument('-d', '--directory', help='指定配置文件目录', default=None)
    args = parser.parse_args()
    
    # 设置工作目录
    if args.directory:
        if not os.path.exists(args.directory):
            print(f"错误：指定的目录 '{args.directory}' 不存在")
            return
        os.chdir(args.directory)
    
    # 加载配置
    smtp_config = load_config()
    if not smtp_config:
        print("错误：未找到SMTP配置或配置文件不存在")
        return
    
    # 测试邮件发送
    test_email(smtp_config)

if __name__ == '__main__':
    main() 