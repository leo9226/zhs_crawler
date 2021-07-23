"""Crawl available tennis courts from ZHS (Munich) and send an email to a provided email address"""
import datetime
import os
import re
import smtplib
import urllib.parse
from collections import defaultdict
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Dict
from typing import List
from typing import Optional
from typing import Pattern
from typing import Tuple

import click
import pandas as pd
import requests
from bs4 import BeautifulSoup  # type: ignore
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv
from loguru import logger


# TODO: tests; structure (dirs);


class Zhs:
    """Class to perform all steps - from building the URLs to sending the email"""

    def __init__(
        self,
        date: str,
        start_hour: int,
        end_hour: int,
        receiver_email: str,
    ) -> None:
        load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

        self.date = date
        self.start_hour = start_hour
        self.end_hour = end_hour
        self.receiver_email = receiver_email
        self.base_url = (
            "https://ssl.forumedia.eu/zhs-courtbuchung.de"
            "/reservations.php?action=showReservations&type_id=1&"
        )
        self.sender_email = os.environ["SENDER_EMAIL"]
        self.sender_password = os.environ["SENDER_PASSWORD"]
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
        # real_date = all_courts.find(name="input", attrs={"name": "date"}).get("value")

        court_periods = all_courts.find_all(
            name="table", attrs={"class": "areaPeriods"}
        )

        result: Dict = defaultdict(dict)

        for court in court_periods:
            court_number = court.find("th").text
            available_hours = court.find_all(name="td", attrs={"class": "avaliable"})

            times_for_court = []
            for available in available_hours:
                time = available.find(name="a").text
                times_for_court.append(time)
            result[court_number] = times_for_court

        # remove courts with no available time slots
        return {k: v for k, v in result.items() if len(v) > 0}

    def filter_relevant_courts(self, available_courts: Dict) -> pd.DataFrame:
        """
        Create a Dataframe from the available courts data &
        filter only the relevant ones, i.e. matching the hours where the players want to play
        :param available_courts: Dataframe with all available courts
        :return: Dataframe with only the relevant courts
        """

        construct_df = []
        for court_num, times in available_courts.items():
            for time in times:
                start, end = time.split(" - ")
                construct_df.append(
                    [
                        self.date,
                        court_num,
                        start,
                        end,
                    ]
                )

        courts_df = pd.DataFrame(
            data=construct_df, columns=["date", "court", "start_time", "end_time"]
        )

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

    def compose_message(self, relevant_courts: pd.DataFrame) -> str:
        """
        Compose the E-Mail
        :param relevant_courts: Dataframe with all relevant tennis courts
        :return: the composed message, i.e. the body of the email
        """

        mail_content = ""
        mail_content += (
            f"On {self.date}, between {self.start_hour}:00 and {self.end_hour}:00, "
            "the following courts are available:\n"
        )
        for court, start, end in zip(
            relevant_courts["court"],
            relevant_courts["start_time"],
            relevant_courts["end_time"],
        ):
            mail_content += f"  -> {court}: {start} - {end}\n"

        return mail_content.rstrip("\n")

    def send_email(self, mail_content: str) -> None:
        """
        Send the composed message to the player's provided email address
        :param mail_content: mail conent, i.e. the body of the email
        :return:
        """

        message = MIMEMultipart()
        message["From"] = self.sender_email
        message["To"] = self.receiver_email
        message["Subject"] = "Free Court Alert!"

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

    def run(self) -> None:
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
        logger.info(f"{all_relevant_courts.shape[0] // 2} relevant courts were found!")
        mail_content = self.compose_message(relevant_courts=all_relevant_courts)
        if all_relevant_courts.shape[0]:
            self.send_email(mail_content=mail_content)


# pylint: disable=unused-argument
def verify_start_end(
    ctx: click.core.Context, param: click.core.Option, value: Tuple[int, int]
) -> Optional[Tuple[int, int]]:
    """Verify if start_hour is smaller than end_hour"""

    start_hour, end_hour = value
    if start_hour < end_hour:
        logger.info(f"Time Window {value} is valid")
        return value
    raise click.BadParameter(f"{start_hour} must be smaller than {end_hour}!")


# pylint: disable=unused-argument
def verify_date(
    ctx: click.core.Context, param: click.core.Option, value: str
) -> Optional[str]:
    """
    Verify that
    1) the date format is of yyyy-mm-dd
    2) the date is valid
    3) the date is not in the past
    4) the date is at max 8 days in the future
    """

    try:
        input_date = datetime.datetime.strptime(value, "%Y-%m-%d")
        today = datetime.datetime.today()
        if input_date < today:
            raise click.BadParameter(
                f"Input date is before today. {value} was provided"
            )
        max_date = today + relativedelta(days=8)
        if input_date > max_date:
            raise click.BadParameter(
                f"Input date is too far in the future. {value} was provided"
            )
        logger.info(f"Date {value} is valid")
        return value
    except ValueError as value_error:
        raise click.BadParameter(
            f"Incorrect date or date format, must be YYYY-MM-DD! {value} was provided."
        ) from value_error


# pylint: disable=unused-argument
def verify_email(
    ctx: click.core.Context, param: click.core.Option, value: str,
) -> Optional[str]:
    """Verify if email is valid"""

    # http://www.regular-expressions.info/email.html
    email_pattern: Pattern = re.compile(
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        flags=re.IGNORECASE,
    )
    if re.match(pattern=email_pattern, string=value):
        logger.info(f"Email {value} is valid")
        return value
    raise click.BadParameter(f"Invalid email! {value} was provided.")


@click.command()
@click.option(
    "--date",
    type=str,
    help=(
        "The date where you want to find a court. Format: yyyy-mm-dd. "
        "e.g. `--date 2021-07-23` for the 23rd of July in 2021."
        "Date must not be in the past. Date must not be further than 8 days in the future."
    ),
    callback=verify_date,  # type: ignore
)
@click.option(
    "--time-window",
    type=click.Tuple(
        [click.IntRange(8, 20, clamp=True), click.IntRange(8, 20, clamp=True)]
    ),
    callback=verify_start_end,  # type: ignore
    help=(
        "At what time do you want to play? First value: start hour, second value: end hour. "
        "E.g. `--time-window 17 20`, if you want to play between 17:00 and 20:00."
    ),
)
@click.option(
    "--receiver-email",
    required=True,
    type=str,
    callback=verify_email,  # type: ignore
    help="Your email address. E.g. `--email dalai.lama@tibet.cn`",
)
def cli(date: str, time_window: Tuple[int, int], receiver_email: str):
    """Build Zhs class from CL inputs and execute it"""

    start_hour, end_hour = time_window
    zhs = Zhs(
        date=date,
        start_hour=start_hour,
        end_hour=end_hour,
        receiver_email=receiver_email,
    )
    zhs.run()


if __name__ == "__main__":
    # pylint: disable=no-value-for-parameter
    cli()
