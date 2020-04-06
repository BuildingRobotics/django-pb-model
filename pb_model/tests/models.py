#!/usr/bin/env python
# -*- coding: utf-8 -*-


from __future__ import absolute_import
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils import timezone

from pb_model.models import ProtoBufMixin

from . import models_pb2


class Relation(ProtoBufMixin, models.Model):
    pb_model = models_pb2.Relation

    num = models.IntegerField(default=0)


class M2MRelation(ProtoBufMixin, models.Model):
    pb_model = models_pb2.M2MRelation

    num = models.IntegerField(default=0)


class Main(ProtoBufMixin, models.Model):
    pb_model = models_pb2.Main

    string_field = models.CharField(max_length=32)
    integer_field = models.IntegerField()
    float_field = models.FloatField()
    bool_field = models.BooleanField(default=False)
    datetime_field = models.DateTimeField(default=timezone.now)

    OPT0, OPT1, OPT2, OPT3 = 0, 1, 2, 3
    OPTS = [
        (OPT0, "option-0"),
        (OPT1, "option-1"),
        (OPT2, "option-2"),
        (OPT3, "option-3"),
    ]
    choices_field = models.IntegerField(default=OPT0, choices=OPTS)

    fk_field = models.ForeignKey(Relation, on_delete=models.DO_NOTHING)
    m2m_field = models.ManyToManyField(M2MRelation)


class Embedded(ProtoBufMixin, models.Model):
    pb_model = models_pb2.Root.Embedded
    pb_2_dj_fields = '__all__'


class ListWrapper(ProtoBufMixin, models.Model):
    pb_model = models_pb2.Root.ListWrapper
    pb_2_dj_fields = '__all__'


class MapWrapper(ProtoBufMixin, models.Model):
    pb_model = models_pb2.Root.MapWrapper
    pb_2_dj_fields = '__all__'


class Root(ProtoBufMixin, models.Model):
    pb_model = models_pb2.Root
    pb_2_dj_fields = '__all__'
    pb_2_dj_field_map = {'uint32_field': 'uint32_field_renamed'}

    uuid_field = models.UUIDField(null=True)


class Sub(ProtoBufMixin, models.Model):
    pb_model = models_pb2.Sub

    name = models.CharField(max_length=32, default="")


class Comfy(ProtoBufMixin, models.Model):
    pb_model = models_pb2.Comfy

    number = models.IntegerField(default=0)
    sub = models.ForeignKey(Sub, null=True)


class ComfyWithEnum(Comfy):
    WEEKDAYS = (
        (1, "Monday"),
        (2, "Tuesday"),
    )

    pb_model = models_pb2.ComfyWithEnum

    work_days = ArrayField(
        blank=True,
        base_field=models.PositiveSmallIntegerField(choices=WEEKDAYS),
        null=True,
    )


class ComfyWithGTypes(Comfy):
    pb_model = models_pb2.ComfyWithGTypes

    bool_val = models.BooleanField()
    str_val = models.CharField(max_length=32, null=True, default="")
    float_val = models.FloatField(default=None)


class Item(ProtoBufMixin, models.Model):
    pb_model = models_pb2.Item

    comfy = models.ForeignKey(Comfy, related_name="items")
    nr = models.IntegerField()


class SubBadFields(ProtoBufMixin, models.Model):
    pb_model = models_pb2.Sub
    pb_type_cast = False

    name = models.BooleanField(default=True)


class ComfyBadFields(ProtoBufMixin, models.Model):
    pb_model = models_pb2.ComfyWithGTypes

    number = models.IntegerField(default=0)
    sub = models.ForeignKey(SubBadFields, null=True)
    bool_val = models.CharField(max_length=32)
    str_val = models.IntegerField(null=True, default=0)
    float_val = models.CharField(max_length=32, default=None)
