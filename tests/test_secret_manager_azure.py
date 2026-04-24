import types

import pytest

from pdsno.security.secret_manager import ExternalKMSAdapter


class _FakeSecret:
    def __init__(self, value: str):
        self.value = value


class _FakeAzureClient:
    def __init__(self):
        self.store = {}
        self.set_calls = []
        self.get_calls = []

    def set_secret(self, name, value, tags=None):
        self.set_calls.append((name, value, tags))
        self.store[name] = (value, tags)

    def get_secret(self, name):
        self.get_calls.append(name)
        if name not in self.store:
            raise KeyError(name)
        value, _tags = self.store[name]
        return _FakeSecret(value)


def test_azure_secret_name_passthrough_for_safe_ids():
    assert ExternalKMSAdapter._azure_secret_name("safe-Name-123") == "safe-Name-123"


def test_azure_secret_name_hashes_unsafe_ids():
    name1 = ExternalKMSAdapter._azure_secret_name("device/switch-01_password")
    name2 = ExternalKMSAdapter._azure_secret_name("device/switch-01_password")
    assert name1 == name2
    assert name1.startswith("pdsno-")
    assert "-" in name1


def test_azure_store_and_retrieve_mocked_client(monkeypatch):
    adapter = ExternalKMSAdapter("azure", {"vault_url": "https://example.vault.azure.net"})
    fake_client = _FakeAzureClient()

    monkeypatch.setattr(adapter, "_get_azure_client", lambda: fake_client)

    assert adapter.store_secret("device_switch-01_password", "s3cr3t") is True

    value = adapter.retrieve_secret("device_switch-01_password")
    assert value == "s3cr3t"


def test_azure_missing_dependency_or_config_returns_failure(monkeypatch):
    adapter = ExternalKMSAdapter("azure", {})

    def _boom():
        raise RuntimeError("Azure SDK missing")

    monkeypatch.setattr(adapter, "_get_azure_client", _boom)

    assert adapter.store_secret("x", "y") is False
    assert adapter.retrieve_secret("x") is None
