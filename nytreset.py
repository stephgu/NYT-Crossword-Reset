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
    seen_dates = set()
    if os.path.exists(text_file_path):
        with open(text_file_path, 'r') as file:
            seen_dates.update(file.read().splitlines())
    formatted_date = date.replace('-', '/')
    if formatted_date not in seen_dates:
        with open(text_file_path, 'a') as file:
            file.write(formatted_date + '\n')

@retry(retry_on_exception=retry_if_exception, stop_max_attempt_number=3, wait_fixed=2000)
def find_incomplete_puzzles(driver, text_file_path, months):
    print("Searching for incomplete puzzles...")
    driver.get("https://www.nytimes.com/crosswords/archive")
    WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, ".calendar")))
    back_button_selector = ".archive_prev"
    for _ in range(months):
        try:
            WebDriverWait(driver, 2).until(
                EC.visibility_of_all_elements_located((By.CSS_SELECTOR, ".puzzleInfo")))
            incomplete_puzzles = driver.find_elements(By.XPATH, "//a[.//span[text()='Resume']]")
            for puzzle in incomplete_puzzles:
                href = puzzle.get_attribute("href")
                puzzle_date = "-".join(href.split("/")[-3:])
                save_date_to_text(puzzle_date, text_file_path)
            print("Moving to the previous month...")
            if driver.find_elements(By.CSS_SELECTOR, back_button_selector):
                time.sleep(2)
                driver.find_element(By.CSS_SELECTOR, back_button_selector).click()
                WebDriverWait(driver, 30).until(EC.visibility_of_element_located(
                    (By.CSS_SELECTOR, back_button_selector)))
        except Exception as e:
            print(f"Error while gathering incomplete puzzles: {e}")
            break

@retry(retry_on_exception=retry_if_exception, stop_max_attempt_number=3, wait_fixed=2000)
def clear_puzzle_for_date(driver, date):
    print(f"Clearing puzzle for date: {date}...")
    puzzle_url = f"https://www.nytimes.com/crosswords/game/daily/{date}"
    driver.get(puzzle_url)
    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Play']"))).click()
    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='clear']"))).click()
    time.sleep(2)
    WebDriverWait(driver, 10).until(EC.element_to_be_clickable(
        (By.XPATH, "//button[contains(text(), 'Puzzle & Timer')]"))).click()
    time.sleep(2)
    WebDriverWait(driver, 10).until(EC.element_to_be_clickable(
        (By.XPATH, "//button[@aria-label='Start over']"))).click()
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


def main(cookie_value, headless, months, mode):
    print("Script started. Preparing to clear NYT Crossword puzzles...")
    text_file_path = "incomplete_puzzles.txt"
    driver = init_browser(headless, cookie_value)

    if mode in ["scan", "both"]:
        find_incomplete_puzzles(driver, text_file_path, months)
    if mode in ["fix", "both"]:
        clear_puzzles_from_text(driver, text_file_path)

    print("Operation completed.")
    driver.quit()


if __name__ == "__main__":
    credentials = load_or_prompt_settings()

    parser = argparse.ArgumentParser(description="NYTimes Crossword Puzzle Automation")
    parser.add_argument('--headless', nargs='?', const=True, default=None, help="Run browser in headless mode (yes/no).")
    parser.add_argument('--months', type=int, default=None, help="Number of months to go back for puzzles. Required if mode is 'scan' or 'both'.")
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

    if args.mode in ['scan', 'both'] and args.months is None:
        while True:
            months_input = input("Enter the number of months to go back for puzzles: ").strip()
            try:
                args.months = int(months_input)
                break
            except ValueError:
                print("Please enter a valid integer for the number of months.")

    cookie_value = credentials.get('cookie')
    username = credentials.get('username')
    password = credentials.get('password')

    if not cookie_value and username and password:
        auth_cookie = get_auth_cookie(username, password)
        cookie_value = auth_cookie['value']

    main(cookie_value, args.headless, args.months, args.mode)