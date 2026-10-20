from datetime import date, timedelta
from django.db import models


class Plant(models.Model):
    name = models.CharField(max_length=100)
    photo = models.ImageField(upload_to="plants/")
    species = models.CharField(max_length=200, blank=True)
    confidence = models.FloatField(default=0)
    top3 = models.JSONField(default=list)
    diagnosis = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class CareTask(models.Model):
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="tasks")
    kind = models.CharField(max_length=50)
    every_days = models.PositiveIntegerField()
    next_due = models.DateField()

    def mark_done(self):
        self.next_due = date.today() + timedelta(days=self.every_days)
        self.save()
