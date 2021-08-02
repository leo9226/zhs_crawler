"""Crawl available tennis courts from ZHS (Munich) and send an email to a provided email address"""
import datetime
import os
import smtplib
import time
import urllib.parse
from collections import defaultdict
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Dict
from typing import List
from typing import Optional

import pandas as pd  # type: ignore
import requests  # type: ignore
from bs4 import BeautifulSoup  # type: ignore
from dateutil.relativedelta import relativedelta  # type: ignore
from dotenv import load_dotenv  # type: ignore
from loguru import logger

from src.zhs_crawler.book_court import BookTennisCourt


# TODO: Put proper headers to requests.get
# TODO: switch to requests.Session -> class variable
# TODO: clean-up & refactoring

# TODO: telegram bot / discord bot?


class Zhs:
    """Class to perform all steps - from building the URLs to sending the email"""

    # pylint: disable=too-many-instance-attributes
    def __init__(
        self,
        date: str,
        start_hour: int,
        end_hour: int,
        receiver_email: str,
        interval: int,
        book_court: bool,
    ) -> None:
        load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env")

        self.date = date
        self.start_hour = start_hour
        self.end_hour = end_hour
        self.receiver_email = receiver_email
        self.interval = interval
        self.book_court = book_court
        self.base_url = (
            "https://ssl.forumedia.eu/zhs-courtbuchung.de"
            "/reservations.php?action=showReservations&type_id=1&"
        )
        self.sender_email = os.environ["SENDER_EMAIL"]
        self.sender_password = os.environ["SENDER_PASSWORD"]
        self.book_tennis_court = BookTennisCourt()
        logger.info(f"{self.__class__.__qualname__} successfully instantiated")

    def build_url(self, page: int) -> str:
        """
        Put together the base_url and the query parameters
        :param page: page number
        :return: the full URL
        """

        url_parameters = {
            "date": self.date,
            "page": page,
        }

        return self.base_url + urllib.parse.urlencode(query=url_parameters)

    @staticmethod
    def crawl_page(url: str) -> BeautifulSoup:
        """
        Fetches the HTML from the website
        :param url: the URL to be crawled
        :return: HTML page content
        """

        page = requests.get(url=url)
        return BeautifulSoup(markup=page.content, features="html.parser")

    @staticmethod
    def filter_all_available_courts(page_content: BeautifulSoup) -> Dict[str, List]:
        """
        Filter the HTML content for all available courts
        :param page_content: HTML content of the page
        :return: Dictionary with available court times per court
        """

        all_courts = page_content.find(id="main-content-tabs").find(
            name="table", attrs={"class": "allarea"}
        )

        court_periods = all_courts.find_all(
            name="table", attrs={"class": "areaPeriods"}
        )

        result: Dict = defaultdict(dict)

        for court in court_periods:
            court_number = court.find("th").text
            available_hours = court.find_all(name="td", attrs={"class": "avaliable"})

            times_for_court = []
            for available in available_hours:
                start_end_time = available.find(name="a").text
                times_for_court.append(start_end_time)
            result[court_number] = times_for_court

        # remove courts with no available time slots
        filtered = {k: v for k, v in result.items() if len(v) > 0}

        fixed_times = {}

        for court, times in filtered.items():
            _, court_int = court.split(" ")
            tmp_times = []
            for i, slot in enumerate(times):
                if i % 2 == 0:
                    start, _ = slot.split(" - ")
                    end = (
                        datetime.datetime.strptime(start, "%H:%M")
                        + relativedelta(hours=1)
                    ).strftime("%H:%M")
                    tmp_times.extend([start + " - " + end])
            fixed_times[court_int] = tmp_times
        return fixed_times

    def filter_relevant_courts(self, available_courts: Dict) -> pd.DataFrame:
        """
        Create a Dataframe from the available courts data &
        filter only the relevant ones, i.e. matching the hours where the players want to play
        :param available_courts: Dataframe with all available courts
        :return: Dataframe with only the relevant courts
        """

        construct_df = []
        for court_num, times in available_courts.items():
            for start_end_time in times:
                start, end = start_end_time.split(" - ")
                construct_df.append([self.date, court_num, start, end])

        courts_df = pd.DataFrame(
            data=construct_df, columns=["date", "court", "start_time", "end_time"]
        )
        courts_df["court"] = courts_df["court"].astype(int)

        return courts_df.loc[
            (
                courts_df["start_time"].apply(lambda x: x[:2]).astype(int)
                >= self.start_hour
            )
            & (
                courts_df["end_time"].apply(lambda x: x[:2]).astype(int)
                <= self.end_hour
            )
        ]

    def compose_message(
        self, booked_court: Optional[pd.DataFrame], relevant_courts: pd.DataFrame
    ) -> str:
        """
        Compose the E-Mail
        :param booked_court: The booked court
        :param relevant_courts: Dataframe with all relevant tennis courts
        :return: the composed message, i.e. the body of the email
        """

        mail_content = "Dear Roger,\n\n"
        if booked_court:
            mail_content += (
                f"Court number {booked_court['court'].iloc[0]} was booked on "
                f"{booked_court['date'].iloc[0]} at {booked_court['start_time'].iloc[0]}!\n\n\n"
            )
        mail_content += (
            f"Here is an overview of all available courts on "
            f"{self.date} between {self.start_hour}:00 and {self.end_hour}:00:\n\n"
        )
        for court, start, end in zip(
            relevant_courts["court"],
            relevant_courts["start_time"],
            relevant_courts["end_time"],
        ):
            mail_content += f"  -> Court {court}: {start} - {end}\n"

        return mail_content.rstrip("\n")

    def send_email(
        self, booked_court: Optional[pd.DataFrame], relevant_courts: pd.DataFrame
    ) -> None:
        """
        Send the composed message to the player's provided email address
        :param booked_court: The booked court
        :param relevant_courts: All relevant courts
        :return:
        """

        message = MIMEMultipart()
        message["From"] = self.sender_email
        message["To"] = self.receiver_email
        message["Subject"] = "Court Alert! Court's Booked!"

        mail_content = self.compose_message(
            booked_court=booked_court, relevant_courts=relevant_courts
        )

        # The body and the attachments for the mail
        message.attach(payload=MIMEText(mail_content, "plain"))

        # Create SMTP session for sending the mail
        session = smtplib.SMTP(host="smtp.gmail.com", port=587)
        session.starttls()  # enable security
        session.login(user=self.sender_email, password=self.sender_password)

        text = message.as_string()
        session.sendmail(
            from_addr=self.sender_email, to_addrs=self.receiver_email, msg=text
        )
        session.quit()

        logger.info(f"Message successfully sent to {self.receiver_email}!")

    def run_court_search(self) -> bool:
        """
        Put everything together. Loop through Zhs Pages 2, 3 and 4 and do the following for each
        1) build the url
        2) crawl the page
        3) filter all available courts
        4) filter only the relevant courts according to the hours
        5) compose the email message
        6) if there are available courts, send an email
        :return:
        """

        all_relevant_courts = pd.DataFrame()
        for page in range(2, 5):
            logger.info(f"Crawling page number {page}...")
            url = self.build_url(page=page)
            content = self.crawl_page(url=url)
            available_courts = self.filter_all_available_courts(page_content=content)
            relevant_courts = self.filter_relevant_courts(
                available_courts=available_courts
            )
            all_relevant_courts = pd.concat([all_relevant_courts, relevant_courts])
        logger.info(f"{all_relevant_courts.shape[0]} relevant courts were found!")

        if all_relevant_courts.shape[0]:
            booked_court = None
            if self.book_court:
                booked_court = all_relevant_courts.sample(1)
                self.book_tennis_court.book_tennis_court(
                    date=booked_court["date"].iloc[0],
                    court_number=booked_court["court"].iloc[0],
                    start_time=booked_court["start_time"].iloc[0],
                )
            self.send_email(
                booked_court=booked_court, relevant_courts=all_relevant_courts
            )
            return True

        logger.info(
            f"No courts found. Zhs will be crawled again in {self.interval} seconds ..."
        )
        return False

    def crawl_zhs(self) -> None:
        """Crawl Zhs until a court is found"""

        found_a_court = False
        while not found_a_court:
            found_a_court = self.run_court_search()
            if not found_a_court:
                time.sleep(self.interval)
