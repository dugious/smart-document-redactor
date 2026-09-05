"""Optional browser smoke: pip install playwright; uses installed Edge."""
from pathlib import Path
import subprocess
import time
import urllib.request
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    server = subprocess.Popen([str(ROOT/'.venv/Scripts/python.exe'), '-m', 'streamlit', 'run', 'app.py',
                               '--server.headless=true', '--server.port=8518'], cwd=ROOT,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen('http://127.0.0.1:8518/_stcore/health', timeout=1).close()
                break
            except OSError:
                time.sleep(.5)
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='msedge', headless=True)
            page = browser.new_page(viewport={'width': 1440, 'height': 1100}, device_scale_factor=1)
            page.goto('http://127.0.0.1:8518')
            page.get_by_text('Bắt đầu với tài liệu mẫu', exact=True).wait_for()
            target = ROOT/'docs/images'; target.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(target/'workspace-empty.png'), full_page=True)
            page.locator('input[type=file]').set_input_files(str(ROOT/'examples/synthetic-input.txt'))
            page.get_by_text('02 / Duyệt kết quả', exact=True).wait_for()
            page.get_by_text('Tôi hiểu giới hạn kiểm tra, bao gồm các cảnh báo phía trên.', exact=True).click()
            assert page.get_by_role('checkbox').is_checked()
            page.get_by_role('button', name='Áp dụng các lựa chọn', exact=True).click()
            download = page.get_by_role('button', name='Tải file đã xử lý', exact=True)
            download.wait_for()
            with page.expect_download() as event:
                download.click()
            contents = Path(event.value.path()).read_text(encoding='utf-8')
            assert 'demo@example.com' not in contents and '[EMAIL]' in contents
            page.screenshot(path=str(target/'workspace-result.png'), full_page=True)
            page.set_viewport_size({'width': 390, 'height': 844})
            page.screenshot(path=str(target/'workspace-mobile.png'), full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
            browser.close()
            print('Edge browser TXT upload/apply/download + mobile overflow: PASS')
    finally:
        server.terminate(); server.wait(timeout=15)


if __name__ == '__main__':
    main()
