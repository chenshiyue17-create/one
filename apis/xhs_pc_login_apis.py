import json
import time
import random
import uuid

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context
from loguru import logger

class TLSAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        context = create_urllib3_context()
        context.set_ciphers('DEFAULT@SECLEVEL=1')
        kwargs['ssl_context'] = context
        return super(TLSAdapter, self).init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args, **kwargs):
        context = create_urllib3_context()
        context.set_ciphers('DEFAULT@SECLEVEL=1')
        kwargs['ssl_context'] = context
        return super(TLSAdapter, self).proxy_manager_for(*args, **kwargs)

from xhs_utils.http_util import REQUEST_TIMEOUT
from xhs_utils.xhs_util import generate_headers, splice_str
from xhs_utils.common_util import generate_a1, generate_web_id, fetch_sec_cookies, fetch_gid


class XHSLoginApi:
    def __init__(self):
        self.base_url = "https://edith.xiaohongshu.com"
        self.as_url = "https://as.xiaohongshu.com"

    def _get_request_headers(self):
        return {
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'zh-CN,zh;q=0.9',
            'content-type': 'application/json;charset=UTF-8',
            'origin': 'https://www.xiaohongshu.com',
            'referer': 'https://www.xiaohongshu.com/',
        }

    def generate_init_cookies(self):
        ts = int(time.time() * 1000)
        a1 = generate_a1()
        web_id = generate_web_id(a1)
        cookies = {
            'abRequestId': str(uuid.uuid4()),
            'ets': str(ts),
            'webBuild': '4.50.0',
            'xsecappid': 'xhs-pc-web',
            'loadts': str(ts + random.randint(50, 200)),
            'a1': a1,
            'webId': web_id,
        }

        req_headers = self._get_request_headers()
        
        # Try to fetch additional required cookies
        sec_poison_id, websectiga = fetch_sec_cookies(cookies, req_headers)
        if sec_poison_id:
            cookies['sec_poison_id'] = sec_poison_id
        if websectiga:
            cookies['websectiga'] = websectiga

        gid = fetch_gid(cookies, req_headers)
        if gid:
            cookies['gid'] = gid

        return cookies

    def _make_request(self, method, url, **kwargs):
        with requests.Session() as session:
            session.trust_env = False  # Ignore system proxies
            # Use TLSAdapter to avoid UNEXPECTED_EOF_WHILE_READING issues
            session.mount("https://", TLSAdapter())
            kwargs['headers'] = kwargs.get('headers', {})
            kwargs['headers']['Connection'] = 'close'
            return session.request(method, url, **kwargs)

    def generate_qrcode(self, cookies):
        api = '/api/sns/web/v1/login/qrcode/create'
        data = {"qr_type": 1}

        headers, data_str = generate_headers(cookies['a1'], api, data, method='POST')
        resp = self._make_request(
            'POST',
            self.base_url + api,
            headers=headers, cookies=cookies, data=data_str,
            timeout=REQUEST_TIMEOUT
        )
        for key, value in resp.cookies.items():
            cookies[key] = value

        res = resp.json()
        if not res.get('success'):
            return False, res.get('msg', '获取二维码失败'), None
        
        data = res.get('data') or {}
        return True, '成功', {
            'cookies': cookies,
            'qr_id': data['qr_id'],
            'code': data['code'],
            'qr_url': data['url'],
        }

    def check_qrcode_status(self, qr_id, code, cookies):
        """Directly poll the status endpoint for better reliability."""
        api = '/api/sns/web/v1/login/qrcode/status'
        params = {"qr_id": qr_id, "code": code}
        splice_api = splice_str(api, params)

        headers, _ = generate_headers(cookies['a1'], splice_api, method='GET')
        try:
            resp = self._make_request(
                'GET',
                self.base_url + splice_api,
                headers=headers, cookies=cookies,
                timeout=REQUEST_TIMEOUT
            )
            for key, value in resp.cookies.items():
                cookies[key] = value
            
            res = resp.json()
            if not res.get('success'):
                # Some errors return success=False but might be recoverable
                msg = res.get('msg', '查询失败')
                if '过期' in msg or 'expired' in msg.lower():
                    return False, '二维码已过期', cookies
                return False, msg, cookies

            data = res.get('data', {})
            login_info = data.get('login_info')
            
            if login_info:
                # Login confirmed
                if 'session' in login_info:
                    cookies['web_session'] = login_info['session']
                return True, '验证成功', cookies
            
            # Check for intermediate statuses if not confirmed
            # Note: XHS might not always return a clear status if not confirmed
            # We assume it's pending if login_info is missing but success is True
            return False, '请扫描二维码', cookies

        except Exception as e:
            logger.error(f"Check QR code status failed: {e}")
            return False, str(e), cookies

    def get_user_info(self, cookies):
        api = '/api/sns/web/v2/user/me'
        headers, _ = generate_headers(cookies['a1'], api, method='GET')
        try:
            resp = self._make_request(
                'GET',
                self.base_url + api,
                headers=headers, cookies=cookies,
                timeout=REQUEST_TIMEOUT
            )
            for key, value in resp.cookies.items():
                cookies[key] = value
            res = resp.json()
            return res.get('success', False), res.get('data', {}), cookies
        except Exception as e:
            return False, {}, cookies

    def cookies_to_str(self, cookies):
        return '; '.join(f'{k}={v}' for k, v in cookies.items())

    def send_phone_code(self, phone, cookies, zone='86'):
        api = '/api/sns/web/v2/login/send_code'
        params = {"phone": phone, "zone": zone, "type": "login"}
        splice_api = splice_str(api, params)

        headers, _ = generate_headers(cookies['a1'], splice_api, method='GET')
        resp = self._make_request(
            'GET',
            self.base_url + splice_api,
            headers=headers, cookies=cookies,
            timeout=REQUEST_TIMEOUT
        )
        res = resp.json()
        return res.get('success', False), res.get('msg', ''), res

    def login_by_phone(self, phone, code, cookies, zone='86'):
        check_api = '/api/sns/web/v1/login/check_code'
        params = {"phone": phone, "zone": zone, "code": code}
        splice_api = splice_str(check_api, params)

        headers, _ = generate_headers(cookies['a1'], splice_api, method='GET')
        resp = self._make_request(
            'GET',
            self.base_url + splice_api,
            headers=headers, cookies=cookies,
            timeout=REQUEST_TIMEOUT
        )
        res = resp.json()
        if not res.get('success'):
            return False, res.get('msg', '验证码验证失败'), {'cookies': cookies}
        
        mobile_token = (res.get('data') or {}).get('mobile_token')
        if not mobile_token:
            return False, res.get('msg', '验证码响应缺少 mobile_token'), {'cookies': cookies}

        login_api = '/api/sns/web/v2/login/code'
        data = {"mobile_token": mobile_token, "zone": zone, "phone": phone}
        headers, data_str = generate_headers(cookies['a1'], login_api, data, method='POST')
        resp = self._make_request(
            'POST',
            self.base_url + login_api,
            headers=headers, cookies=cookies, data=data_str,
            timeout=REQUEST_TIMEOUT
        )
        for key, value in resp.cookies.items():
            cookies[key] = value

        res = resp.json()
        if not res.get('success'):
            return False, res.get('msg', '登录失败'), {'cookies': cookies}
        
        session = (res.get('data') or {}).get('session')
        if session:
            cookies['web_session'] = session
            
        return True, '成功', {
            'cookies': cookies,
            'res_json': res,
        }
