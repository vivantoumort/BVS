import math
import tkinter as tk
from tkinter import ttk, messagebox

try:
    import tkintermapview
    MAP_OK = True
except ImportError:
    MAP_OK = False



BG = "#1f2d44"
PANEL = "#f4f1eb"
MAP_BG = "#e6efea"
TEXT = "#2b2b2b"
MUTED = "#666666"
GREEN = "#3f735e"
DARK = "#24334d"

EARTH_M = 111_320
G = 9.81


def vector(speed, angle_deg):
    """Перевод скорости и направления в восточную и северную составляющие."""
    angle = math.radians(angle_deg)
    east = speed * math.sin(angle)
    north = speed * math.cos(angle)
    return east, north


def meters_to_coords(lat, east_m, north_m):
    """Перевод смещения в метрах в координаты."""
    dlat = north_m / EARTH_M
    dlon = east_m / (EARTH_M * max(0.2, math.cos(math.radians(lat))))
    return dlat, dlon


def make_ellipse(lat, lon, width_m, height_m, angle_deg, points=60):
    """Создание точек эллипса для отображения на карте."""
    a = width_m / 2
    b = height_m / 2
    angle = math.radians(angle_deg)

    result = []

    for i in range(points):
        t = 2 * math.pi * i / points

        x = a * math.cos(t)
        y = b * math.sin(t)

        east = x * math.sin(angle) + y * math.cos(angle)
        north = x * math.cos(angle) - y * math.sin(angle)

        dlat, dlon = meters_to_coords(lat, east, north)
        result.append((lat + dlat, lon + dlon))

    return result


def calculate_zone(data):

    lat = data["lat"]
    lon = data["lon"]
    height = data["height"]
    speed = data["speed"]
    course = data["course"]
    battery = data["battery"]
    wind_speed = data["wind_speed"]
    wind_from = data["wind_from"]
    reason = data["reason"]

    wind_to = (wind_from + 180) % 360

    if reason == "Потеря связи":
        time_s = max(15, min(120, 20 + battery * 0.8))
        move_k = 0.7
        wind_k = 0.7
        base_error = 60

    elif reason == "Низкий заряд":
        time_s = max(10, min(60, 10 + battery * 0.4))
        move_k = 0.5
        wind_k = 0.7
        base_error = 45

    elif reason == "Отказ двигателя":
        time_s = max(2, math.sqrt(max(0, 2 * height / G)))
        move_k = 0.25
        wind_k = 0.6
        base_error = 35

    else: 
        time_s = max(10, min(90, height / 2))
        move_k = 0.4
        wind_k = 0.7
        base_error = 45

    move_e, move_n = vector(speed * move_k, course)
    wind_e, wind_n = vector(wind_speed * wind_k, wind_to)

    east = (move_e + wind_e) * time_s
    north = (move_n + wind_n) * time_s

    dlat, dlon = meters_to_coords(lat, east, north)

    center_lat = lat + dlat
    center_lon = lon + dlon

    distance = math.hypot(east, north)
    direction = (math.degrees(math.atan2(east, north)) + 360) % 360

    width = 100 + base_error + distance * 0.35 + wind_speed * 5 + height * 0.1
    height_zone = 50 + width * 0.42

    width = min(width, 1200)
    height_zone = min(height_zone, width * 0.75)

    if wind_speed <= 5 and reason != "Потеря связи":
        confidence = "высокая"
    elif wind_speed <= 10:
        confidence = "средняя"
    else:
        confidence = "низкая"

    return {
        "center_lat": center_lat,
        "center_lon": center_lon,
        "distance": distance,
        "direction": direction,
        "width": width,
        "height": height_zone,
        "time": time_s,
        "confidence": confidence
    }


class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("БВС-Поиск")
        self.geometry("1450x760")
        self.minsize(1150, 680)
        self.configure(bg=BG)

        self.result = None
        self.map_objects = []

        self.build_ui()

    def build_ui(self):
        top = tk.Frame(self, bg=BG, height=55)
        top.pack(fill="x", padx=20, pady=(12, 8))
        top.pack_propagate(False)

        tk.Label(
            top,
            text="БВС-Поиск",
            bg=BG,
            fg="#eee6db",
            font=("Segoe UI Semibold", 20)
        ).pack(side="left")

        tk.Label(
            top,
            text="  расчёт примерной зоны поиска потерянного дрона",
            bg=BG,
            fg="#c9d0da",
            font=("Segoe UI", 11)
        ).pack(side="left")

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        body.grid_columnconfigure(0, minsize=330)
        body.grid_columnconfigure(1, weight=1, minsize=580)
        body.grid_columnconfigure(2, minsize=330)
        body.grid_rowconfigure(0, weight=1)

        left = tk.Frame(body, bg=PANEL)
        center = tk.Frame(body, bg=MAP_BG)
        right = tk.Frame(body, bg=PANEL)

        left.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        center.grid(row=0, column=1, sticky="nsew", padx=(0, 18))
        right.grid(row=0, column=2, sticky="nsew")

        self.build_left(left)
        self.build_map(center)
        self.build_right(right)

    def title_label(self, parent, text):
        tk.Label(
            parent,
            text=text,
            bg=parent["bg"],
            fg=TEXT,
            font=("Segoe UI Semibold", 17)
        ).pack(anchor="w", padx=22, pady=(20, 16))

    def build_left(self, parent):
        self.title_label(parent, "Данные потери")

        self.vars = {
            "lat": tk.StringVar(value="62.035500"),
            "lon": tk.StringVar(value="129.675500"),
            "height": tk.StringVar(value="100"),
            "course": tk.StringVar(value="90"),
            "speed": tk.StringVar(value="12"),
            "battery": tk.StringVar(value="20"),
            "wind_speed": tk.StringVar(value="5"),
            "wind_from": tk.StringVar(value="270"),
            "reason": tk.StringVar(value="Потеря связи")
        }

        form = tk.Frame(parent, bg=PANEL)
        form.pack(fill="x", padx=22)

        fields = [
            ("Широта", "lat"),
            ("Долгота", "lon"),
            ("Высота, м", "height"),
            ("Курс, °", "course"),
            ("Скорость, м/с", "speed"),
            ("Заряд, %", "battery"),
            ("Ветер, м/с", "wind_speed"),
            ("Направление ветра, °", "wind_from")
        ]

        for label, key in fields:
            tk.Label(
                form,
                text=label,
                bg=PANEL,
                fg=MUTED,
                font=("Segoe UI", 10)
            ).pack(anchor="w", pady=(4, 1))

            ttk.Entry(
                form,
                textvariable=self.vars[key]
            ).pack(fill="x", ipady=4)

        tk.Label(
            form,
            text="Что случилось",
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI", 10)
        ).pack(anchor="w", pady=(6, 1))

        ttk.Combobox(
            form,
            textvariable=self.vars["reason"],
            state="readonly",
            values=[
                "Потеря связи",
                "Низкий заряд",
                "Отказ двигателя",
                "Аварийная посадка"
            ]
        ).pack(fill="x")

        ttk.Button(
            parent,
            text="Рассчитать зону",
            command=self.calculate
        ).pack(fill="x", padx=22, pady=(20, 8))

        ttk.Button(
            parent,
            text="Сбросить",
            command=self.reset
        ).pack(fill="x", padx=22)

    def build_map(self, parent):
        self.title_label(parent, "Карта")

        holder = tk.Frame(parent, bg=MAP_BG)
        holder.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        if MAP_OK:
            self.map = tkintermapview.TkinterMapView(holder, corner_radius=0)
            self.map.pack(fill="both", expand=True)
            self.map.set_position(62.0355, 129.6755)
            self.map.set_zoom(15)
            self.canvas = None
        else:
            self.map = None
            self.canvas = tk.Canvas(
                holder,
                bg=MAP_BG,
                highlightthickness=0
            )
            self.canvas.pack(fill="both", expand=True)
            self.canvas.bind(
                "<Configure>",
                lambda event: self.draw_simple_map()
            )

        status = (
            "OpenStreetMap"
            if MAP_OK
            else "Для настоящей карты: pip install tkintermapview"
        )

        tk.Label(
            parent,
            text=status,
            bg=MAP_BG,
            fg=MUTED,
            font=("Segoe UI", 9)
        ).pack(pady=(0, 15))

    def build_right(self, parent):
        self.title_label(parent, "Результат")

        self.result_label = tk.Label(
            parent,
            text=(
                "Введите данные слева\n"
                "и нажмите «Рассчитать зону»."
            ),
            justify="left",
            anchor="nw",
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI", 12)
        )
        self.result_label.pack(
            fill="x",
            padx=22,
            pady=(80, 0)
        )

        tk.Label(
            parent,
            text=(
                "Программа показывает примерную\n"
                "область, с которой можно начать поиск."
            ),
            justify="left",
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI", 9)
        ).pack(
            anchor="w",
            padx=22,
            pady=(35, 0)
        )

    def get_number(self, key, name):
        try:
            return float(self.vars[key].get().replace(",", "."))
        except ValueError:
            raise ValueError(f"Поле «{name}» заполнено неверно.")

    def read_data(self):
        data = {
            "lat": self.get_number("lat", "Широта"),
            "lon": self.get_number("lon", "Долгота"),
            "height": self.get_number("height", "Высота"),
            "course": self.get_number("course", "Курс") % 360,
            "speed": self.get_number("speed", "Скорость"),
            "battery": self.get_number("battery", "Заряд"),
            "wind_speed": self.get_number("wind_speed", "Ветер"),
            "wind_from": self.get_number("wind_from", "Направление ветра") % 360,
            "reason": self.vars["reason"].get()
        }

        if not -90 <= data["lat"] <= 90:
            raise ValueError("Широта должна быть от -90 до 90.")

        if not -180 <= data["lon"] <= 180:
            raise ValueError("Долгота должна быть от -180 до 180.")

        if not 0 <= data["battery"] <= 100:
            raise ValueError("Заряд должен быть от 0 до 100%.")

        if data["height"] < 0 or data["speed"] < 0 or data["wind_speed"] < 0:
            raise ValueError("Высота и скорости не могут быть отрицательными.")

        return data

    def calculate(self):
        try:
            data = self.read_data()
            self.result = calculate_zone(data)
        except ValueError as error:
            messagebox.showerror("Ошибка", str(error))
            return

        r = self.result

        self.result_label.config(
            text=(
                f"Уверенность: {r['confidence']}\n\n"
                f"Расчётный центр:\n"
                f"{r['center_lat']:.6f}, {r['center_lon']:.6f}\n\n"
                f"Смещение:\n"
                f"{r['distance']:.0f} м\n\n"
                f"Направление:\n"
                f"{r['direction']:.0f}°\n\n"
                f"Зона поиска:\n"
                f"{r['width']:.0f} × {r['height']:.0f} м"
            )
        )

        self.update_map(data)

    def clear_map(self):
        for obj in self.map_objects:
            try:
                obj.delete()
            except Exception:
                pass
        self.map_objects.clear()

    def update_map(self, data):
        if MAP_OK:
            self.clear_map()

            last = self.map.set_marker(
                data["lat"],
                data["lon"],
                text="Последняя точка"
            )

            center = self.map.set_marker(
                self.result["center_lat"],
                self.result["center_lon"],
                text="Центр поиска"
            )

            polygon_points = make_ellipse(
                self.result["center_lat"],
                self.result["center_lon"],
                self.result["width"],
                self.result["height"],
                self.result["direction"]
            )

            polygon = self.map.set_polygon(
                polygon_points,
                fill_color="#b9d1c5",
                outline_color=GREEN,
                border_width=2
            )

            self.map_objects = [last, center, polygon]

            mid_lat = (data["lat"] + self.result["center_lat"]) / 2
            mid_lon = (data["lon"] + self.result["center_lon"]) / 2

            self.map.set_position(mid_lat, mid_lon)

            if self.result["distance"] < 200:
                self.map.set_zoom(17)
            elif self.result["distance"] < 700:
                self.map.set_zoom(16)
            else:
                self.map.set_zoom(15)

        else:
            self.draw_simple_map()

    def draw_simple_map(self):
        if self.canvas is None:
            return

        self.canvas.delete("all")

        w = max(100, self.canvas.winfo_width())
        h = max(100, self.canvas.winfo_height())

        cx = w / 2
        cy = h / 2

        for x in range(0, w, 80):
            self.canvas.create_line(x, 0, x, h, fill="#d7e1dc")

        for y in range(0, h, 80):
            self.canvas.create_line(0, y, w, y, fill="#d7e1dc")

        if self.result is None:
            self.canvas.create_oval(
                cx - 150, cy - 75,
                cx + 150, cy + 75,
                outline=GREEN,
                width=3,
                fill="#c7d9d0"
            )

            self.canvas.create_oval(
                cx - 8, cy - 8,
                cx + 8, cy + 8,
                fill=DARK,
                outline=DARK
            )
            return

        distance = max(self.result["distance"], 1)
        shift = min(distance * 0.25, 120)

        angle = math.radians(self.result["direction"])

        px = cx + shift * math.sin(angle)
        py = cy - shift * math.cos(angle)

        rw = min(self.result["width"] * 0.20, 220)
        rh = min(self.result["height"] * 0.20, 110)

        self.canvas.create_oval(
            px - rw / 2,
            py - rh / 2,
            px + rw / 2,
            py + rh / 2,
            outline=GREEN,
            width=3,
            fill="#c7d9d0"
        )

        self.canvas.create_line(
            cx, cy, px, py,
            fill=GREEN,
            width=2,
            arrow="last"
        )

        self.canvas.create_oval(
            cx - 8, cy - 8,
            cx + 8, cy + 8,
            fill=DARK,
            outline=DARK
        )

        self.canvas.create_oval(
            px - 5, py - 5,
            px + 5, py + 5,
            fill=GREEN,
            outline=GREEN
        )

    def reset(self):
        defaults = {
            "lat": "62.035500",
            "lon": "129.675500",
            "height": "100",
            "course": "90",
            "speed": "12",
            "battery": "20",
            "wind_speed": "5",
            "wind_from": "270",
            "reason": "Потеря связи"
        }

        for key, value in defaults.items():
            self.vars[key].set(value)

        self.result = None

        self.result_label.config(
            text=(
                "Введите данные слева\n"
                "и нажмите «Рассчитать зону»."
            )
        )

        if MAP_OK:
            self.clear_map()
            self.map.set_position(62.0355, 129.6755)
            self.map.set_zoom(15)
        else:
            self.draw_simple_map()


if __name__ == "__main__":
    App().mainloop()
