from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        app_label = "sampleapp"

    def __str__(self) -> str:
        return self.name


class Bundle(models.Model):
    """Targets Stock via M2M -> gives Stock a reverse M2M relation.

    Regression guard: builder must not treat reverse relations as fields.
    """

    name = models.CharField(max_length=100)
    stocks = models.ManyToManyField("Stock", related_name="bundles", blank=True)

    class Meta:
        app_label = "sampleapp"


class House(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        app_label = "sampleapp"

    def __str__(self) -> str:
        return self.name


class Space(models.Model):
    name = models.CharField(max_length=100)
    house = models.ForeignKey(House, on_delete=models.CASCADE, related_name="spaces")

    class Meta:
        app_label = "sampleapp"

    def __str__(self) -> str:
        return self.name


class Stock(models.Model):
    STATUS_CHOICES = [("draft", "Draft"), ("active", "Active")]

    name = models.CharField(max_length=255)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="stocks")
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    house = models.ForeignKey(House, on_delete=models.SET_NULL, null=True, blank=True)
    # Should only allow Spaces belonging to the Stock's house (relation_filters).
    spaces = models.ManyToManyField(Space, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "sampleapp"

    def __str__(self) -> str:
        return self.name
