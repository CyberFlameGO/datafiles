# pylint: disable=unused-variable,protected-access

from dataclasses import dataclass
from pathlib import Path

import pytest

from datafiles import managers


@dataclass
class MyModel:
    foobar: int


class MyField:
    @classmethod
    def to_data(cls, value):
        return value


def describe_instance_manager():
    @pytest.fixture
    def manager():
        return managers.InstanceManager(
            instance=MyModel(foobar=42), pattern=None, fields={}
        )

    def describe_path():
        def is_none_when_no_pattern(expect, manager):
            expect(manager.path) == None

        def is_absolute_based_on_the_file(expect, manager):
            manager._pattern = '../../tmp/sample.yml'
            root = Path(__file__).parents[2]
            expect(manager.path) == root / 'tmp' / 'sample.yml'

    def describe_text():
        def is_blank_when_no_fields(expect, manager):
            expect(manager.text) == ""

        def is_yaml_by_default(expect, manager):
            manager.fields = {'foobar': MyField}
            expect(manager.text) == "foobar: 42\n"

        def with_custom_format(expect, manager):
            manager._pattern = '_.json'
            manager.fields = {'foobar': MyField}
            expect(manager.text) == '{"foobar": 42}'

        def with_unknown_format(expect, manager):
            manager._pattern = '_.xyz'
            with expect.raises(ValueError):
                manager.text

    def describe_load():
        def it_requires_path(expect, manager):
            with expect.raises(RuntimeError):
                manager.load()

    def describe_save():
        def it_requires_path(expect, manager):
            with expect.raises(RuntimeError):
                manager.save()
