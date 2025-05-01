from rest_framework import serializers


class DynamicFieldsModelSerializer(serializers.ModelSerializer):
    """
    A ModelSerializer that takes an additional `fields` argument that
    controls which fields should be displayed.
    """

    def __init__(self, *args, **kwargs):

        # Don't pass these fields arg up to the superclass
        fields = kwargs.pop("fields", None)
        exclude = kwargs.pop("exclude", None)
        nested = kwargs.pop("nested", None)

        # Instantiate the superclass normally
        super(DynamicFieldsModelSerializer, self).__init__(*args, **kwargs)

        if fields is not None:
            # Drop any fields that are not specified in the `fields` argument.
            allowed = set(fields)
            existing = set(self.fields)
            for field_name in existing - allowed:
                self.fields.pop(field_name)

        if exclude is not None:

            exclude = set(exclude)
            for field_name in exclude:
                self.fields.pop(field_name)

        if nested is not None:
            for serializer in nested:
                try:
                    nested_serializer = self.fields[serializer]
                except Exception as e:
                    continue

                allowed = set(nested[serializer])
                existing = set(nested_serializer.fields.keys())
                for field_name in existing - allowed:
                    nested_serializer.fields.pop(field_name)
