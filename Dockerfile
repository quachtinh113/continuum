# Sử dụng Ubuntu làm nền tảng để dễ cài đặt Wine
FROM ubuntu:24.04

# Thiết lập biến môi trường tránh hỏi tương tác khi cài đặt
ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Asia/Ho_Chi_Minh \
    WINEPREFIX=/root/.wine \
    WINEARCH=win64

# Cài đặt các gói hệ thống, Wine và môi trường đồ họa ảo (Xvfb)
RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common \
    gnupg2 \
    wget \
    curl \
    ca-certificates \
    xvfb \
    x11vnc \
    fluxbox \
    dbus-x11 \
    && dpkg --add-architecture i386 \
    && mkdir -pm755 /etc/apt/keyrings \
    && wget -O /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key \
    && wget -NP /etc/apt/keyrings/ https://dl.winehq.org/wine-builds/ubuntu/dists/noble/winehq-noble.sources \
    && apt-get update \
    && apt-get install -y --install-recommends winehq-stable \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Thiết lập thư mục làm việc
WORKDIR /app

# Khởi tạo Wine prefix
RUN wineboot --init

# Tải và cài đặt Python Windows (phiên bản 3.12.8 AMD64) vào môi trường Wine
RUN wget -q https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe \
    && xvfb-run wine python-3.12.8-amd64.exe /quiet InstallAllUsers=1 PrependPath=1 \
    && rm python-3.12.8-amd64.exe

# Sao chép toàn bộ mã nguồn dự án vào container
COPY . .

# Cài đặt thư viện Python (bao gồm MetaTrader5) trong Wine Python
RUN xvfb-run wine python -m pip install --no-cache-dir --upgrade pip \
    && xvfb-run wine python -m pip install --no-cache-dir -r requirements.txt

# Tạo thư mục chứa dữ liệu MetaTrader 5 trong môi trường ảo Wine
RUN mkdir -p /root/.wine/drive_c/Program\ Files/MetaTrader\ 5

# Thiết lập cổng hiển thị ảo cho giao diện đồ họa MT5
ENV DISPLAY=:1

# Sửa lỗi kết thúc dòng CRLF của Windows và phân quyền thực thi cho entrypoint.sh
RUN apt-get update && apt-get install -y --no-install-recommends dos2unix \
    && dos2unix entrypoint.sh \
    && chmod +x entrypoint.sh \
    && apt-get purge -y dos2unix \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Khởi chạy script điều hướng
CMD ["bash", "entrypoint.sh"]
