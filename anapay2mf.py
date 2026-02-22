"""
ANA Payの情報をメールから取得してスプレッドシートに書き込む

それからスプレッドシートの情報を元に、Money Fowardに情報を書き込む
"""

import base64
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import gspread
import helium
from dateutil import parser
from dotenv import load_dotenv
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

import quickstart

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
]

# Google Spreadsheet ID and Sheet name
SHEET_ID = "1fVCe4-zFnQVv0rRtJPt8TO9DsL3maFxjohYsAvZHclc"
SHEET_NAME = "ANAPay"

MF_URL = "https://moneyforward.com/cf"

format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
logging.basicConfig(format=format, level=logging.INFO)

load_dotenv()


@dataclass
class ANAPay:
    """ANA Pay information"""

    email_date: datetime = None
    date_of_use: datetime = None
    amount: int = 0
    store: str = ""

    def values(self) -> tuple[str, str, str, str]:
        """return tuple of values for spreadsheet"""
        return self.email_date_str, self.date_of_use_str, self.amount, self.store

    @property
    def email_date_str(self) -> str:
        return f"{self.email_date:%Y-%m-%d %H:%M:%S}"

    @property
    def date_of_use_str(self) -> str:
        return f"{self.date_of_use:%Y-%m-%d %H:%M:%S}"


def get_mail_info(res: dict) -> ANAPay | None:
    """
    1件のメールからANA Payの利用情報を取得して返す
    """
    ana_pay = ANAPay()
    for header in res["payload"]["headers"]:
        if header["name"] == "Date":
            date_str = header["value"].replace(" +0900 (JST)", "")
            ana_pay.email_date = parser.parse(date_str)

    # 本文から日時、金額、店舗を取り出す
    # ご利用日時：2023-06-28 22:46:19
    # ご利用金額：44,308円
    # ご利用店舗：SMOKEBEERFACTORY OTSUKATE
    data = res["payload"]["body"]["data"]
    body = base64.urlsafe_b64decode(data).decode()
    for line in body.splitlines():
        if line.startswith("ご利用"):
            key, value = line.split("：")
            if key == "ご利用日時":
                ana_pay.date_of_use = parser.parse(value)
            elif key == "ご利用金額":
                ana_pay.amount = int(value.replace(",", "").replace("円", ""))
            elif key == "ご利用店舗":
                ana_pay.store = value
    return ana_pay


def get_anapay_info(after: str) -> list[ANAPay]:
    """
    gmailからANA Payの利用履歴を取得する
    """
    ana_pay_list = []

    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    service = build("gmail", "v1", credentials=creds)

    # https://developers.google.com/gmail/api/reference/rest/v1/users.messages/list
    query = f"from:payinfo@121.ana.co.jp subject:ご利用のお知らせ after:{after}"
    results = service.users().messages().list(userId="me", q=query).execute()
    messages = results.get("messages", [])
    for message in reversed(messages):
        # https://developers.google.com/gmail/api/reference/rest/v1/users.messages/get
        res = service.users().messages().get(userId="me", id=message["id"]).execute()
        ana_pay = get_mail_info(res)
        if ana_pay:
            ana_pay_list.append(ana_pay)
    return ana_pay_list

    after = "2023/06/28"


def get_last_email_date(records: list[dict[str, str]]):
    """get last email date for gmail search"""
    after = "2023/06/28"
    if records:
        last_email_date = parser.parse(records[-1]["email_date"])
        after = f"{last_email_date:%Y/%m/%d}"
    return after


def gmail2spredsheet(worksheet):
    """gmailからANA Payの利用履歴を取得しスプレッドシートに書き込む"""
    # get all records from spreadsheet
    records = worksheet.get_all_records()
    logging.info("Records in spreadsheet: %d", len(records))

    # get last day from records
    after = get_last_email_date(records)
    logging.info("Last day on spreadsheet: %s", after)
    email_date_set = set(parser.parse(r["email_date"]) for r in records)

    # get ANA Pay email from Gamil
    ana_pay_list = get_anapay_info(after)
    logging.info("ANA Pay emails: %d", len(ana_pay_list))

    # add ANA Pay record to spreadsheet
    count = 0
    for ana_pay in ana_pay_list:
        # メールの日付が存在しない場合はレコードを追加
        if ana_pay.email_date not in email_date_set:
            worksheet.append_row(ana_pay.values(), value_input_option="USER_ENTERED")
            count += 1
            logging.info("Record added to spreadsheet: %s", ana_pay.values())
    logging.info("Records added to spreadsheet: %d", count)


def login_mf():
    """login moneyforward (Two-step navigation version)"""
    email = os.getenv("EMAIL")
    password = os.getenv("PASSWORD")

    if not email:
        logging.error("!!! EMAIL IS EMPTY !!! Check GitHub Secrets.")
        raise ValueError("EMAIL secret is not set")
    
    logging.info(f"Login to moneyfoward with: {email[:3]}***")
    
    from selenium.webdriver.firefox.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    import time
    
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--width=1920")
    options.add_argument("--height=1080")
    # 言語を日本語に固定しつつ、ブラウザのふりをする
    options.set_preference("intl.accept_languages", "ja-JP, ja")
    options.set_preference("general.useragent.override", "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0")
    
    import helium
    helium.start_firefox("https://id.moneyforward.com/", options=options)
    driver = helium.get_driver()
    
    try:
        wait = WebDriverWait(driver, 20)
        time.sleep(5)

        # 【追加】紹介ページにいる場合、ログイン画面へ遷移するボタンを押す
        logging.info("Checking if we need to click 'Sign in' button...")
        try:
            # ログインボタン（リンク）を探す。hrefにsign_inが含まれるものを優先
            signin_btn_selectors = [
                (By.XPATH, "//a[contains(@href, '/sign_in/email')]"),
                (By.XPATH, "//a[contains(text(), 'ログイン') or contains(text(), 'Sign in')]"),
                (By.CSS_SELECTOR, "a.button")
            ]
            
            target_btn = None
            for by, sel in signin_btn_selectors:
                elements = driver.find_elements(by, sel)
                if elements and elements[0].is_displayed():
                    target_btn = elements[0]
                    break
            
            if target_btn:
                logging.info("Found Sign-in button. Clicking it...")
                target_btn.click()
                time.sleep(5)
        except Exception as e:
            logging.info(f"No initial sign-in button needed or error: {e}")

        # 1. メールアドレス入力
        logging.info("Step 1: Entering email...")
        email_selector = "input[name='mfid_user[email]'], input[type='email']"
        email_input = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, email_selector)))
        email_input.clear()
        email_input.send_keys(email)
        
        # 次へボタン
        submit_selector = "button[type='submit'], input[type='submit']"
        driver.find_element(By.CSS_SELECTOR, submit_selector).click()
        
        # 2. パスワード入力
        logging.info("Step 2: Entering password...")
        time.sleep(5)
        pass_selector = "input[name='mfid_user[password]'], input[type='password']"
        pass_input = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, pass_selector)))
        pass_input.send_keys(password)
        
        # ログイン完了ボタン
        driver.find_element(By.CSS_SELECTOR, submit_selector).click()
        
        # 3. ログイン成功確認
        logging.info("Step 3: Verifying login...")
        time.sleep(10)
        logging.info(f"Final Title: {driver.title}")
        if "マネーフォワード" in driver.title or "家計簿" in driver.title or "Dashboard" in driver.title:
            logging.info("Login Success!")
        else:
            logging.warning("Login might have failed or still on ID page.")

    except Exception as e:
        logging.error(f"Login failed: {str(e)}")
        driver.save_screenshot("login_error.png")
        logging.error(f"Current URL: {driver.current_url}")
        raise e

def add_mf_record(dt: datetime, amount: int, store: str, store_info: dict | None):
    """
    add record to moneyfoward
    """

    # https://selenium-python-helium.readthedocs.io/en/latest/api.html
    helium.click("手入力")
    # breakpoint()
    helium.write(f"{dt:%Y/%m/%d}", into="日付")
    helium.click("日付")

    helium.write(amount, into="支出金額")
    asset = helium.find_all(helium.ComboBox())[0]
    for option in asset.options:
        if option.startswith("ANA Pay"):
            helium.select(asset, option)

    if store_info:
        category = helium.find_all(helium.Link("未分類"))[0]
        l_category = helium.find_all(helium.S("#js-large-category-selected"))[0]
        helium.click(l_category)
        helium.click(store_info["大項目"])

        m_category = helium.find_all(helium.S("#js-middle-category-selected"))[0]
        helium.click(m_category)
        helium.click(store_info["中項目"])

        helium.write(store_info["店名"], into="内容をご入力下さい(任意)")
    else:
        helium.write(store, into="内容をご入力下さい(任意)")

    helium.click("保存する")
    logging.info(f"Record added to moneyforward: {dt:%Y/%m/%d}, {amount}, {store}")

    helium.wait_until(helium.Button("続けて入力する").exists)
    helium.click("続けて入力する")


def spreadsheet2mf(worksheet, store_dict: dict[str, dict[str, str]]) -> None:
    """スプレッドシートからmoneyfowardに書き込む"""

    records = worksheet.get_all_records()

    # すべてmoneyforwardに登録済みならなにもしない
    if all(record["mf"] == "done" for record in records):
        return

    login_mf()  # login to moneyfoward
    added = 0
    for count, record in enumerate(records):
        if record["mf"] != "done":
            date_of_use = parser.parse(record["date_of_use"])
            amount = int(record["amount"])
            store = record["store"]
            add_mf_record(date_of_use, amount, store, store_dict.get(store))

            # update spread sheets for "done" message
            worksheet.update_cell(count + 2, 5, "done")
            added += 1
    helium.kill_browser()

    logging.info(f"Records added to moneyforward: {added}")


def main():
    try:
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        service = build('gmail', 'v1', credentials=creds)
        results = service.users().labels().list(userId='me').execute()
    except RefreshError:
        # recreate token
        Path("token.json").unlink(missing_ok=True)
        quickstart.main()

    gc = gspread.oauth(
        credentials_filename="credentials.json", authorized_user_filename="token.json"
    )
    sheet = gc.open_by_key(SHEET_ID)
    anapay_sheet = sheet.worksheet("ANAPay")
    store_sheet = sheet.worksheet("ANAPayStore")
    store_dict = {store["store"]: store for store in store_sheet.get_all_records()}

    gmail2spredsheet(anapay_sheet)
    spreadsheet2mf(anapay_sheet, store_dict)


if __name__ == "__main__":
    main()
