import pytest
from nexis.core.parser import parse
from nexis.core.permissions import Permissions
from nexis.core.results import Preview, Request, Risk
from nexis.storage.repository import validate_workflow
from nexis.utils.validation import url, name, executable


@pytest.mark.parametrize(
    "text,expected",
    [
        ("open notepad", Request("open", "notepad")),
        ("  FIND report.pdf  ", Request("find", "report.pdf")),
        ("clear history", Request("clear_history")),
        ("help", Request("help")),
        ("run start coding", Request("run", "start coding")),
    ],
)
def test_parse(text, expected):
    assert parse(text) == expected


@pytest.mark.parametrize("text", ["", " ", "x" * 1001, "open\nnotepad", "open\tnotepad"])
def test_bad_input(text):
    with pytest.raises(ValueError):
        parse(text)


@pytest.mark.parametrize("value", ["https://example.com", "https://example.com:443/a?q=b#x"])
def test_https(value):
    assert url(value) == value


@pytest.mark.parametrize(
    "value",
    [
        "javascript:alert(1)",
        "file:///C:/data",
        "data:text/a,b",
        "http://example.com",
        "https://user:pass@example.com",
        "https://",
        "https://x:bad",
        "https://x\\@evil",
        "https://x y",
        "https://x:",
    ],
)
def test_bad_url(value):
    with pytest.raises(ValueError):
        url(value)


def test_permissions_default_deny():
    policy = Permissions()
    for risk in (Risk.MEDIUM, Risk.HIGH):
        assert not policy.authorise(Preview("x", "target", "effect", risk))
    assert policy.authorise(Preview("x", "target", "effect", Risk.LOW))
    policy.confirm_low = True
    assert not policy.authorise(Preview("x", "target", "effect", Risk.LOW))
    assert Permissions(lambda p: True).authorise(Preview("x", "target", "effect", Risk.HIGH))


@pytest.mark.parametrize(
    "steps",
    [
        [],
        ["help"],
        ["run nested"],
        ["powershell x"],
        ["clear history"],
        ["open x"] * 31,
        "open notepad",
        [123],
    ],
)
def test_workflow_validation(steps):
    with pytest.raises(ValueError):
        validate_workflow(steps)


def test_safe_names():
    assert name(" Intro ") == "intro"
    for value in ("x & calc", "../a", "x|y", "x;calc", "x$(y)"):
        with pytest.raises(ValueError):
            name(value)


def test_executable_validation(tmp_path):
    for filename in ("cmd.exe", "powershell.exe", "node.exe", "bad.bat", "bad.py"):
        path = tmp_path / filename
        path.touch()
        with pytest.raises(ValueError):
            executable(str(path))
    path = tmp_path / "editor.exe"
    path.touch()
    assert executable(str(path)) == path.resolve()
    with pytest.raises(ValueError):
        executable("relative.exe")
