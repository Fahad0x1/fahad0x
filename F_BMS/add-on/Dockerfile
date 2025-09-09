FROM python:3.10-slim-buster

# تثبيت الحزم الأساسية لنظام التشغيل اللازمة لـ OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libsm6 \
    libxext6 \
    libxrender1 \
    libfontconfig1 \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libv4l-dev \
    libgstreamer1.0-dev \
    libgtk2.0-dev \
    && rm -rf /var/lib/apt/lists/*

# نسخ الملفات الأساسية للمشروع
COPY requirements.txt /app/
COPY app.py /app/
COPY templates/ /app/templates/

# تثبيت مكتبات بايثون
WORKDIR /app
RUN pip install --no-cache-dir -r requirements.txt

# إعدادات الإضافة
COPY add-on/config.json /data/config.json

# نسخ السكريبت الذي يشغل التطبيق
COPY add-on/rootfs/run.sh /usr/bin/run.sh
RUN chmod a+x /usr/bin/run.sh

# فتح البورت
EXPOSE 5000

CMD ["/usr/bin/run.sh"]