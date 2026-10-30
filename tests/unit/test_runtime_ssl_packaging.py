import runpy
from pathlib import Path

import pytest

helpers = runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts/runtime_ssl.py"))
resources = helpers["ssl_runtime_data"]
SIDECAR = helpers["SIDECAR"]


def test_standard_interpreter_does_not_invent_a_policy_file(tmp_path):
    source = tmp_path / "ssl.py"
    source.write_text("# ordinary CPython SSL module")
    assert resources(source) == []


def test_required_distrust_resource_cannot_be_silently_omitted(tmp_path):
    source = tmp_path / "ssl.py"
    source.write_text("required_file = '" + SIDECAR + "'")
    with pytest.raises(RuntimeError, match="not bypassed"):
        resources(source)


def test_public_policy_resource_is_returned_unchanged(tmp_path):
    source = tmp_path / "ssl.py"
    source.write_text("# managed interpreter")
    resource = tmp_path / SIDECAR
    content = b"-----BEGIN TRUSTED CERTIFICATE-----\nPUBLIC-POLICY-FIXTURE\n-----END TRUSTED CERTIFICATE-----\n"
    resource.write_bytes(content)
    assert resources(source) == [(str(resource.resolve()), ".")]
    assert resource.read_bytes() == content


@pytest.mark.parametrize("content", [b"-----BEGIN PRIVATE KEY-----\nDo not package", b"invalid policy resource"])
def test_policy_resource_never_packages_private_keys_or_invalid_data(tmp_path, content):
    source = tmp_path / "ssl.py"
    source.write_text("# managed interpreter")
    (tmp_path / SIDECAR).write_bytes(content)
    with pytest.raises(RuntimeError, match="packaging stopped"):
        resources(source)
