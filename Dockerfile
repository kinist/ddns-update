# 使用Python Alpine基础镜像（轻量级）
FROM python:3.11-alpine

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制源代码
COPY src/ /app/

# 创建必要的目录
RUN mkdir -p /etc/ddns-update /var/log/ddns-update

# 复制配置文件示例到应用目录（不会被挂载覆盖）
COPY src/config.yaml.example /app/config.yaml.example

# 设置执行权限
RUN chmod +x /app/ddns-client.py

# 运行程序
CMD ["python", "/app/ddns-client.py"]

