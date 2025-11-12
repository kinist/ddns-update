# DDNS Update Client

[中文文档](#中文文档) | [English Documentation](#english-documentation)

<a name="中文文档"></a>
# DDNS 更新客户端

一款轻量级DDNS（动态域名解析）客户端，用于将IP地址更新到DDNS服务提供商（如Dynu）。支持Docker容器化部署，提供定时更新、多用户支持和邮件通知功能。

[切换到英文版](#english-documentation)

## 功能特点

- **自动检测IP**: 自动检测公网IP地址变化，支持多个IP检测服务容错
- **多用户支持**: 支持配置多个DDNS用户，每个用户下的所有域名自动更新
- **定时更新**: 支持crontab格式的灵活定时更新策略
- **邮件通知**: 在IP变化和更新状态时发送邮件通知
- **容器化部署**: 基于Docker的容器化部署，简单易用

## 快速开始

1. **克隆仓库并准备目录**
   ```bash
   git clone https://github.com/kinist/ddns-update.git
   cd ddns-update
   mkdir -p persistence/config persistence/logs
   ```

2. **构建并启动**
   ```bash
   docker-compose build
   docker-compose up -d
   ```

3. **配置服务**
   
   编辑 `persistence/config/config.yaml` 文件，填入您的DDNS和SMTP配置信息，然后重启容器：
   ```bash
   docker-compose restart
   ```

## 常用命令

```bash
docker-compose up -d      # 启动服务
docker-compose down       # 停止服务
docker-compose logs -f    # 查看日志
docker-compose restart    # 重启服务
```

## 配置文件

配置文件位置：`persistence/config/config.yaml`

首次启动时，如果配置文件不存在，会自动从示例文件复制。

### 配置示例

```yaml
ddns:
  server: api-ipv4.dynu.com
  port: 8245
  protocol: http
  path: /nic/update
  last_ip: 0.0.0.0
  users:
    - username: user1
      password: pwd1
    - username: user2
      password: pwd2
  # 更新频率（crontab格式：分钟 小时 日期 月份 星期）
  schedule: "*/5 * * * *"  # 每5分钟执行一次
smtp:
  server: mail.sohu.com
  port: 465
  username: example@sohu.com
  password: password
  sender: example@sohu.com
  receiver: ddns-update@qq.com
  use_tls: false
```

### Crontab 格式示例

- `*/5 * * * *` - 每5分钟
- `0 * * * *` - 每小时
- `0 0 * * *` - 每天午夜

## 日志

日志文件位置：`persistence/logs/ddns-update.log`

- 按日期自动切割，保留7天
- 查看日志：`docker-compose logs -f` 或 `tail -f persistence/logs/ddns-update.log`

## 常见问题

**容器启动后立即退出**
- 检查配置文件是否存在且格式正确
- 查看日志：`docker-compose logs ddns-update`

**DDNS更新失败**
- 检查DDNS凭据是否正确
- 查看日志文件了解具体错误信息

**邮件通知不工作**
- 检查SMTP设置是否正确
- 对于Gmail等服务，可能需要创建应用密码

## 许可证

本项目采用MIT许可证 - 有关详细信息，请参阅LICENSE文件。

---

<a name="english-documentation"></a>
# DDNS Update Client

A lightweight DDNS (Dynamic DNS) client for updating IP addresses to DDNS service providers like Dynu. Supports Docker containerized deployment with scheduled updates, multi-user support, and email notifications.

[Switch to Chinese](#中文文档)

## Features

- **Auto IP Detection**: Automatically detects public IP address changes with multiple IP check services for fault tolerance
- **Multi-User Support**: Supports configuring multiple DDNS users, automatically updates all domains for each user
- **Scheduled Updates**: Supports flexible crontab-format update schedules
- **Email Notifications**: Sends email notifications on IP changes and update status
- **Containerized Deployment**: Docker-based containerized deployment, simple and easy to use

## Quick Start

1. **Clone repository and prepare directories**
   ```bash
   git clone https://github.com/kinist/ddns-update.git
   cd ddns-update
   mkdir -p persistence/config persistence/logs
   ```

2. **Build and start**
   ```bash
   docker-compose build
   docker-compose up -d
   ```

3. **Configure the service**
   
   Edit `persistence/config/config.yaml` file with your DDNS and SMTP configuration, then restart the container:
   ```bash
   docker-compose restart
   ```

## Common Commands

```bash
docker-compose up -d      # Start service
docker-compose down       # Stop service
docker-compose logs -f    # View logs
docker-compose restart    # Restart service
```

## Configuration

Configuration file location: `persistence/config/config.yaml`

On first startup, if the configuration file doesn't exist, it will be automatically copied from the example file.

### Configuration Example

```yaml
ddns:
  server: api-ipv4.dynu.com
  port: 8245
  protocol: http
  path: /nic/update
  last_ip: 0.0.0.0
  users:
    - username: user1
      password: pwd1
    - username: user2
      password: pwd2
  # Update schedule (crontab format: minute hour day month weekday)
  schedule: "*/5 * * * *"  # Every 5 minutes
smtp:
  server: mail.sohu.com
  port: 465
  username: example@sohu.com
  password: password
  sender: example@sohu.com
  receiver: ddns-update@qq.com
  use_tls: false
```

### Crontab Format Examples

- `*/5 * * * *` - Every 5 minutes
- `0 * * * *` - Every hour
- `0 0 * * *` - Daily at midnight

## Logging

Log file location: `persistence/logs/ddns-update.log`

- Auto rotation daily, retains 7 days
- View logs: `docker-compose logs -f` or `tail -f persistence/logs/ddns-update.log`

## Troubleshooting

**Container exits immediately after startup**
- Check if configuration file exists and format is correct
- View logs: `docker-compose logs ddns-update`

**DDNS update fails**
- Check DDNS credentials are correct
- View log files for specific error messages

**Email notifications not working**
- Check SMTP settings are correct
- For Gmail and similar services, you may need to create an app password

## License

This project is licensed under the MIT License - see the LICENSE file for details.
