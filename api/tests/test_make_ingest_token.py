"""scripts/make_ingest_token.py (mounted at /scripts in the api container)."""

import hashlib
import importlib.util
import re

spec = importlib.util.spec_from_file_location("make_ingest_token", "/scripts/make_ingest_token.py")
make_ingest_token = importlib.util.module_from_spec(spec)
spec.loader.exec_module(make_ingest_token)


def test_a_token_is_ing_plus_256_random_bits():
    token = make_ingest_token.make_token()
    # token_urlsafe(32) is 43 characters from the URL-safe base64 alphabet.
    assert re.fullmatch(r"ing_[A-Za-z0-9_-]{43}", token)
    assert make_ingest_token.make_token() != token


def test_the_hash_is_the_sha256_hex_the_server_expects():
    token = "ing_fake-canary-token"
    assert make_ingest_token.token_hash(token) == hashlib.sha256(token.encode()).hexdigest()
    assert re.fullmatch(r"[0-9a-f]{64}", make_ingest_token.token_hash(token))


def test_it_writes_nothing_to_disk(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    make_ingest_token.main()
    assert list(tmp_path.iterdir()) == []
    assert "INGEST_TOKEN_SHA256=" in capsys.readouterr().out
