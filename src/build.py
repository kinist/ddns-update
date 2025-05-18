#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import shutil
import subprocess
import platform
import argparse
from datetime import datetime

def create_readme():
    """创建README文件"""
    readme_content = """DDNS更新客户端使用说明

1. 配置文件说明
   - 请修改config.yaml中的配置信息
   - 包括DDNS账号信息和邮件通知设置

2. 运行程序
   Windows系统：
   - 双击运行ddns-update.exe
   - 或在命令行中运行：ddns-update.exe
   
   Linux系统：
   - 添加执行权限：chmod +x ddns-update
   - 运行程序：./ddns-update
   
   命令行参数：
   - 指定工作目录：ddns-update -d 目录路径
   - 查看帮助：ddns-update -h

3. 日志文件
   - 程序运行日志保存在run.log文件中
   - 包含IP变化、更新状态等信息

4. 注意事项
   - 首次使用请修改自动生成的配置文件
   - 确保网络连接正常
   - 确保有足够的权限运行程序
"""
    
    return readme_content

def build_for_platform(target_platform, target_arch=None):
    """为特定平台和架构打包程序"""
    # 设置平台相关参数
    if target_platform == 'windows_x86':
        output_name = 'ddns-update'
        icon_file = 'icon.ico'
        extension = '.exe'
        output_dir = '../release/windows_x86'
    elif target_platform == 'linux':
        output_name = 'ddns-update'
        extension = ''
        if target_arch == 'arm':
            output_dir = '../release/linux_arm'
        else:
            output_dir = '../release/linux_x86'
    else:
        print(f"不支持的平台: {target_platform}")
        return False
    
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    # 构建PyInstaller命令
    cmd = [
        'pyinstaller',
        '--onefile',
        '--clean',
        '--noconfirm',
        '--name', output_name,
        '--distpath', output_dir
    ]
    
    # 只有Windows平台才添加图标
    if target_platform == 'windows_x86':
        cmd.extend(['--icon', icon_file])
    
    # 添加主程序文件
    cmd.append('ddns-client.py')
    
    # 如果是交叉编译，添加目标平台参数
    if target_platform != sys.platform:
        if (target_platform == 'linux' and sys.platform.startswith('win')) or \
           (target_platform == 'windows_x86' and sys.platform.startswith('linux')):
            cmd.append('--target-platform')
            cmd.append(target_platform)
    
    # 执行打包命令
    print(f"开始为 {target_platform} {target_arch or ''} 平台打包...")
    try:
        subprocess.run(cmd, check=True)
        
        # 创建README文件
        readme_content = create_readme()
        readme_path = os.path.join(output_dir, 'README.txt')
        with open(readme_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(readme_content)
        
        # 创建示例配置文件
        config_example = """ddns:
  server: api-ipv4.dynu.com
  port: 8245
  protocol: http
  path: /nic/update
  username: username
  password: password
  domains:
  - yourname1.dynudomain.com
  - yourname2.dynudomain.com
  - yourname3.dynudomain.com
  - yourname4.dynudomain.com
  last_ip: 127.0.0.1
smtp:
  server: mail.qq.com
  port: 465
  username: yourname@qq.com
  password: password
  sender: yourname@sender.com
  receiver: yourname@receiver.com
  use_tls: false
"""
        config_path = os.path.join(output_dir, 'config.yaml')
        with open(config_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(config_example)
        
        print(f"打包成功！输出文件在 {output_dir} 目录:")
        print(f"1. {output_name}{extension} - 可执行程序")
        print(f"2. config.yaml - 配置文件模板")
        print(f"3. README.txt - 使用说明")
        return True
    except Exception as e:
        print(f"打包失败: {e}")
        return False

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='DDNS客户端打包工具')
    parser.add_argument('--platform', choices=['all', 'windows_x86', 'linux_x86', 'linux_arm'], 
                        default='all', help='目标平台')
    args = parser.parse_args()
    
    # 设置工作目录为脚本所在目录
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # 根据参数打包指定平台
    if args.platform == 'all' or args.platform == 'windows_x86':
        build_for_platform('windows_x86')
    
    if args.platform == 'all' or args.platform == 'linux_x86':
        build_for_platform('linux')
    
    if args.platform == 'all' or args.platform == 'linux_arm':
        build_for_platform('linux', 'arm')

if __name__ == '__main__':
    main() 