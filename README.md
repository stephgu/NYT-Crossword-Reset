## Overview
Small CLI script that automates the process of identifying and resetting incomplete New York Times Crossword puzzles in a user's history. It aims to ensure that the user's history only reflects completed puzzles. The script operates in three modes: scanning for incomplete puzzles (`scan`), fixing incomplete puzzles (`fix`), and performing both operations (`both`).

## Prerequisites
- **Selenium WebDriver**: Specifically, the Chrome WebDriver is required for this script. Download it from [Chrome WebDriver](https://sites.google.com/a/chromium.org/chromedriver/) and ensure it's accessible in your system's PATH.
- **Python Packages**: The script requires several Python packages listed in `requirements.txt`.

## Configuration
Before running the script, configure your New York Times credentials in the `settings.ini` file. Otherwise, you'll be asked to provide them when first running.
- `cookie`: Your NYTimes cookie if available. (Optional)
- `username`: Your NYTimes username.
- `password`: Your NYTimes password.

If the `cookie` is not provided, the script will attempt to authenticate using the `username` and `password` and save the resulting `cookie`.

## Options
The following options can be provided as command-line arguments or you'll be prompted while running.
- `--headless`: Run the browser in headless mode. Use `y` for headless mode or `n` for normal mode.
- `--months`: Specify the number of months to go back for scanning incomplete puzzles. Required if mode is `scan` or `both`.
- `--mode`: Specify the operation mode. Choose `scan` to find incomplete puzzles, `fix` to reset incomplete puzzles, or `both` to perform both operations.