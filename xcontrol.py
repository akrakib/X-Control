# XControl by akrakib - USB diye Android phone-er screen Windows-e dekha ar mouse/keyboard diye control kora
import sys, os, re, time, queue, shutil, subprocess, threading, struct, socket, random, collections
from datetime import datetime
from PySide6 import QtCore, QtGui, QtWidgets
import av

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def base_dir():
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def find_adb():
    exe = "adb.exe" if os.name == "nt" else "adb"
    p = os.path.join(base_dir(), "bin", exe)
    if os.path.exists(p):
        return p, True
    return (shutil.which("adb") or "adb"), False


ADB, ADB_BUNDLED = find_adb()


def adb(*args, timeout=15):
    return subprocess.run([ADB, *args], capture_output=True, timeout=timeout,
                          creationflags=CREATE_NO_WINDOW)


def adb_missing():
    return not (os.path.exists(ADB) or shutil.which(ADB))


def device_state():
    """'device' | 'unauthorized' | 'offline' | None (kono device nai)"""
    try:
        out = adb("devices").stdout.decode(errors="ignore").splitlines()[1:]
    except Exception:
        return None
    for line in out:
        parts = line.split()
        if len(parts) >= 2:
            return parts[1]
    return None


def get_screen_size():
    out = adb("shell", "wm", "size").stdout.decode(errors="ignore")
    m = re.findall(r"(\d+)x(\d+)", out)
    if not m:
        return None
    w, h = m[-1]  # shesh-ta "Override size" thakle seta, na hole Physical
    return int(w), int(h)


def stream_size(w, h, max_side=1280):
    s = min(1.0, max_side / max(w, h))
    return max(16, int(w * s) // 16 * 16), max(16, int(h * s) // 16 * 16)


class InputShell:
    """Ekta persistent 'adb shell' rekhe tate command pathay (protibar adb process shuru korar cheye druto)."""

    def __init__(self):
        self.proc = None
        self.log = None  # callback(str), thread-safe hote hobe
        self.q = queue.Queue()
        threading.Thread(target=self._loop, daemon=True).start()

    def _log(self, msg):
        if self.log:
            try:
                self.log(msg)
            except Exception:
                pass

    def send(self, cmd):
        self._log("Sent: " + cmd)
        self.q.put(cmd)

    def _read(self, proc):
        try:
            for line in proc.stdout:
                t = line.decode(errors="ignore").strip()
                if t:
                    self._log("PHONE: " + t[:160])
        except Exception:
            pass

    def _ensure(self):
        if self.proc is None or self.proc.poll() is not None:
            self.proc = subprocess.Popen([ADB, "shell"], stdin=subprocess.PIPE,
                                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                         creationflags=CREATE_NO_WINDOW)
            threading.Thread(target=self._read, args=(self.proc,), daemon=True).start()

    def _loop(self):
        while True:
            cmd = self.q.get()
            try:
                self._ensure()
                self.proc.stdin.write((cmd + "\n").encode())
                self.proc.stdin.flush()
            except Exception as e:
                self._log(f"Shell error: {e}")
                self.proc = None

    def close(self):
        try:
            if self.proc:
                self.proc.kill()
        except Exception:
            pass


def text_cmd(text):
    t = text.replace("'", "'\\''").replace(" ", "%s")
    return f"input text '{t}'"


# ======================= scrcpy-server control (druto input) =======================
SCRCPY_VERSION = "5.0.1"  # server jar-er version-er sathe hubohu milte hobe
SERVER_REMOTE = "/data/local/tmp/scrcpy-server.jar"
FINGER_ID = -2  # -1 holo mouse, tai finger hishebe -2


def find_server():
    p = os.path.join(base_dir(), "bin", "scrcpy-server.jar")
    return p if os.path.exists(p) else None


# Message format: scrcpy v5.0.1 ControlMessageReader.java onujayi (big-endian)
def m_touch(action, x, y, w, h, pressure):
    buttons = 0 if action == 1 else 1
    return struct.pack(">BBqiiHHHii", 2, action, FINGER_ID, x, y, w, h, pressure, 1, buttons)


def m_key(action, keycode):
    return struct.pack(">BBiii", 0, action, keycode, 0, 0)


def m_text(text):
    b = text.encode("utf-8")
    return struct.pack(">BI", 1, len(b)) + b


def m_scroll(x, y, w, h, v):
    vs = max(-32768, min(32767, int(v / 16.0 * 32768)))
    return struct.pack(">BiiHHhhi", 3, x, y, w, h, 0, vs, 0)


def m_clipboard(text, paste=True):
    b = text.encode("utf-8")
    return struct.pack(">BqBI", 9, 0, 1 if paste else 0, len(b)) + b


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class ScrcpyLink(threading.Thread):
    """scrcpy-server (shudhu control, video/audio bondho) phone-e chalay ar socket diye input pathay."""

    def __init__(self, log):
        super().__init__(daemon=True)
        self.log = log
        self.running = True
        self.sock = None
        self.proc = None
        self.port = None
        self.dead = threading.Event()
        self.sendq = queue.Queue()

    def connected(self):
        return self.sock is not None and not self.dead.is_set()

    def send(self, data):
        if self.connected():
            self.sendq.put(data)

    def run(self):
        while self.running:
            if adb_missing() or device_state() != "device":
                time.sleep(1)
                continue
            jar = find_server()
            if not jar:
                self.log("scrcpy-server.jar nei, adb input use hocche (dhire)")
                time.sleep(10)
                continue
            ok = False
            try:
                ok = self.session(jar)
            except Exception as e:
                self.log(f"Control error: {e}")
            self.cleanup()
            if not self.running:
                break
            time.sleep(1 if ok else 5)

    def session(self, jar):
        r = adb("push", jar, SERVER_REMOTE, timeout=40)
        if r.returncode != 0:
            self.log("Server push fail: " + r.stderr.decode(errors="ignore").strip()[:100])
            return False
        scid = random.randint(1, 0x7FFFFFFF)
        self.port = free_port()
        r = adb("forward", f"tcp:{self.port}", f"localabstract:scrcpy_{scid:08x}")
        if r.returncode != 0:
            self.log("adb forward fail: " + r.stderr.decode(errors="ignore").strip()[:100])
            return False
        cmd = [ADB, "shell", f"CLASSPATH={SERVER_REMOTE}", "app_process", "/",
               "com.genymobile.scrcpy.Server", SCRCPY_VERSION,
               f"scid={scid:x}", "log_level=info", "tunnel_forward=true",
               "video=false", "audio=false", "control=true", "cleanup=false",
               "send_device_meta=false", "clipboard_autosync=false"]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     creationflags=CREATE_NO_WINDOW)
        out = collections.deque(maxlen=6)

        def rd(proc):
            try:
                for line in proc.stdout:
                    t = line.decode(errors="ignore").strip()
                    if t:
                        out.append(t)
            except Exception:
                pass
        threading.Thread(target=rd, args=(self.proc,), daemon=True).start()

        s = None
        for _ in range(30):
            if not self.running:
                return False
            if self.proc.poll() is not None:
                break
            try:
                c = socket.create_connection(("127.0.0.1", self.port), timeout=2)
                c.settimeout(2)
                if c.recv(1) == b"\x00":  # dummy byte: server sathe connect hoyeche
                    s = c
                    break
                c.close()
            except Exception:
                pass
            time.sleep(0.4)
        if s is None:
            self.log("scrcpy server connect hoyni: " + " | ".join(list(out)[-2:])[:150])
            return False

        s.settimeout(None)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.dead.clear()
        self.sock = s
        threading.Thread(target=self._sender, args=(s,), daemon=True).start()
        threading.Thread(target=self._drain, args=(s,), daemon=True).start()
        self.log("Control: FAST mode (scrcpy)")
        while self.running and not self.dead.is_set() and self.proc.poll() is None:
            time.sleep(0.5)
        if self.running:
            self.log("Control: server bondho, abar chalu hocche...")
        return True

    @staticmethod
    def _is_move(msg):
        # touch message (type 2) + action 2 (move)
        return len(msg) > 1 and msg[0] == 2 and msg[1] == 2

    def _sender(self, s):
        while self.running and not self.dead.is_set() and self.sock is s:
            try:
                batch = [self.sendq.get(timeout=0.5)]
            except queue.Empty:
                continue
            # jevabe queue-te jome thake shob nei; porpor move event thakle shudhu shesh-ta pathai (lag jome na)
            while True:
                try:
                    batch.append(self.sendq.get_nowait())
                except queue.Empty:
                    break
            out = [m for i, m in enumerate(batch)
                   if not (self._is_move(m) and i + 1 < len(batch) and self._is_move(batch[i + 1]))]
            try:
                s.sendall(b"".join(out))  # ek syscall-e shob
            except Exception:
                self.dead.set()

    def _drain(self, s):
        # device theke asha message (clipboard etc.) pore phele dei, na hole buffer bhore jete pare
        try:
            while s.recv(4096):
                pass
        except Exception:
            pass
        self.dead.set()

    def cleanup(self):
        self.dead.set()
        s, self.sock = self.sock, None
        if s:
            try:
                s.close()
            except Exception:
                pass
        if self.proc:
            try:
                self.proc.kill()
            except Exception:
                pass
            self.proc = None
        if self.port:
            try:
                adb("forward", "--remove", f"tcp:{self.port}", timeout=5)
            except Exception:
                pass
            self.port = None
        while not self.sendq.empty():
            try:
                self.sendq.get_nowait()
            except Exception:
                break

    def stop(self):
        self.running = False
        self.cleanup()


class Input:
    """Input pathanor ekta-i API. scrcpy server chalu thakle FAST, na hole adb shell input (dhire) fallback."""

    def __init__(self, shell, link):
        self.shell = shell
        self.link = link
        self.size = (1080, 2400)  # ekhonkar screen (rotation soho) w, h
        self._press = None

    @property
    def fast(self):
        return self.link.connected()

    def touch(self, action, x, y):
        """action: 0 = down, 2 = move, 1 = up"""
        if self.fast:
            w, h = self.size
            self.link.send(m_touch(action, x, y, w, h, 0 if action == 1 else 0xFFFF))
            return
        # fallback: tap / swipe / long press
        if action == 0:
            self._press = (x, y, time.time())
        elif action == 1 and self._press:
            x1, y1, t0 = self._press
            self._press = None
            ms = int((time.time() - t0) * 1000)
            dist = ((x - x1) ** 2 + (y - y1) ** 2) ** 0.5
            if dist < 20:
                if ms > 500:
                    self.shell.send(f"input swipe {x1} {y1} {x1} {y1} {ms}")
                else:
                    self.shell.send(f"input tap {x1} {y1}")
            else:
                self.shell.send(f"input swipe {x1} {y1} {x} {y} {max(100, min(ms, 1500))}")

    def key(self, code):
        if self.fast:
            self.link.send(m_key(0, code) + m_key(1, code))
        else:
            self.shell.send(f"input keyevent {code}")

    def text(self, txt):
        ascii_ok = all(32 <= ord(c) < 127 for c in txt)
        if self.fast:
            if ascii_ok and len(txt) <= 300:
                self.link.send(m_text(txt))
            else:
                self.link.send(m_clipboard(txt, True))  # Bangla/Unicode: clipboard + paste
        elif ascii_ok:
            self.shell.send(text_cmd(txt))

    def scroll(self, x, y, notches):
        """notches > 0 = wheel upore (content niche nambe)"""
        if self.fast:
            w, h = self.size
            self.link.send(m_scroll(x, y, w, h, float(notches)))
        else:
            d = self.size[1] // 4
            self.shell.send(f"input swipe {x} {y} {x} {y + (d if notches > 0 else -d)} 150")



class VideoThread(QtCore.QThread):
    frame = QtCore.Signal(QtGui.QImage)
    status = QtCore.Signal(str)
    devsize = QtCore.Signal(int, int)

    def __init__(self):
        super().__init__()
        self.running = True
        self.proc = None
        self.use_size = True

    def run(self):
        while self.running:
            if adb_missing():
                self.status.emit("ADB paoa jayni! bin\\adb.exe nei. setup_adb.bat chalan.")
                self.msleep(1500)
                continue
            st = device_state()
            if st is None:
                self.status.emit("Phone paoa jachche na. USB cable lagan ar USB Debugging on korun.")
                self.msleep(1000)
                continue
            if st == "unauthorized":
                self.status.emit("Phone-er screen-e 'Allow USB debugging' e OK korun.")
                self.msleep(1000)
                continue
            if st != "device":
                self.status.emit(f"Device state: {st}")
                self.msleep(1000)
                continue
            size = get_screen_size()
            if not size:
                self.status.emit("Screen size pawa jayni, abar chesta hocche...")
                self.msleep(1000)
                continue
            self.devsize.emit(*size)
            self.stream(size)

    def stream(self, size):
        cmd = [ADB, "exec-out", "screenrecord", "--output-format=h264",
               "--bit-rate", "8000000", "--time-limit", "170"]
        if self.use_size:
            sw, sh = stream_size(*size)
            cmd += ["--size", f"{sw}x{sh}"]
        cmd.append("-")
        started = time.time()
        stats = {"bytes": 0, "frames": 0, "err": "", "pk": 0, "head": "", "dec": 0}
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     bufsize=0, creationflags=CREATE_NO_WINDOW)
        proc = self.proc

        def read_err():
            try:
                for line in proc.stderr:
                    t = line.decode(errors="ignore").strip()
                    if t:
                        stats["err"] = t
            except Exception:
                pass
        threading.Thread(target=read_err, daemon=True).start()

        codec = av.CodecContext.create("h264", "r")
        # Frame-threading decoder-e frame joma rakhe (static screen-e kichui dekhay na), tai thread bondho
        try:
            codec.thread_type = "NONE"
            codec.thread_count = 1
        except Exception:
            pass
        try:
            codec.options = {"flags": "low_delay"}
        except Exception:
            pass

        # Reader thread: pipe theke data niye queue-te rakhe, jate idle (screen na bodlale) dhora jay
        q = queue.Queue()

        def reader():
            try:
                while True:
                    d = proc.stdout.read(65536)
                    q.put(d)
                    if not d:
                        break
            except Exception:
                q.put(b"")
        threading.Thread(target=reader, daemon=True).start()

        def decode_packets(packets):
            for packet in packets:
                stats["pk"] += 1
                try:
                    frames = codec.decode(packet)
                    stats["dec"] += 1
                except Exception as e:
                    stats["err"] = f"decode: {e}"
                    continue
                for fr in frames:
                    try:
                        rgb = fr.reformat(format="rgb24")
                        pl = rgb.planes[0]
                        qimg = QtGui.QImage(bytes(pl), rgb.width, rgb.height, pl.line_size,
                                            QtGui.QImage.Format_RGB888).copy()
                    except Exception as e:
                        stats["err"] = f"convert: {e}"
                        continue
                    stats["frames"] += 1
                    self.frame.emit(qimg)

        last_report = 0
        pending = False
        try:
            while self.running:
                try:
                    data = q.get(timeout=0.1)
                except queue.Empty:
                    # 100ms kono data nai: parser-e atke thaka last frame ber kore ani
                    if pending:
                        pending = False
                        try:
                            decode_packets(list(codec.parse(None)))
                        except Exception as e:
                            stats["err"] = f"flush: {e}"
                    data = None
                if data is not None:
                    if not data:
                        try:
                            decode_packets(list(codec.parse(None)))
                        except Exception as e:
                            stats["err"] = f"flush-end: {e}"
                        break
                    if not stats["head"]:
                        stats["head"] = data[:24].hex(" ")
                    stats["bytes"] += len(data)
                    pending = True
                    decode_packets(list(codec.parse(data)))
                if time.time() - last_report > 1:
                    last_report = time.time()
                    self.status.emit(f"Connected | bytes={stats['bytes']} pk={stats['pk']} dec={stats['dec']} frames={stats['frames']} {stats['err']}")
        except Exception as e:
            self.status.emit(f"Stream error: {e}")
        finally:
            try:
                proc.kill()
            except Exception:
                pass
        if stats["frames"] == 0:
            rc = proc.poll()
            self.status.emit(f"Frame nai | bytes={stats['bytes']} pk={stats['pk']} dec={stats['dec']} rc={rc} t={time.time()-started:.1f}s size={self.use_size} err={stats['err']} head={stats['head']}")
            if time.time() - started < 5:
                self.use_size = not self.use_size
            self.msleep(2500)

    def stop(self):
        self.running = False
        try:
            if self.proc:
                self.proc.kill()
        except Exception:
            pass


KEYMAP = {
    QtCore.Qt.Key_Return: 66, QtCore.Qt.Key_Enter: 66, QtCore.Qt.Key_Backspace: 67,
    QtCore.Qt.Key_Delete: 112, QtCore.Qt.Key_Escape: 4, QtCore.Qt.Key_Tab: 61,
    QtCore.Qt.Key_Up: 19, QtCore.Qt.Key_Down: 20, QtCore.Qt.Key_Left: 21,
    QtCore.Qt.Key_Right: 22, QtCore.Qt.Key_Home: 3, QtCore.Qt.Key_PageUp: 92,
    QtCore.Qt.Key_PageDown: 93,
}


class ScreenView(QtWidgets.QWidget):
    def __init__(self, inp):
        super().__init__()
        self.inp = inp
        self.img = None
        self.dev_size = (1080, 2400)
        self.pressing = False
        self.last_move = 0.0
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setMinimumSize(270, 480)

    def set_frame(self, img):
        self.img = img
        self.update()

    def target_rect(self):
        if self.img is None:
            return QtCore.QRect()
        iw, ih = self.img.width(), self.img.height()
        s = min(self.width() / iw, self.height() / ih)
        w, h = int(iw * s), int(ih * s)
        return QtCore.QRect((self.width() - w) // 2, (self.height() - h) // 2, w, h)

    def paintEvent(self, _):
        p = QtGui.QPainter(self)
        p.fillRect(self.rect(), QtGui.QColor(0, 0, 0))
        if self.img is not None:
            p.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
            p.drawImage(self.target_rect(), self.img)

    def eff_dev(self):
        dw, dh = self.dev_size
        if self.img is not None and (self.img.width() > self.img.height()) != (dw > dh):
            dw, dh = dh, dw
        return dw, dh

    def to_dev(self, pos, clamp=True):
        r = self.target_rect()
        if r.isNull() or r.width() == 0 or r.height() == 0:
            return None
        if not clamp and not r.contains(pos):
            return None
        fx = min(1.0, max(0.0, (pos.x() - r.x()) / r.width()))
        fy = min(1.0, max(0.0, (pos.y() - r.y()) / r.height()))
        dw, dh = self.eff_dev()
        return int(fx * (dw - 1)), int(fy * (dh - 1))

    def mousePressEvent(self, e):
        self.setFocus()
        if e.button() == QtCore.Qt.LeftButton:
            pt = self.to_dev(e.position().toPoint(), clamp=False)
            if pt:
                self.pressing = True
                self.inp.size = self.eff_dev()
                self.inp.touch(0, *pt)
        elif e.button() == QtCore.Qt.RightButton:
            self.inp.key(4)  # right click = Back
        elif e.button() == QtCore.Qt.MiddleButton:
            self.inp.key(3)  # middle click = Home

    def mouseMoveEvent(self, e):
        if not self.pressing or not (e.buttons() & QtCore.Qt.LeftButton):
            return
        pt = self.to_dev(e.position().toPoint())  # throttle nai: ScrcpyLink nijei jomano move merge kore
        if pt:
            self.inp.size = self.eff_dev()
            self.inp.touch(2, *pt)

    def mouseReleaseEvent(self, e):
        if e.button() != QtCore.Qt.LeftButton or not self.pressing:
            return
        self.pressing = False
        pt = self.to_dev(e.position().toPoint())
        if pt:
            self.inp.size = self.eff_dev()
            self.inp.touch(1, *pt)

    def wheelEvent(self, e):
        pt = self.to_dev(e.position().toPoint())
        if not pt:
            return
        self.inp.size = self.eff_dev()
        self.inp.scroll(pt[0], pt[1], e.angleDelta().y() / 120.0)

    def keyPressEvent(self, e):
        if e.modifiers() & QtCore.Qt.ControlModifier and e.key() == QtCore.Qt.Key_V:
            txt = QtWidgets.QApplication.clipboard().text()
            if txt:
                self.inp.text(txt)  # PC clipboard theke phone-e paste
            return
        if e.key() in KEYMAP:
            self.inp.key(KEYMAP[e.key()])
            return
        txt = e.text()
        if txt and txt.isprintable() and not (e.modifiers() & QtCore.Qt.ControlModifier):
            self.inp.text(txt)


# ======================= icon (code diye aka, kono image file lage na) =======================
def draw_app_icon(size=256):
    """Simple phone icon: nil rounded-square-er upor sada phone."""
    pm = QtGui.QPixmap(size, size)
    pm.fill(QtCore.Qt.transparent)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    u = size / 256.0
    bg = QtGui.QLinearGradient(0, 0, 0, size)
    bg.setColorAt(0, QtGui.QColor("#3b82f6"))
    bg.setColorAt(1, QtGui.QColor("#1d4ed8"))
    p.setPen(QtCore.Qt.NoPen)
    p.setBrush(bg)
    p.drawRoundedRect(QtCore.QRectF(8 * u, 8 * u, 240 * u, 240 * u), 56 * u, 56 * u)
    # phone body
    p.setBrush(QtGui.QColor("#ffffff"))
    p.drawRoundedRect(QtCore.QRectF(78 * u, 36 * u, 100 * u, 184 * u), 22 * u, 22 * u)
    # screen
    p.setBrush(QtGui.QColor("#1e3a8a"))
    p.drawRoundedRect(QtCore.QRectF(88 * u, 60 * u, 80 * u, 130 * u), 8 * u, 8 * u)
    # speaker + home dot
    p.setBrush(QtGui.QColor("#93a3c8"))
    p.drawRoundedRect(QtCore.QRectF(114 * u, 45 * u, 28 * u, 6 * u), 3 * u, 3 * u)
    p.drawEllipse(QtCore.QPointF(128 * u, 205 * u), 6 * u, 6 * u)
    p.end()
    return pm


def app_icon():
    ic = QtGui.QIcon()
    for s in (16, 24, 32, 48, 64, 128, 256):
        ic.addPixmap(draw_app_icon(s))
    return ic


def draw_button_icon(kind, color="#e5e7eb", size=64):
    pm = QtGui.QPixmap(size, size)
    pm.fill(QtCore.Qt.transparent)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    u = size / 64.0
    c = QtGui.QColor(color)
    pen = QtGui.QPen(c, 4.5 * u, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(QtCore.Qt.NoBrush)
    P = lambda x, y: QtCore.QPointF(x * u, y * u)
    if kind == "back":      # bam-mukhi tirbhuj
        p.setBrush(c)
        p.drawPolygon(QtGui.QPolygonF([P(44, 14), P(44, 50), P(16, 32)]))
    elif kind == "home":    # gol
        p.drawEllipse(P(32, 32), 17 * u, 17 * u)
    elif kind == "recent":  # choukon
        p.drawRoundedRect(QtCore.QRectF(16 * u, 16 * u, 32 * u, 32 * u), 6 * u, 6 * u)
    elif kind == "power":
        path = QtGui.QPainterPath()
        path.arcMoveTo(QtCore.QRectF(14 * u, 16 * u, 36 * u, 36 * u), 120)
        path.arcTo(QtCore.QRectF(14 * u, 16 * u, 36 * u, 36 * u), 120, -300)
        p.drawPath(path)
        p.drawLine(P(32, 10), P(32, 30))
    elif kind in ("volup", "voldown"):
        p.setBrush(c)
        p.setPen(QtCore.Qt.NoPen)
        p.drawPolygon(QtGui.QPolygonF([P(10, 25), P(20, 25), P(32, 14), P(32, 50), P(20, 39), P(10, 39)]))
        p.setPen(pen)
        p.setBrush(QtCore.Qt.NoBrush)
        p.drawArc(QtCore.QRectF(28 * u, 24 * u, 16 * u, 16 * u), -60 * 16, 120 * 16)
        if kind == "volup":
            p.drawLine(P(50, 32), P(60, 32))
            p.drawLine(P(55, 27), P(55, 37))
        else:
            p.drawLine(P(50, 32), P(60, 32))
    elif kind == "status":  # window, niche status bar
        p.drawRoundedRect(QtCore.QRectF(14 * u, 10 * u, 36 * u, 44 * u), 6 * u, 6 * u)
        p.setBrush(c)
        p.drawRect(QtCore.QRectF(14 * u, 42 * u, 36 * u, 6 * u))
    elif kind == "shot":    # camera
        p.drawRoundedRect(QtCore.QRectF(10 * u, 20 * u, 44 * u, 32 * u), 6 * u, 6 * u)
        p.drawLine(P(22, 20), P(26, 13))
        p.drawLine(P(26, 13), P(38, 13))
        p.drawLine(P(38, 13), P(42, 20))
        p.drawEllipse(P(32, 36), 8 * u, 8 * u)
    p.end()
    return pm


def button_icon(kind):
    ic = QtGui.QIcon()
    ic.addPixmap(draw_button_icon(kind, "#e5e7eb"), QtGui.QIcon.Normal)
    ic.addPixmap(draw_button_icon(kind, "#6b7280"), QtGui.QIcon.Disabled)
    return ic


class SidePanel(QtWidgets.QWidget):
    """Phone window-er baire dan pashe bhasha icon bar (SmartGaGa-r moto). Handle-e click korle hide/show.
    Window transparent, tai bar-er niche kono kalo jayga thake na."""
    WIDTH_BTN = 22

    def __init__(self, main, buttons):
        super().__init__(main, QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint |
                         QtCore.Qt.WindowDoesNotAcceptFocus | QtCore.Qt.NoDropShadowWindowHint)
        self.main = main
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.expanded = True

        self.panel = QtWidgets.QFrame()
        self.panel.setObjectName("panel")
        self.panel.setStyleSheet(
            "#panel{background:#111827;border-radius:12px}"
            "QToolButton{background:transparent;border:0;border-radius:8px;padding:5px}"
            "QToolButton:hover{background:#374151}"
            "QToolButton:pressed{background:#2563eb}")
        pl = QtWidgets.QVBoxLayout(self.panel)
        pl.setContentsMargins(4, 6, 4, 6)
        pl.setSpacing(2)
        for item in buttons:
            if item is None:
                sep = QtWidgets.QFrame()
                sep.setFixedHeight(1)
                sep.setStyleSheet("background:#374151")
                pl.addWidget(sep)
                continue
            kind, tip, fn = item
            b = QtWidgets.QToolButton()
            b.setIcon(button_icon(kind))
            b.setIconSize(QtCore.QSize(self.WIDTH_BTN, self.WIDTH_BTN))
            b.setToolTip(tip)
            b.setFocusPolicy(QtCore.Qt.NoFocus)
            b.setAutoRaise(True)
            b.clicked.connect(lambda _=False, f=fn: f())
            pl.addWidget(b)

        self.handle = QtWidgets.QToolButton()
        self.handle.setFixedSize(14, 44)
        self.handle.setFocusPolicy(QtCore.Qt.NoFocus)
        self.handle.setCursor(QtCore.Qt.PointingHandCursor)
        self.handle.clicked.connect(self.toggle)
        hv = QtWidgets.QVBoxLayout()
        hv.setContentsMargins(0, 0, 0, 0)
        hv.addSpacing(100)
        hv.addWidget(self.handle)
        hv.addStretch(1)

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.panel, 0, QtCore.Qt.AlignTop)
        lay.addLayout(hv)      # handle shobsomoy bar-er dan-e; bar lukale phone screen-er gaye
        self._refresh()

    def _refresh(self):
        self.panel.setVisible(self.expanded)
        # bar dekha gele handle bar-ke bondho korar jonno, na hole kholar jonno
        self.handle.setStyleSheet(
            "QToolButton{background:#111827;border:0;border-top-right-radius:8px;"
            "border-bottom-right-radius:8px;color:#e5e7eb;font-size:14px;font-weight:bold}"
            "QToolButton:hover{background:#374151}")
        self.handle.setText("\u2039" if self.expanded else "\u203a")
        self.handle.setToolTip("Hide bar" if self.expanded else "Show bar")
        self.adjustSize()
        self.reposition()

    def toggle(self):
        self.expanded = not self.expanded
        self._refresh()

    def reposition(self):
        m = self.main
        tl = m.mapToGlobal(QtCore.QPoint(m.width(), 0))
        self.move(tl.x(), tl.y() + 6)


class Main(QtWidgets.QMainWindow):
    shot_done = QtCore.Signal(str)
    input_log = QtCore.Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("XControl  \u00b7  akrakib")
        self.sized = False
        self.shell = InputShell()
        self.link = ScrcpyLink(lambda m: self.input_log.emit(m))
        self.inp = Input(self.shell, self.link)
        self.view = ScreenView(self.inp)
        self.setCentralWidget(self.view)

        self.setWindowIcon(app_icon())
        self.side = SidePanel(self, [
            ("back", "Back", lambda: self.inp.key(4)),
            ("home", "Home", lambda: self.inp.key(3)),
            ("recent", "Recent apps", lambda: self.inp.key(187)),
            ("power", "Power", lambda: self.inp.key(26)),
            ("volup", "Volume +", lambda: self.inp.key(24)),
            ("voldown", "Volume -", lambda: self.inp.key(25)),
            None,
            ("shot", "Screenshot", self.screenshot),
            ("status", "Hide / show status bar", self.toggle_status),
        ])

        credit = QtWidgets.QLabel('by <a href="https://akrakib.pages.dev/" style="color:#3b82f6">akrakib</a>')
        credit.setTextFormat(QtCore.Qt.RichText)
        credit.setOpenExternalLinks(True)  # click korle browser-e link khole
        credit.setCursor(QtCore.Qt.PointingHandCursor)
        credit.setToolTip("https://akrakib.pages.dev/")
        credit.setStyleSheet("color:#6b7280;font-size:10px;padding:0 6px")
        self.statusBar().addPermanentWidget(credit)
        self.inlog = QtWidgets.QLabel("")
        self.inlog.setStyleSheet("color:#0a5; padding-right:8px")
        self.statusBar().addPermanentWidget(self.inlog)
        self.input_log.connect(self.inlog.setText)
        self.shell.log = self.input_log.emit
        self.link.start()
        self.shot_done.connect(lambda m: self.statusBar().showMessage(m, 5000))
        self.statusBar().showMessage("Shuru hocche...")

        self.video = VideoThread()
        self.video.frame.connect(self.on_frame)
        self.video.status.connect(lambda m: self.statusBar().showMessage(m))
        self.video.devsize.connect(lambda w, h: setattr(self.view, "dev_size", (w, h)))
        self.video.start()
        self.resize(420, 820)

    def on_frame(self, img):
        self.view.set_frame(img)
        if not self.sized:
            self.sized = True
            avail = QtWidgets.QApplication.primaryScreen().availableGeometry()
            h = min(900, avail.height() - 160)
            w = int(h * img.width() / img.height())
            self.resize(w, h + 30)  # niche status bar

    def toggle_status(self):
        sb = self.statusBar()
        h = sb.height()
        if sb.isVisible():
            sb.hide()
            self.resize(self.width(), self.height() - h)
        else:
            sb.show()
            self.resize(self.width(), self.height() + h)

    def screenshot(self):
        def work():
            try:
                data = adb("exec-out", "screencap", "-p", timeout=20).stdout
                folder = os.path.join(os.path.expanduser("~"), "Pictures", "XControl")
                os.makedirs(folder, exist_ok=True)
                path = os.path.join(folder, datetime.now().strftime("shot_%Y%m%d_%H%M%S.png"))
                with open(path, "wb") as f:
                    f.write(data)
                self.shot_done.emit(f"Screenshot saved: {path}")
            except Exception as e:
                self.shot_done.emit(f"Screenshot failed: {e}")
        threading.Thread(target=work, daemon=True).start()

    # bar phone window-er sathe sathe chole
    def moveEvent(self, e):
        super().moveEvent(e)
        if hasattr(self, "side"):
            self.side.reposition()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "side"):
            self.side.reposition()

    def showEvent(self, e):
        super().showEvent(e)
        self.side.show()
        self.side.reposition()

    def changeEvent(self, e):
        super().changeEvent(e)
        if e.type() == QtCore.QEvent.WindowStateChange and hasattr(self, "side"):
            self.side.setVisible(not self.isMinimized())
            self.side.reposition()

    def closeEvent(self, e):
        self.side.close()
        self.video.stop()
        self.video.wait(2000)
        self.link.stop()
        self.shell.close()
        if ADB_BUNDLED:
            try:
                adb("kill-server", timeout=5)
            except Exception:
                pass
        e.accept()


def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setWindowIcon(app_icon())
    w = Main()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
