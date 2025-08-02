# imgsetsortr.py
# Copyright (c) 2025
#
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""
imgsetsortr

A utility for grouping images in a folder based on contiguous timestamps from EXIF DateTimeOriginal.
Images are grouped if 5 or more have timestamps within a user-settable time increment.
Groups are moved into subfolders named with place (from EXIF or XMP metadata), date, hour, and file count
(e.g., 'brisbane_20250403_1600hrs_20'). A GUI allows folder selection, subfolder processing, and displays results.
Comprehensive logging is written to a file in the application directory.
"""

import sys
import os
import shutil
import threading
import time
import logging
from datetime import datetime
from tkinter import filedialog, messagebox, Tk, Label, Button, Listbox, END, StringVar
from tkinter import ttk
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
import exifread
import re

# Default time difference threshold (seconds) between consecutive images
TIME_DIFF_THRESHOLD = 1.0

# Initialize geocoder for location lookup
geolocator = Nominatim(user_agent="imgsetsortr")

# Set up logging
def setup_logging(app_dir):
    """Configure logging to a file in the application directory.

    Args:
        app_dir (str): Directory where the log file will be saved.

    Returns:
        logging.Logger: Configured logger instance.
    """
    log_file = os.path.join(app_dir, "imgsetsortr.log")
    logging.basicConfig(
        filename=log_file,
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(message)s",
        encoding="utf-8"
    )
    logger = logging.getLogger("imgsetsortr")
    logger.info("Logging initialized")
    return logger

# Get the application directory
def get_app_dir():
    """Determine the writable application directory for settings and logs.

    Returns:
        str: Path to the application directory.
    """
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        if os.access(exe_dir, os.W_OK):
            return exe_dir
    script_dir = os.path.dirname(__file__)
    if os.access(script_dir, os.W_OK):
        return script_dir
    config_dir = os.path.expanduser("~/.config/imgsetsortr")
    os.makedirs(config_dir, exist_ok=True)
    return config_dir

SETTINGS_FILE = os.path.join(get_app_dir(), "settings.txt")
logger = setup_logging(get_app_dir())

# Load/save last used folder
def load_last_folder():
    """Load the last used folder path from the settings file.

    Returns:
        str or None: The last used folder path, or None if not set or invalid.
    """
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                folder = f.read().strip()
                if folder and os.path.isdir(folder):
                    logger.info(f"Loaded last folder: {folder}")
                    return folder
        except Exception as e:
            logger.error(f"Failed to load last folder: {e}")
    return None

def save_last_folder(folder):
    """Save the given folder path to the settings file.

    Args:
        folder (str): The folder path to save.
    """
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            f.write(folder)
        logger.info(f"Saved last folder: {folder}")
    except Exception as e:
        logger.error(f"Failed to save last folder: {e}")

# Get image files
def get_image_files(directory, recursive=False):
    """Retrieve a list of image file paths from the given directory.

    Skips '_groups' folders to avoid reprocessing grouped images.

    Args:
        directory (str): Path to the directory to search.
        recursive (bool): Whether to include image files from subdirectories.

    Returns:
        list: List of image file paths with extensions .jpg, .jpeg, or .png.
    """
    image_files = []
    if recursive:
        for root, dirs, files in os.walk(directory):
            if os.path.basename(root) in ["_groups"]:
                continue
            for f in files:
                if f.lower().endswith((".jpg", ".jpeg", ".png")):
                    image_files.append(os.path.join(root, f))
    else:
        image_files = [
            os.path.join(directory, f)
            for f in os.listdir(directory)
            if f.lower().endswith((".jpg", ".jpeg", ".png"))
            and os.path.isfile(os.path.join(directory, f))
        ]
    logger.info(f"Found {len(image_files)} image files in {directory} (recursive={recursive})")
    return image_files

def get_image_files_by_folder(directory, recursive=False):
    """Retrieve image files grouped by folder.

    Skips '_groups' folders. Returns a dictionary mapping folder paths to lists of image files.

    Args:
        directory (str): Root directory to search.
        recursive (bool): Whether to include subfolders.

    Returns:
        dict: Mapping from folder path to list of image file paths.
    """
    folders = {}
    if recursive:
        for root, dirs, files in os.walk(directory):
            if os.path.basename(root) in ["_groups"]:
                continue
            image_files = [
                os.path.join(root, f)
                for f in files
                if f.lower().endswith((".jpg", ".jpeg", ".png"))
            ]
            if image_files:
                folders[root] = image_files
    else:
        folders[directory] = get_image_files(directory, recursive=False)
    logger.info(f"Found images in {len(folders)} folders in {directory}")
    return folders

# Get image timestamp
def get_image_timestamp(path):
    """Get the DateTimeOriginal timestamp from EXIF metadata, falling back to file modification time.

    Args:
        path (str): Path to the image file.

    Returns:
        datetime or None: Timestamp as a datetime object, or None if unavailable.
    """
    try:
        with open(path, 'rb') as f:
            tags = exifread.process_file(f, details=False)
            date_str = tags.get('EXIF DateTimeOriginal')
            if date_str:
                # Parse EXIF DateTimeOriginal (format: YYYY:MM:DD HH:MM:SS)
                try:
                    dt = datetime.strptime(str(date_str), "%Y:%m:%d %H:%M:%S")
                    logger.debug(f"Got EXIF DateTimeOriginal for {path}: {dt}")
                    return dt
                except ValueError as e:
                    logger.warning(f"Invalid EXIF DateTimeOriginal for {path}: {e}")
        # Fallback to file modification time
        mtime = datetime.fromtimestamp(os.path.getmtime(path))
        logger.debug(f"Using file mtime for {path}: {mtime}")
        return mtime
    except Exception as e:
        logger.error(f"Failed to get timestamp for {path}: {e}")
        return None

# Convert GPS coordinates to decimal
def gps_to_decimal(gps_coords, direction):
    """Convert GPS coordinates from DMS format to decimal degrees.

    Args:
        gps_coords (tuple): Tuple of (degrees, minutes, seconds).
        direction (str): Hemisphere direction ('N', 'S', 'E', 'W').

    Returns:
        float: Decimal degrees, negative for S or W directions.
    """
    try:
        degrees, minutes, seconds = gps_coords
        decimal = float(degrees) + float(minutes)/60 + float(seconds)/3600
        if direction in ['S', 'W']:
            decimal = -decimal
        return decimal
    except Exception as e:
        logger.error(f"Failed to convert GPS coordinates {gps_coords}: {e}")
        return None

# Extract place from EXIF or XMP metadata
def get_place_from_exif_or_xmp(file_path):
    """Extract location from EXIF GPS or XMP metadata, using reverse geocoding for GPS.

    Args:
        file_path (str): Path to the image file.

    Returns:
        str: City name (lowercase, underscores), or 'unknown' if no location is found.
    """
    try:
        # Try EXIF first
        with open(file_path, 'rb') as f:
            tags = exifread.process_file(f, details=False)
            gps_info = {key: tags[key] for key in tags if key.startswith('GPS')}
            if gps_info.get('GPS GPSLatitude') and gps_info.get('GPS GPSLongitude'):
                lat = gps_info.get('GPS GPSLatitude').values
                lat_ref = str(gps_info.get('GPS GPSLatitudeRef', 'N'))
                lon = gps_info.get('GPS GPSLongitude').values
                lon_ref = str(gps_info.get('GPS GPSLongitudeRef', 'E'))
                if lat and lon:
                    latitude = gps_to_decimal(lat, lat_ref)
                    longitude = gps_to_decimal(lon, lon_ref)
                    if latitude is not None and longitude is not None:
                        try:
                            location = geolocator.reverse((latitude, longitude), language="en", timeout=5)
                            if location and location.raw.get("address"):
                                address = location.raw["address"]
                                city = address.get("city") or address.get("town") or address.get("village") or "unknown"
                                logger.info(f"Got city from EXIF GPS for {file_path}: {city}")
                                return city.lower().replace(" ", "_")
                        except (GeocoderTimedOut, GeocoderUnavailable) as e:
                            logger.warning(f"Geocoding failed for {file_path}: {e}")

        # Try XMP metadata
        with open(file_path, 'rb') as f:
            data = f.read()
            xmp_match = re.search(rb'<xmp:City>(.*?)</xmp:City>', data, re.IGNORECASE | re.DOTALL)
            if xmp_match:
                city = xmp_match.group(1).decode('utf-8', errors='ignore').strip()
                if city:
                    logger.info(f"Got city from XMP for {file_path}: {city}")
                    return city.lower().replace(" ", "_")
        logger.debug(f"No location found for {file_path}")
        return "unknown"
    except Exception as e:
        logger.error(f"Failed to get place for {file_path}: {e}")
        return "unknown"

# Confirm close if work in progress
def confirm_close(root, progress):
    """Prompt user to confirm closing the app if processing is in progress.

    Args:
        root (Tk): The main Tkinter window.
        progress (ttk.Progressbar): The progress bar widget.
    """
    if 0 < progress["value"] < 100:
        if not messagebox.askyesno(
            "Work in progress:",
            "Are you sure you want to close?",
        ):
            logger.info("Close cancelled by user")
            return
    logger.info("Closing application")
    root.destroy()

def main():
    """Launch the Tkinter GUI for selecting a folder and grouping images by timestamp.

    Features:
    - Folder selection with browse button and last folder memory.
    - Option to process subfolders.
    - User-settable time difference threshold for grouping.
    - Listbox displaying folder contents.
    - Progress bar with elapsed/estimated time and processed/total counts.
    - Start, Pause, and Close buttons, with a warning if closing during processing.
    - Results listbox showing number of groups, images moved, and singles left.
    - Comprehensive logging to a file.
    """
    logger.info("Starting imgsetsortr application")
    root = Tk()
    root.resizable(True, True)
    root.title("imgsetsortr - Group Images by Timestamp")
    root.configure(bg="lightcoral")
    root.tk_setPalette(background="lightcoral", foreground="blue")
    default_font = ("Arial", 12, "bold")
    root.option_add("*Font", default_font)

    # Set window size and position
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width - 800) // 4
    y = (screen_height - 600) // 4
    root.geometry(f"600x800+{x}+{y}")
    logger.debug("Window initialized with geometry 600x800")

    # Set window icon if available
    icon_path = os.path.join(os.path.dirname(__file__), "imgs/imgsetsortr.ico")
    if os.path.exists(icon_path):
        root.iconbitmap(icon_path)
        logger.debug(f"Set window icon: {icon_path}")

    # Store selected folder
    selected_folder = {"path": load_last_folder()}

    # Prompt text
    label = Label(
        root,
        text="Select folder[s] containing images to group:",
        bg="lightcoral",
        fg="blue",
        font=("Arial", 14, "bold"),
    )
    label.pack(pady=10)

    # Frame for folder label and browse button
    frame_folder = ttk.Frame(root)
    frame_folder.pack(fill="x", padx=10)
    label_selected_folder = Label(
        frame_folder,
        text=selected_folder["path"] if selected_folder["path"] else "No folder selected",
        fg="black" if selected_folder["path"] else "gray",
        bg="lightcoral",
    )
    label_selected_folder.pack(side="left", fill="x", expand=True)

    def browse_folder():
        """Handle folder selection and update the UI with folder contents."""
        initialdir = selected_folder["path"] if selected_folder["path"] else None
        folder = filedialog.askdirectory(initialdir=initialdir)
        if folder:
            selected_folder["path"] = folder
            save_last_folder(folder)
            label_selected_folder.config(text=folder, fg="blue")
            listbox_results.delete(0, END)
            progress["value"] = 0
            label_elapsed.config(text="Elapsed: 0s")
            label_remaining.config(text="Estimated remaining: --")
            label_processed.config(text="Processed: 0")
            label_total.config(text="Total: --")
            update_folder_contents_listbox()
            logger.info(f"Selected folder: {folder}")

    button_browse = Button(
        frame_folder, text="Browse", command=browse_folder, bg="lightblue"
    )
    button_browse.pack(side="right", padx=5, pady=5)

    # Checkbox for processing subfolders
    frame_folder_options = ttk.Frame(root)
    frame_folder_options.pack(pady=5, fill="x")
    style = ttk.Style()
    frame_folder_options.configure(style="FolderOptions.TFrame")
    style.configure("TCheckbutton", background="lightcoral", foreground="blue")
    style.configure("FolderOptions.TFrame", background="lightcoral")

    frame_folder_options.columnconfigure(0, weight=1)
    frame_folder_options.columnconfigure(1, weight=0)
    frame_folder_options.columnconfigure(2, weight=1)

    process_subfolders_var = StringVar(value="0")
    check_subfolders = ttk.Checkbutton(
        frame_folder_options,
        text="Process subfolders",
        variable=process_subfolders_var,
        onvalue="1",
        offvalue="0",
        command=lambda: update_folder_contents_listbox(),
    )
    check_subfolders.grid(row=0, column=1, padx=10, pady=2)
    logger.debug("Initialized subfolder checkbox")

    # Time difference threshold
    frame_thresholds = ttk.Frame(root)
    frame_thresholds.pack(pady=5, fill="x")
    frame_thresholds.configure(style="Thresholds.TFrame")
    style.configure("Thresholds.TFrame", background="lightcoral")

    frame_thresholds.columnconfigure(0, weight=1)
    frame_thresholds.columnconfigure(1, weight=0)
    frame_thresholds.columnconfigure(2, weight=0)
    frame_thresholds.columnconfigure(3, weight=1)

    Label(frame_thresholds, text="Time diff (s):", font=("Arial", 12, "bold")).grid(
        row=0, column=1, padx=(0, 2), pady=2, sticky="e"
    )
    time_diff_var = StringVar(value=str(TIME_DIFF_THRESHOLD))
    entry_time_diff = ttk.Entry(frame_thresholds, textvariable=time_diff_var, width=5)
    entry_time_diff.grid(row=0, column=2, padx=(0, 10), pady=2, sticky="w")
    entry_time_diff.configure(background="lightblue", foreground="blue")

    def update_thresholds():
        """Update the global time difference threshold based on user input."""
        global TIME_DIFF_THRESHOLD
        try:
            val = float(time_diff_var.get())
            TIME_DIFF_THRESHOLD = max(0.01, val)
            logger.info(f"Updated time threshold to {TIME_DIFF_THRESHOLD}s")
        except Exception as e:
            logger.warning(f"Invalid time diff input, keeping previous: {e}")

    entry_time_diff.bind("<FocusOut>", lambda e: update_thresholds())
    entry_time_diff.bind("<Return>", lambda e: update_thresholds())

    # Label for total image count
    label_image_count = Label(root, text="No folder selected")
    label_image_count.pack()

    # Listbox for folder contents
    frame_listbox = ttk.Frame(root)
    frame_listbox.pack(fill="both", expand=True, padx=10, pady=5)
    listbox_folder_contents = Listbox(
        frame_listbox, width=80, height=18, bg="lightblue", fg="blue"
    )
    listbox_folder_contents.pack(side="left", fill="both", expand=True)
    scrollbar_folder = ttk.Scrollbar(
        frame_listbox, orient="vertical", command=listbox_folder_contents.yview
    )
    scrollbar_folder.pack(side="right", fill="y")
    listbox_folder_contents.config(yscrollcommand=scrollbar_folder.set)

    # Results listbox
    listbox_results = Listbox(root, width=30, height=3, bg="lightblue", fg="blue")
    listbox_results.pack(pady=10)

    def update_folder_contents_listbox():
        """Update the listbox with the contents of the selected folder(s)."""
        listbox_folder_contents.delete(0, END)
        folder = selected_folder["path"]
        if not folder:
            return
        try:
            recursive = process_subfolders_var.get() == "1"
            folders_dict = get_image_files_by_folder(folder, recursive=recursive)
            total_images = sum(len(files) for files in folders_dict.values())
            label_image_count.config(text=f"Total images found: {total_images}")
            for subfolder, files in sorted(folders_dict.items()):
                rel_subfolder = os.path.relpath(subfolder, folder)
                listbox_folder_contents.insert(END, f"[{rel_subfolder}]")
                for f in sorted(files):
                    listbox_folder_contents.insert(END, f"    {os.path.basename(f)}")
            logger.info(f"Updated folder contents listbox with {total_images} images")
        except Exception as e:
            label_image_count.config(text="Error reading folder")
            listbox_folder_contents.insert(END, f"Error: {e}")
            logger.error(f"Error updating folder contents: {e}")

    # Progress bar and info
    frame_progress = ttk.Frame(root)
    frame_progress.pack(pady=5, fill="x")
    frame_progress.configure(style="Progress.TFrame")
    style.configure("Progress.TFrame", background="lightcoral")

    frame_labels = ttk.Frame(frame_progress)
    frame_labels.pack(fill="x")
    frame_labels.configure(style="Labels.TFrame")
    style.configure("Labels.TFrame", background="lightcoral", foreground="blue")

    frame_left = ttk.Frame(frame_labels)
    frame_left.pack(side="left", anchor="w")
    frame_left.configure(style="Labels.TFrame")
    frame_right = ttk.Frame(frame_labels)
    frame_right.pack(side="right", anchor="e")
    frame_right.configure(style="Labels.TFrame")

    label_elapsed = Label(
        frame_left,
        text="Elapsed: 0s",
        bg="lightcoral",
        fg="blue",
        font=("Arial", 12, "bold"),
    )
    label_elapsed.pack(anchor="w")
    label_remaining = Label(
        frame_left,
        text="Estimated remaining: --",
        bg="lightcoral",
        fg="blue",
        font=("Arial", 12, "bold"),
    )
    label_remaining.pack(anchor="w")

    label_processed = Label(
        frame_right,
        text="Processed: 0",
        bg="lightcoral",
        fg="blue",
        font=("Arial", 12, "bold"),
    )
    label_processed.pack(anchor="e")
    label_total = Label(
        frame_right,
        text="Total: --",
        bg="lightcoral",
        fg="blue",
        font=("Arial", 12, "bold"),
    )
    label_total.pack(anchor="e")

    progress = ttk.Progressbar(
        frame_progress, orient="horizontal", length=300, mode="determinate"
    )
    progress.pack(fill="x", pady=5, padx=5, expand=True)

    def update_progress(
        value, elapsed=None, remaining=None, processed=None, total=None
    ):
        """Update the progress bar and info labels.

        Args:
            value (int): Percentage (0–100) for the progress bar.
            elapsed (float, optional): Elapsed time in seconds.
            remaining (float, optional): Estimated time remaining in seconds.
            processed (int, optional): Number of files processed.
            total (int, optional): Total number of files to process.
        """
        progress["value"] = value
        if elapsed is not None:
            label_elapsed.config(text=f"Elapsed: {int(elapsed)}s")
        if remaining is not None:
            if remaining >= 0:
                label_remaining.config(text=f"Estimated remaining: {int(remaining)}s")
            else:
                label_remaining.config(text="Estimated remaining: --")
        if processed is not None:
            label_processed.config(text=f"Processed: {processed}")
        if total is not None:
            label_total.config(text=f"Total: {total}")
        root.update_idletasks()
        logger.debug(f"Progress updated: value={value}, processed={processed}, total={total}")

    def start_grouping():
        """Perform image grouping based on contiguous timestamps and move to subfolders."""
        progress["value"] = 0
        label_elapsed.config(text="Elapsed: 0s")
        label_remaining.config(text="Estimated remaining: --")
        label_processed.config(text="Processed: 0")
        label_total.config(text="Total: --")
        listbox_results.delete(0, END)

        folder = selected_folder["path"]
        if not folder:
            messagebox.showerror(
                "No folder selected", "Please select a folder before starting."
            )
            logger.error("Start attempted with no folder selected")
            return
        update_thresholds()
        logger.info(f"Starting grouping for folder: {folder}, threshold: {TIME_DIFF_THRESHOLD}s")

        def task():
            start_time = time.time()
            folders_dict = get_image_files_by_folder(
                folder, recursive=(process_subfolders_var.get() == "1")
            )
            image_files = [f for files in folders_dict.values() for f in files]
            total_files = len(image_files)
            root.after(0, update_progress, 0, 0, None, 0, total_files)
            logger.info(f"Total files to process: {total_files}")

            processed = [0]
            total_paused_time = [0]
            pause_start_time = [None]

            def progress_callback(value):
                now = time.time()
                elapsed = max(0, now - start_time - total_paused_time[0])
                if value > 0:
                    avg_time_per_percent = elapsed / value
                    remaining = avg_time_per_percent * (100 - value)
                else:
                    remaining = -1
                processed_count = int((value / 100) * total_files)
                processed[0] = processed_count
                root.after(
                    0,
                    update_progress,
                    value,
                    elapsed,
                    remaining,
                    processed_count,
                    total_files,
                )

            # Sort images by timestamp, then by filename to handle identical timestamps
            image_files.sort(key=lambda x: (get_image_timestamp(x) or datetime.max, os.path.basename(x)))
            groups = []
            current_group = []
            last_timestamp = None

            for i, path in enumerate(image_files):
                curr_time = get_image_timestamp(path)
                if curr_time is None:
                    logger.warning(f"Skipping {path} due to missing timestamp")
                    continue
                if not current_group:
                    current_group.append(path)
                    last_timestamp = curr_time
                else:
                    time_diff = (curr_time - last_timestamp).total_seconds()
                    if time_diff <= TIME_DIFF_THRESHOLD:
                        current_group.append(path)
                    else:
                        if len(current_group) >= 5:
                            groups.append(current_group)
                            logger.debug(f"Formed group of {len(current_group)} images ending at {last_timestamp}")
                        current_group = [path]
                    last_timestamp = curr_time
                while not pause_event.is_set():
                    time.sleep(0.1)
                progress_callback(min(100, int((i / len(image_files)) * 100)))

            if len(current_group) >= 5:
                groups.append(current_group)
                logger.debug(f"Formed final group of {len(current_group)} images")

            # Move groups to directories
            for group in groups:
                if not group:
                    continue
                subdir = os.path.dirname(group[0])
                dest_dir = os.path.join(subdir, "_groups")
                os.makedirs(dest_dir, exist_ok=True)
                place = get_place_from_exif_or_xmp(group[0])
                first_time = get_image_timestamp(group[0])
                if first_time:
                    date_str = first_time.strftime("%Y%m%d")
                    hour_str = first_time.strftime("%H00hrs")
                    count = len(group)
                    folder_name = f"{place}_{date_str}_{hour_str}_{count}"
                    group_dir = os.path.join(dest_dir, folder_name)
                    os.makedirs(group_dir, exist_ok=True)
                    logger.info(f"Creating group directory: {group_dir}")
                    for file in group:
                        try:
                            dest_path = os.path.join(group_dir, os.path.basename(file))
                            shutil.move(file, dest_path)
                            logger.debug(f"Moved {file} to {dest_path}")
                        except Exception as e:
                            logger.error(f"Failed to move {file}: {e}")

            num_groups = len(groups)
            total_moved = sum(len(g) for g in groups)
            num_singles = total_files - total_moved
            elapsed = time.time() - start_time - total_paused_time[0]
            root.after(0, update_progress, 100, elapsed, 0, total_files, total_files)
            root.after(
                0,
                lambda: [
                    listbox_results.insert(END, f"Groups created: {num_groups}"),
                    listbox_results.insert(END, f"Images moved: {total_moved}"),
                    listbox_results.insert(END, f"Singles left: {num_singles}"),
                    messagebox.showinfo(
                        "Done", f"Created {num_groups} groups with {total_moved} images."
                    ),
                ],
            )
            logger.info(f"Grouping complete: {num_groups} groups, {total_moved} images moved, {num_singles} singles left")

        threading.Thread(target=task, daemon=True).start()

    # Button row: Start | Pause | Close
    frame_buttons = ttk.Frame(root)
    frame_buttons.pack(fill="x", pady=10)
    frame_buttons.configure(style="Buttons.TFrame")
    style.configure("Buttons.TFrame", background="lightcoral")

    frame_buttons.columnconfigure(0, weight=1)
    frame_buttons.columnconfigure(1, weight=0)
    frame_buttons.columnconfigure(2, weight=1)
    frame_buttons.columnconfigure(3, weight=0)
    frame_buttons.columnconfigure(4, weight=1)
    frame_buttons.columnconfigure(5, weight=0)
    frame_buttons.columnconfigure(6, weight=1)

    button_start = Button(
        frame_buttons,
        text="Start",
        command=start_grouping,
        width=7,
        bg="limegreen",
        activebackground="green2",
        font=("Arial", 12, "bold"),
    )
    button_start.grid(row=0, column=1, padx=10)

    pause_event = threading.Event()
    pause_event.set()
    pause_continue_label = StringVar(value="Pause")
    pause_start_time = [None]
    total_paused_time = [0]

    def pause_or_continue():
        """Toggle between pausing and resuming the grouping process."""
        if pause_event.is_set():
            pause_event.clear()
            pause_continue_label.set("Continue")
            pause_start_time[0] = time.time()
            logger.info("Paused processing")
        else:
            pause_event.set()
            pause_continue_label.set("Pause")
            if pause_start_time[0] is not None:
                total_paused_time[0] += time.time() - pause_start_time[0]
                pause_start_time[0] = None
            logger.info("Resumed processing")

    button_pause = Button(
        frame_buttons,
        textvariable=pause_continue_label,
        command=pause_or_continue,
        width=10,
        bg="gold",
        activebackground="yellow",
        font=("Arial", 12, "bold"),
    )
    button_pause.grid(row=0, column=3, padx=10)

    button_close = Button(
        frame_buttons,
        text="EXIT",
        command=lambda: confirm_close(root, progress),
        width=7,
        bg="red",
        activebackground="darkred",
        font=("Arial", 12, "bold"),
    )
    button_close.grid(row=0, column=5, padx=10)

    root.mainloop()

if __name__ == "__main__":
    main()