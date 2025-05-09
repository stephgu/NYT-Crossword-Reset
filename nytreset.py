import argparse
import os
import time
import requests
import configparser
from retrying import retry
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
config_file_path = 'settings.ini'


def load_or_prompt_settings():
    config = configparser.ConfigParser()
    config.read(config_file_path)

    if 'Credentials' not in config.sections():
        config.add_section('Credentials')

    for setting in ['cookie', 'username', 'password']:
        if setting not in config['Credentials'] or not config['Credentials'][setting]:
            value = input(f"Enter NYTimes {setting}: ")
            config.set('Credentials', setting, value)

    with open(config_file_path, 'w') as configfile:
        config.write(configfile)

    return config['Credentials']

def retry_if_exception(exception):
    return isinstance(exception, Exception)

@retry(retry_on_exception=retry_if_exception, stop_max_attempt_number=3, wait_fixed=2000)
def get_auth_cookie(username, password):
    login_resp = requests.post(
        "https://myaccount.nytimes.com/svc/ios/v2/login",
        data={"login": username, "password": password},
        headers={"User-Agent": "Crosswords/20191213190708 CFNetwork/1128.0.1 Darwin/19.6.0", "client_id": "ios.crosswords"},
    )
    login_resp.raise_for_status()
    for cookie in login_resp.json()["data"]["cookies"]:
        if cookie["name"] == "NYT-S":
            return {"name": "NYT-S", "value": cookie["cipheredValue"], "domain": ".nytimes.com"}
    raise RuntimeError("Could not get authentication cookie from login.")

def init_browser(headless=True, cookie_value=None):
    print("Initializing the browser...")
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument('--headless')
    browser = webdriver.Chrome(options=options)
    browser.get("https://www.nytimes.com/crosswords/archive")
    if cookie_value:
        print("Adding provided cookie to browser session...")
        browser.add_cookie({'name': "NYT-S", 'value': cookie_value, 'domain': '.nytimes.com'})
    return browser

def save_date_to_text(date, text_file_path):
    print(f"Saving date {date} to text file...")
    formatted_date = date.replace('-', '/')
    with open(text_file_path, 'a') as file:
        file.write(formatted_date + '\n')

@retry(retry_on_exception=retry_if_exception, stop_max_attempt_number=3, wait_fixed=2000)
def find_incomplete_puzzles(driver, text_file_path, start_date, end_date):
    # Clear the file first before writing dates to it. 
    with open(text_file_path, 'r+') as file:
        file.truncate(0)
    month_urls_to_check = []
    start_month, year = start_date.split("/")
    start_month = int(start_month)
    end_month = int(end_date.split("/")[0])

    for i in range(end_month - start_month + 1):
        month = start_month + i
        month_urls_to_check.append(f"{year}/{month}")

    driver.get("https://www.nytimes.com/crosswords/archive/mini")
    WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, ".calendar")))
    back_button_selector = ".archive_prev"
    for month_url in month_urls_to_check:
        try:
            print(f'Searching for completed puzzles for {month_url}...')
            driver.get(f"https://www.nytimes.com/crosswords/archive/mini/{month_url}")
            WebDriverWait(driver, 5).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, ".calendar")))
            WebDriverWait(driver, 2).until(
                EC.visibility_of_all_elements_located((By.CSS_SELECTOR, ".puzzleInfo")))
            WebDriverWait(driver, 3).until(EC.visibility_of_element_located((By.XPATH, "//a[.//span[text()='Review']]")))
            incomplete_puzzles = driver.find_elements(By.XPATH, "//a[.//span[text()='Review']]")
            for puzzle in incomplete_puzzles:
                href = puzzle.get_attribute("href")
                puzzle_date = "-".join(href.split("/")[-3:])
                save_date_to_text(puzzle_date, text_file_path)
        except Exception as e:
            print(f"Error while gathering incomplete puzzles: {e}")
            break

@retry(retry_on_exception=retry_if_exception, stop_max_attempt_number=3, wait_fixed=2000)
def clear_puzzle_for_date(driver, date):
    print(f"Clearing puzzle for date: {date}...")
    puzzle_url = f"https://www.nytimes.com/crosswords/game/mini/{date}"
    driver.get(puzzle_url)
    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Play']"))).click()
    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Reset']"))).click()
    print("Puzzle cleared.")

def clear_puzzles_from_text(driver, text_file_path):
    if not os.path.exists(text_file_path):
        print("Text file does not exist.")
        return
    print("Clearing puzzles from text file...")
    with open(text_file_path, 'r') as file:
        dates = file.read().splitlines()
    for date in dates:
        try:
            clear_puzzle_for_date(driver, date)
        except Exception as e:
            print(f"Error clearing puzzle for {date}: {e}")


def main(cookie_value, headless, start_date, end_date, mode):
    print("Script started. Preparing to clear NYT Crossword puzzles...")
    text_file_path = "incomplete_puzzles.txt"
    driver = init_browser(headless, cookie_value)

    if mode in ["scan", "both"]:
        find_incomplete_puzzles(driver, text_file_path, start_date, end_date)
    if mode in ["fix", "both"]:
        clear_puzzles_from_text(driver, text_file_path)

    print("Operation completed.")
    driver.quit()


if __name__ == "__main__":
    credentials = load_or_prompt_settings()

    parser = argparse.ArgumentParser(description="NYTimes Crossword Puzzle Automation")
    parser.add_argument('--headless', nargs='?', const=True, default=None, help="Run browser in headless mode (yes/no).")
    parser.add_argument('--start_date', type=str, default=None, help="Start date. Format must be MM/YYYY. The end and start date have to be in the same year.")
    parser.add_argument('--end_date', type=str, default=None, help="End date. Format must be MM/YYYY. The end and start date have to be in the same year.")
    parser.add_argument('--mode', choices=['scan', 'fix', 'both'], default=None, help="Operation mode: scan for incomplete puzzles, fix incomplete puzzles, or both.")
    args = parser.parse_args()

    # Prompt for headless if not provided
    if args.headless is None:
        headless_input = input("Run in headless mode? (y/n): ").strip().lower()
        args.headless = headless_input == 'y'

    if args.mode is None:
        args.mode = input("Enter operation mode (scan, fix, both): ").strip().lower()
        while args.mode not in ['scan', 'fix', 'both']:
            print("Invalid mode. Please choose from 'scan', 'fix', or 'both'.")
            args.mode = input("Enter operation mode (scan, fix, both): ").strip().lower()

    cookie_value = credentials.get('cookie')
    username = credentials.get('username')
    password = credentials.get('password')

    if not cookie_value and username and password:
        auth_cookie = get_auth_cookie(username, password)
        cookie_value = auth_cookie['value']

    main(cookie_value, args.headless, args.start_date, args.end_date, args.mode)