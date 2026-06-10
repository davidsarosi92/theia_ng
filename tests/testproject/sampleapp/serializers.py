"""A DRF serializer used to exercise the optional DRF adapter."""

from rest_framework import serializers

from .models import Stock


class StockSerializer(serializers.ModelSerializer):
    # A serializer-level rule the generic ORM path would not know about.
    def validate_name(self, value: str) -> str:
        if value.lower() == "forbidden":
            raise serializers.ValidationError("This name is not allowed.")
        return value

    class Meta:
        model = Stock
        fields = ["id", "name", "category", "quantity", "status", "is_active", "notes"]
        read_only_fields = ["id"]
