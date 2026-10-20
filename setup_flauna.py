"""
Flauna demo generator.
Run ONCE from an empty folder, with your venv active and `pip install django pillow requests pybioclip` done:

    python setup_flauna.py

It creates the Django project, the app, all templates, runs migrations.
Then start the server with:  python manage.py runserver 0.0.0.0:8000
"""
import os
import subprocess
import sys
import textwrap

MODEL = "gemma3:4b"  # change if you pulled a different Ollama vision model


def run(*args):
    print(">", " ".join(args))
    subprocess.check_call(list(args))


def write(path, content):
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(textwrap.dedent(content).lstrip("\n"))
    print("  wrote", path)


# ---------------------------------------------------------------- project
if not os.path.exists("manage.py"):
    run("django-admin", "startproject", "config", ".")
if not os.path.exists("plants"):
    run(sys.executable, "manage.py", "startapp", "plants")

# ---------------------------------------------------------------- settings
with open("config/settings.py", "a", encoding="utf-8") as f:
    f.write(f'''

# ---- Flauna demo settings ----
INSTALLED_APPS += ["plants"]
ALLOWED_HOSTS = ["*"]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
TEMPLATES[0]["DIRS"] = [BASE_DIR / "templates"]
OLLAMA_MODEL = "{MODEL}"
OLLAMA_URL = "http://localhost:11434/api/chat"
''')

write("config/urls.py", '''
    from django.contrib import admin
    from django.urls import path, include
    from django.conf import settings
    from django.conf.urls.static import static

    urlpatterns = [
        path("admin/", admin.site.urls),
        path("", include("plants.urls")),
    ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
''')

# ---------------------------------------------------------------- models
write("plants/models.py", '''
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
''')

# ---------------------------------------------------------------- AI services
write("plants/services.py", '''
    import base64
    import requests
    from django.conf import settings

    _classifier = None


    def identify(path):
        """BioCLIP: top-3 species predictions."""
        global _classifier
        from bioclip import TreeOfLifeClassifier, Rank
        if _classifier is None:
            _classifier = TreeOfLifeClassifier()  # loads once; slow the first time
        preds = _classifier.predict(path, Rank.SPECIES)[:3]
        out = []
        for p in preds:
            out.append({
                "name": p.get("common_name") or p.get("species", "?"),
                "species": p.get("species", ""),
                "score": round(float(p.get("score", 0)), 3),
            })
        return out


    def diagnose(path, species):
        """Local Ollama vision model: describes the plant's condition and gives advice."""
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        prompt = (
            f"You are a houseplant and garden care expert. The plant in the photo looks like: {species}. "
            "Briefly describe the plant's condition (leaves, color, signs of disease or pests), "
            "then give 3-4 concrete care tips (watering, light, soil, fertilizer). "
            "Be concise. At the end, state your confidence: low, medium or high."
        )
        r = requests.post(settings.OLLAMA_URL, json={
            "model": settings.OLLAMA_MODEL,
            "stream": False,
            "messages": [{"role": "user", "content": prompt, "images": [b64]}],
        }, timeout=600)
        r.raise_for_status()
        return r.json()["message"]["content"]
''')

# ---------------------------------------------------------------- views / urls
write("plants/views.py", '''
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
                plant.diagnosis = f"Identification error: {e}\\n\\n"
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
''')

write("plants/urls.py", '''
    from django.urls import path
    from . import views

    urlpatterns = [
        path("", views.plant_list, name="plant_list"),
        path("scan/", views.scan, name="scan"),
        path("plant/<int:pk>/", views.plant_detail, name="plant_detail"),
        path("today/", views.today, name="today"),
        path("done/<int:pk>/", views.done, name="done"),
    ]
''')

# ---------------------------------------------------------------- templates
write("templates/base.html", '''
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>Flauna</title>
      <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-green-50 text-gray-800">
      <nav class="bg-green-700 text-white p-4 flex gap-6">
        <a href="/" class="font-bold">🌿 Flauna</a>
        <a href="/scan/">Scan</a>
        <a href="/today/">To do today</a>
      </nav>
      <main class="max-w-2xl mx-auto p-4">{% block content %}{% endblock %}</main>
    </body>
    </html>
''')

write("templates/scan.html", '''
    {% extends "base.html" %}
    {% block content %}
    <h1 class="text-2xl mb-4">Scan a plant</h1>
    <form method="post" enctype="multipart/form-data" class="space-y-3"
          onsubmit="document.getElementById('b').innerText='Analyzing... this can take a while';">
      {% csrf_token %}
      <input name="name" placeholder="Name (optional)" class="border p-2 w-full">
      <input type="file" name="photo" accept="image/*" capture="environment" required>
      <button id="b" class="bg-green-700 text-white px-4 py-2 rounded">Identify</button>
    </form>
    {% endblock %}
''')

write("templates/plant_list.html", '''
    {% extends "base.html" %}
    {% block content %}
    <h1 class="text-2xl mb-4">My plants</h1>
    {% for p in plants %}
    <a href="{% url 'plant_detail' p.id %}" class="flex gap-4 bg-white p-3 rounded mb-2">
      <img src="{{ p.photo.url }}" class="w-20 h-20 object-cover rounded">
      <div><b>{{ p.name }}</b><br>{{ p.species }}</div>
    </a>
    {% empty %}<p>No plants yet. Tap Scan to add one.</p>{% endfor %}
    {% endblock %}
''')

write("templates/plant_detail.html", '''
    {% extends "base.html" %}
    {% block content %}
    <h1 class="text-2xl">{{ plant.name }}</h1>
    <img src="{{ plant.photo.url }}" class="w-full rounded my-3">
    <h2 class="font-bold">Species identification (BioCLIP)</h2>
    <ul class="mb-4">
      {% for s in plant.top3 %}
      <li>{{ s.name }} <i>({{ s.species }})</i> - confidence {{ s.score }}</li>
      {% endfor %}
    </ul>
    <h2 class="font-bold">Diagnosis and care advice</h2>
    <p class="whitespace-pre-line">{{ plant.diagnosis }}</p>
    <p class="text-sm text-gray-500 mt-4">Indicative result generated by a local AI model.</p>
    <h2 class="font-bold mt-4">Reminders</h2>
    <ul>
      {% for t in plant.tasks.all %}
      <li>{{ t.kind }} every {{ t.every_days }} days - next: {{ t.next_due }}</li>
      {% endfor %}
    </ul>
    {% endblock %}
''')

write("templates/today.html", '''
    {% extends "base.html" %}
    {% block content %}
    <h1 class="text-2xl mb-4">To do today</h1>
    {% for t in tasks %}
    <form method="post" action="{% url 'done' t.id %}" class="flex justify-between bg-white p-3 rounded mb-2">
      {% csrf_token %}
      <span>{{ t.kind }} - {{ t.plant.name }}</span>
      <button class="bg-green-700 text-white px-3 rounded">Done ✓</button>
    </form>
    {% empty %}<p>Nothing to do 🎉</p>{% endfor %}
    {% endblock %}
''')

# ---------------------------------------------------------------- migrate
run(sys.executable, "manage.py", "makemigrations", "plants")
run(sys.executable, "manage.py", "migrate")

print("\nDONE. Start the app with:\n  python manage.py runserver 0.0.0.0:8000")
