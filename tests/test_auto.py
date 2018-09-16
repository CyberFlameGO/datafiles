# pylint: disable=unused-variable

from dataclasses import dataclass, field
from typing import List

import pytest

from datafiles import sync


@sync('../tmp/sample.yml')
@dataclass
class Sample:
    item: str = 'a'
    items: List[int] = field(default_factory=lambda: [1])

    def __getitem__(self, key):
        return self.items[key]  # pylint: disable=unsubscriptable-object


@sync('../tmp/sample.yml')
@dataclass
class SampleWithIter:
    items: List[int] = field(default_factory=lambda: [1])

    def __iter__(self):
        return iter(self.items)


def describe_automatic_load():
    @pytest.mark.xfail
    def with_getattribute(write, expect):
        sample = Sample()

        write(
            'tmp/sample.yml',
            """
            item: b
            """,
        )

        expect(sample.item) == 'b'

    def with_getitem(write, expect):
        sample = Sample()

        write(
            'tmp/sample.yml',
            """
            items: [2]
            """,
        )

        expect(sample[0]) == 2

    def with_iter(write, expect):
        sample = SampleWithIter()

        write(
            'tmp/sample.yml',
            """
            items: [2]
            """,
        )

        expect([x for x in sample]) == [2]
