#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import logging
import json
import uuid

from django.db import models
from django.conf import settings
from django.utils import timezone

from google.protobuf.descriptor import FieldDescriptor as FD


LOGGER = logging.getLogger(__name__)

PB_FIELD_TYPE_TIMESTAMP = FD.MAX_TYPE + 1
PB_FIELD_TYPE_REPEATED = FD.MAX_TYPE + 2
PB_FIELD_TYPE_MAP = FD.MAX_TYPE + 3
PB_FIELD_TYPE_MESSAGE = FD.MAX_TYPE + 4
PB_FIELD_TYPE_REPEATED_MESSAGE = FD.MAX_TYPE + 5
PB_FIELD_TYPE_MESSAGE_MAP = FD.MAX_TYPE + 6

FIELD_TYPE_CAST = {
    FD.TYPE_DOUBLE: float,
    FD.TYPE_FLOAT: float,
    FD.TYPE_INT64: long,
    FD.TYPE_UINT64: long,
    FD.TYPE_INT32: int,
    FD.TYPE_BOOL: bool,
    FD.TYPE_STRING: str,
    FD.TYPE_BYTES: bytes,
    FD.TYPE_UINT32: int,
    FD.TYPE_SINT32: int,
    FD.TYPE_SINT64: long,
}
GFIELD_TYPE_CAST = {
    "DoubleValue": float,
    "FloatValue": float,
    "Int64Value": long,
    "UInt64Value": long,
    "Int32Value": int,
    "UInt32Value": int,
    "BoolValue": bool,
    "StringValue": str,
    "BytesValue": bytes,
}


def normalize_dj_value(pb_field, dj_field_value, force_type_cast):
    if force_type_cast and dj_field_value is not None:
        mtype = pb_field.message_type
        if mtype:
            type_cast = GFIELD_TYPE_CAST.get(mtype.name)
        else:
            type_cast = FIELD_TYPE_CAST.get(pb_field.type)
        if type_cast:
            dj_field_value = type_cast(dj_field_value)
    return dj_field_value


def set_pb_value(pb_obj, pb_field, dj_field_value):
    mtype = pb_field.message_type
    if mtype and mtype.full_name.startswith("google.protobuf"):
        if dj_field_value is not None:
            getattr(pb_obj, pb_field.name).value = dj_field_value
    else:
        setattr(pb_obj, pb_field.name, dj_field_value)


def _defaultfield_to_pb(pb_obj, pb_field, dj_field_value, force_type_cast, **_):
    """ handling any fields conversion to protobuf
    """
    LOGGER.debug("Django Value field, assign proto msg field: {} = {}".format(pb_field.name, dj_field_value))
    if sys.version_info < (3,) and type(dj_field_value) is buffer:
        dj_field_value = bytes(dj_field_value)
    try:
        dj_field_value = normalize_dj_value(pb_field, dj_field_value, force_type_cast)
        set_pb_value(pb_obj, pb_field, dj_field_value)
    except TypeError as e:
        e.args = ["Failed to serialize field '{}' - {}".format(pb_field.name, e)]
        raise


def normalize_pb_value(pb_field, pb_value, dj_field_type, force_type_cast):
    mtype = pb_field.message_type

    if force_type_cast:
        to_py = dj_field_type().to_python
        if mtype:
            if mtype.name in GFIELD_TYPE_CAST:
                return to_py(pb_value.value)
        else:
            if pb_field.type in FIELD_TYPE_CAST:
                return to_py(pb_value)

    if mtype and mtype.full_name.startswith("google.protobuf"):
        return pb_value.value
    return pb_value


def _defaultfield_from_pb(instance, dj_field_name, pb_field, pb_value, dj_field_type,
                          force_type_cast):
    """ handling any fields setting from protobuf
    """
    pb_value = normalize_pb_value(pb_field, pb_value, dj_field_type, force_type_cast)
    LOGGER.debug("Django Value Field, set dj field: {} = {}".format(dj_field_name, pb_value))
    setattr(instance, dj_field_name, pb_value)


def _datetimefield_to_pb(pb_obj, pb_field, dj_field_value, **_):
    """handling Django DateTimeField field

    :param pb_obj: protobuf message obj which is return value of to_pb()
    :param pb_field: protobuf message field which is current processing field
    :param dj_field_value: Currently proecessing django field value
    :returns: None
    """
    if getattr(getattr(pb_obj, pb_field.name), 'FromDatetime', False):
        if settings.USE_TZ:
            dj_field_value = timezone.make_naive(dj_field_value, timezone=timezone.utc)
        getattr(pb_obj, pb_field.name).FromDatetime(dj_field_value)


def _datetimefield_from_pb(instance, dj_field_name, pb_field, pb_value, **_):
    """handling datetime field (Timestamp) object to dj field

    :param dj_field_name: Currently target django field's name
    :param pb_value: Currently processing protobuf message value
    :returns: None
    """
    dt = pb_value.ToDatetime()
    if settings.USE_TZ:
        dt = timezone.localtime(timezone.make_aware(dt, timezone.utc))
    # FIXME: not datetime field
    setattr(instance, dj_field_name, dt)


def _uuid_to_pb(pb_obj, pb_field, dj_field_value, **_):
    """handling Django UUIDField field

    :param pb_obj: protobuf message obj which is return value of to_pb()
    :param pb_field: protobuf message field which is current processing field
    :param dj_field_value: Currently proecessing django field value
    :returns: None
    """
    setattr(pb_obj, pb_field.name, str(dj_field_value))


def _uuid_from_pb(instance, dj_field_name, pb_field, pb_value, **_):
    """handling string object to dj UUIDField

    :param dj_field_name: Currently target django field's name
    :param pb_value: Currently processing protobuf message value
    :returns: None
    """
    setattr(instance, dj_field_name, uuid.UUID(pb_value))


def _filefield_to_pb(pb_obj, pb_field, dj_value, force_type_cast, **_):
    try:
        value = str(dj_value)
    except ValueError:
        value = ''
    _defaultfield_to_pb(pb_obj, pb_field, value, force_type_cast=force_type_cast)


def array_to_pb(pb_obj, pb_field, dj_field_value, **_):
    getattr(pb_obj, pb_field.name).extend(dj_field_value)


class ProtoBufFieldMixin(object):
    @staticmethod
    def to_pb(pb_obj, pb_field, dj_field_value, **_):
        raise NotImplementedError()

    @staticmethod
    def from_pb(instance, dj_field_name, pb_field, pb_value, **_):
        raise NotImplementedError()


class JSONField(models.TextField):
    def from_db_value(self, value, expression, connection, context=None):
        return self._deserialize(value)

    def to_python(self, value):
        if isinstance(value, str):
            return self._deserialize(value)

        return value

    def get_prep_value(self, value):
        return json.dumps(value)

    def _deserialize(self, value):
        if value is None:
            return None

        return json.loads(value)


class ArrayField(JSONField, ProtoBufFieldMixin):
    @staticmethod
    def to_pb(pb_obj, pb_field, dj_field_value, **_):
        getattr(pb_obj, pb_field.name).extend(dj_field_value)

    @staticmethod
    def from_pb(instance, dj_field_name, pb_field, pb_value, **_):
        setattr(instance, dj_field_name, list(pb_value))


class MapField(JSONField, ProtoBufFieldMixin):
    @staticmethod
    def to_pb(pb_obj, pb_field, dj_field_value, **_):
        getattr(pb_obj, pb_field.name).update(dj_field_value)

    @staticmethod
    def from_pb(instance, dj_field_name, pb_field, pb_value, **_):
        setattr(instance, dj_field_name, dict(pb_value))


class RepeatedMessageField(models.ManyToManyField, ProtoBufFieldMixin):
    class Descriptor(models.fields.related_descriptors.ManyToManyDescriptor):
        def __init__(self, field_name, index_field_name, rel, reverse=False):
            super(RepeatedMessageField.Descriptor, self).__init__(rel, reverse)
            self._field_name = field_name
            self._index_field_name = index_field_name

        def __get__(self, instance, cls=None):
            if instance is None:
                raise AttributeError('Can only be accessed via an instance.')

            if self._field_name not in instance.__dict__:
                instance.__dict__[self._field_name] = [self.related_manager_cls(instance).get(id=id_) for id_ in getattr(instance, self._index_field_name)]
            return instance.__dict__[self._field_name]

        def __set__(self, instance, value):
            instance.__dict__[self._field_name] = value

    def __init__(self, *args, **kwargs):
        super(RepeatedMessageField, self).__init__(default=[], *args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super(RepeatedMessageField, self).deconstruct()
        kwargs.pop('default')
        return name, path, args, kwargs

    def contribute_to_class(self, cls, name):
        index_field_name = '%s_index' % name
        index_field = JSONField(default=[], editable=False, blank=True)
        index_field.creation_counter = self.creation_counter
        cls.add_to_class(index_field_name, index_field)
        super(RepeatedMessageField, self).contribute_to_class(cls, name)
        setattr(cls, self.attname, RepeatedMessageField.Descriptor(name, index_field_name, self.remote_field, reverse=False))

    def save(self, instance):
        for message in getattr(instance, self.attname):
            type(instance).__dict__[self.attname].related_manager_cls(instance).add(message)
        setattr(instance, '%s_index' % self.attname, [q.id for q in instance.__dict__[self.attname]])

    def load(self, instance):
        getattr(instance, self.attname)

    @staticmethod
    def to_pb(pb_obj, pb_field, dj_field_value, expand_level, **_):
        getattr(pb_obj, pb_field.name).extend(
            [m.to_pb(expand_level=expand_level) for m in dj_field_value]
        )

    @staticmethod
    def from_pb(instance, dj_field_name, pb_field, pb_value, **_):
        related_model = instance._meta.get_field(dj_field_name).related_model
        setattr(instance, dj_field_name, [related_model().from_pb(pb_message) for pb_message in pb_value])


class RepeatedForeignField(JSONField):
    """
    This is an naive proxy field for JSONField to support types cannot
    easily extend with protobuf support.
    """
    pass

class MessageMapField(models.ManyToManyField, ProtoBufFieldMixin):
    class Descriptor(models.fields.related_descriptors.ManyToManyDescriptor):
        def __init__(self, field_name, index_field_name, rel, reverse=False):
            super(MessageMapField.Descriptor, self).__init__(rel, reverse)
            self._field_name = field_name
            self._index_field_name = index_field_name

        def __get__(self, instance, cls=None):
            if instance is None:
                raise AttributeError('Can only be accessed via an instance.')

            if self._field_name not in instance.__dict__:
                instance.__dict__[self._field_name] = {key: self.related_manager_cls(instance).get(id=id_) for key, id_ in getattr(instance, self._index_field_name).items()}
            return instance.__dict__[self._field_name]

        def __set__(self, instance, value):
            instance.__dict__[self._field_name] = value

    def __init__(self, *args, **kwargs):
        super(MessageMapField, self).__init__(default={}, *args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super(MessageMapField, self).deconstruct()
        kwargs.pop('default')
        return name, path, args, kwargs

    def contribute_to_class(self, cls, name):
        index_field_name = '%s_index' % name
        index_field = JSONField(default={}, editable=False, blank=True)
        index_field.creation_counter = self.creation_counter
        cls.add_to_class(index_field_name, index_field)
        super(MessageMapField, self).contribute_to_class(cls, name)
        setattr(cls, self.attname, MessageMapField.Descriptor(name, index_field_name, self.remote_field, reverse=False))

    def save(self, instance):
        for message in getattr(instance, self.attname).values():
            type(instance).__dict__[self.attname].related_manager_cls(instance).add(message)
        setattr(instance, '%s_index' % self.attname, {key: message.id for key, message in instance.__dict__[self.attname].items()})

    def load(self, instance):
        getattr(instance, self.attname)

    @staticmethod
    def to_pb(pb_obj, pb_field, dj_field_value, expand_level, **_):
        for key in dj_field_value:
            getattr(pb_obj, pb_field.name)[key].CopyFrom(
                dj_field_value[key].to_pb(expand_level=expand_level)
            )

    @staticmethod
    def from_pb(instance, dj_field_name, pb_field, pb_value, **_):
        related_model = instance._meta.get_field(dj_field_name).related_model
        setattr(instance, dj_field_name, {key: related_model().from_pb(pb_message) for key, pb_message in pb_value.items()})
