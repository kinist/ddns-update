# 使用Python Alpine基础镜像（轻量级）
FROM python:3.11-alpine

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 创建必要的目录
RUN mkdir -p /etc/ddns-update /var/log/ddns-update

# 只复制必要的文件
COPY src/ddns-update.py /app/ddns-update.py
COPY src/config.yaml.example /app/config.yaml.example

# 设置执行权限
RUN chmod +x /app/ddns-update.py

# 运行程序
CMD ["python", "/app/ddns-update.py"]

