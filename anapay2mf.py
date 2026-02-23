def login_mf():
    """login moneyforward (Hyper-Robust Chrome Edition)"""
    email = os.getenv("EMAIL")
    password = os.getenv("PASSWORD")

    if not email:
        logging.error("!!! EMAIL IS EMPTY !!! Check GitHub Secrets.")
        raise ValueError("EMAIL secret is not set")
    
    logging.info(f"Login to moneyfoward with: {email[:3]}***")
    
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.keys import Keys
    import time
    import helium

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    
    helium.start_chrome("https://id.moneyforward.com/", options=options)
    driver = helium.get_driver()
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    try:
        wait = WebDriverWait(driver, 30)

        # --- 0. ログインページへ確実に誘導（前回成功した処理） ---
        logging.info("Step 0: Handling English/Intro page...")
        time.sleep(5)
        entry_selectors = [
            "//a[contains(text(), 'Sign in')]",
            "//a[contains(text(), 'ログイン')]",
            "//a[contains(@href, 'sign_in')]",
            "//button[contains(text(), 'Sign in')]"
        ]
        for selector in entry_selectors:
            try:
                elements = driver.find_elements(By.XPATH, selector)
                if elements:
                    logging.info(f"Entry button found! Clicking: {selector}")
                    driver.execute_script("arguments[0].click();", elements[0])
                    time.sleep(5)
                    break
            except:
                continue

        # --- 1. メールアドレス入力（前回成功した処理） ---
        logging.info("Step 1: Entering email...")
        email_selector = "input[name='mfid_user[email]'], input[type='email'], #mfid_user_email"
        email_input = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, email_selector)))
        
        email_input.click()
        email_input.send_keys(Keys.CONTROL + "a")
        email_input.send_keys(Keys.BACKSPACE)
        time.sleep(1)
        
        for char in email:
            email_input.send_keys(char)
            time.sleep(0.1)

        # --- 1.5 次へ（超堅牢版：Enterキーで突破） ---
        logging.info("Step 1.5: Clicking Next (Hyper-Robust)...")
        time.sleep(1)
        try:
            # 第一の矢：Enterキーを送信（これが一番確実）
            email_input.send_keys(Keys.ENTER)
            logging.info("Pressed ENTER key on email field.")
        except:
            # 第二の矢：考えられる全てのボタンタグを狙い撃ち
            next_selectors = [
                "//input[@type='submit']",
                "//button[@type='submit']",
                "//button[contains(text(), 'Sign in')]",
                "//input[@value='Sign in']"
            ]
            for sel in next_selectors:
                try:
                    btn = driver.find_element(By.XPATH, sel)
                    driver.execute_script("arguments[0].click();", btn)
                    logging.info(f"Clicked Next using: {sel}")
                    break
                except:
                    continue

        # --- 2. パスワード入力 ---
        logging.info("Step 2: Entering password...")
        time.sleep(5) # 画面切り替えを長めに待つ
        pass_input = wait.until(EC.visibility_of_element_located((By.NAME, "mfid_user[password]")))
        for char in password:
            pass_input.send_keys(char)
            time.sleep(0.1)

        # --- 2.5 ログイン実行（超堅牢版：Enterキーで突破） ---
        logging.info("Step 2.5: Clicking final Login button (Hyper-Robust)...")
        time.sleep(1)
        try:
            # ここでもEnterキーで確実に送信
            pass_input.send_keys(Keys.ENTER)
            logging.info("Pressed ENTER key on password field.")
        except:
            submit_selectors = [
                "//input[@type='submit']",
                "//button[@type='submit']",
                "//button[contains(text(), 'Sign in')]",
                "//input[@value='Sign in']"
            ]
            for sel in submit_selectors:
                try:
                    btn = driver.find_element(By.XPATH, sel)
                    driver.execute_script("arguments[0].click();", btn)
                    logging.info(f"Clicked Login using: {sel}")
                    break
                except:
                    continue

        # --- 3. ログイン完了待ち ---
        logging.info("Step 3: Waiting for authentication...")
        for i in range(10):
            time.sleep(10)
            logging.info(f"Checking URL... ({i+1}/10): {driver.current_url}")
            if "id.moneyforward.com" not in driver.current_url:
                logging.info("Successfully left ID page!")
                break

        driver.get("https://moneyforward.com/")
        time.sleep(10)

    except Exception as e:
        logging.error(f"Login failed: {str(e)}")
        driver.save_screenshot("login_error.png")
        raise e
