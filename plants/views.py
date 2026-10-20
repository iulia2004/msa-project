from datetime import date
from django.shortcuts import render, redirect, get_object_or_404
from .models import Plant, CareTask
from . import services


def plant_list(request):
    plants = Plant.objects.order_by("-created")
    return render(request, "plant_list.html", {"plants": plants})


def scan(request):
    if request.method == "POST":
        plant = Plant.objects.create(
            name=request.POST.get("name") or "New plant",
            photo=request.FILES["photo"],
        )
        path = plant.photo.path
        try:
            top3 = services.identify(path)
            plant.top3 = top3
            plant.species = top3[0]["name"]
            plant.confidence = top3[0]["score"]
        except Exception as e:
            plant.species = "unknown"
            plant.diagnosis = f"Identification error: {e}\n\n"
        try:
            plant.diagnosis += services.diagnose(path, plant.species)
        except Exception as e:
            plant.diagnosis += f"Diagnosis error: {e}"
        plant.save()
        for kind, days in [("Water", 7), ("Fertilize", 30)]:
            CareTask.objects.create(plant=plant, kind=kind, every_days=days,
                                    next_due=date.today())
        return redirect("plant_detail", plant.id)
    return render(request, "scan.html")


def plant_detail(request, pk):
    return render(request, "plant_detail.html", {"plant": get_object_or_404(Plant, pk=pk)})


def today(request):
    tasks = CareTask.objects.filter(next_due__lte=date.today()).select_related("plant")
    return render(request, "today.html", {"tasks": tasks})


def done(request, pk):
    if request.method == "POST":
        get_object_or_404(CareTask, pk=pk).mark_done()
    return redirect("today")
