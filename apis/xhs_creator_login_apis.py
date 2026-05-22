import json
import time
import random

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

from apis.xhs_creator_apis import XHS_Creator_Apis
from xhs_utils.http_util import REQUEST_TIMEOUT
from xhs_utils.xhs_creator_util import generate_xsc, splice_str
from xhs_utils.common_util import generate_a1, generate_web_id, fetch_sec_cookies, fetch_gid


class XHSCreatorLoginApi:
    def __init__(self):
        self.customer_url = "https://customer.xiaohongshu.com"
        self.creator_url = "https://creator.xiaohongshu.com"

    def _make_request(self, method, url, **kwargs):
        with requests.Session() as session:
            session.mount("https://", TLSAdapter())
            session.trust_env = False
            kwargs['headers'] = kwargs.get('headers', {})
            kwargs['headers']['Connection'] = 'close'
            kwargs['proxies'] = {"http": None, "https": None}
            return session.request(method, url, **kwargs)

    def _get_request_headers(self):
        return {
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'zh-CN,zh;q=0.9',
            'sec-ch-ua': '"Google Chrome";v="121", "Not.A/Brand";v="8", "Chromium";v="121"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'origin': 'https://creator.xiaohongshu.com',
            'referer': 'https://creator.xiaohongshu.com/',
        }

    def generate_init_cookies(self):
        ts = int(time.time() * 1000)
        a1 = generate_a1()
        web_id = generate_web_id(a1)
        cookies = {
            'ets': str(ts),
            'xsecappid': 'ugc',
            'loadts': str(ts + random.randint(50, 200)),
            'a1': a1,
            'webId': web_id,
        }
        
        headers = self._get_request_headers()
        # Ensure initial connection to set basic cookies
        try:
            resp = self._make_request(
                'GET',
                self.creator_url + '/login',
                headers=headers,
                cookies=cookies,
                allow_redirects=False,
                timeout=REQUEST_TIMEOUT
            )
            for key, value in resp.cookies.items():
                cookies[key] = value
        except Exception as e:
            logger.debug(f"Init Creator login page failed: {e}")

        sec_poison_id, websectiga = fetch_sec_cookies(cookies, headers)
        if sec_poison_id:
            cookies['sec_poison_id'] = sec_poison_id
        if websectiga:
            cookies['websectiga'] = websectiga

        gid = fetch_gid(cookies, headers)
        if gid:
            cookies['gid'] = gid

        return cookies

    def generate_qrcode(self, cookies):
        api = '/api/cas/customer/web/qr-code'
        data = {"service": "https://creator.xiaohongshu.com"}

        headers = self._get_request_headers()
        headers['content-type'] = 'application/json'
        headers.update(generate_xsc(cookies['a1'], api, data, method='POST'))

        data_str = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
        resp = self._make_request(
            'POST',
            self.customer_url + api,
            headers=headers,
            cookies=cookies,
            data=data_str.encode('utf-8'),
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
            'qr_id': data['id'],
            'qr_url': data['url'],
        }

    def check_qrcode_status(self, qr_id, cookies):
        api = '/api/cas/customer/web/qr-code'
        params = {
            'service': 'https://creator.xiaohongshu.com',
            'qr_code_id': qr_id,
            'source': ''
        }
        splice_api = splice_str(api, params)

        headers = self._get_request_headers()
        headers.update(generate_xsc(cookies['a1'], splice_api, method='GET'))

        try:
            resp = self._make_request(
                'GET',
                self.customer_url + splice_api,
                headers=headers,
                cookies=cookies,
                timeout=REQUEST_TIMEOUT
            )
            for key, value in resp.cookies.items():
                cookies[key] = value

            res = resp.json()
            if not res.get('success'):
                return False, res.get('msg', '查询失败'), cookies

            status = (res.get('data') or {}).get('status')
            
            # Status mapping: 1: confirmed, 2: pending scan, 3: scanned, waiting confirm, -1: expired
            status_map = {
                1: (True, '验证成功'),
                2: (False, '请扫描二维码'),
                3: (False, '请确认登录'),
                -1: (False, '二维码已过期'),
            }
            success, msg = status_map.get(status, (False, f'未知状态: {status}'))
            
            # If confirmed, ensure session cookies are updated
            if success:
                # The cookies from this response might contain customer_session or tgt
                pass
                
            return success, msg, cookies

        except Exception as e:
            logger.error(f"Creator QR check failed: {e}")
            return False, str(e), cookies

    def exchange_creator_session_from_user_cookies(self, user_cookies):
        """Exchange PC cookies for Creator cookies."""
        merged_cookies = self.generate_init_cookies()
        merged_cookies.update(user_cookies)

        api = '/api/cas/customer/web/service-ticket'
        data = {"service": "https://creator.xiaohongshu.com", "source": "official", "type": "tgt"}

        headers = self._get_request_headers()
        headers['content-type'] = 'application/json'
        headers.update(generate_xsc(merged_cookies['a1'], api, data, method='POST'))

        data_str = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
        try:
            resp = self._make_request(
                'POST',
                self.customer_url + api,
                headers=headers,
                cookies=merged_cookies,
                data=data_str.encode('utf-8'),
                timeout=REQUEST_TIMEOUT
            )
            for key, value in resp.cookies.items():
                merged_cookies[key] = value

            res = resp.json()
            if not res.get('success'):
                return False, res.get('msg', '同步 Creator 账号失败'), {'cookies': merged_cookies}
            
            return True, '成功', {'cookies': merged_cookies}
        except Exception as e:
            return False, str(e), {'cookies': merged_cookies}

    def get_user_info(self, cookies):
        api = '/api/galaxy/user/info'
        headers = self._get_request_headers()
        headers.update(generate_xsc(cookies['a1'], api, method='GET'))

        try:
            resp = self._make_request(
                'GET',
                self.creator_url + api,
                headers=headers,
                cookies=cookies,
                timeout=REQUEST_TIMEOUT
            )
            for key, value in resp.cookies.items():
                cookies[key] = value
            res = resp.json()
            return res.get('success', False), res.get('data', {}), cookies
        except Exception as e:
            return False, {}, cookies

    def send_phone_code(self, phone, cookies, zone='86'):
        api = '/api/cas/customer/web/verify-code'
        data = {"service": "https://creator.xiaohongshu.com", "phone": phone, "zone": zone}

        headers = self._get_request_headers()
        headers['content-type'] = 'application/json'
        headers.update(generate_xsc(cookies['a1'], api, data, method='POST'))

        data_str = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
        resp = self._make_request(
            'POST',
            self.customer_url + api,
            headers=headers,
            cookies=cookies,
            data=data_str.encode('utf-8'),
            timeout=REQUEST_TIMEOUT
        )
        res = resp.json()
        return res.get('success', False), res.get('msg', ''), res

    def login_by_phone(self, phone, code, cookies, zone='86'):
        api = '/api/cas/customer/web/service-ticket'
        data = {
            "service": "https://creator.xiaohongshu.com",
            "zone": zone,
            "phone": phone,
            "verify_code": code,
            "source": "",
            "type": "phoneVerifyCode"
        }

        headers = self._get_request_headers()
        headers['content-type'] = 'application/json'
        headers.update(generate_xsc(cookies['a1'], api, data, method='POST'))

        data_str = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
        resp = self._make_request(
            'POST',
            self.customer_url + api,
            headers=headers,
            cookies=cookies,
            data=data_str.encode('utf-8'),
            timeout=REQUEST_TIMEOUT
        )
        for key, value in resp.cookies.items():
            cookies[key] = value

        res = resp.json()
        return res.get('success', False), res.get('msg', ''), {'cookies': cookies, 'res_json': res}
