import os
import tkinter as tk
from tkinter import filedialog, ttk
import exifread
from datetime import datetime
import shutil
import logging
from geopy.geocoders import Nominatim
import threading
import time

# Initialize logging
logging.basicConfig(filename='imgsetsortr.log', level=logging.DEBUG, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

class ImageSetSorter:
    def __init__(self, root):
        self.root = root
        self.root.title("Image Set Sorter")
        self.root.geometry("600x800")
        logging.info("Starting imgsetsortr application")
        logging.debug("Window initialized with geometry 600x800")

        self.input_dir = tk.StringVar()
        self.time_threshold = tk.DoubleVar(value=1.0)
        self.running = False
        self.paused = False
        self.last_folder = self.load_last_folder()

        # Create main frame with scrollbar
        self.canvas = tk.Canvas(root)
        self.scrollbar = ttk.Scrollbar(root, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # Layout
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # GUI Elements
        ttk.Label(self.scrollable_frame, text="Input Folder:").pack(pady=5)
        self.folder_entry = ttk.Entry(self.scrollable_frame, textvariable=self.input_dir, width=50)
        self.folder_entry.pack(pady=5)
        if self.last_folder:
            self.input_dir.set(self.last_folder)
            logging.info(f"Loaded last folder: {self.last_folder}")
        ttk.Button(self.scrollable_frame, text="Browse", command=self.browse_folder).pack(pady=5)

        ttk.Label(self.scrollable_frame, text="Time Threshold (seconds):").pack(pady=5)
        ttk.Entry(self.scrollable_frame, textvariable=self.time_threshold, width=10).pack(pady=5)

        self.subfolder_var = tk.BooleanVar()
        ttk.Checkbutton(self.scrollable_frame, text="Include Subfolders", variable=self.subfolder_var).pack(pady=5)
        logging.debug("Initialized subfolder checkbox")

        self.folder_contents = tk.Listbox(self.scrollable_frame, width=80, height=20)
        self.folder_contents.pack(pady=5)

        self.progress = ttk.Progressbar(self.scrollable_frame, length=400, mode='determinate')
        self.progress.pack(pady=5)

        self.status_label = ttk.Label(self.scrollable_frame, text="")
        self.status_label.pack(pady=5)

        ttk.Button(self.scrollable_frame, text="Start", command=self.start_grouping).pack(pady=5)
        ttk.Button(self.scrollable_frame, text="Pause", command=self.pause_grouping).pack(pady=5)
        ttk.Button(self.scrollable_frame, text="Exit", command=self.exit_app).pack(pady=5)

    def load_last_folder(self):
        try:
            with open("last_folder.txt", "r") as f:
                return f.read().strip()
        except FileNotFoundError:
            return ""

    def save_last_folder(self):
        with open("last_folder.txt", "w") as f:
            f.write(self.input_dir.get())

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.input_dir.set(folder)
            self.save_last_folder()
            self.update_folder_contents()

    def update_folder_contents(self):
        self.folder_contents.delete(0, tk.END)
        folder = self.input_dir.get()
        if not folder:
            return
        image_extensions = ('.jpg', '.jpeg', '.png')
        image_files = []
        for root, _, files in os.walk(folder) if self.subfolder_var.get() else [(folder, [], os.listdir(folder))]:
            image_files.extend(os.path.join(root, f) for f in files if f.lower().endswith(image_extensions))
        logging.info(f"Found images in {1 if not self.subfolder_var.get() else len(set(os.path.dirname(f) for f in image_files))} folders in {folder}")
        for image in image_files:
            self.folder_contents.insert(tk.END, os.path.basename(image))
        logging.info(f"Updated folder contents listbox with {len(image_files)} images")
        return image_files

    def get_exif_datetime(self, image_path):
        try:
            with open(image_path, 'rb') as f:
                tags = exifread.process_file(f)
                if 'EXIF DateTimeOriginal' in tags:
                    dt_str = str(tags['EXIF DateTimeOriginal'])
                    subsec = str(tags.get('EXIF SubSecTimeOriginal', '0')).zfill(6)
                    dt = datetime.strptime(f"{dt_str}.{subsec}", "%Y:%m:%d %H:%M:%S.%f")
                    logging.debug(f"Got EXIF DateTimeOriginal for {image_path}: {dt}")
                    return dt
        except Exception as e:
            logging.error(f"Error reading EXIF for {image_path}: {e}")
        return None

    def get_city_from_gps(self, image_path):
        try:
            with open(image_path, 'rb') as f:
                tags = exifread.process_file(f)
                if 'GPS GPSLatitude' in tags and 'GPS GPSLongitude' in tags:
                    lat = self.convert_gps(tags['GPS GPSLatitude'], tags.get('GPS GPSLatitudeRef', 'N'))
                    lon = self.convert_gps(tags['GPS GPSLongitude'], tags.get('GPS GPSLongitudeRef', 'E'))
                    geolocator = Nominatim(user_agent="imgsetsortr")
                    location = geolocator.reverse((lat, lon), language='en')
                    logging.debug(f"Nominatim.reverse: https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json&accept-language=en&addressdetails=1")
                    if location and 'address' in location.raw and 'city' in location.raw['address']:
                        city = location.raw['address']['city']
                        logging.info(f"Got city from EXIF GPS for {image_path}: {city}")
                        return city
                    return "unknown"
        except Exception as e:
            logging.error(f"Error getting city for {image_path}: {e}")
        return "unknown"

    def convert_gps(self, gps, ref):
        degrees, minutes, seconds = [float(x) for x in gps.values]
        decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
        if ref in ('S', 'W'):
            decimal = -decimal
        return decimal

    def group_images(self, image_files):
        images = []
        for image_path in image_files:
            dt = self.get_exif_datetime(image_path)
            if dt:
                images.append((image_path, dt))
        images.sort(key=lambda x: x[1])

        groups = []
        current_group = []
        for image_path, dt in images:
            if not current_group or (dt - current_group[-1][1]).total_seconds() <= self.time_threshold.get():
                current_group.append((image_path, dt))
            else:
                groups.append(current_group)
                current_group = [(image_path, dt)]
        if current_group:
            groups.append(current_group)

        return groups

    def start_grouping(self):
        if self.running:
            return
        self.running = True
        self.paused = False
        self.status_label.config(text="Processing...")
        threading.Thread(target=self.process_images, daemon=True).start()

    def pause_grouping(self):
        self.paused = not self.paused
        self.status_label.config(text="Paused" if self.paused else "Processing...")

    def process_images(self):
        folder = self.input_dir.get()
        if not folder:
            self.status_label.config(text="Select a folder!")
            self.running = False
            return

        threshold = self.time_threshold.get()
        logging.info(f"Updated time threshold to {threshold}s")
        logging.info(f"Starting grouping for folder: {folder}, threshold: {threshold}s")

        image_files = self.update_folder_contents()
        if not image_files:
            self.status_label.config(text="No images found!")
            self.running = False
            return

        logging.info(f"Found {len(image_files)} image files in {folder} (recursive={self.subfolder_var.get()})")
        groups = self.group_images(image_files)
        logging.info(f"Total files to process: {len(image_files)}")

        output_dir = os.path.join(folder, "_groups")
        city = self.get_city_from_gps(image_files[0]) if image_files else "unknown"
        date_time = datetime.now().strftime("%Y%m%d_%H%Mhrs")

        total_images = len(image_files)
        processed = 0

        for i, group in enumerate(groups, 1):
            if not self.running or self.paused:
                while self.paused and self.running:
                    time.sleep(0.1)
                if not self.running:
                    break

            group_dir = os.path.join(output_dir, f"{city}_{date_time}_{i:02d}_{len(group)}")
            logging.info(f"Creating group directory: {group_dir}")
            os.makedirs(group_dir, exist_ok=True)

            for image_path, dt in group:
                if not self.running:
                    break
                dest_path = os.path.join(group_dir, os.path.basename(image_path))
                shutil.move(image_path, dest_path)
                logging.debug(f"Moved {image_path} to {dest_path}")
                processed += 1
                self.progress['value'] = (processed / total_images) * 100
                logging.debug(f"Progress updated: value={self.progress['value']}, processed={processed}, total={total_images}")
                self.root.update()

        self.status_label.config(text=f"Grouping complete: {len(groups)} groups, {processed} images moved, {total_images - processed} singles left")
        logging.info(f"Grouping complete: {len(groups)} groups, {processed} images moved, {total_images - processed} singles left")
        self.running = False

    def exit_app(self):
        self.running = False
        self.save_last_folder()
        self.root.quit()

if __name__ == "__main__":
    root = tk.Tk()
    app = ImageSetSorter(root)
    root.mainloop()