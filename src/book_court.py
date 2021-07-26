import os
import time
from pathlib import Path

import selenium  # type: ignore
from dotenv import load_dotenv
from loguru import logger
from selenium import webdriver


# selenium needs to find the right court-page
# //*[@id="pager-block"]/div[X]/div[2]/a/strong
COURT_PAGE_MAPPER = {
    2: 2,
    3: 2,
    4: 2,
    5: 2,
    6: 3,
    7: 3,
    8: 3,
    9: 3,
    10: 3,
    11: 3,
    12: 3,
    13: 3,
    14: 4,
    15: 4,
    16: 4,
    17: 4,
}


# necessary for Buchung button as it does not have an id/name
# '/html/body/div[5]/article/div/div[4]/div/table/tbody/tr/td[X]/form/div/input'
MAP_COURT_TO_XPATH = {
    2: 1,
    3: 2,
    4: 3,
    5: 4,
    6: 1,
    7: 2,
    8: 3,
    9: 4,
    10: 5,
    11: 6,
    12: 7,
    13: 8,
    14: 1,
    15: 2,
    16: 3,
    17: 4,
}


class BookTennisCourt:
    """Book a free court with Selenium"""

    def __init__(self) -> None:
        load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

        self.login_name = os.environ["LOGIN_NAME"]
        self.login_password = os.environ["LOGIN_PASSWORD"]
        logger.info(f"{self.__class__.__qualname__} successfully instantiated")

    def book_tennis_court(self, date: str, court_number: int, start_time: str) -> None:
        """Book a court with Selenium"""

        # instantiate driver and open page
        driver = webdriver.Firefox()
        driver.get(
            url="https://ssl.forumedia.eu/zhs-courtbuchung.de/reservations.php?"
            f"action=showRevervations&type_id=1&date={date}&page=1"
        )

        # login
        driver.find_element_by_id("login_block")
        driver.find_element_by_id("login_block").click()
        driver.find_element_by_id("login").send_keys(self.login_name)
        driver.find_element_by_id("password").send_keys(self.login_password)
        driver.find_element_by_xpath(
            '//*[@id="respond1"]/form/table/tbody/tr/td[1]/input'
        ).click()

        # wait for cookie pop-up and click OK
        driver.implicitly_wait(5)
        driver.find_element_by_xpath('//*[@id="button_apply"]').click()

        time.sleep(3)

        # go to the right page
        driver.find_element_by_xpath(
            f'//*[@id="pager-block"]/div[{COURT_PAGE_MAPPER[court_number]}]/div[2]/a/strong'
        ).click()

        # click the correct checkbox
        driver.find_element_by_id(f"order_el_{court_number}_{start_time}").click()

        # click on "Buchung" button (confirm booking)
        driver.find_element_by_xpath(
            f"/html/body/div[5]/article/div/div[4]/div/table/tbody/"
            f"tr/td[{MAP_COURT_TO_XPATH[court_number]}]/form/div/input"
        ).click()

        # final click on "Bestätigen" (additional confirmation
        driver.find_element_by_xpath(
            "/html/body/div[5]/article/div/form/div/input"
        ).click()

        # close the driver and all browser windows
        driver.quit()

        logger.info(f"Booked court {court_number} on {date} for 1 hour starting at {start_time}!")


if __name__ == "__main__":
    s = BookTennisCourt()
    s.book_tennis_court(date="2021-07-27", court_number=3, start_time="08:30")
