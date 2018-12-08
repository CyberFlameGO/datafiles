import dataclasses
from abc import ABCMeta, abstractmethod
from collections.abc import Iterable
from typing import Any, Dict, Union

import log
from cachetools import cached

from .utils import Missing


class Converter(metaclass=ABCMeta):
    """Base class for attribute conversion."""

    TYPE: Any = None
    DEFAULT: Any = None

    @classmethod
    def as_optional(cls):
        name = 'Optional' + cls.__name__
        return type(name, (cls,), {'DEFAULT': None})

    @classmethod
    @abstractmethod
    def to_python_value(cls, deserialized_data):
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def to_preserialization_data(cls, python_value):
        raise NotImplementedError


class Boolean(Converter):

    TYPE = bool
    DEFAULT = False
    _FALSY = {'false', 'f', 'no', 'n', 'disabled', 'off', '0'}

    @classmethod
    def to_python_value(cls, deserialized_data):
        if isinstance(deserialized_data, str):
            return deserialized_data.lower() not in cls._FALSY
        return cls.TYPE(deserialized_data)

    @classmethod
    def to_preserialization_data(cls, python_value):
        if python_value is None:
            return cls.DEFAULT
        return cls.TYPE(python_value)


class Float(Converter):

    TYPE = float
    DEFAULT = 0.0

    @classmethod
    def to_python_value(cls, deserialized_data):
        return cls.to_preserialization_data(deserialized_data)

    @classmethod
    def to_preserialization_data(cls, python_value):
        if python_value is None:
            return cls.DEFAULT
        return cls.TYPE(python_value)


class Integer(Converter):

    TYPE = int
    DEFAULT = 0

    @classmethod
    def to_python_value(cls, deserialized_data):
        return cls.to_preserialization_data(deserialized_data)

    @classmethod
    def to_preserialization_data(cls, python_value):
        if python_value is None:
            return cls.DEFAULT
        try:
            return cls.TYPE(python_value)
        except ValueError as exc:
            try:
                data = cls.TYPE(float(python_value))
            except ValueError:
                raise exc from None
            else:
                msg = f'Precision lost in conversion to int: {python_value}'
                log.warn(msg)
                return data


class String(Converter):

    TYPE = str
    DEFAULT = ''

    @classmethod
    def to_python_value(cls, deserialized_data):
        return cls.to_preserialization_data(deserialized_data)

    @classmethod
    def to_preserialization_data(cls, python_value):
        if python_value is None:
            return cls.DEFAULT
        return cls.TYPE(python_value)


class List:

    CONVERTER = None

    @classmethod
    def subclass(cls, converter: Converter):
        name = f'{converter.__name__}List'  # type: ignore
        bases = (cls,)
        attributes = {'CONVERTER': converter}
        return type(name, bases, attributes)

    @classmethod
    def to_python_value(cls, deserialized_data):
        value = []

        if dataclasses.is_dataclass(cls.CONVERTER):
            # pylint: disable=not-callable
            convert = lambda data: cls.CONVERTER(**data)
        else:
            convert = cls.CONVERTER.to_python_value

        if deserialized_data is None:
            pass

        elif isinstance(deserialized_data, str):
            for item in deserialized_data.split(','):
                value.append(convert(item))
        else:
            try:
                items = iter(deserialized_data)
            except TypeError:
                value.append(convert(deserialized_data))
            else:
                for item in items:
                    value.append(convert(item))

        return value

    @classmethod
    def to_preserialization_data(cls, python_value):
        data = []

        if dataclasses.is_dataclass(cls.CONVERTER):
            convert = (
                lambda value: value.datafile.data
                if hasattr(value, 'datafile')
                else value
            )
        else:
            convert = cls.CONVERTER.to_preserialization_data

        if python_value is None:
            pass

        elif isinstance(python_value, Iterable):

            if isinstance(python_value, str):
                data.append(convert(python_value))

            elif isinstance(python_value, set):
                data.extend(sorted(convert(item) for item in python_value))

            else:
                for item in python_value:
                    data.append(convert(item))
        else:
            data.append(convert(python_value))

        return data


class Dictionary:

    DATACLASS = None
    CONVERTERS = None

    @classmethod
    def subclass(cls, dataclass, converters: Dict[str, Converter]):
        name = f'{dataclass.__name__}Converter'
        bases = (cls,)
        attributes = {'DATACLASS': dataclass, 'CONVERTERS': converters}
        return type(name, bases, attributes)

    @classmethod
    def to_python_value(cls, deserialized_data):
        data = deserialized_data if deserialized_data else {}
        value = cls.DATACLASS(**data)  # pylint: disable=not-callable
        return value

    @classmethod
    def to_preserialization_data(cls, python_value, *, default=Missing):
        data = {}

        for name, converter in cls.CONVERTERS.items():

            if isinstance(python_value, dict):
                try:
                    value = python_value[name]
                except KeyError as e:
                    log.debug(e)
                    continue
            else:
                try:
                    value = getattr(python_value, name)
                except AttributeError as e:
                    log.debug(e)
                    continue

            if default is not Missing:
                if value == getattr(default, name):
                    log.debug(f"Skipped default value for '{name}' attribute")
                    continue

            data[name] = converter.to_preserialization_data(value)

        return data


@cached(cache={}, key=lambda cls, **kwargs: cls)
def map_type(cls, **kwargs):
    """Infer the converter type from a dataclass, type, or annotation."""
    log.debug(f'Mapping {cls} to converter')

    if dataclasses.is_dataclass(cls):
        converters = {}
        for field in dataclasses.fields(cls):
            converters[field.name] = map_type(field.type, **kwargs)
        converter = Dictionary.subclass(cls, converters)
        log.debug(f'Mapped {cls} to new converter: {converter}')
        return converter

    if hasattr(cls, '__origin__'):
        converter = None

        if cls.__origin__ == list:
            try:
                converter = map_type(cls.__args__[0], **kwargs)
            except TypeError as exc:
                log.debug(exc)
                exc = TypeError(f"Type is required with 'List' annotation")
                raise exc from None
            else:
                converter = List.subclass(converter)

        elif cls.__origin__ == Union:
            converter = map_type(cls.__args__[0], **kwargs)
            assert len(cls.__args__) == 2
            assert cls.__args__[1] == type(None)
            converter = converter.as_optional()

        if converter:
            log.debug(f'Mapped {cls} to new converter: {converter}')
            return converter

        raise TypeError(f'Unsupported container type: {cls.__origin__}')

    else:
        for converter in Converter.__subclasses__():
            if converter.TYPE == cls:
                log.debug(f'Mapped {cls} to existing converter: {converter}')
                return converter

    raise TypeError(f'Could not map type: {cls}')
