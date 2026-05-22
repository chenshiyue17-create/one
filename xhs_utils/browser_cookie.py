import browser_cookie3
import requests
from loguru import logger

def get_xhs_cookies_from_browser(browser_type='chrome'):
    """
    Attempt to retrieve XHS cookies from the specified local browser.
    Supported types: 'chrome', 'edge', 'firefox', 'safari' (macOS only)
    """
    browsers_to_try = [browser_type]
    if browser_type == 'auto' or not browser_type:
        browsers_to_try = ['chrome', 'edge', 'firefox', 'safari']
    
    last_error = "No xiaohongshu.com cookies found in any browser."
    
    for b in browsers_to_try:
        try:
            cj = None
            if b == 'chrome':
                cj = browser_cookie3.chrome(domain_name='xiaohongshu.com')
            elif b == 'edge':
                cj = browser_cookie3.edge(domain_name='xiaohongshu.com')
            elif b == 'firefox':
                cj = browser_cookie3.firefox(domain_name='xiaohongshu.com')
            elif b == 'safari':
                cj = browser_cookie3.safari(domain_name='xiaohongshu.com')
            
            if cj:
                cookies_dict = requests.utils.dict_from_cookiejar(cj)
                if cookies_dict and 'a1' in cookies_dict:
                    # Successfully found valid cookies
                    cookies_str = '; '.join([f"{k}={v}" for k, v in cookies_dict.items()])
                    logger.info(f"Successfully retrieved cookies from {b}")
                    return cookies_str, None
                elif cookies_dict:
                    last_error = f"Found cookies in {b} but 'a1' is missing. Please log in again."
        except Exception as e:
            error_msg = str(e)
            if "Operation not permitted" in error_msg:
                logger.warning(f"Permission denied for {b}. Skipping...")
                last_error = f"无法访问 {b} 的数据。请尝试在系统设置中为终端授予‘完全磁盘访问权限’，或改用 Chrome 浏览器。"
            else:
                logger.debug(f"Failed to get cookies from {b}: {e}")
                last_error = error_msg
                
    return None, last_error

if __name__ == "__main__":
    ck, err = get_xhs_cookies_from_browser('chrome')
    if ck:
        print(f"Found cookies: {ck[:50]}...")
    else:
        print(f"Error: {err}")
