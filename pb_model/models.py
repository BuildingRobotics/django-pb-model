#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
import functools
import logging
import six

from django.db import models
from django.conf import settings
from django.contrib.postgres import fields as postgres_fields

from google.protobuf.descriptor import FieldDescriptor as FD

from . import fields
from six.moves import map


logging.basicConfig()
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.WARNING)
if settings.DEBUG:
    LOGGER.setLevel(logging.DEBUG)


class DjangoPBModelError(Exception):
    pass


class Meta(type(models.Model)):
    def __init__(self, name, bases, attrs):
        super(Meta, self).__init__(name, bases, attrs)
        self.pb_2_dj_field_serializers = self.pb_2_dj_field_serializers.copy()
        self.pb_2_dj_field_serializers.update(attrs.get('pb_2_dj_field_serializers', {}))

        self.pb_auto_field_type_mapping = self.pb_auto_field_type_mapping.copy()
        self.pb_auto_field_type_mapping.update(attrs.get('pb_auto_field_type_mapping', {}))

        if self.pb_model is not None:
            if self.pb_2_dj_fields == '__all__':
                self.pb_2_dj_fields = list(self.pb_model.DESCRIPTOR.fields_by_name.keys())

            for pb_field_name in self.pb_2_dj_fields:
                pb_field_descriptor = self.pb_model.DESCRIPTOR.fields_by_name[pb_field_name]
                dj_field_name = self.pb_2_dj_field_map.get(pb_field_name, pb_field_name)
                if dj_field_name not in attrs:
                    field = self._create_field(pb_field_descriptor)
                    if field is not None:
                        field.contribute_to_class(self, dj_field_name)

    def _create_field(self, message_field):
        message_field_type = message_field.type

        if Meta._is_message_map_field(message_field):
            mapped_message = message_field.message_type.fields_by_name['value'].message_type
            return self._create_message_map_field(message_field.containing_type.name, mapped_message.name, message_field.name)
        elif Meta._is_map_field(message_field):
            return self._create_map_field()
        elif Meta._is_repeated_message_field(message_field):
            return self._create_repeated_message_field(message_field.containing_type.name, message_field.message_type.name, message_field.name)
        elif Meta._is_repeated_field(message_field):
            return self._create_repeated_field()
        elif Meta._is_message_field(message_field):
            if message_field.message_type.name == 'Timestamp':
                return self._create_timestamp_field()
            else:
                return self._create_message_field(message_field.containing_type.name, message_field.message_type.name, message_field.name)
        else:
            return self._create_generic_field(message_field_type)

    @staticmethod
    def _is_message_field(field_descriptor):
        return field_descriptor.message_type is not None

    @staticmethod
    def _is_repeated_field(field_descriptor):
        return field_descriptor.label == field_descriptor.LABEL_REPEATED

    @staticmethod
    def _is_repeated_message_field(field_descriptor):
        """
        Checks if a given field is a protobuf repeated field.
        :param field_descriptor: protobuf field descriptor
        :return: bool
        """
        return Meta._is_repeated_field(field_descriptor) and Meta._is_message_field(field_descriptor)

    @staticmethod
    def _is_map_field(field_descriptor):
        """
        Checks if a given field is a protobuf map to native field (map<int/float/str/etc., int/float/str/etc.>).
        :param field_descriptor: protobuf field descriptor
        :return: bool
        """
        return field_descriptor.message_type is not None and set(field_descriptor.message_type.fields_by_name.keys()) == {'key', 'value'}

    @staticmethod
    def _is_message_map_field(field_descriptor):
        """
        Checks if a given field is a protobuf map to message field (map<int/float/str/etc., Message>).
        :param field_descriptor: protobuf field descriptor
        :return: bool
        """
        return Meta._is_map_field(field_descriptor) and Meta._is_message_field(field_descriptor.message_type.fields_by_name['value'])

    def _create_generic_field(self, type_):
        """
        Creates a django field of the type that is defined in `pb_auto_field_type_mapping`.
        :param type_: Protobuf field type.
        :return: Django field.
        """
        field_type = self.pb_auto_field_type_mapping[type_]
        return field_type(null=True)

    def _create_timestamp_field(self):
        field_type = self.pb_auto_field_type_mapping[fields.PB_FIELD_TYPE_TIMESTAMP]
        return field_type()

    def _create_map_field(self):
        field_type = self.pb_auto_field_type_mapping[fields.PB_FIELD_TYPE_MAP]
        return field_type()

    def _create_repeated_field(self):
        field_type = self.pb_auto_field_type_mapping[fields.PB_FIELD_TYPE_REPEATED]
        return field_type()

    def _create_message_field(self, own_type, related_type, field_name):
        field_type = self.pb_auto_field_type_mapping[fields.PB_FIELD_TYPE_MESSAGE]
        return field_type(to=related_type, related_name='%s_%s' % (own_type, field_name), on_delete=models.deletion.CASCADE, null=True)

    def _create_repeated_message_field(self, own_type, related_type, field_name):
        """
        Creates a django relation that mimics a repeated message field.
        :param own_type: Name of the message that contains this field.
        :param related_type: Name of the message with which the relation is established.
        :param field_name: Name of the created field.
        :return: RepeatedMessageField
        """
        field_type = self.pb_auto_field_type_mapping[fields.PB_FIELD_TYPE_REPEATED_MESSAGE]
        return field_type(to=related_type, related_name='%s_%s' % (own_type, field_name))

    def _create_message_map_field(self, own_type, related_type, field_name):
        """
        Creates a django relation that mimics a scalar to message map field.
        :param own_type: Name of the message that contains this field.
        :param related_type: Name of the message with which the relation is established.
        :param field_name: Name of the created field.
        :return: MapToMessageField
        """
        field_type = self.pb_auto_field_type_mapping[fields.PB_FIELD_TYPE_MESSAGE_MAP]
        return field_type(to=related_type, related_name='%s_%s' % (own_type, field_name))


class ProtoBufMixin(six.with_metaclass(Meta, models.Model)):
    """This is mixin for model.Model.
    By setting attribute ``pb_model``, you can specify target ProtoBuf Message
    to handle django model.

    By settings attribute ``pb_2_dj_field_map``, you can mapping field from
    ProtoBuf to Django to handle schema migrations and message field chnages
    """
    class Meta:
        abstract = True

    pb_model = None
    pb_type_cast = True
    pb_2_dj_fields = []  # list of pb field names that are mapped, special case pb_2_dj_fields = '__all__'
    pb_2_dj_field_map = {}  # pb field in keys, dj field in value
    pb_2_dj_field_serializers = {
        models.DateTimeField: (fields._datetimefield_to_pb,
                               fields._datetimefield_from_pb),
        models.UUIDField: (fields._uuid_to_pb,
                           fields._uuid_from_pb),
        postgres_fields.ArrayField: (fields.array_to_pb, None),
    }  # dj field in key, serializer function pairs in value
    pb_auto_field_type_mapping = {
        FD.TYPE_DOUBLE: models.FloatField,
        FD.TYPE_FLOAT: models.FloatField,
        FD.TYPE_INT64: models.BigIntegerField,
        FD.TYPE_UINT64: models.BigIntegerField,
        FD.TYPE_INT32: models.IntegerField,
        FD.TYPE_FIXED64: models.DecimalField,
        FD.TYPE_FIXED32: models.DecimalField,
        FD.TYPE_BOOL: models.NullBooleanField,
        FD.TYPE_STRING: models.TextField,
        FD.TYPE_BYTES: models.BinaryField,
        FD.TYPE_UINT32: models.PositiveIntegerField,
        FD.TYPE_ENUM: models.IntegerField,
        FD.TYPE_SFIXED32: models.DecimalField,
        FD.TYPE_SFIXED64: models.DecimalField,
        FD.TYPE_SINT32: models.IntegerField,
        FD.TYPE_SINT64: models.BigIntegerField,
        fields.PB_FIELD_TYPE_TIMESTAMP: models.DateTimeField,
        fields.PB_FIELD_TYPE_REPEATED: fields.ArrayField,
        fields.PB_FIELD_TYPE_MAP: fields.MapField,
        fields.PB_FIELD_TYPE_MESSAGE: models.ForeignKey,
        fields.PB_FIELD_TYPE_REPEATED_MESSAGE: fields.RepeatedMessageField,
        fields.PB_FIELD_TYPE_MESSAGE_MAP: fields.MessageMapField,
    }  # pb field type in key, dj field type in value
    """
    {ProtoBuf-field-name: Django-field-name} key-value pair mapping to handle
    schema migration or any model changes.
    """

    default_serializers = (fields._defaultfield_to_pb, fields._defaultfield_from_pb)

    def __init__(self, *args, **kwargs):
        super(ProtoBufMixin, self).__init__(*args, **kwargs)

        self.default_serializers = tuple([functools.partial(func, force_type_cast=self.pb_type_cast) for func in self.default_serializers])
        for m2m_field in self._meta.many_to_many:
            if issubclass(type(m2m_field), fields.ProtoBufFieldMixin):
                m2m_field.load(self)
        # TODO: also object.update

    def save(self, *args, **kwargs):
        super(ProtoBufMixin, self).save(*args, **kwargs)
        for m2m_field in self._meta.many_to_many:
            if issubclass(type(m2m_field), fields.ProtoBufFieldMixin):
                m2m_field.save(self)
        kwargs['force_insert'] = False
        super(ProtoBufMixin, self).save(*args, **kwargs)

    def _field_to_pb(self, _f, _pb_obj, _dj_field_map, expand_level):
        _dj_f_name = self.pb_2_dj_field_map.get(_f.name, _f.name)
        if _dj_f_name not in _dj_field_map:
            LOGGER.warning("No such django field: {}".format(_f.name))
            return

        try:
            _dj_f_value, _dj_f_type = getattr(self, _dj_f_name), _dj_field_map[
                _dj_f_name]
            if not (_dj_f_type.null and _dj_f_value is None):
                # See if there's a custom serializer for this field relation or not.
                field_serializers = self._get_serializers(type(_dj_f_type), _f)
                if field_serializers and field_serializers != self.default_serializers:
                    self._value_to_protobuf(
                        _pb_obj, _f, type(_dj_f_type), _dj_f_value,
                        expand_level=expand_level
                    )
                else:
                    if _dj_f_type.is_relation and not issubclass(
                            type(_dj_f_type), fields.ProtoBufFieldMixin
                    ):
                        if expand_level is None or expand_level:
                            self._relation_to_protobuf(
                                _pb_obj, _f, _dj_f_type, _dj_f_value,
                                expand_level=(
                                        expand_level - 1
                                ) if expand_level else expand_level
                            )
                    else:
                        self._value_to_protobuf(
                            _pb_obj, _f, type(_dj_f_type), _dj_f_value,
                            expand_level=expand_level
                        )
        except AttributeError as e:
            LOGGER.error(
                "Fail to serialize field: {} for {}. Error: {}".format(
                    _dj_f_name, self._meta.model, e
                )
            )
            raise DjangoPBModelError(
                "Can't serialize Model({})'s field: {}. Err: {}".format(
                    _dj_f_name, self._meta.model, e
                )
            )

    def to_pb(self, expand_level=None):
        """Convert django model to protobuf instance by pre-defined name

        :returns: ProtoBuf instance
        """
        _pb_obj = self.pb_model()
        _dj_field_map = {f.name: f for f in self._meta.get_fields()}

        excs = []
        for _f in _pb_obj.DESCRIPTOR.fields:
            try:
                self._field_to_pb(
                    _f, _pb_obj=_pb_obj, _dj_field_map=_dj_field_map,
                    expand_level=expand_level
                )
            except Exception as exc:
                excs.append(exc)

        excs_str = "\n".join(map(str, excs))
        if excs_str:
            raise Exception("multiple exceptions found:\n{}".format(excs_str))

        LOGGER.info("Coverted Protobuf object: {}".format(_pb_obj))
        return _pb_obj

    def _relation_to_protobuf(
            self, pb_obj, pb_field, dj_field_type, dj_field_value, expand_level
    ):
        """Handling relation to protobuf

        :param pb_obj: protobuf message obj which is return value of to_pb()
        :param pb_field: protobuf message field which is current processing field
        :param dj_field_type: Currently proecessing django field type
        :param dj_field_value: Currently proecessing django field value
        :returns: None

        """
        LOGGER.debug("Django Relation field, recursively serializing")
        if any([dj_field_type.many_to_many, dj_field_type.one_to_many]):
            self._m2m_to_protobuf(
                pb_obj, pb_field, dj_field_value, expand_level=expand_level
            )
        else:
            getattr(pb_obj, pb_field.name).CopyFrom(dj_field_value.to_pb(
                expand_level=expand_level
            ))

    def _m2m_to_protobuf(self, pb_obj, pb_field, dj_m2m_field, expand_level):
        """
        This is hook function from m2m field to protobuf. By default, we assume
        target message field is "repeated" nested message, ex:

        ```
        message M2M {
            int32 id = 1;
        }

        message Main {
            int32 id = 1;

            repeated M2M m2m = 2;
        }
        ```

        If this is not the format you expected, overwrite
        `_m2m_to_protobuf(self, pb_obj, pb_field, dj_field_value, expand_level)`
        by yourself.

        :param pb_obj: intermedia-converting Protobuf obj, which would is return value of to_pb()
        :param pb_field: the Protobuf message field which supposed to assign after converting
        :param dj_m2mvalue: Django many_to_many field
        :returns: None

        """
        getattr(pb_obj, pb_field.name).extend(
            [_m2m.to_pb(expand_level=expand_level) for _m2m in dj_m2m_field.all()]
        )

    def _get_serializers(self, dj_field_type, pb_field=None):
        """Getting the correct serializers for a field type

        :param dj_field_type: Currently processing django field type
        :returns: Tuple containing serialization func pair
        """
        if issubclass(dj_field_type, fields.ProtoBufFieldMixin):
            funcs = dj_field_type.to_pb, dj_field_type.from_pb
        else:
            defaults = self.default_serializers
            funcs = self.pb_2_dj_field_serializers.get(dj_field_type, None)
            if not funcs:
                if pb_field:
                    # Check by field name
                    funcs = self.pb_2_dj_field_serializers.get(pb_field.name, defaults)
                else:
                    funcs = defaults

        if len(funcs) != 2:
            LOGGER.warning(
                "Custom serializers require a pair of functions: {0} is misconfigured".
                    format(dj_field_type))
            return defaults

        return funcs

    def _value_to_protobuf(
            self, pb_obj, pb_field, dj_field_type, dj_field_value, expand_level
    ):
        """Handling value to protobuf

        :param pb_obj: protobuf message obj which is return value of to_pb()
        :param pb_field: protobuf message field which is current processing field
        :param dj_field_type: Currently proecessing django field type
        :param dj_field_value: Currently proecessing django field value
        :returns: None

        """
        s_funcs = self._get_serializers(dj_field_type, pb_field)
        s_funcs[0](pb_obj, pb_field, dj_field_value, expand_level=expand_level)

    def from_pb(self, _pb_obj):
        """Convert given protobuf obj to mixin Django model

        :returns: Django model instance
        """
        _dj_field_map = {f.name: f for f in self._meta.get_fields()}
        LOGGER.debug("ListFields() return fields which contains value only")
        for _f, _v in _pb_obj.ListFields():
            _dj_f_name = self.pb_2_dj_field_map.get(_f.name, _f.name)
            _dj_f_type = _dj_field_map[_dj_f_name]

            field_serializers = self._get_serializers(type(_dj_f_type), _f)
            if field_serializers and field_serializers != self.default_serializers:
                self._protobuf_to_value(_dj_f_name, type(_dj_f_type), _f, _v)

            if _f.message_type is not None:
                dj_field = _dj_field_map[_dj_f_name]
                if dj_field.is_relation and not issubclass(
                        type(dj_field), fields.ProtoBufFieldMixin
                ):
                    self._protobuf_to_relation(_dj_f_name, dj_field, _f, _v)
                    continue
            self._protobuf_to_value(_dj_f_name, type(_dj_f_type), _f, _v)
        LOGGER.info("Coveretd Django model instance: {}".format(self))
        return self

    def _protobuf_to_relation(self, dj_field_name, dj_field, pb_field,
                              pb_value):
        """Handling protobuf nested message to relation key

        :param dj_field_name: Currently target django field's name
        :param dj_field: Currently target django field
        :param pb_field: Currently processing protobuf message field
        :param pb_value: Currently processing protobuf message value
        :returns: None
        """
        LOGGER.debug("Django Relation Feild, deserializing Probobuf message")
        if any([dj_field.many_to_many, dj_field.one_to_many]):
            self._protobuf_to_m2m(dj_field_name, dj_field, pb_value)
            return

        if hasattr(dj_field, 'related_model'):
            # django > 1.8 compatible
            setattr(self, dj_field_name, dj_field.related_model().from_pb(pb_value))
        else:
            setattr(self, dj_field_name, dj_field.related.model().from_pb(pb_value))

    def _protobuf_to_m2m(self, dj_field_name, dj_field, pb_repeated_set):
        """
        This is hook function to handle repeated list to m2m field while converting
        from protobuf to django. By default, no operation is performed, which means
        you may query current relation if your coverted django model instance has a valid PK.

        If you want to modify your database while converting on-the-fly, overwrite
        logics such as:

        ```
        from django.db import transaction

        ...

        class PBCompatibleModel(ProtoBufMixin, models.Model):

            def _repeated_to_m2m(self, dj_field, _pb_repeated_set):
                with transaction.atomic():
                    for item in _pb_repeated_set:
                        dj_field.get_or_create(pk=item.pk, defaults={....})

            ...

        ```

        :param dj_field: Django many_to_many field
        :param pb_repeated_set: the Protobuf message field which contains data that is going to be converted
        :returns: None

        """
        return

    def _protobuf_to_value(self, dj_field_name, dj_field_type, pb_field,
                           pb_value):
        """Handling protobuf singular value

        :param dj_field_name: Currently target django field's name
        :param dj_field_type: Currently proecessing django field type
        :param pb_field: Currently processing protobuf message field
        :param pb_value: Currently processing protobuf message value
        :returns: None
        """
        s_funcs = self._get_serializers(dj_field_type, pb_field)
        s_funcs[1](self, dj_field_name, pb_field, pb_value, dj_field_type=dj_field_type)
