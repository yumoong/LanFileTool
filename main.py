import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import os
import webbrowser
import socket
import qrcode
from PIL import Image, ImageTk
from flask import Flask, request, send_from_directory, render_template_string
from werkzeug.utils import secure_filename
import logging

# --- 配置与全局变量 ---
# 屏蔽 Flask 的调试日志，保持控制台干净
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

PORT = 8000
app = Flask(__name__)
SERVER_THREAD = None
SHARED_FOLDER = os.getcwd() # 默认当前目录

# --- 网页模板 (HTML+CSS) ---
# 这是一个嵌入在代码里的微型网页，对方看到的界面就是这个
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>局域网文件传输站</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background-color: #f0f2f5; margin: 0; padding: 20px; color: #333; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
        h1 { text-align: center; color: #0078D7; margin-bottom: 30px; }
        
        /* 上传区域样式 */
        .upload-box { border: 2px dashed #0078D7; background: #f0f8ff; padding: 30px; text-align: center; border-radius: 10px; margin-bottom: 30px; }
        .btn-upload { background: #0078D7; color: white; border: none; padding: 10px 25px; border-radius: 6px; font-size: 16px; cursor: pointer; margin-top: 10px; }
        .btn-upload:hover { background: #005a9e; }
        
        /* 文件列表样式 */
        h3 { border-bottom: 2px solid #eee; padding-bottom: 10px; }
        ul { list-style: none; padding: 0; }
        li { background: #fff; border-bottom: 1px solid #f0f0f0; padding: 15px; display: flex; justify-content: space-between; align-items: center; }
        li:hover { background-color: #fafafa; }
        .filename { font-weight: 500; font-size: 16px; word-break: break-all; margin-right: 10px; }
        .btn-download { text-decoration: none; color: #0078D7; border: 1px solid #0078D7; padding: 5px 15px; border-radius: 4px; font-size: 14px; white-space: nowrap; }
        .btn-download:hover { background: #0078D7; color: white; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 局域网互传</h1>
        
        <div class="upload-box">
            <p>👇 <b>发送文件给对方</b> (支持多选)</p>
            <form action="/upload" method="post" enctype="multipart/form-data">
                <input type="file" name="file" multiple style="margin-bottom: 15px;">
                <br>
                <input type="submit" value="开始上传" class="btn-upload">
            </form>
        </div>

        <h3>📂 对方共享的文件:</h3>
        <ul>
            {% for file in files %}
            <li>
                <span class="filename">{{ file }}</span>
                <a href="/download/{{ file }}" class="btn-download">下载</a>
            </li>
            {% endfor %}
        </ul>
        {% if not files %}
            <p style="text-align:center; color:gray;">暂无文件</p>
        {% endif %}
    </div>
</body>
</html>
"""

# --- Flask 后端逻辑 ---
@app.route('/')
def index():
    files = []
    try:
        # 只列出文件，不列出文件夹，防止报错
        files = [f for f in os.listdir(SHARED_FOLDER) if os.path.isfile(os.path.join(SHARED_FOLDER, f)) and not f.startswith('.')]
    except Exception:
        pass
    return render_template_string(HTML_TEMPLATE, files=files)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return '错误：没有文件'
    uploaded_files = request.files.getlist("file")
    count = 0
    for file in uploaded_files:
        if file.filename:
            filename = secure_filename(file.filename)
            if not filename: filename = file.filename # 处理中文文件名兼容性
            file.save(os.path.join(SHARED_FOLDER, filename))
            count += 1
    return f'<script>alert("成功上传 {count} 个文件！"); window.location.href="/";</script>'

@app.route('/download/<path:filename>')
def download_file(filename):
    return send_from_directory(SHARED_FOLDER, filename, as_attachment=True)

# --- 核心工具函数 ---
def get_ip_address():
    """获取本机IP"""
    s = socket.socket(socket.socket.AF_INET, socket.socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def run_flask_app():
    """在后台线程运行Web服务器"""
    # host='0.0.0.0' 代表允许外部设备访问
    app.run(host='0.0.0.0', port=PORT, threaded=True)

# --- GUI 界面逻辑 ---
def on_start_click():
    global SHARED_FOLDER, SERVER_THREAD
    SHARED_FOLDER = entry_path.get()
    
    if not os.path.isdir(SHARED_FOLDER):
        messagebox.showerror("错误", "请选择一个有效的文件夹路径！")
        return

    # 1. 获取信息
    ip = get_ip_address()
    url = f"http://{ip}:{PORT}"
    
    # 2. 锁定按钮，防止重复点击
    btn_start.config(state="disabled", text="正在运行", bg="#4CAF50")
    
    # 3. 更新界面信息
    label_info.config(text=f"✅ 服务已启动\n本机 IP: {ip}\n端口: {PORT}", fg="#0078D7")
    label_tip.config(text=f"让对方扫描下方二维码\n或者浏览器输入: {url}")
    
    # 4. 生成二维码
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img_qr = qr.make_image(fill='black', back_color='white')
    img_qr = img_qr.resize((180, 180), Image.Resampling.LANCZOS)
    photo_qr = ImageTk.PhotoImage(img_qr)
    
    label_qr_img.config(image=photo_qr)
    label_qr_img.image = photo_qr # 必须保留引用
    
    # 5. 启动 Flask 服务器线程
    SERVER_THREAD = threading.Thread(target=run_flask_app, daemon=True)
    SERVER_THREAD.start()
    
    # 6. 自动用默认浏览器打开（给自己看）
    webbrowser.open(f"http://127.0.0.1:{PORT}")

def select_directory():
    path = filedialog.askdirectory()
    if path:
        entry_path.delete(0, tk.END)
        entry_path.insert(0, path)

# --- 构建主窗口 ---
root = tk.Tk()
root.title("PC 局域网传文件助手")
root.geometry("400x550")
root.resizable(False, False) # 禁止拉伸窗口

# 顶部标题
tk.Label(root, text="双向文件传输站", font=("微软雅黑", 16, "bold"), fg="#333").pack(pady=(20, 10))

# 文件夹选择区
frame_select = tk.Frame(root)
frame_select.pack(pady=10, padx=20, fill="x")
tk.Label(frame_select, text="共享哪个文件夹：", font=("微软雅黑", 10)).pack(anchor="w")

entry_path = tk.Entry(frame_select, font=("微软雅黑", 9))
entry_path.pack(side="left", fill="x", expand=True, padx=(0, 5))
entry_path.insert(0, os.getcwd()) # 默认当前路径

btn_browse = tk.Button(frame_select, text="浏览...", command=select_directory)
btn_browse.pack(side="right")

# 启动按钮
btn_start = tk.Button(root, text="🚀 启动服务", command=on_start_click, bg="#0078D7", fg="white", font=("微软雅黑", 12, "bold"), height=2, width=20, relief="flat")
btn_start.pack(pady=15)

# 信息展示区
label_info = tk.Label(root, text="点击上方按钮启动", font=("微软雅黑", 10), justify="center", fg="gray")
label_info.pack()

# 二维码区
label_qr_img = tk.Label(root) # 用于放图
label_qr_img.pack(pady=10)

label_tip = tk.Label(root, text="", font=("微软雅黑", 9), fg="gray", justify="center")
label_tip.pack(side="bottom", pady=20)

root.mainloop()