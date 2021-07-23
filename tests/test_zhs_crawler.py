import datetime

import pytest
from click.testing import CliRunner
from dateutil.relativedelta import relativedelta  # type: ignore

from zhs.zhs import cli


@pytest.fixture(name="today")
def fixture_today() -> str:
    """Fixture for today's date in %Y-%m-%d format"""
    return datetime.date.today().strftime("%Y-%m-%d")


@pytest.fixture(name="runner")
def fixture_runner() -> CliRunner:
    """Fixture for the Cli runner"""
    return CliRunner()


def test_zhs(today: str, runner: CliRunner) -> None:
    """End-to-end test for Zhs"""

    result = runner.invoke(
        cli, f"--date {today} --time-window 8 20 --receiver-email hi@bye.com"
    )
    assert result.exit_code == 0


def test_email_callback(today: str, runner: CliRunner) -> None:
    """Test if the email callback triggers an error"""

    result = runner.invoke(
        cli, f"--date {today} --time-window 8 20 --receiver-email fail",
    )
    assert result.exit_code == 2
    assert "Error: Invalid value for '--receiver-email'" in result.stdout


def test_time_window_callback(today: str, runner: CliRunner) -> None:
    """Test if the time window callback triggers an error"""

    result = runner.invoke(
        cli, f"--date {today} --time-window 21 20 --receiver-email hi@bye.com",
    )
    assert result.exit_code == 2
    assert "Error: Invalid value for '--time-window'" in result.stdout


def test_date_past_callback(runner: CliRunner) -> None:
    """Test if the date callback triggers an error if the date lies in the past"""

    result = runner.invoke(
        cli, "--date 2021-07-22 --time-window 21 20 --receiver-email hi@bye.com",
    )
    assert result.exit_code == 2
    assert "Error: Invalid value for '--date'" in result.stdout


def test_date_future_callback(runner: CliRunner):
    """Test if the email callback triggers an error if the date is too far in the future"""

    future = (datetime.date.today() + relativedelta(days=9)).strftime("%Y-%m-%d")

    result = runner.invoke(
        cli, f"--date {future} --time-window 21 20 --receiver-email hi@bye.com",
    )
    assert result.exit_code == 2
    assert "Error: Invalid value for '--date'" in result.stdout
