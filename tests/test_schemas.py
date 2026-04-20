"""ActionInput schema 校验测试"""
import pytest
from pydantic import ValidationError
from backend.app.schemas import ActionInput


class TestActionInput:
    def test_normal_content(self):
        a = ActionInput(content="向北走")
        assert a.content == "向北走"

    def test_strips_whitespace(self):
        a = ActionInput(content="  打开箱子  ")
        assert a.content == "打开箱子"

    def test_collapses_excessive_whitespace(self):
        a = ActionInput(content="a" + " " * 10 + "b")
        assert "          " not in a.content

    def test_rejects_empty(self):
        with pytest.raises(ValidationError):
            ActionInput(content="")

    def test_rejects_whitespace_only(self):
        with pytest.raises(ValidationError):
            ActionInput(content="     ")

    def test_rejects_too_long(self):
        with pytest.raises(ValidationError):
            ActionInput(content="x" * 2001)
