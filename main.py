from flask import Flask, request, jsonify
from selenium import webdriver
from datetime import datetime
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
import json
import time
import threading
import os
import logging
import uuid
import re

app = Flask(__name__)
drivers = {}



LOG_FILE = "responses_log.jsonl"
log_lock = threading.Lock()

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s', handlers=[
    logging.FileHandler(LOG_FILE, encoding="utf-8"),
    logging.StreamHandler()
])

def write_log(entry: dict):
    logging.info(entry)
    entry["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = json.dumps(entry, ensure_ascii=False)
    with log_lock:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")

def create_chrome_driver(headless: bool = False):
    options = Options()
    if headless:
       #options.add_argument("--headless=new")
        options.add_argument("--enable-gpu")
        options.add_argument("--use-gl=swiftshader")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--disable-gpu-compositing")
        options.add_argument("--disable-accelerated-2d-canvas")
        options.add_argument("--disable-accelerated-video-decode")

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins")
    options.add_argument("--window-size=1280,1024")
    options.add_experimental_option("excludeSwitches", ["enable-logging", "enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    service = Service("chromedriver.exe")
    driver = webdriver.Chrome(service=service, options=options)
    write_log({"action": "create_driver", "status": "success"})
    return driver

def load_cookies_from_file(driver, file_path="cookies.json"):
    if not os.path.exists(file_path):
        write_log({"action": "load_cookies", "status": "warning", "message": "Cookie file not found"})
        return False

    with open(file_path, "r", encoding="utf-8") as f:
        cookies = json.load(f)

    success_count = 0
    fail_count = 0

    for cookie in cookies:
        cookie.pop("sameSite", None)
        cookie.pop("hostOnly", None)
        cookie.pop("storeId", None)
        if "name" in cookie and "value" in cookie:
            try:
                driver.add_cookie(cookie)
                success_count += 1
            except Exception as e:
                fail_count += 1
                write_log({"action": "load_cookies", "status": "error", "cookie": cookie.get("name"), "error": str(e)})

    try:
        driver.refresh()
    except Exception as e:
        write_log({"action": "load_cookies", "status": "error", "message": "driver.refresh failed", "error": str(e)})
        return False

    write_log({"action": "load_cookies", "status": "success", "added": success_count, "failed": fail_count})
    return True


def normalize_version(v: str):
    if not v:
        return "Fast"
    v = v.strip()
    if v in ('Thinking', '3'):
        return "Thinking with 3 pro"
    return "Fast"

def normalize_cards(c: str):
    if not c:
        return None
    valid_cards = ["Create image", "Write", "Build", "Deep Research","Create Video", "Learn"]
    return c if c in valid_cards else None

def switch_version(driver, version: str):
    try:
        wait = WebDriverWait(driver, 20)
        modal = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//button[contains(@class,'input-area-switch') and .//span[normalize-space()='Fast']]")
        ))
        modal.click()
        if version == "Fast":
            fast_button = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//button[@data-test-id='bard-mode-option-fast']")))
            fast_button.click()
        else:
            pro_button = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//button[@data-test-id='bard-mode-option-thinkingwith3pro']")))
            pro_button.click()
        write_log({"action": "switch_version", "status": "success", "version": version})
        return True
    except Exception as e:
        write_log({"action": "switch_version", "status": "error", "version": version, "error": str(e)})
        return False

def select_card(driver, card: str):
    xpath_map = {
        "Create image": "//button[contains(@class, 'card-legacy') and contains(@aria-label, 'Create Image')]",
        "ٌWrite":"//button[contains(@class, 'card-legacy') and contains(@aria-label, 'Write')]",
        "Build": "//button[contains(@class, 'card-legacy') and contains(@aria-label, 'Build')]",
        "Deep Research ": "//button[contains(@class, 'card-legacy') and contains(@aria-label, 'Deep Research')]",
        "Create Video": "//button[contains(@class, 'card-legacy') and contains(@aria-label, 'Create Video')]",
        "Learn": "//button[contains(@class, 'card-legacy') and contains(@aria-label, 'Learn')]",
    }
    if card not in xpath_map:
        write_log({"action": "select_card", "status": "warning", "message": f"Card '{card}' not recognized"})
        return False
    try:
        element = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, xpath_map[card]))
        )
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
        time.sleep(0.5)
        element.click()
        write_log({"action": "select_card", "status": "success", "card": card})
        return True
    except Exception as e:
        write_log({"action": "select_card", "status": "error", "card": card, "error": str(e)})
        return False

def check_forbidden_page(driver, url: str):
    page_source = driver.page_source.lower()
    if "error 403" in page_source or "forbidden" in page_source:
        write_log({"action": "check_forbidden", "status": "error", "url": url})
        driver.quit()
        raise SystemExit("Stopped due to 403 Forbidden error")
    else:
        write_log({"action": "check_forbidden", "status": "success", "url": url})

def start_browser(headless=False):
    driver = create_chrome_driver(headless=headless)
    url = "https://gemini.google.com/app"
    driver.get(url)
    check_forbidden_page(driver, url)
    write_log({"action": "start_browser", "status": "success"})
    return driver


def parse_cookie_table(cookie_str):
    cookies = []
    lines = cookie_str.strip().split("\n")

    for line in lines:
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        name = parts[0]
        value = parts[1]
        domain = parts[2]
        path = parts[3]
        expires = parts[4]

       
        try:
            expiry_ts = int(datetime.strptime(expires, "%Y-%m-%dT%H:%M:%S.%fZ").timestamp())
        except:
            expiry_ts = None

        cookies.append({
            "name": name,
            "value": value,
            "domain": domain,
            "path": path,
            "expiry": expiry_ts,
            "secure": parts[6].strip() == "✓",
            "httpOnly": False, 
            "sameSite": parts[9].strip() if len(parts) > 9 and parts[9].strip() else "Lax",
        })

    return cookies




@app.route("/update_cookies", methods=["POST"])
def update_cookies_table():
    if request.content_type == "application/json":
        data = request.get_json()
        cookies = data.get("cookies")
    else:
        cookies = request.get_data(as_text=True)

    if not cookies:
        return jsonify({"error": "cookies table text required"}), 400

    parsed = parse_cookie_table(cookies)

    try:   
       with open("cookies.json", "w", encoding="utf-8") as f:
        json.dump(parsed, f, indent=4, ensure_ascii=False)
        
        write_log({"action": "update_cookies", "status": "written"})
        return jsonify({"action":"write_new_cookies","status": "written"})
    
    except Exception as e:
        
        write_log({"action": "update_cookies", "status": "error", "error": str(e)})
        return jsonify({"error": str(e)}), 500
        
    

    



@app.route("/login_with_cookies", methods=["POST"])
def login_with_cookies():
    data = request.get_json()
    version = normalize_version(data.get("version"))
    card = normalize_cards(data.get("card"))
    session_id = uuid.uuid4().hex
    driver = None
    try:
        driver = start_browser(headless=False)
        drivers[session_id] = driver
        driver.get("https://gemini.google.com/app")
        write_log({"action": "open_website", "status": "success", "session_id": session_id})
        load_cookies_from_file(driver)
        switch_version(driver, version)
        select_card(driver, card)
        write_log({"action": "login_with_cookies", "status": "success", "session_id": session_id})
        return jsonify({"status": "ok", "session_id": session_id})
    except Exception as e:
        write_log({"action": "login_with_cookies", "status": "error", "session_id": session_id, "error": str(e)})
        if driver:
            try:
                driver.quit()
            except:
                pass
            drivers.pop(session_id, None)
        return jsonify({"status": "error", "message": str(e), "session_id": session_id}), 500
    
  
  
  
def check_driver_alive(driver):
    try:
        driver.title
        return True
    except:
        return False
    
    
    
def send_prompt_text(ask_gemini_box , text):
    lines =text.split("\n")
    for i , line in enumerate(lines):
        ask_gemini_box.send_keys(line)
        if i < len(line) -1 :
            ask_gemini_box.send_keys(Keys.SHIFT , Keys.ENTER)
            
    ask_gemini_box.send_keys(Keys.ENTER)        
            
              

@app.route("/send_prompt", methods=["POST"])
def send_prompt():
    try:
        data = request.get_json()
        prompt = data.get("prompt")
        session_id = data.get("session_id")
        write_log({"action": "send_prompt_request", "session_id": session_id, "prompt": prompt})

        if not prompt:
            write_log({"action": "send_prompt", "status": "warning", "session_id": session_id, "message": "Prompt missing"})
            return jsonify({"error": "Prompt is required"}), 400

        driver = drivers.get(session_id)
        
        if not check_driver_alive(driver):
            write_log({"action": "send_prompt", "status": "error", "session_id": session_id, "message": "Driver not active"})
            return jsonify({"error": "driver not active"}), 404

        wait = WebDriverWait(driver, 20)

        ask_gemini_box = wait.until(EC.visibility_of_element_located(
            (By.XPATH, '/html/body/chat-app/main/side-navigation-v2/bard-sidenav-container/bard-sidenav-content/div[2]/div/div[2]/chat-window/div/input-container/div/input-area-v2/div/div/div[1]/div/div/rich-textarea/div[1]/p')
        ))
        ask_gemini_box.click()
        ask_gemini_box.clear()
        send_prompt_text(ask_gemini_box, prompt)
        time.sleep(1)

        write_log({"action": "send_prompt", "status": "sent", "session_id": session_id})

        WAIT_ELEMENT = "//button[@data-test-id='copy-button' and @mattooltip='Copy response']"

         
        while True:
            if not check_driver_alive(driver):
                return jsonify({"status": "error", "message": "driver closed manually", "session_id": session_id}), 410
            try:
                wait_elem = driver.find_element(By.XPATH, WAIT_ELEMENT)
                if wait_elem.is_displayed():
                    break
            except:
                pass
            time.sleep(5)

       
        text_part = driver.find_elements(By.XPATH, ".//p | .//h1 | .//h2 | .//h3 | .//h4")

        texts = []
        for el in text_part:
            try:
                text = el.text.strip()
                if text:
                    texts.append(text)
            except:
                continue

       
        def extract_codes(driver):
            codes = []
            wait = WebDriverWait(driver, 10)

            for _ in range(5): 
                try:
                    wait.until(EC.presence_of_all_elements_located((By.TAG_NAME, "pre")))
                    
                    blocks = driver.find_elements(By.TAG_NAME, "pre")

                    for block in blocks:
                        try:
                            code = block.text.strip()
                            if code and code not in codes:
                                codes.append(code)
                        except StaleElementReferenceException:
                            continue

                    return codes

                except:
                    time.sleep(1)

            return codes

        write_log({"action": "send_prompt", "status": "response_received", "session_id": session_id})

        return jsonify({
            'status': 'ok',
            "full_response": texts,
            "code_blocks": extract_codes(driver)
        })

    except Exception as e:
        write_log({"action": "send_prompt", "status": "error", "session_id": session_id, "error": str(e)})
        return jsonify({"error": str(e)}), 500


@app.route("/close_driver", methods=['POST'])
def close_driver():
    data = request.get_json()
    session_id = data.get("session_id")
    driver = drivers.get(session_id)
    if not driver:
        write_log({"action": "close_driver", "status": "error", "session_id": session_id, "message": "Driver not active"})
        return jsonify({"error": "driver not active"}), 404
    try:
        driver.quit()
        drivers.pop(session_id, None)
        write_log({"action": "close_driver", "status": "success", "session_id": session_id})
        return jsonify({"status": "closed", "session_id": session_id})
    except Exception as e:
        write_log({"action": "close_driver", "status": "error", "session_id": session_id, "error": str(e)})
        return jsonify({"error": str(e)}), 500

@app.route('/active_driver', methods=['GET'])
def active_driver():
    active = []
    for session_id, driver in drivers.items():
        try:
            _ = driver.title
            active.append({"session_id": session_id, "status": "active"})
        except:
            active.append({"session_id": session_id, "status": "dead"})
    write_log({"action": "active_driver", "status": "checked", "drivers": active})
    return jsonify({"active_count": len(active), "drivers": active})

if __name__ == "__main__":
    write_log({"action": "server_start", "status": "running", "message": "Server is up and ready"})
    logging.info("Server is running...")
    app.run(host="127.0.0.1", port=8085, debug=False, use_reloader=False)
