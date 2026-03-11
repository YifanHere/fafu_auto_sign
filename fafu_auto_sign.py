import requests
import time
import random
import string
import hashlib
import base64
from urllib.parse import urlparse

# ================= 配置区域 =================
# 填入你抓包获取的 User Token (抓包 Authorization 解码后的最后一部分，形如 2_xxxxxxxx)
USER_TOKEN = "$YOUR_TOKEN_HERE$"

# 伪造坐标 (福建农林大学安溪校区A10号楼附近坐标，可自己微调)
TARGET_LNG = 118.237686
TARGET_LAT = 25.077727

# ================= 核心：签名破解算法 =================
def generate_auth_header(full_url):
    """
    根据破解的JS逻辑，生成合法的 Authorization 头部
    """
    # 1. 提取不带参数的纯净URL
    parsed_url = urlparse(full_url)
    clean_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
    
    # 2. 生成 16位 随机字符串
    nonce = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
    
    # 3. 生成 秒级时间戳
    timestamp = str(int(time.time()))
    
    # 4. Secret Key
    secret = "AtPs2O1xEnhwkKDV"
    
    # 5. 拼接原始字符串: Secret + CleanURL + Timestamp + Nonce
    raw_string = f"{secret}{clean_url}{timestamp}{nonce}"
    
    # 6. 计算 MD5
    sign = hashlib.md5(raw_string.encode('utf-8')).hexdigest()
    
    # 7. 拼接最终字符串并 Base64 编码
    # 格式: timestamp:nonce:sign:user_token
    auth_raw = f"{timestamp}:{nonce}:{sign}:{USER_TOKEN}"
    auth_base64 = base64.b64encode(auth_raw.encode('utf-8')).decode('utf-8')
    
    return auth_base64

def get_common_headers(url):
    return {
        "Host": "stuhtapi.fafu.edu.cn",
        "X-Requested-With": "cn.edu.fafu.iportal",
        "Authorization": generate_auth_header(url),  # 动态生成签名
        "User-Agent": "Mozilla/5.0 (Linux; Android 16; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Mobile Safari/537.36 HuaWei-AnyOffice/1.0.0/cn.edu.fafu.iportal",
        "Referer": "http://stuhealth.fafu.edu.cn/",
        "Origin": "http://stuhealth.fafu.edu.cn",
        "Accept-Encoding": "gzip, deflate"
    }

# ================= 业务逻辑 =================
BASE_URL = "http://stuhtapi.fafu.edu.cn"

def get_pending_task():
    """获取正在进行中的签到任务 (包含详细调试输出)"""
    url = f"{BASE_URL}/health-api/sign_in/student/my/page?rows=10&pageNum=1&signState=0"
    headers = get_common_headers(url)
    
    try:
        # 为了确保请求头完整，显式加上 Content-Type
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        
        res = requests.post(url, headers=headers)
        
        # ================= 核心调试区 =================
        print(f"[*] 请求 URL: {url}")
        print(f"[*] 发送的 Headers Authorization: {headers['Authorization']}")
        print(f"[*] HTTP 状态码: {res.status_code}")
        print(f"[*] 服务器原始返回数据: {res.text}")
        # ==============================================
        
        # 尝试解析 JSON
        data = res.json()
        
        if 'records' not in data:
            print("[-] 服务器没有返回 'records' 字段，请根据上方原始返回数据排查原因(通常是Token过期或签名错误)。")
            return None
            
        current_time_ms = int(time.time() * 1000)
        
        for task in data['records']:
            task_id = task['id']
            task_name = task['name']
            begin_time = task['beginTime']
            end_time = task['endTime']
            
            is_active = begin_time <= current_time_ms <= end_time
            is_target_type = "晚归" in task_name
            
            if is_active and is_target_type:
                print(f"[*] 精准匹配到进行中的晚归签到任务: 【{task_name}】 (ID: {task_id})")
                return task_id
            elif is_active and not is_target_type:
                print(f"[!] 发现进行中的其他签到，跳过: 【{task_name}】")
                
        print("[-] 列表中没有正在有效时间内的晚归签到任务。")
        return None
        
    except Exception as e:
        print(f"[!] 获取任务列表时发生异常: {e}")
        return None

def upload_image():
    """上传一张预先准备好的宿舍照片"""
    url = f"{BASE_URL}/health-api/qiniu/image/upload?filePre=welink/school/health/&isCompress=1&isDeleteAfterDays=1"
    headers = get_common_headers(url)
    
    # 请确保同目录下有一张名为 dorm.jpg 的照片
    try:
        files = {'file': ('dorm.jpg', open('dorm.jpg', 'rb'), 'image/jpeg')}
        res = requests.post(url, headers=headers, files=files)
        img_url = res.text.strip()
        print(f"[*] 照片上传成功, 七牛云URL: {img_url}")
        return img_url
    except FileNotFoundError:
        print("[!] 错误：请在脚本同目录下放一张名为 dorm.jpg 的照片作为签到图片！")
        return None

def submit_sign(task_id, sign_img_url):
    """提交最终签到数据"""
    # 加入随机偏移，防止每天坐标完全一样被判定为脚本
    lng = TARGET_LNG + random.uniform(-0.00005, 0.00005)
    lat = TARGET_LAT + random.uniform(-0.00005, 0.00005)
    
    url = f"{BASE_URL}/health-api/sign_in/{task_id}/student/sign?lng={lng:.6f}&lat={lat:.6f}&signImg={sign_img_url}&signInPositionId=516208"
    headers = get_common_headers(url)
    
    res = requests.post(url, headers=headers)
    
    if res.status_code == 200:
        print(f"✅ 签到成功！当前提交坐标：[{lng:.6f}, {lat:.6f}]")
    else:
        print(f"❌ 签到失败，状态码: {res.status_code}, 返回: {res.text}")

def keep_alive_and_sign():
    print(">>> 启动自动保活与签到守护进程...")
    while True:
        try:
            # 1. 尝试获取任务 (顺便起到了保活 Token 的作用)
            task_id = get_pending_task()
            
            # 2. 如果碰巧遇到晚归签到任务，就执行签到
            if task_id:
                img_url = upload_image()
                if img_url:
                    submit_sign(task_id, img_url)
            else:
                current_time = time.strftime('%H:%M:%S', time.localtime())
                print(f"[{current_time}] 心跳保活成功，未发现任务。睡眠 15 分钟...")
                
        except Exception as e:
            print(f"[!] 发生异常: {e}")
            
        # 3. 睡眠 15 分钟 (15 * 60 = 900 秒)
        time.sleep(900)

# ================= 执行入口 =================
if __name__ == "__main__":
    keep_alive_and_sign()
    print(">>> 任务执行结束。")