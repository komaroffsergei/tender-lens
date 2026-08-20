from __future__ import annotations

import argparse

import pytest

from tender_lens.cli import _limit_value, build_parser


def test_cli_limit_accepts_supported_range():
    assert _limit_value("1") == 1
    assert _limit_value("1000") == 1000
    args = build_parser().parse_args(["create-api-key", "--name", "demo", "--limit", "25"])
    assert args.limit == 25


@pytest.mark.parametrize("raw", ["0", "1001", "not-a-number"])
def test_cli_limit_rejects_invalid_values(raw):
    with pytest.raises(argparse.ArgumentTypeError):
        _limit_value(raw)
