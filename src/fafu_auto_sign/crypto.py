"""
加密模块 - 处理签名和授权头生成。
"""
import hashlib
import base64
import random
import string
import time
from urllib.parse import urlparse


SECRET_KEY = "AtPs2O1xEnhwkKDV"


def generate_auth_header(url: str, user_token: str) -> str:
    """
    生成 Authorization 请求头。
    
    算法:
    1. 解析 URL，去除查询参数，只保留 scheme://netloc/path
    2. 生成 16 位随机 nonce
    3. 获取当前 Unix 时间戳（秒）
    4. 拼接字符串: secret + clean_url + timestamp + nonce
    5. 计算 MD5 哈希作为签名
    6. 拼接 auth 字符串: timestamp:nonce:sign:user_token
    7. Base64 编码
    
    Args:
        url: 完整 URL
        user_token: 用户令牌
        
    Returns:
        Base64 编码的授权字符串
    """
    parsed_url = urlparse(url)
    clean_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
    
    nonce = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
    timestamp = str(int(time.time()))
    
    raw_string = f"{SECRET_KEY}{clean_url}{timestamp}{nonce}"
    sign = hashlib.md5(raw_string.encode('utf-8')).hexdigest()
    
    auth_raw = f"{timestamp}:{nonce}:{sign}:{user_token}"
    auth_base64 = base64.b64encode(auth_raw.encode('utf-8')).decode('utf-8')
    
    return auth_base64


def generate_headers(url: str, user_token: str) -> dict:
    """
    生成完整的 HTTP 请求头。
    
    Args:
        url: 请求的 URL
        user_token: 用户令牌
        
    Returns:
        包含所有必需字段的请求头字典
    """
    return {
        "Host": "stuhtapi.fafu.edu.cn",
        "X-Requested-With": "cn.edu.fafu.iportal",
        "Authorization": generate_auth_header(url, user_token),
        "User-Agent": "Mozilla/5.0 (Linux; Android 16; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Mobile Safari/537.36 HuaWei-AnyOffice/1.0.0/cn.edu.fafu.iportal",
        "Referer": "http://stuhealth.fafu.edu.cn/",
        "Origin": "http://stuhealth.fafu.edu.cn",
        "Accept-Encoding": "gzip, deflate"
    }
