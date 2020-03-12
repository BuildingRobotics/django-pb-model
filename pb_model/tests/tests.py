import datetime
import uuid

from django.core.exceptions import ObjectDoesNotExist
from django.test import TestCase
from django.db import models as dj_models

from google.protobuf.timestamp_pb2 import Timestamp
from google.protobuf.descriptor import FieldDescriptor

# Create your tests here.

from pb_model.models import ProtoBufMixin
from . import models, models_pb2


class ProtoBufConvertingTest(TestCase):

    def setUp(self):
        pass

    def test_single_model(self):
        relation_item = models.Relation.objects.create(num=10)
        relation_item2 = models.Relation()

        relation_item2.from_pb(relation_item.to_pb())

        self.assertEqual(relation_item.id, relation_item2.id,
                         msg="{}(src) != {}(target)".format(relation_item.id, relation_item2.id))
        self.assertEqual(relation_item.num, relation_item2.num,
                         msg="{}(src) != {}(target)".format(relation_item.num, relation_item2.num))

    def test_model_with_key(self):
        main_item = models.Main.objects.create(
            string_field='Hello world', integer_field=2017,
            float_field=3.14159, bool_field=True,
            choices_field=models.Main.OPT2,
            fk_field=models.Relation.objects.create(num=2018),
        )
        m2m_relations = [models.M2MRelation.objects.create(num=i+2000) for i in range(5)]
        for m2m in m2m_relations:
            main_item.m2m_field.add(m2m)

        main_item2 = models.Main()
        main_item2.from_pb(main_item.to_pb())

        self.assertEqual(main_item.id, main_item2.id,
                         msg="{}(src) != {}(target)".format(main_item.id, main_item2.id))
        self.assertEqual(main_item.string_field, main_item2.string_field,
                         msg="{}(src) != {}(target)".format(main_item.string_field, main_item2.string_field))
        self.assertEqual(main_item.integer_field, main_item2.integer_field,
                         msg="{}(src) != {}(target)".format(main_item.integer_field, main_item2.integer_field))
        self.assertAlmostEqual(main_item.float_field, main_item2.float_field, delta=1e-6,
                               msg="{}(src) != {}(target)".format(main_item.float_field, main_item2.float_field))
        self.assertEqual(main_item.bool_field, main_item2.bool_field,
                         msg="{}(src) != {}(target)".format(main_item.bool_field, main_item2.bool_field))
        self.assertEqual(main_item.choices_field, main_item2.choices_field,
                         msg="{}(src) != {}(target)".format(main_item.choices_field, main_item2.choices_field))

        time_diff = main_item.datetime_field - main_item2.datetime_field
        # convertion may affect 1 microsecond due to resolution difference
        # between Protobuf timestamp and Python datetime
        self.assertAlmostEqual(0, time_diff.total_seconds(), delta=1e-6,
                               msg="{}(src) != {}(target)".format(main_item.datetime_field, main_item2.datetime_field))

        self.assertEqual(main_item.fk_field.id, main_item2.fk_field.id,
                         msg="{}(src) != {}(target)".format(main_item.fk_field.id, main_item2.fk_field.id))
        self.assertEqual(main_item.fk_field.num, main_item2.fk_field.num,
                         msg="{}(src) != {}(target)".format(main_item.fk_field.num, main_item2.fk_field.num))

        self.assertListEqual(
            list(main_item.m2m_field.order_by('id').values_list('id', flat=True)),
            list(main_item2.m2m_field.order_by('id').values_list('id', flat=True)),
            msg="{}(src) != {}(target)".format(
                main_item.m2m_field.order_by('id').values_list('id', flat=True),
                main_item2.m2m_field.order_by('id').values_list('id', flat=True))
        )
    
        main_item2.save()
        main_item2 = models.Main.objects.get()
        assert main_item.to_pb() == main_item2.to_pb()

    def test_inheritance(self):
        class Parent(ProtoBufMixin, dj_models.Model):
            pb_model = models_pb2.Root
            pb_2_dj_fields = ['uint32_field']
            pb_2_dj_field_map = {'uint32_field': 'uint32_field_renamed'}
            pb_auto_field_type_mapping = {
                FieldDescriptor.TYPE_UINT32: dj_models.IntegerField
            }

        class Child(Parent):
            pb_model = models_pb2.Root
            pb_2_dj_fields = ['uint64_field']
            pb_2_dj_field_map = {'uint64_field': 'uint64_field_renamed'}
            pb_auto_field_type_mapping = {
                FieldDescriptor.TYPE_UINT32: dj_models.FloatField,
                FieldDescriptor.TYPE_UINT64: dj_models.IntegerField
            }

        assert ProtoBufMixin.pb_auto_field_type_mapping[FieldDescriptor.TYPE_UINT32] is dj_models.PositiveIntegerField
        assert Parent.pb_auto_field_type_mapping[FieldDescriptor.TYPE_UINT32] is dj_models.IntegerField

        assert {f.name for f in Parent._meta.get_fields()} == {'child', 'id', 'uint32_field_renamed'}
        assert type(Parent._meta.get_field('uint32_field_renamed')) is dj_models.IntegerField

        assert {f.name for f in Child._meta.get_fields()} == {'parent_ptr', 'id', 'uint32_field_renamed', 'uint64_field_renamed'}
        assert type(Child._meta.get_field('uint32_field_renamed')) is dj_models.IntegerField
        assert type(Child._meta.get_field('uint64_field_renamed')) is dj_models.IntegerField

    def test_custom_serializer(self):
        """
        Default serialization strategies can be overriden
        """

        def serializer(pb_obj, pb_field, dj_value, **_):
            """
            Serialize NativeRelation as a repeated int32
            """
            getattr(pb_obj, 'foreign_field').extend([dj_value.first, dj_value.second, dj_value.third])


        def deserializer(instance, dj_field_name, pb_field, pb_value, **_):
            setattr(instance, 'foreign_field',
                    NativeRelation(
                        first=pb_value[0],
                        second=pb_value[1],
                        third=pb_value[2]
                    ))

        # This is a relation type that's not ProtoBuf enabled
        class NativeRelation(dj_models.Model):
            first = dj_models.IntegerField()
            second = dj_models.IntegerField()
            third = dj_models.IntegerField()


        class Model(ProtoBufMixin, dj_models.Model):
            pb_model = models_pb2.Root
            pb_2_dj_fields = ['foreign_field']
            pb_2_dj_field_serializers = {
                'foreign_field': (serializer, deserializer)
            }
            foreign_field = dj_models.ForeignKey(NativeRelation, on_delete=dj_models.DO_NOTHING)

        _in = Model(foreign_field=NativeRelation(first=123, second=456, third=789))

        out = Model().from_pb(_in.to_pb())

        assert out.foreign_field.first == 123
        assert out.foreign_field.second == 456
        assert out.foreign_field.third == 789


    def test_auto_fields(self):
        timestamp = Timestamp()
        timestamp.FromDatetime(datetime.datetime.now())
        pb_object = models_pb2.Root(
            uint32_field=1234,
            uint64_field=123,
            int64_field=123,
            float_field=12.3,
            double_field=12.3,
            string_field='123',
            bytes_field=b'123',
            bool_field=True,
            uuid_field=str(uuid.uuid4()),

            enum_field=1,
            timestamp_field=timestamp,
            repeated_uint32_field=[1, 2, 3],
            map_string_to_string_field={'qwe': 'asd'},

            message_field=models_pb2.Root.Embedded(data=123),
            repeated_message_field=[models_pb2.Root.Embedded(data=123), models_pb2.Root.Embedded(data=456), models_pb2.Root.Embedded(data=789)],
            map_string_to_message_field={'qwe': models_pb2.Root.Embedded(data=123), 'asd': models_pb2.Root.Embedded(data=456)},

            list_field_option=models_pb2.Root.ListWrapper(data=['qwe', 'asd', 'zxc'])
        )

        dj_object = models.Root()
        dj_object.from_pb(pb_object)
        dj_object.message_field.save()
        dj_object.message_field = dj_object.message_field
        for m in dj_object.repeated_message_field:
            m.save()
        for m in dj_object.map_string_to_message_field.values():
            m.save()
        dj_object.list_field_option.save()
        dj_object.list_field_option = dj_object.list_field_option
        dj_object.save()

        dj_object_from_db = models.Root.objects.get()
        assert [o.data for o in dj_object_from_db.repeated_message_field] == [123, 456, 789]
        assert {k: o.data for k, o in dj_object_from_db.map_string_to_message_field.items()} == {'qwe': 123, 'asd': 456}
        assert dj_object_from_db.uint32_field_renamed == pb_object.uint32_field
        result = dj_object_from_db.to_pb()
        assert pb_object == result


class ComfyConvertingTest(TestCase):

    def test_comfy_model(self):
        sub1 = models.Sub.objects.create(name="test_sub")
        comfy1 = models.Comfy.objects.create(number=10, sub=sub1)
        item1 = models.Item.objects.create(comfy=comfy1, nr=5)
        self.assertEqual(1, comfy1.id)
        self.assertEqual(10, comfy1.number)
        self.assertEqual(5, item1.nr)

        comfy1_pb = comfy1.to_pb(expand_level=1)
        self.assertEqual("1", comfy1_pb.id)
        self.assertEqual("10", comfy1_pb.number)
        self.assertEqual(5, comfy1_pb.items[0].nr)
        self.assertEqual("test_sub", comfy1_pb.sub.name)

        comfy2 = models.Comfy()
        comfy2.from_pb(comfy1_pb)
        self.assertEqual(1, comfy2.id)
        self.assertEqual(10, comfy2.number)
        self.assertEqual(5, comfy2.items.get().nr)
        self.assertEqual("test_sub", comfy2.sub.name)

    def test_no_relation_expansion(self):
        sub1 = models.Sub.objects.create(name="test_sub")
        comfy_no_expand1 = models.Comfy.objects.create(number=11, sub=sub1)
        item_no_expand1 = models.Item.objects.create(
            comfy=comfy_no_expand1, nr=6
        )

        comfy_no_expand1_pb = comfy_no_expand1.to_pb(expand_level=0)
        self.assertFalse(comfy_no_expand1_pb.items)
        self.assertFalse(comfy_no_expand1_pb.sub.name)

        item_no_expand1.delete()
        comfy_no_expand1.delete()
        del item_no_expand1, comfy_no_expand1

        comfy_no_expand2 = models.Comfy()
        comfy_no_expand2.from_pb(comfy_no_expand1_pb)
        with self.assertRaises(ObjectDoesNotExist):
            # FIXME(cmiN): Check `_protobuf_to_m2m` hook if you want on-the-fly
            #  full population of the model.
            comfy_no_expand2.items.get()

    def test_with_enum(self):
        comfy1 = models.ComfyWithEnum.objects.create(number=12)
        comfy1.work_days = [1, 2]

        comfy1_pb = comfy1.to_pb()
        self.assertEqual(comfy1.work_days, comfy1_pb.work_days)

    def test_with_gtypes(self):
        sub1 = models.Sub.objects.create(name="test_sub")
        comfy1 = models.ComfyWithGTypes.objects.create(
            sub=sub1, bool_val=True, float_val=3.14
        )
        comfy1.str_val = None  # unset

        comfy1_pb = comfy1.to_pb()
        self.assertEqual(comfy1.bool_val, comfy1_pb.bool_val.value)
        self.assertEqual(
            round(comfy1.float_val, 2), round(comfy1_pb.float_val.value, 2)
        )
        # NOTE(cmiN): Unset values are seen as literal defaults.
        self.assertEqual("", comfy1_pb.str_val.value)

        comfy2 = models.ComfyWithGTypes()
        comfy2.from_pb(comfy1_pb)
        self.assertEqual(comfy1.bool_val, comfy2.bool_val)
        self.assertEqual(round(comfy1.float_val, 2), round(comfy2.float_val, 2))
        self.assertEqual("", comfy2.str_val)

    def test_with_wrong_types(self):
        sub1 = models.SubBadFields.objects.create(name=True)
        exc_tpl = "type {}, but expected one of: bytes, unicode"
        exp_sep = r"[\s\S]+?"
        sub_exp = r"multiple exceptions found" + exp_sep + exp_sep.join(
            map(exc_tpl.format, ("int", "bool"))
        )
        with self.assertRaisesRegexp(Exception, sub_exp):
            sub1.to_pb()

        comfy1 = models.ComfyBadFields.objects.create(
            sub=sub1, bool_val="not-a-bool-but-works", float_val="not-a-float"
        )
        with self.assertRaisesRegexp(Exception, sub_exp):
            comfy1.to_pb()

        sub1.id, sub1.name = map(str, (sub1.id, sub1.name))  # get past above error
        with self.assertRaisesRegexp(
                Exception,
                exp_sep.join([
                    r"multiple exceptions found",
                    r"could not convert string to float: not-a-float"
                ])
        ):
            comfy1.to_pb()
