# DDNS Update Client

[中文文档](#中文文档) | [English Documentation](#english-documentation)

<a name="中文文档"></a>
# DDNS 更新客户端

一款轻量级DDNS（动态域名解析）客户端，用于将IP地址更新到DDNS服务提供商（如Dynu）。

[切换到英文版](#english-documentation)

## 功能特点

- **自动检测IP**: 自动检测公网IP地址变化
- **多域名支持**: 支持使用一个IP地址更新多个域名
- **邮件通知**: 在IP变化和更新状态时发送邮件通知
- **自动配置**: 首次运行时自动生成配置文件模板
- **跨平台**: 支持Windows、Linux x86和Linux ARM平台
- **详细日志**: 提供全面的日志记录，便于故障排查

## 系统要求

- Windows或Linux操作系统
- Python 3.11或更高版本（用于开发）
- 提供以下预编译二进制文件：
  - Windows x86
  - Linux x86
  - Linux ARM

## 安装方法

### 预编译二进制文件

1. 从发布区下载适合您系统的二进制文件：
   - Windows: `ddns-update-windows-x86_64.zip`
   - Linux x86: `ddns-update-linux-x86_64.tar.gz`
   - Linux ARM: `ddns-update-linux-arm.tar.gz`
2. 将压缩包解压到您希望的位置：
   ```bash
   # Windows
   unzip ddns-update-windows-x86_64.zip -d "C:\Program Files\ddns-update\"
   
   # Linux
   mkdir -p /opt/ddns-update
   tar -xzf ddns-update-linux-x86_64.tar.gz -C /opt/ddns-update/
   ```
3. 使用您的DDNS提供商信息配置`config.yaml`文件

### 从源代码安装

```bash
# 克隆仓库
git clone https://github.com/kinist/ddns-update.git
cd ddns-update

# 安装依赖
pip install -r requirements.txt

# 运行客户端
python src/ddns-update.py
```

**注意**：在Debian/Ubuntu系统（如Ubuntu 22.04+）上可能会遇到"externally-managed-environment"错误，这是因为这些系统实施了PEP 668。解决方法：

```bash
# 创建并使用虚拟环境（推荐）
python3 -m venv ddns-venv
source ddns-venv/bin/activate
pip install -r requirements.txt
python src/ddns-update.py
```

## 使用方法

### Windows系统

```
ddns-update.exe
```

或指定工作目录：

```
ddns-update.exe -d C:\path\to\config\directory
```

### Linux系统

```
chmod +x ddns-update
./ddns-update
```

或指定工作目录：

```
./ddns-update -d /path/to/config/directory
```

## 配置文件

客户端使用YAML配置文件（`config.yaml`）。如果文件不存在，将在首次运行时自动生成模板。

```yaml
ddns:
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
```

### 配置字段

#### DDNS部分

| 字段 | 说明 |
|------|------|
| server | DDNS服务器主机名 |
| port | DDNS服务器端口 |
| protocol | 协议（http/https） |
| path | 更新路径 |
| username | DDNS账户用户名 |
| password | DDNS账户密码 |
| domains | 要更新的域名列表 |
| last_ip | 缓存的IP地址（自动更新） |

#### SMTP部分

| 字段 | 说明 |
|------|------|
| server | SMTP服务器主机名 |
| port | SMTP服务器端口 |
| username | 邮箱账户用户名 |
| password | 邮箱账户密码 |
| sender | 发件人邮箱地址 |
| receiver | 收件人邮箱地址 |
| use_tls | 是否使用TLS加密 |

## 命令行参数

```
usage: ddns-update [-h] [-d DIRECTORY]

DDNS客户端程序

options:
  -h, --help                           显示帮助信息并退出
  -d DIRECTORY, --directory DIRECTORY  设置工作目录
```

| 参数 | 说明 |
|------|------|
| -h, --help | 显示帮助信息 |
| -d, --directory | 设置工作目录 |

## 日志记录

客户端将所有活动记录到工作目录中名为`run.log`的文件中。日志包括：

- IP地址检测结果
- DDNS更新请求和响应
- 邮件通知状态
- 错误消息和警告

## 常见问题

### 更新失败

1. 检查config.yaml文件中的DDNS凭据
2. 验证域名是否正确输入
3. 查看run.log文件了解具体错误信息
4. 确保互联网连接正常

### 邮件通知不工作

1. 检查config.yaml中的SMTP设置
2. 对于Gmail或其他具有增强安全性的服务，您可能需要创建应用密码
3. 验证防火墙是否允许SMTP端口上的出站连接

### 程序执行后不退出

如果程序在执行DDNS更新请求后挂起不退出：

1. 最新版本已添加超时设置，更新到最新版本应该解决此问题
2. 如果问题仍然存在，可以使用timeout命令限制运行时间：
   ```bash
   # Linux系统
   timeout 60s ./ddns-update
   
   # Windows系统（需要安装timeout工具）
   timeout /t 60 /nobreak && taskkill /f /im ddns-update.exe
   ```

### Debian/Ubuntu系统依赖安装问题

在Debian/Ubuntu系统（如Ubuntu 22.04+）上安装依赖时可能会遇到"externally-managed-environment"错误：

1. 使用虚拟环境（推荐）：
   ```bash
   python3 -m venv ddns-venv
   source ddns-venv/bin/activate
   pip install -r requirements.txt
   ```

2. 或使用系统包管理器：
   ```bash
   sudo apt install python3-yaml python3-requests
   ```

## 许可证

本项目采用MIT许可证 - 有关详细信息，请参阅LICENSE文件。

---

<a name="english-documentation"></a>
# DDNS Update Client

A lightweight DDNS (Dynamic DNS) client for updating IP addresses to DDNS service providers like Dynu.

[Switch to Chinese](#中文文档)

## Features

- **Auto IP Detection**: Automatically detects public IP address changes
- **Multiple Domains**: Supports updating multiple domain names with one IP address
- **Email Notifications**: Sends email notifications on IP changes and update status
- **Auto Configuration**: Generates template configuration file on first run
- **Cross-Platform**: Supports Windows, Linux x86 and Linux ARM platforms
- **Detailed Logging**: Comprehensive logging for troubleshooting

## System Requirements

- Windows or Linux operating system
- Python 3.11 or later (for development)
- Pre-compiled binaries available for:
  - Windows x86
  - Linux x86
  - Linux ARM

## Installation

### Pre-compiled Binaries

1. Download the appropriate binary for your system from the releases section:
   - Windows: `ddns-update-windows-x86_64.zip`
   - Linux x86: `ddns-update-linux-x86_64.tar.gz`
   - Linux ARM: `ddns-update-linux-arm.tar.gz`
2. Extract the archive to your desired location:
   ```bash
   # Windows
   unzip ddns-update-windows-x86_64.zip -d "C:\Program Files\ddns-update\"
   
   # Linux
   mkdir -p /opt/ddns-update
   tar -xzf ddns-update-linux-x86_64.tar.gz -C /opt/ddns-update/
   ```
3. Configure the `config.yaml` file with your DDNS provider information

### From Source

```bash
# Clone the repository
git clone https://github.com/kinist/ddns-update.git
cd ddns-update

# Install dependencies
pip install -r requirements.txt

# Run the client
python src/ddns-update.py
```

**Note**: On Debian/Ubuntu systems (like Ubuntu 22.04+), you might encounter an "externally-managed-environment" error due to PEP 668. Solution:

```bash
# Create and use a virtual environment (recommended)
python3 -m venv ddns-venv
source ddns-venv/bin/activate
pip install -r requirements.txt
python src/ddns-update.py
```

## Usage

### Windows

```
ddns-update.exe
```

Or with a specific working directory:

```
ddns-update.exe -d C:\path\to\config\directory
```

### Linux

```
chmod +x ddns-update
./ddns-update
```

Or with a specific working directory:

```
./ddns-update -d /path/to/config/directory
```

## Configuration

The client uses a YAML configuration file (`config.yaml`). A template will be automatically generated on first run if the file doesn't exist.

```yaml
ddns:
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
```

### Configuration Fields

#### DDNS Section

| Field | Description |
|-------|-------------|
| server | DDNS server hostname |
| port | DDNS server port |
| protocol | Protocol (http/https) |
| path | Update path |
| username | DDNS account username |
| password | DDNS account password |
| domains | List of domains to update |
| last_ip | Cached IP address (auto-updated) |

#### SMTP Section

| Field | Description |
|-------|-------------|
| server | SMTP server hostname |
| port | SMTP server port |
| username | Email account username |
| password | Email account password |
| sender | Sender email address |
| receiver | Recipient email address |
| use_tls | Whether to use TLS encryption |

## Command Line Arguments

```
usage: ddns-update [-h] [-d DIRECTORY]

DDNS client program

options:
  -h, --help                           show this help message and exit
  -d DIRECTORY, --directory DIRECTORY  set working directory
```

| Argument | Description |
|----------|-------------|
| -h, --help | Show help message |
| -d, --directory | Set working directory |

## Logging

The client logs all activities to a file named `run.log` in the working directory. The log includes:

- IP address detection results
- DDNS update requests and responses
- Email notification status
- Error messages and warnings

## Troubleshooting

### Update Fails

1. Check your DDNS credentials in the config.yaml file
2. Verify that your domain names are correctly entered
3. Check the run.log file for specific error messages
4. Ensure your internet connection is active

### Email Notifications Not Working

1. Check your SMTP settings in config.yaml
2. For Gmail or other services with enhanced security, you may need to create an app password
3. Verify your firewall allows outgoing connections on the SMTP port

### Program Doesn't Exit After Execution

If the program hangs after sending DDNS update requests:

1. The latest version has added timeout settings which should resolve this issue
2. If the problem persists, you can use the timeout command to limit runtime:
   ```bash
   # Linux systems
   timeout 60s ./ddns-update
   
   # Windows systems (requires timeout tool)
   timeout /t 60 /nobreak && taskkill /f /im ddns-update.exe
   ```

### Dependency Installation Issues on Debian/Ubuntu

On Debian/Ubuntu systems (like Ubuntu 22.04+), you might encounter an "externally-managed-environment" error when installing dependencies:

1. Use a virtual environment (recommended):
   ```bash
   python3 -m venv ddns-venv
   source ddns-venv/bin/activate
   pip install -r requirements.txt
   ```

2. Or use the system package manager:
   ```bash
   sudo apt install python3-yaml python3-requests
   ```

## License

This project is licensed under the MIT License - see the LICENSE file for details. 