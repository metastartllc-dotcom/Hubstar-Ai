from typer.testing import CliRunner

from app.cli.main import app


runner = CliRunner()


def test_interactive_command_starts_and_exits_with_15():
    result = runner.invoke(app, ["interactive"], input="15\n")

    assert result.exit_code == 0
    assert "Үндсэн цэс" in result.stdout
    assert "Програмаас гарч байна" in result.stdout


def test_default_command_starts_and_exits_with_15():
    result = runner.invoke(app, input="15\n")

    assert result.exit_code == 0
    assert "Үндсэн цэс" in result.stdout
    assert "Програмаас гарч байна" in result.stdout
