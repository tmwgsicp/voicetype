#!/usr/bin/env python3
# Copyright (C) 2026 VoiceType Contributors
# Licensed under AGPL-3.0

"""
Get Aliyun NLS Token using AccessKey.
获取阿里云 NLS Token。
"""

import time
import hmac
import hashlib
import base64
import json
import urllib.request
import urllib.parse
from typing import Optional


def get_aliyun_nls_token(access_key_id: str, access_key_secret: str) -> Optional[str]:
    """
    获取阿里云智能语音交互 Token。
    
    Args:
        access_key_id: AccessKey ID
        access_key_secret: AccessKey Secret
    
    Returns:
        Token 字符串，失败返回 None
    """
    # API 地址
    url = "https://nls-meta.cn-shanghai.aliyuncs.com/"
    
    # 通用参数
    params = {
        "AccessKeyId": access_key_id,
        "Action": "CreateToken",
        "Format": "JSON",
        "RegionId": "cn-shanghai",
        "SignatureMethod": "HMAC-SHA1",
        "SignatureNonce": str(int(time.time() * 1000)),
        "SignatureVersion": "1.0",
        "Timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "Version": "2019-02-28",
    }
    
    # 1. 构造规范化请求字符串
    sorted_params = sorted(params.items())
    query_string = "&".join([f"{k}={urllib.parse.quote(str(v), safe='')}" for k, v in sorted_params])
    
    # 2. 构造待签名字符串
    string_to_sign = f"GET&{urllib.parse.quote('/', safe='')}&{urllib.parse.quote(query_string, safe='')}"
    
    # 3. 计算签名
    h = hmac.new(
        (access_key_secret + "&").encode('utf-8'),
        string_to_sign.encode('utf-8'),
        hashlib.sha1
    )
    signature = base64.b64encode(h.digest()).decode('utf-8')
    
    # 4. 添加签名到参数
    params["Signature"] = signature
    
    # 5. 发送请求
    final_url = url + "?" + urllib.parse.urlencode(params)
    
    try:
        response = urllib.request.urlopen(final_url, timeout=10)
        data = json.loads(response.read())
        
        if "Token" in data:
            token_info = data["Token"]
            token = token_info.get("Id")
            expire_time = token_info.get("ExpireTime")
            
            print(f"[OK] Token obtained, expires at: {expire_time}")
            return token
        else:
            print(f"[FAIL] No token in response: {data}")
            return None
            
    except Exception as e:
        print(f"[FAIL] Error getting token: {e}")
        return None


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 3:
        print("Usage: python get_aliyun_token.py <access_key_id> <access_key_secret>")
        sys.exit(1)
    
    access_key_id = sys.argv[1]
    access_key_secret = sys.argv[2]
    
    token = get_aliyun_nls_token(access_key_id, access_key_secret)
    
    if token:
        print(f"\nToken: {token}")
    else:
        print("\nFailed to get token")
        sys.exit(1)
