import datetime
import re
from typing import Optional
from typing import Pattern
from typing import Tuple

import click
import pandas as pd  # type: ignore
from dateutil.relativedelta import relativedelta  # type: ignore
from loguru import logger

from src.zhs_crawler.zhs import Zhs


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
        input_date = pd.Timestamp(datetime.datetime.strptime(value, "%Y-%m-%d"))
        today = pd.Timestamp(datetime.date.today())
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
    ctx: click.core.Context,
    param: click.core.Option,
    value: str,
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
        [click.IntRange(8, 20, clamp=False), click.IntRange(8, 20, clamp=False)]
    ),
    callback=verify_start_end,  # type: ignore
    help=(
        "At what time do you want to play? First value: start hour, second value: end hour. "
        "Must be between 8 and 20 (boundaries included)!"
        "E.g. `--time-window 17 20`, if you want to play between 17:00 and 20:00."
    ),
)
@click.option(
    "--receiver-email",
    required=True,
    type=str,
    callback=verify_email,  # type: ignore
    help="Your email address. E.g. `--email dalai.lama@tibet.com`",
)
@click.option(
    "--book-court",
    default=True,
    type=bool,
    help="Automatically book a court? Default is True. E.g. `--book-court True`",
)
@click.option(
    "--interval",
    default=60,
    type=click.IntRange(min=5),
    help="""Interval in seconds in which Zhs will be crawled if no free courts are found.
    Minimum is 5 seconds. Default is 60 seconds. E.g. `--interval 60`""",
)
def cli(
    date: str,
    time_window: Tuple[int, int],
    receiver_email: str,
    interval: int,
    book_court: bool,
):
    """Build Zhs class from CL inputs and execute it"""

    start_hour, end_hour = time_window
    zhs = Zhs(
        date=date,
        start_hour=start_hour,
        end_hour=end_hour,
        receiver_email=receiver_email,
        interval=interval,
        book_court=book_court,
    )
    zhs.crawl_zhs()


if __name__ == "__main__":
    # pylint: disable=no-value-for-parameter
    cli()
