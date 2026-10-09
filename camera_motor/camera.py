"""Raspberry Pi camera face and drowsiness prototype.

Bullseye setup (use the distro packages for camera/OpenCV compatibility):
	sudo apt update
	sudo apt install python3-picamera2 python3-opencv

Optional eye-landmark inference requires MediaPipe, if a compatible ARM wheel
is available for the installed Raspberry Pi OS/Python version. Check first:
	python3 -c "import mediapipe; print(mediapipe.__version__)"
Do not install an x86-only wheel on the Pi. Without MediaPipe, Haar face
detection still runs, but eye state and drowsiness remain indeterminate.

Run from a graphical desktop:
	python3 camera.py
Run without a display (for example over SSH):
	python3 camera.py --headless
The headless mode writes the CSV but has no live preview or q-key control;
 stop it with Ctrl+C. The CSV is appended beside this script by default; `--log`
 selects another path. State changes and five-second snapshots are appended;
 existing rows are never overwritten.

MediaPipe mode uses the eye aspect ratio (EAR), the sum of two vertical
landmark distances divided by twice the horizontal distance. EAR <= 0.20 is
closed, EAR >= 0.25 is open, and values between them are uncertain. These are
starting values, not validated medical thresholds. A closed eye lasting 0.8 s
is labeled sleepy and 3.0 s is labeled likely asleep; brief blinks are ignored.
The largest face is the primary subject. Other faces are boxed but do not
affect the state. If landmarks are unavailable, the program never treats a
missing eye as a closed eye.

Before running, check the OS with `cat /etc/os-release`, Python with
`python3 --version`, and the camera with `libcamera-hello --list-cameras`.
Install the Bullseye packages with `sudo apt install libcamera-apps
python3-picamera2 python3-opencv`; use the system Python so apt packages remain
visible. This program has not been run on the target Pi.

Checks: keep a face near-frontal with eyes open; blink briefly; close both eyes
for about one second and then at least three seconds; leave the frame; obscure
or turn away from the eyes; vary the lighting; then restart and confirm old CSV
rows remain. Expected results are awake, no sleepy label for a brief blink,
sleepy, likely asleep, face-not-detected, indeterminate, possibly indeterminate,
and an appended log respectively. Tune thresholds with the real camera. This
is a visual estimate, not a sleep diagnosis.
"""

import argparse
import csv
import datetime as dt
import os
import sys
import time
from pathlib import Path


CAMERA_SIZE = (640, 480)
CAMERA_FPS = 15
EAR_CLOSED_THRESHOLD = 0.20
EAR_OPEN_THRESHOLD = 0.25
DROWSY_CLOSED_SECONDS = 0.8
SLEEP_CLOSED_SECONDS = 3.0
LOG_INTERVAL_SECONDS = 5.0

CSV_FIELDS = (
	"判定日時",
	"顔検出状態",
	"顔数",
	"目検出状態",
	"左目EAR",
	"右目EAR",
	"閉眼継続秒",
	"判定結果",
	"補足情報",
)


def eye_aspect_ratio(landmarks, indices, width, height):
	"""Calculate EAR from six normalized face-mesh landmark indices."""
	points = [
		(landmarks[index].x * width, landmarks[index].y * height)
		for index in indices
	]
	horizontal = ((points[0][0] - points[3][0]) ** 2 + (points[0][1] - points[3][1]) ** 2) ** 0.5
	if horizontal <= 0:
		return None
	vertical_one = ((points[1][0] - points[5][0]) ** 2 + (points[1][1] - points[5][1]) ** 2) ** 0.5
	vertical_two = ((points[2][0] - points[4][0]) ** 2 + (points[2][1] - points[4][1]) ** 2) ** 0.5
	return (vertical_one + vertical_two) / (2.0 * horizontal)


def classify_state(eye_state, closed_seconds):
	"""Return a user-facing state without equating missing eyes to closed."""
	if eye_state == "open":
		return "起きている"
	if eye_state == "closed":
		if closed_seconds >= SLEEP_CLOSED_SECONDS:
			return "寝ている可能性が高い"
		if closed_seconds >= DROWSY_CLOSED_SECONDS:
			return "眠そう"
		return "起きている（短時間の閉眼）"
	if eye_state == "no_face":
		return "判定不能（顔未検出）"
	if eye_state == "no_landmarks":
		return "判定不能（目のランドマーク未使用）"
	return "判定不能（目を十分に検出できない）"


class CsvLogger:
	"""Append state changes and periodic snapshots without overwriting logs."""

	def __init__(self, path, interval_seconds):
		self.path = Path(path)
		self.interval_seconds = interval_seconds
		self.last_state = None
		self.last_write = 0.0

	def write_if_due(self, row, state, now_monotonic):
		changed = state != self.last_state
		periodic = now_monotonic - self.last_write >= self.interval_seconds
		if not changed and not periodic:
			return

		needs_header = not self.path.exists() or self.path.stat().st_size == 0
		try:
			with self.path.open("a", newline="", encoding="utf-8-sig") as log_file:
				writer = csv.DictWriter(log_file, fieldnames=CSV_FIELDS)
				if needs_header:
					writer.writeheader()
				writer.writerow(row)
		except OSError as error:
			raise RuntimeError(f"CSVログを書き込めません: {self.path}: {error}") from error

		self.last_state = state
		self.last_write = now_monotonic


def load_dependencies():
	try:
		import cv2
	except ImportError as error:
		raise RuntimeError(
			"OpenCVがありません。Bullseyeでは `sudo apt install python3-opencv` "
			"を実行してください。"
		) from error

	try:
		from picamera2 import Picamera2
	except ImportError as error:
		raise RuntimeError(
			"Picamera2がありません。Bullseyeでは `sudo apt install "
			"python3-picamera2` を実行してください。"
		) from error

	try:
		import mediapipe as mp
		face_mesh_module = mp.solutions.face_mesh
	except (ImportError, AttributeError):
		face_mesh_module = None

	return cv2, Picamera2, face_mesh_module


def create_face_detector(cv2):
	cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
	detector = cv2.CascadeClassifier(str(cascade_path))
	if detector.empty():
		raise RuntimeError(f"OpenCVの顔検出データを読み込めません: {cascade_path}")
	return detector


def draw_label(cv2, frame, text, position, color, scale=0.65, thickness=2):
	cv2.putText(
		frame,
		text,
		position,
		cv2.FONT_HERSHEY_SIMPLEX,
		scale,
		color,
		thickness,
		cv2.LINE_AA,
	)


def run(args):
	cv2, Picamera2, face_mesh_module = load_dependencies()
	face_detector = create_face_detector(cv2)
	camera = None
	face_mesh = None
	window_created = False
	logger = CsvLogger(args.log, LOG_INTERVAL_SECONDS)
	closed_since = None
	previous_state = None

	try:
		camera = Picamera2()
		camera_config = camera.create_video_configuration(
			main={"size": CAMERA_SIZE, "format": "RGB888"},
			controls={"FrameRate": CAMERA_FPS},
		)
		camera.configure(camera_config)
		camera.start()
		time.sleep(1.0)
	except Exception as error:
		if camera is not None:
			try:
				camera.stop()
			except Exception:
				pass
		raise RuntimeError(
			"カメラを開始できません。CSI接続、カメラ認識、他アプリによる占有を確認してください。"
			f" Picamera2詳細: {error}"
		) from error

	if face_mesh_module is not None:
		face_mesh = face_mesh_module.FaceMesh(
			static_image_mode=False,
			max_num_faces=3,
			refine_landmarks=True,
			min_detection_confidence=0.5,
			min_tracking_confidence=0.5,
		)
		print("顔・目ランドマーク: MediaPipe FaceMesh")
	else:
		print("顔検出: OpenCV Haar Cascade / 目判定: 利用不可（判定不能になります）")

	if not args.headless:
		try:
			cv2.namedWindow("Sleep detection", cv2.WINDOW_NORMAL)
			window_created = True
		except cv2.error as error:
			camera.stop()
			raise RuntimeError(
				"画面表示を開始できません。デスクトップGUIで実行するか、SSHでは "
				"`--headless` を指定してください。"
			) from error

	face_box_color = (0, 210, 0)
	status_color = (0, 210, 0)
	try:
		while True:
			frame = camera.capture_array()
			if frame is None:
				raise RuntimeError("カメラから画像を取得できませんでした。")
			frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
			height, width = frame.shape[:2]
			gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
			faces = face_detector.detectMultiScale(
				gray,
				scaleFactor=1.2,
				minNeighbors=5,
				minSize=(50, 50),
			)
			faces = sorted(faces, key=lambda box: box[2] * box[3], reverse=True)
			now = time.monotonic()
			timestamp = dt.datetime.now().astimezone().isoformat(timespec="seconds")
			left_ear = None
			right_ear = None
			eye_state = "no_face"
			note = ""

			mesh_faces = None
			if face_mesh is not None:
				rgb_frame = cv2.resize(
					cv2.cvtColor(frame, cv2.COLOR_BGR2RGB),
					(320, 240),
					interpolation=cv2.INTER_AREA,
				)
				mesh_result = face_mesh.process(rgb_frame)
				mesh_faces = mesh_result.multi_face_landmarks or []

			for index, (x, y, face_width, face_height) in enumerate(faces):
				cv2.rectangle(
					frame,
					(x, y),
					(x + face_width, y + face_height),
					face_box_color,
					2,
				)
				draw_label(cv2, frame, f"Face {index + 1}", (x, max(20, y - 8)), face_box_color, 0.55, 1)

			if faces:
				if face_mesh is None:
					eye_state = "no_landmarks"
					note = "MediaPipe未導入; Haar顔検出のみ"
				elif mesh_faces:
					primary_mesh = max(
						mesh_faces,
						key=lambda face: (
							max(point.x for point in face.landmark)
							- min(point.x for point in face.landmark)
						)
						* (
							max(point.y for point in face.landmark)
							- min(point.y for point in face.landmark)
						),
					)
					landmarks = primary_mesh.landmark
					left_ear = eye_aspect_ratio(landmarks, (362, 385, 387, 263, 373, 380), 320, 240)
					right_ear = eye_aspect_ratio(landmarks, (33, 160, 158, 133, 153, 144), 320, 240)
					if left_ear is not None and right_ear is not None:
						average_ear = (left_ear + right_ear) / 2.0
						if average_ear <= EAR_CLOSED_THRESHOLD:
							eye_state = "closed"
							if closed_since is None:
								closed_since = now
						elif average_ear >= EAR_OPEN_THRESHOLD:
							eye_state = "open"
							closed_since = None
						else:
							eye_state = "uncertain"
							closed_since = None
						note = f"平均EAR={average_ear:.3f}"
					else:
						eye_state = "uncertain"
						closed_since = None
						note = "EARを計算できません"
				else:
					eye_state = "uncertain"
					closed_since = None
					note = "顔ランドマーク未検出"
			else:
				closed_since = None
				note = "顔未検出"

			if eye_state not in ("closed",):
				closed_since = None
			closed_seconds = now - closed_since if closed_since is not None else 0.0
			state = classify_state(eye_state, closed_seconds)
			status_color = (0, 0, 230) if "寝ている" in state else (0, 165, 255) if "眠そう" in state else (0, 210, 0)
			face_status = "検出" if faces else "未検出"
			eye_status = {
				"open": "開眼推定",
				"closed": "閉眼推定",
				"uncertain": "不確か",
				"no_landmarks": "未対応",
				"no_face": "対象なし",
			}[eye_state]
			display_state = {
				"起きている": "AWAKE",
				"起きている（短時間の閉眼）": "AWAKE (BRIEF CLOSURE)",
				"眠そう": "DROWSY",
				"寝ている可能性が高い": "POSSIBLE SLEEP",
				"判定不能（顔未検出）": "UNKNOWN (NO FACE)",
				"判定不能（目のランドマーク未使用）": "UNKNOWN (NO LANDMARKS)",
				"判定不能（目を十分に検出できない）": "UNKNOWN (EYES UNCERTAIN)",
			}[state]
			display_eye_status = {
				"open": "OPEN ESTIMATE",
				"closed": "CLOSED ESTIMATE",
				"uncertain": "UNCERTAIN",
				"no_landmarks": "UNAVAILABLE",
				"no_face": "NO SUBJECT",
			}[eye_state]
			ears_text = (
				f"EAR L:{left_ear:.3f} R:{right_ear:.3f}"
				if left_ear is not None and right_ear is not None
				else "EAR: --"
			)
			draw_label(cv2, frame, f"State: {display_state}", (12, 28), status_color, 0.62, 2)
			draw_label(cv2, frame, f"Faces: {face_status} ({len(faces)})  Eyes: {display_eye_status}", (12, 55), (255, 255, 255), 0.55, 1)
			draw_label(cv2, frame, f"{ears_text}  Closed: {closed_seconds:.1f}s", (12, 80), (255, 255, 255), 0.55, 1)
			draw_label(cv2, frame, timestamp, (12, height - 14), (255, 255, 255), 0.45, 1)

			row = {
				"判定日時": timestamp,
				"顔検出状態": face_status,
				"顔数": len(faces),
				"目検出状態": eye_status,
				"左目EAR": f"{left_ear:.4f}" if left_ear is not None else "",
				"右目EAR": f"{right_ear:.4f}" if right_ear is not None else "",
				"閉眼継続秒": f"{closed_seconds:.2f}",
				"判定結果": state,
				"補足情報": note,
			}
			logger.write_if_due(row, state, now)

			if state != previous_state:
				print(f"{timestamp}  {state}  顔:{len(faces)}  目:{eye_status}  {note}")
				previous_state = state
			if not args.headless:
				cv2.imshow("Sleep detection", frame)
				if cv2.waitKey(1) & 0xFF == ord("q"):
					break

	except KeyboardInterrupt:
		print("\nCtrl+Cを受け付けました。終了処理を行います。")
	finally:
		if face_mesh is not None:
			face_mesh.close()
		if camera is not None:
			camera.stop()
		if window_created:
			cv2.destroyAllWindows()
		print(f"CSVログ: {os.path.abspath(args.log)}")


def parse_args():
	parser = argparse.ArgumentParser(description="Raspberry Piの顔・目状態推定")
	parser.add_argument(
		"--log",
		default=str(Path(__file__).resolve().with_name("sleep_detection_log.csv")),
		help="追記するCSVログのパス (default: %(default)s)",
	)
	parser.add_argument(
		"--headless",
		action="store_true",
		help="GUIを使わず実行する。終了はCtrl+C",
	)
	return parser.parse_args()


if __name__ == "__main__":
	try:
		run(parse_args())
	except RuntimeError as error:
		print(f"エラー: {error}", file=sys.stderr)
		sys.exit(1)
