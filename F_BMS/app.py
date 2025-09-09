import os, datetime, requests
import cv2
from flask import Flask, request, session, redirect, url_for, render_template, flash, jsonify, Response
from flask_sqlalchemy import SQLAlchemy
import threading
import queue
import json
import time
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify
from flask import Flask, jsonify, render_template
import requests
import pandas as pd


app = Flask(__name__)
app.config['SECRET_KEY'] = 'supersecretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////data/unified_platform.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

HA_URL = "http://10.0.8.228:8123/api"
HA_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJhZDE3YmE5MmJkODk0OWQ5YjI2NTc2OGU1MGMxMTNjMiIsImlhdCI6MTc1Njc1NjA4MiwiZXhwIjoyMDcyMTE2MDgyfQ.yrX6oGwsK7l8PWlQe9pjYmYOtQY7p6RceMnHRrz0x4c"


# API_KEY = "mCYkdNbXqLAoUA9UWf3WCeOETo7M4ClY"
# ACCESS_TOKEN = "m4D2pHVuLMHutLs_eLakkO1z"


HEADERS = {
    "Authorization": f"Bearer {HA_TOKEN}",
    "Content-Type": "application/json"
}


HA_URL = os.environ.get("HA_URL")
HA_TOKEN = os.environ.get("HA_TOKEN")

HEADERS = {
    "Authorization": f"Bearer {HA_TOKEN}",
    "Content-Type": "application/json"
}



@app.route("/")
def root():
    # أول ما يفتح على "/" يوديه تلقائي لـ /home
    return redirect(url_for("login"))

@app.route("/home")
# @login_required
def home():
    return render_template("home.html")  # هنا صفحة الهوم الخاصة فيك

@app.route("/sections")
def sections():
    return render_template("sections.html")  # صفحة الأقسام

class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    reserved_by = db.Column(db.String(100), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)

    # حقول التكرار
    repeat = db.Column(db.String(20), default="none")   # none, daily, weekly
    repeat_until = db.Column(db.DateTime, nullable=True)

# ---------------- Database ----------------
class Setting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), unique=True, nullable=False)
    value = db.Column(db.String(512), nullable=False)

class Camera(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    rtsp_url = db.Column(db.String(1024), nullable=False)
    note = db.Column(db.String(255), default='')

with app.app_context():
    db.create_all()

# ---------------- Helper Functions ----------------
def get_setting(key, default=""):
    s = Setting.query.filter_by(key=key).first()
    return s.value if s else default

def set_setting(key, value):
    s = Setting.query.filter_by(key=key).first()
    if not s:
        s = Setting(key=key, value=value)
        db.session.add(s)
    else:
        s.value = value
    db.session.commit()



    # ecobee 
API_KEY = "mCYkdNbXqLAoUA9UWf3WCeOETo7M4ClY"
TOKEN_FILE = "templates/ecobee_tokens.json"
BASE_URL = "https://api.ecobee.com"


def refresh_tokens():
    with open(TOKEN_FILE, "r") as f:
        tokens = json.load(f)[0]
    refresh_token = tokens['refresh_token']
    response = requests.post(f"{BASE_URL}/token", params={
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": API_KEY
    })
    new_tokens = response.json()
    with open(TOKEN_FILE, "w") as f:
        json.dump([new_tokens], f)
    return new_tokens['access_token']


def get_thermostat_data(access_token):
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "Authorization": f"Bearer {access_token}"
    }
    params = {
        "format": "json",
        "body": json.dumps({
            "selection": {
                "selectionType": "registered",
                "selectionMatch": "",
                "includeRuntime": True,
                "includeSensors": True
            }
        })
    }
    response = requests.get(f"{BASE_URL}/1/thermostat", headers=headers, params=params)
    return response.json()
# ecobee 

# ---------------- login ----------------

# Decorator لحماية الصفحات
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("auth_token"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


def fahrenheit_to_celsius(f):
        if f is None:
            return None
        return round((f - 32) * 5 / 9, 1)

temp_f = 680 / 10        # 68°F
temp_c = (temp_f - 32) * 5 / 9  # 20°C تقريباً
@app.route("/ecobee/api")
@login_required
def ecobee_api():
    try:
        access_token = refresh_tokens()
        data = get_thermostat_data(access_token)

        entries = []
        for t in data.get('thermostatList', []):
            runtime = t.get('runtime', {})

            # درجات الحرارة
            actual_f = runtime.get('actualTemperature', 0) / 10
            desired_f = runtime.get('desiredCool', 0) / 10

            actual_c = fahrenheit_to_celsius(actual_f)
            desired_c = fahrenheit_to_celsius(desired_f)

            entries.append({
                "zone": t['name'],
                "hvac_state": t.get('settings', {}).get('hvacMode', 'unknown'),
                "current_temp": round(actual_c, 1),
                "set_temp": round(desired_c, 1),
                "humidity": runtime.get('humidity', 'N/A'),
                "isConnected": runtime.get('connected', False)
            })

        return jsonify(entries)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


#---------------- Convert F to C ----------------

# def fahrenheit_to_celsius(f):
#         if f is None:
#             return None
#         return round((f - 32) * 5 / 9, 1)
# إرسال أمر لتغيير درجة الحرارة
@login_required
def set_ecobee_temp(thermostat_id, temperature_c):
    access_token = refresh_tokens()
    # تحويل Celsius إلى 0.1°F * 10 لأن Ecobee يستخدم درجات ×10
    temp_f = round((temperature_c * 9/5 + 32) * 10)
    
    payload = {
        "selection": {
            "selectionType": "thermostats",
            "selectionMatch": thermostat_id
        },
        "thermostat": {
            "runtime": {
                # "desiredHeat": temp_f,  # لتدفئة
                "desiredCool": temp_f   # للتبريد
            }
        }
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }

    # نرسل الأمر للـ Ecobee API
    response = requests.post(
        "https://api.ecobee.com/1/thermostat",
        headers=headers,
        json=payload
    )
    return response.json()

# راوت لتحديث درجة الحرارة من الزر
@app.route("/ecobee/set_temp", methods=["POST"])
@login_required
def ecobee_set_temp():
    data = request.json
    thermostat_id = data.get("thermostat_id")
    new_temp = data.get("temperature_c")

    if not thermostat_id or new_temp is None:
        return jsonify({"error": "Missing parameters"}), 400

    try:
        result = set_ecobee_temp(thermostat_id, new_temp)
        return jsonify({"success": True, "result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500



# ---------------- SmartAir REST Client ----------------
class SmartAirREST:
    def __init__(self, base_url, username, password, verify_tls=False):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.verify_tls = verify_tls
        self.s = requests.Session()
        self.logged_in = False

    def login(self):
        r = self.s.post(f"{self.base_url}/TesaSmartairPlatform/REST/user/login",
                        json={"userName": self.username, "password": self.password},
                        verify=self.verify_tls)
        r.raise_for_status()
        if "JSESSIONID" in self.s.cookies:
            self.logged_in = True
        return self.logged_in

    # --- Door Actions ---
    def door_open(self, door_id: int):
        return self._door_action(door_id, "DOOR_OPEN")

    def door_close(self, door_id: int):
        return self._door_action(door_id, "DOOR_CLOSE")

    def door_passage(self, door_id: int):
        return self._door_action(door_id, "DOOR_PASSAGE")

    def _door_action(self, door_id: int, action: str):
        r = self.s.post(f"{self.base_url}/TesaSmartairPlatform/REST/wirelessDoor/{door_id}",
                        data=action,
                        headers={"Content-Type":"application/json"},
                        verify=self.verify_tls)
        r.raise_for_status()
        return r.text

    # --- Users ---
    def user_list(self, first=0, pageSize=999):
        r = self.s.get(f"{self.base_url}/TesaSmartairPlatform/REST/user?first={first}&pageSize={pageSize}&excludeDeleted=false",
                       verify=self.verify_tls,
                       headers={"Accept":"application/json"})
        return r.json().get("userData", [])

    def add_user(self, name, email, expire_days=365):
        expire_date = (datetime.datetime.utcnow() + datetime.timedelta(days=expire_days)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        payload = {
            "deleted": False,
            "grants": [],
            "userType": "USER_STANDARD",
            "userEmailAddress": email,
            "userName": name,
            "dateExpiration": expire_date
        }
        r = self.s.post(f"{self.base_url}/TesaSmartairPlatform/REST/user",
                        json=payload,
                        verify=self.verify_tls)
        return r.json()

    def get_doors(self, first=0, pageSize=999, sortField="doorName"):
        r = self.s.get(f"{self.base_url}/TesaSmartairPlatform/REST/wirelessDoor?first={first}&pageSize={pageSize}&sortField={sortField}&sortOrder=ASC",
                       verify=self.verify_tls,
                       headers={"Accept":"application/json"})
        r.raise_for_status()
        return r.json().get("wirelessDoor", [])

def get_smartair():
    client = SmartAirREST(
        get_setting("smartair_host", "https://10.0.9.124:8181"),
        get_setting("smartair_operator", "fahad"),
        get_setting("smartair_password", "102030"),
        verify_tls=False
    )
    client.login()
    return client

# ---------------- Alarm System (SSE) ----------------
alarm_subscribers_lock = threading.Lock()
alarm_subscribers = []

def broadcast_alarm(event: dict):
    """Send alarm event to all subscribers."""
    with alarm_subscribers_lock:
        dead = []
        for q in alarm_subscribers:
            try:
                q.put_nowait(event)
            except Exception:
                dead.append(q)
        for q in dead:
            alarm_subscribers.remove(q)

@app.route("/events")
def sse_events():
    client_q = queue.Queue(maxsize=100)
    with alarm_subscribers_lock:
        alarm_subscribers.append(client_q)

    def gen():
        yield "event: ping\ndata: {}\n\n"
        try:
            while True:
                try:
                    event = client_q.get(timeout=15)
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                except queue.Empty:
                    yield "event: ping\ndata: {}\n\n"
        finally:
            with alarm_subscribers_lock:
                if client_q in alarm_subscribers:
                    alarm_subscribers.remove(client_q)

    return Response(gen(), mimetype="text/event-stream")

# ---------------- Camera Worker ----------------
class CameraWorker:
    """Handles RTSP feed and motion detection per camera."""
    def __init__(self, cam: Camera):
        self.cam = cam
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.last_frame = None
        self.motion_detected = False
        self.stop_flag = threading.Event()
        self.cooldown_until = 0

    def start(self):
        if not self.thread.is_alive():
            self.thread.start()

    def run(self):
        cap = cv2.VideoCapture(self.cam.rtsp_url)
        if not cap.isOpened():
            print(f"[ERROR] Cannot open camera: {self.cam.name}")
            return

        bg_subtractor = cv2.createBackgroundSubtractorMOG2(history=400, varThreshold=32, detectShadows=True)

        while not self.stop_flag.is_set():
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.2)
                continue

            self.last_frame = frame
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            fg_mask = bg_subtractor.apply(gray)
            thresh = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)[1]
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours and time.time() > self.cooldown_until:
                self.motion_detected = True
                self.cooldown_until = time.time() + 5  # 5s cooldown
                broadcast_alarm({
                    "cam_id": self.cam.id,
                    "name": self.cam.name,
                    "msg": "Motion detected!"
                })
            time.sleep(0.05)

    def get_jpeg(self):
        if self.last_frame is None:
            return None
        ret, buffer = cv2.imencode('.jpg', self.last_frame)
        if not ret:
            return None
        return buffer.tobytes()

camera_workers = {}
def start_all_cameras():
    cams = Camera.query.all()
    for cam in cams:
        if cam.id not in camera_workers:
            worker = CameraWorker(cam)
            worker.start()
            camera_workers[cam.id] = worker

# ---------------- Routes ----------------

#ecobbee control page
@app.route("/ecobee/control")
@login_required
def ecobee_control_page():
    return render_template("ecobee_control.html")


#ecobee main page

@app.route("/ecobee")
@login_required
def ecobee():
    return render_template("ecobee.html")














# ---------------- HASS ----------------

@app.route("/state/<entity_id>")
@login_required
def get_state(entity_id):
    # ترجع حالة الجهاز من HA أو DB أو الكاش
    return jsonify({"entity_id": entity_id, "state": "on"}) 

# --- SmartAir Doors ---
@app.route("/smartair/doors", methods=["GET","POST"])
@login_required
def smartair_doors():
    client = get_smartair()
    if request.method == "POST":
        door_id = request.form.get("door_id", type=int)
        action = request.form.get("action")
        try:
            if action == "open":
                res = client.door_open(door_id)
            elif action == "close":
                res = client.door_close(door_id)
            elif action == "passage":
                res = client.door_passage(door_id)
            else:
                res = "Unknown action"
            flash(f"تم تنفيذ {action} على الباب {door_id}: {res}", "success")
        except Exception as e:
            flash(f"خطأ عند تنفيذ {action} على الباب {door_id}: {str(e)}", "danger")
        return redirect(url_for("smartair_doors"))

    try:
        doors = client.get_doors()
    except Exception as e:
        doors = []
        flash(f"خطأ عند جلب الأبواب: {str(e)}", "danger")
    return render_template("doors.html", doors=doors)




# --- Login / Logout / Users / Add User / Encode / Delete User ---
@app.route("/", methods=["GET","POST"])

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        url = "https://bc9998:8181/TesaSmartairPlatform/REST/user/login"
        try:
            r = requests.post(url,
                              json={"userName": username,"password": password},
                              headers={"Content-Type":"application/json"},
                              verify=False)
            # لا تعتمد على raise_for_status فقط
            data = r.json()
            # افترض أن SmartAir يعطي field اسمه "success" أو "error" في الرد
            if r.status_code == 200 and "JSESSIONID" in r.cookies:
                session["auth_token"] = r.cookies.get("JSESSIONID")
                flash("Login successful", "success")
                return redirect(url_for("users"))
            else:
                flash(":( اكتب زين ولا ماعندك يوزر بالاساس !", "danger")
        except Exception as e:
            flash(f"خطأ في الاتصال بالـ SmartAir: {str(e)}", "danger")

    return render_template("login.html")


@app.route("/logout")
# @login_required
def logout():
    session.pop("auth_token", None)
    flash("Logged out","info")
    return redirect(url_for("login"))


@app.route("/users")
@login_required

def users():
    token = session.get("auth_token")
    if not token:
        return redirect(url_for("login"))
    client = get_smartair()
    users = client.user_list()
    return render_template("users.html", users=users)


@app.route("/add_user", methods=["GET", "POST"])
@login_required

def add_user():
    token = session.get("auth_token")
    if not token:
        return redirect(url_for("login"))  # صححت من "index" إلى "login"

    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        expiration = request.form.get("expiration")  # صيغة: YYYY-MM-DDTHH:MM

        # تحويل التاريخ إلى صيغة ISO إذا تم إدخاله
        if expiration:
            expiration_iso = f"{expiration}:00.000Z"
        else:
            expiration_iso = "2025-12-31T23:59:00.000Z"

        url = "https://bc9998:8181/TesaSmartairPlatform/REST/user"
        headers = {
            "Cookie": f"JSESSIONID={token}",
            "Content-Type": "application/json; charset=UTF-8"
        }
        payload = {
            "deleted": False,
            "grants": [],
            "userType": "USER_STANDARD",
            "userName": name,
            "userEmailAddress": email,
            "UOCAccess": True,
            "enkReles": 1,
            "userCarrier": "CAR_PROX",
            "dateExpiration": expiration_iso
        }

        try:
            response = requests.post(url, json=payload, headers=headers, verify=False)
            response.raise_for_status()
            flash("User added successfully", "success")
        except Exception as e:
            flash(f"Error adding user: {str(e)}", "danger")

        return redirect(url_for("users"))

    # ---------------- HTML Form ----------------

    return render_template("add_user.html")


@app.route("/screenshot_camera/<int:cam_id>", methods=["POST"])
def screenshot_camera(cam_id):
    cam = Camera.query.get(cam_id)
    if not cam:
        return jsonify({"success": False, "error": "Camera not found"})
    
    # جرب فتح الفيديو
    cap = cv2.VideoCapture(cam.rtsp_url)
    if not cap.isOpened():
        return jsonify({"success": False, "error": "Cannot open camera stream"})
    
    ret, frame = cap.read()
    cap.release()
    
    if not ret:
        return jsonify({"success": False, "error": "Failed to capture frame"})
    
    os.makedirs("screenshots", exist_ok=True)
    filename = f"screenshots/{cam.name}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    cv2.imwrite(filename, frame)
    
    return jsonify({"success": True, "filename": filename})
@app.route("/encode/<int:user_id>")
@login_required

def encode(user_id):
    token = session.get("auth_token")
    if not token:
        return redirect(url_for("login"))
    url = "https://bc9998:8181/TesaSmartairPlatform/REST/encode/encode"
    headers = {"Cookie": f"JSESSIONID={token}","Content-Type":"application/json; charset=UTF-8"}
    payload = {"technology": None,"agentId": None,"encoderId": None,"types":["ENCODING_TYPE_OPENOW"],"copy": True,"userId": user_id}
    try:
        r = requests.post(url, json=payload, headers=headers, verify=False)
        if r.status_code==200:
            flash(f"Key sent to user {user_id} successfully","success")
        else:
            flash(f"Failed to send key: {r.text}","danger")
    except Exception as e:
        flash(f"Error: {str(e)}","danger")
    return redirect(url_for("users"))

@app.route("/delete_user/<int:user_id>")
@login_required
def delete_user(user_id):
    token = session.get("auth_token")
    if not token:
        return redirect(url_for("login"))
    url = f"https://bc9998:8181/TesaSmartairPlatform/REST/user/{user_id}"
    headers = {"Cookie": f"JSESSIONID={token}"}
    requests.delete(url, headers=headers, verify=False)
    flash("User deleted","info")
    return redirect(url_for("users"))

# --- Home ---
# @app.route("/home")
# @login_required
# def home():
#     # رابط iframe للخريطة
#     floorplan_url = "https://lx3msmkttvho12gfxbcxmuxs7jqbvcm.ui.nabu.casa/dashboard-floorplan/canon?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiIyMjdhNjk5NjE1Yzk0ZGFjYTJiZDYyNTI1MWRkMjMxMyIsImlhdCI6MTc1Njc1MzU4MCwiZXhwIjoyMDcyMTEzNTgwfQ.8D_RjyyZWHQMPoEm3wNkpf7D0W3OX3U6z74n19rGfjw"
#     return render_template("home.html", floorplan_url=floorplan_url)

@app.route("/edit_reservation/<int:id>", methods=["GET", "POST"])
@login_required
def edit_reservation(id):
    reservation = Reservation.query.get_or_404(id)
    if request.method == "POST":
        reservation.room = request.form.get("room")
        reservation.title = request.form.get("title")
        reservation.reserved_by = request.form.get("reserved_by")
        reservation.start_time = datetime.fromisoformat(request.form.get("start_time"))
        reservation.end_time = datetime.fromisoformat(request.form.get("end_time"))
        db.session.commit()
        flash("✏️ تم تعديل الحجز", "info")
        return redirect(url_for("meetings"))

    return render_template("edit_meeting.html", reservation=reservation)

# --- Settings ---
@app.route("/settings", methods=["GET","POST"])
@login_required
def settings():
    if request.method=="POST":
        set_setting("smartair_host", request.form.get("host"))
        set_setting("smartair_operator", request.form.get("op"))
        set_setting("smartair_password", request.form.get("pw"))
        flash("Settings saved","success")
        return redirect(url_for("settings"))
    return render_template("settings.html",
                           host=get_setting("smartair_host"),
                           op=get_setting("smartair_operator"),
                           pw=get_setting("smartair_password"))


def fahrenheit_to_celsius(f):
    if f is None:
        return None
    return round((f - 32) * 5 / 9, 1)

def c_to_f_tenths(c):
    return round((c * 9/5 + 32) * 10)


# --- Cameras ---
@app.route("/cameras", methods=["GET","POST"])
@login_required
def cameras():
    if request.method == "POST":
        name = request.form.get("name")
        url_cam = request.form.get("rtsp_url")
        note = request.form.get("note")
        db.session.add(Camera(name=name, rtsp_url=url_cam, note=note))
        db.session.commit()
        flash("Camera added","success")
        start_all_cameras()
        return redirect(url_for("cameras"))
    start_all_cameras()
    cams = Camera.query.all()
    return render_template("cameras.html", cams=cams)

@app.route("/video_feed/<int:cam_id>")
@login_required
def video_feed(cam_id):
    worker = camera_workers.get(cam_id)
    if not worker:
        return "Camera not found", 404
    def gen():
        while True:
            frame = worker.get_jpeg()
            if frame:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            else:
                time.sleep(0.1)
    return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route("/delete_camera/<int:cam_id>", methods=["POST"])
@login_required
def delete_camera(cam_id):
    cam = Camera.query.get_or_404(cam_id)
    if cam.id in camera_workers:
        camera_workers[cam.id].stop_flag.set()
        del camera_workers[cam.id]
    db.session.delete(cam)
    db.session.commit()
    flash(f"Camera '{cam.name}' deleted", "warning")
    return redirect(url_for("cameras"))
# --- Meetings / Reservations ---
@app.route("/meetings", methods=["GET", "POST"])
@login_required
def meetings():
    if request.method == "POST":
        room = request.form.get("room")
        title = request.form.get("title")
        reserved_by = request.form.get("reserved_by")
        start_time = datetime.fromisoformat(request.form.get("start_time"))
        end_time = datetime.fromisoformat(request.form.get("end_time"))

        # تحقق من صحة التواريخ
        if end_time <= start_time:
            flash("⚠️ تاريخ النهاية يجب أن يكون بعد تاريخ البداية", "danger")
            return redirect(url_for("meetings"))

        repeat = request.form.get("repeat", "none")
        repeat_until_str = request.form.get("repeat_until")
        repeat_until = datetime.fromisoformat(repeat_until_str) if repeat_until_str else None

        # قائمة التواريخ للحجز (تشمل التكرار)
        booking_times = [(start_time, end_time)]
        if repeat != "none" and repeat_until:
            current_start, current_end = start_time, end_time
            while True:
                if repeat == "daily":
                    current_start += timedelta(days=1)
                    current_end += timedelta(days=1)
                elif repeat == "weekly":
                    current_start += timedelta(weeks=1)
                    current_end += timedelta(weeks=1)
                else:
                    break

                if current_start > repeat_until:
                    break

                booking_times.append((current_start, current_end))

        # تحقق من التعارض لكل حجز
        for b_start, b_end in booking_times:
            conflict = Reservation.query.filter(
                Reservation.room == room,
                Reservation.start_time < b_end,
                Reservation.end_time > b_start
            ).first()
            if conflict:
                flash(f"⚠️ لا يمكن إضافة الحجز، يتعارض مع '{conflict.title}' بتاريخ {conflict.start_time} → {conflict.end_time}", "danger")
                return redirect(url_for("meetings"))

        # حفظ الحجوزات (مع التكرار)
        for b_start, b_end in booking_times:
            db.session.add(Reservation(
                room=room,
                title=title,
                reserved_by=reserved_by,
                start_time=b_start,
                end_time=b_end,
                repeat="none"  # الحجز النهائي يُسجل بدون تكرار
            ))
        db.session.commit()

        flash("✅ تم إنشاء الحجز بنجاح", "success")
        return redirect(url_for("meetings"))

    # عرض كل الحجوزات
    reservations = Reservation.query.order_by(Reservation.start_time.desc()).all()
    return render_template("meeting.html", reservations=reservations)

@app.route("/delete_reservation/<int:id>", methods=["POST"])
@login_required
def delete_reservation(id):
    reservation = Reservation.query.get_or_404(id)
    db.session.delete(reservation)
    db.session.commit()
    flash("🗑️ تم حذف الحجز", "warning")
    return redirect(url_for("meetings"))
@app.route("/calendar")
@login_required
def calendar():
    current_date_str = request.args.get("date")
    if current_date_str:
        current_date = datetime.strptime(current_date_str, "%Y-%m-%d").date()
    else:
        current_date = datetime.today().date()

    start_of_week = current_date - timedelta(days=current_date.weekday())  # بداية الأسبوع
    end_of_week = start_of_week + timedelta(days=6)

    reservations = Reservation.query.filter(
        Reservation.start_time >= start_of_week,
        Reservation.end_time <= end_of_week
    ).all()

    return render_template(
        "calendar.html",
        reservations=reservations,
        current_date=current_date,
        start_of_week=start_of_week,
        end_of_week=end_of_week,
        timedelta=timedelta  # <---- هذا هو المفتاح
    )


@app.route("/smartair/doors/list")
@login_required
def doors_list():
    client = get_smartair()
    doors = client.get_doors()
    return {"doors": doors}

@app.route("/smartair/assign_doors/<int:user_id>", methods=["POST"])
@login_required
def assign_doors(user_id):
    client = get_smartair()
    data = request.json
    doors = data.get("doors", [])
    results = []
    for door_id in doors:
        # PUT request لإعطاء تصريح
        url = f"{client.base_url}/TesaSmartairPlatform/REST/plan/lockingPlan"
        params = {
            "userId": user_id,
            "doorId": door_id,
            "canOpen": True,
            "codTimetable": 15,
            "privacyOverride": False
        }
        r = client.s.put(url, params=params, verify=False)
        results.append({"doorId": door_id, "status": r.status_code})
    return {"results": results}


# ---------------- HASS ----------------



@app.route("/floorplan")
@login_required
def floorplan():
    return render_template("floorplan.html")

# route لتغيير حالة أي كيان
@app.route("/toggle/<entity_id>", methods=["POST"])
@login_required
def toggle_entity(entity_id):
    url = f"{HA_URL}/services/homeassistant/toggle"
    payload = {"entity_id": entity_id}
    response = requests.post(url, headers=HEADERS, json=payload)
    if response.ok:
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "error", "details": response.text}), 500

HA_URL = "http://10.0.8.228:8123/api"
HA_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJhZDE3YmE5MmJkODk0OWQ5YjI2NTc2OGU1MGMxMTNjMiIsImlhdCI6MTc1Njc1NjA4MiwiZXhwIjoyMDcyMTE2MDgyfQ.yrX6oGwsK7l8PWlQe9pjYmYOtQY7p6RceMnHRrz0x4c"


headers = {
    "Authorization": f"Bearer {HA_TOKEN}",
    "Content-Type": "application/json"
}


def get_ecobee_devices():
    try:
        r = requests.get(HA_URL, headers=headers, timeout=5)
        r.raise_for_status()
        data = r.json()
        # استثناء كيان محدد + استبعاد غير المتاحين
        return [
            d for d in data
            if 'climate' in d['entity_id']
            and d['state'] != 'unavailable'
            and d['entity_id'] != 'climate.gr_acunit_3017_02_8c51'
        ]
    except Exception as e:
        print("Error fetching devices:", e)
        return []
# Route لإرجاع البيانات على شكل JSON
@app.route("/devices")
def devices():
    return jsonify(get_ecobee_devices())

# Route لتغيير درجة الحرارة
@app.route("/set_temperature/<entity_id>", methods=["POST"])
def set_temperature(entity_id):
    temp = request.json.get("temperature")
    if temp is None:
        return jsonify({"error": "temperature not provided"}), 400
    url = f"{HA_URL}/../services/climate/set_temperature"  # أو رابط كامل للخدمة
    payload = {
        "entity_id": entity_id,
        "temperature": float(temp)
    }
    try:
        r = requests.post(url, headers=HEADERS, json=payload, timeout=5)
        r.raise_for_status()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
# --- Ecobee Dashboard ---

@app.route("/ecobee_dashboard")
@login_required
def ecobee_dashboard():
    """
    صفحة جديدة خاصة بأجهزة Ecobee
    """
    devices = get_ecobee_devices()
    return render_template("ecobee.html", devices=devices)

# ---------------- Main ----------------
# if __name__=="__main__":
#     app.run(host="0.0.0.0", port=5000, debug=True)



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)