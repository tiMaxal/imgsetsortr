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
Groups are moved into subfolders named with place (from XMP, EXIF, GPS metadata, or parent directory),
date, hour, minute, group increment, and file count (e.g., 'kirribilli_20250410-0627_01_20') in a user-selected output folder
(defaulting to input_folder/_groups).
Supports GUI and CLI modes:
- CLI: -s/--source, -r/--recurse, -i/--increment, -o/--output, -?/--help
- GUI: Folder selection, subfolder processing, time threshold adjustment, results display, and help popup.
Comprehensive logging is written to a file in the application directory, including profiling data.

'voded' [vibe-coded] with Grok-ai
"""

import sys
import os
import shutil
import threading
import time
import logging
import cProfile
import pstats
import argparse
from datetime import datetime
from tkinter import filedialog, messagebox, Tk, Label, Button, Listbox, END, StringVar, Canvas, Toplevel, Text
from tkinter import ttk
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
import exifread
import re
import pyexiv2
import webbrowser

# Default time difference threshold (seconds) between consecutive images
TIME_DIFF_THRESHOLD = 1.0

# Initialize geocoder and cache for location lookup
geolocator = Nominatim(user_agent="imgsetsortr")
geocode_cache = {}  # Cache for reverse geocoding results: (lat, lon) -> place

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
HELP_FILE = os.path.join(get_app_dir(), "imgsetsortr_help.html")
logger = setup_logging(get_app_dir())

# Help content for CLI and GUI
HELP_CONTENT = """
imgsetsortr - Group Images by Timestamp

Overview:
imgsetsortr is a utility that groups images based on contiguous timestamps from EXIF DateTimeOriginal metadata. Images are grouped if 5 or more have timestamps within a specified time increment. Groups are moved into subfolders named with a place (derived from XMP, EXIF, GPS metadata, or parent directory), date, hour, minute, group number, and file count (e.g., 'kirribilli_20250410-0627_01_20').

Usage:
- CLI Mode:
  Run from the command line with:
    python imgsetsortr.py -s SOURCE [-r] [-i INCREMENT] [-o OUTPUT] [-? | --help]
  Options:
    -s, --source     Source folder containing images (required).
    -r, --recurse    Process subdirectories recursively (optional).
    -i, --increment  Maximum seconds between images in a group (default: 1.0).
    -o, --output     Output folder for grouped images (default: source/_groups).
    -?, --help       Show this help message and exit.

  Example:
    python imgsetsortr.py -s ./photos -r -i 2.0 -o ./photos_sorted

- GUI Mode:
  Run without arguments to launch the GUI:
    python imgsetsortr.py
  Steps:
    1. Click "Browse Input" to select the folder containing images.
    2. Optionally, click "Browse Output" to choose a custom output folder (defaults to input_folder/_groups).
    3. Check "Process subfolders" to include images in subdirectories.
    4. Adjust "Time diff (s)" to set the maximum seconds between images in a group.
    5. Click "Start" to begin grouping. Use "Pause" to pause/resume, or "EXIT" to close.
    6. Click "Help" (top-left) for these instructions.

Output:
- Groups of 5 or more images with timestamps within the specified increment are moved to subfolders in the output directory.
- Subfolder names follow the format: <place>_<YYYYMMDD-HHMM>_<group_number>_<file_count>.
- Images not in groups (singles) remain in their original folders.
- A log file (imgsetsortr.log) and profiling data (imgsetsortr.prof) are saved in the application directory.

Notes:
- Supported image formats: .jpg, .jpeg, .png.
- Location is derived from XMP (e.g., photoshop:City), EXIF (e.g., XPTitle), GPS reverse geocoding, or the parent directory name.
- Timestamps are read from EXIF DateTimeOriginal, falling back to file modification time if unavailable.
- Invalid timestamps (before 2000 or beyond next year) use file modification time.
- Requires Python libraries: PIL, exifread, pyexiv2, geopy.
"""

def create_help_html():
    """Create an HTML file with help content in the application directory."""
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>imgsetsortr Help</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
        h1 {{ color: #333; }}
        h2 {{ color: #555; }}
        pre {{ background: #f4f4f4; padding: 10px; border-radius: 5px; }}
        p {{ margin: 10px 0; }}
    </style>
</head>
<body>
    <h1>imgsetsortr Help</h1>
    <pre>{HELP_CONTENT}</pre>
</body>
</html>
"""
    try:
        with open(HELP_FILE, "w", encoding="utf-8") as f:
            f.write(html_content)
        logger.info(f"Created help HTML file: {HELP_FILE}")
    except Exception as e:
        logger.error(f"Failed to create help HTML file: {e}")

# Load/save last used folders
def load_last_folders():
    """Load the last used input and output folder paths from the settings file.

    Returns:
        tuple: (input_folder, output_folder), each str or None if not set or invalid.
    """
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
                input_folder = lines[0].strip() if lines else None
                output_folder = lines[1].strip() if len(lines) > 1 else None
                if input_folder and os.path.isdir(input_folder):
                    logger.info(f"Loaded last input folder: {input_folder}")
                else:
                    input_folder = None
                if output_folder and os.path.isdir(output_folder):
                    logger.info(f"Loaded last output folder: {output_folder}")
                else:
                    output_folder = None
                return input_folder, output_folder
        except Exception as e:
            logger.error(f"Failed to load last folders: {e}")
    return None, None

def save_last_folders(input_folder, output_folder):
    """Save the input and output folder paths to the settings file.

    Args:
        input_folder (str): The input folder path to save.
        output_folder (str): The output folder path to save.
    """
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            f.write(f"{input_folder}\n{output_folder}")
        logger.info(f"Saved folders: input={input_folder}, output={output_folder}")
    except Exception as e:
        logger.error(f"Failed to save folders: {e}")

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
    start_time = time.time()
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
    elapsed = time.time() - start_time
    logger.info(f"Found {len(image_files)} image files in {directory} (recursive={recursive}) in {elapsed:.2f}s")
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
    start_time = time.time()
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
    elapsed = time.time() - start_time
    logger.info(f"Found images in {len(folders)} folders in {directory} in {elapsed:.2f}s")
    return folders

# Get image timestamp
def get_image_timestamp(path):
    """Get the DateTimeOriginal timestamp from EXIF metadata, falling back to file modification time.

    Validates the timestamp year to ensure it's reasonable (2000 to current year + 1).

    Args:
        path (str): Path to the image file.

    Returns:
        datetime or None: Timestamp as a datetime object, or None if unavailable.
    """
    start_time = time.time()
    try:
        with open(path, 'rb') as f:
            tags = exifread.process_file(f, details=False)
            date_str = tags.get('EXIF DateTimeOriginal')
            if date_str:
                try:
                    dt = datetime.strptime(str(date_str), "%Y:%m:%d %H:%M:%S")
                    current_year = datetime.now().year
                    if dt.year < 2000 or dt.year > current_year + 1:
                        logger.warning(f"Invalid year in EXIF DateTimeOriginal for {path}: {dt.year}")
                        mtime = datetime.fromtimestamp(os.path.getmtime(path))
                        logger.debug(f"Using file mtime for {path}: {mtime}")
                        elapsed = time.time() - start_time
                        logger.debug(f"Got timestamp for {path} in {elapsed:.2f}s (mtime)")
                        return mtime
                    logger.debug(f"Got EXIF DateTimeOriginal for {path}: {dt}")
                    elapsed = time.time() - start_time
                    logger.debug(f"Got timestamp for {path} in {elapsed:.2f}s (EXIF)")
                    return dt
                except ValueError as e:
                    logger.warning(f"Invalid EXIF DateTimeOriginal for {path}: {e}")
        mtime = datetime.fromtimestamp(os.path.getmtime(path))
        logger.debug(f"Using file mtime for {path}: {mtime}")
        elapsed = time.time() - start_time
        logger.debug(f"Got timestamp for {path} in {elapsed:.2f}s (mtime)")
        return mtime
    except Exception as e:
        logger.error(f"Failed to get timestamp for {path}: {e}")
        elapsed = time.time() - start_time
        logger.debug(f"Failed timestamp for {path} in {elapsed:.2f}s")
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
    start_time = time.time()
    try:
        degrees, minutes, seconds = gps_coords
        decimal = float(degrees) + float(minutes)/60 + float(seconds)/3600
        if direction in ['S', 'W']:
            decimal = -decimal
        elapsed = time.time() - start_time
        logger.debug(f"Converted GPS coords {gps_coords} ({direction}) to {decimal} in {elapsed:.2f}s")
        return decimal
    except Exception as e:
        logger.error(f"Failed to convert GPS coordinates {gps_coords}: {e}")
        elapsed = time.time() - start_time
        logger.debug(f"Failed GPS conversion in {elapsed:.2f}s")
        return None

# Extract place from XMP, EXIF, GPS metadata, or directory
def get_place_from_exif_or_xmp(file_path):
    """Extract location from XMP, EXIF, GPS reverse geocoding, or parent directory.

    Prioritizes:
    1. XMP metadata (photoshop:City, Iptc4xmpCore:LocationCreated, Iptc4xmpCore:LocationShown, dc:location).
    2. EXIF metadata (XPTitle, XPSubject, XPAuthor, XPComment, XPKeywords).
    3. GPS reverse geocoding (suburb, neighbourhood, city, town, or village).
    4. Non-generic parent directory name (skipping '_groups', '_copy', 'sub', etc.).

    Args:
        file_path (str): Path to the image file.

    Returns:
        str: Normalized location name (e.g., 'kirribilli' or 'milsons-point'), or 'unknown' if none found.
    """
    start_time = time.time()
    def normalize_location(location):
        """Normalize location name: hyphenate multi-word names, lowercase, and remove invalid chars."""
        if not location:
            return 'unknown'
        location = re.sub(r'[^\w\s-]', '', location).strip()
        location = '-'.join(word.lower() for word in location.split())
        elapsed = time.time() - start_time
        logger.debug(f"Normalized location '{location}' in {elapsed:.2f}s")
        return location if location else 'unknown'

    try:
        # Try XMP metadata first
        try:
            xmp_start = time.time()
            img = pyexiv2.Image(file_path)
            xmp_data = img.read_xmp()
            xmp_fields = [
                'Xmp.photoshop.City',
                'Xmp.Iptc4xmpCore.LocationCreated',
                'Xmp.Iptc4xmpCore.LocationShown',
                'Xmp.dc.location'
            ]
            for field in xmp_fields:
                if field in xmp_data:
                    location = xmp_data[field]
                    if location:
                        logger.info(f"Got location from XMP {field} for {file_path}: {location}")
                        img.close()
                        elapsed = time.time() - start_time
                        logger.debug(f"Got XMP location in {elapsed:.2f}s")
                        return normalize_location(location)
            img.close()
            elapsed = time.time() - xmp_start
            logger.debug(f"Checked XMP metadata for {file_path} in {elapsed:.2f}s")
        except Exception as e:
            logger.error(f"Error reading XMP metadata for {file_path}: {str(e)}")
            elapsed = time.time() - start_time
            logger.debug(f"Failed XMP metadata read in {elapsed:.2f}s")

        # Read EXIF and GPS metadata in one pass
        exif_start = time.time()
        with open(file_path, 'rb') as f:
            tags = exifread.process_file(f, details=False)
            elapsed = time.time() - exif_start
            logger.debug(f"Read EXIF tags for {file_path} in {elapsed:.2f}s")
            # Try EXIF metadata
            exif_fields = ['Image XPTitle', 'Image XPSubject', 'Image XPAuthor', 'Image XPComment', 'Image XPKeywords']
            for field in exif_fields:
                if field in tags:
                    city = str(tags[field]).strip()
                    if city:
                        logger.info(f"Got location from EXIF {field} for {file_path}: {city}")
                        elapsed = time.time() - start_time
                        logger.debug(f"Got EXIF location in {elapsed:.2f}s")
                        return normalize_location(city)

            # Try GPS reverse geocoding
            gps_start = time.time()
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
                        # Check cache first (rounded to 6 decimal places for consistency)
                        cache_key = (round(latitude, 6), round(longitude, 6))
                        if cache_key in geocode_cache:
                            logger.info(f"Using cached location for {file_path}: {geocode_cache[cache_key]}")
                            elapsed = time.time() - start_time
                            logger.debug(f"Got cached GPS location in {elapsed:.2f}s")
                            return normalize_location(geocode_cache[cache_key])
                        try:
                            location = geolocator.reverse((latitude, longitude), language="en", timeout=5, zoom=16)
                            if location and location.raw.get("address"):
                                address = location.raw["address"]
                                place = (
                                    address.get("suburb") or
                                    address.get("neighbourhood") or
                                    address.get("city") or
                                    address.get("town") or
                                    address.get("village") or
                                    "unknown"
                                )
                                geocode_cache[cache_key] = place
                                logger.info(f"Got location from GPS reverse geocoding for {file_path}: {place}")
                                elapsed = time.time() - start_time
                                logger.debug(f"Got GPS location in {elapsed:.2f}s")
                                return normalize_location(place)
                        except (GeocoderTimedOut, GeocoderUnavailable) as e:
                            logger.warning(f"Geocoding failed for {file_path}: {e}")
                            elapsed = time.time() - gps_start
                            logger.debug(f"Failed GPS geocoding in {elapsed:.2f}s")

        # Fallback to non-generic parent directory
        dir_start = time.time()
        generic_names = {'_copy', 'sub', 'temp', 'backup', 'raw'}  # Generic directories to skip
        current_dir = os.path.dirname(file_path)
        max_levels = 5  # Limit traversal to avoid excessive backtracking
        level = 0
        while current_dir and level < max_levels:
            dir_name = os.path.basename(current_dir)
            normalized_dir = normalize_location(dir_name)
            if dir_name and not dir_name.startswith('_groups') and normalized_dir not in generic_names:
                logger.info(f"Using directory name as location for {file_path}: {dir_name}")
                elapsed = time.time() - start_time
                logger.debug(f"Got directory location in {elapsed:.2f}s")
                return normalize_location(dir_name)
            current_dir = os.path.dirname(current_dir)
            level += 1

        logger.debug(f"No location found for {file_path}")
        elapsed = time.time() - start_time
        logger.debug(f"No location found in {elapsed:.2f}s")
        return "unknown"
    except Exception as e:
        logger.error(f"Failed to get place for {file_path}: {e}")
        elapsed = time.time() - start_time
        logger.debug(f"Failed to get place in {elapsed:.2f}s")
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

# CLI processing function
def process_images_cli(source, recurse, increment, output):
    """Process images using command-line arguments.

    Args:
        source (str): Source folder to process.
        recurse (bool): Whether to process subdirectories.
        increment (float): Maximum time difference (seconds) between images in a group.
        output (str): Output folder for grouped images.
    """
    global TIME_DIFF_THRESHOLD
    TIME_DIFF_THRESHOLD = increment
    logger.info(f"Starting CLI processing: source={source}, recurse={recurse}, increment={increment}, output={output}")

    # Validate source folder
    if not os.path.isdir(source):
        logger.error(f"Source folder does not exist: {source}")
        print(f"Error: Source folder '{source}' does not exist.")
        sys.exit(1)

    # Create output folder if it doesn't exist
    try:
        os.makedirs(output, exist_ok=True)
        logger.info(f"Created/verified output folder: {output}")
    except Exception as e:
        logger.error(f"Failed to create output folder {output}: {str(e)}")
        print(f"Error: Failed to create output folder '{output}': {str(e)}")
        sys.exit(1)

    # Initialize profiler
    profiler = cProfile.Profile()
    profiler.enable()

    start_time = time.time()
    folders_dict = get_image_files_by_folder(source, recursive=recurse)
    image_files = [f for files in folders_dict.values() for f in files]
    total_files = len(image_files)
    logger.info(f"Total files to process: {total_files}")

    def print_progress(value, elapsed, processed, processed_count, total):
        """Print progress to console."""
        remaining = (elapsed / value * (100 - value)) if value > 0 else -1
        processed[0] = processed_count
        print(f"\rProgress: {value:.1f}% | Elapsed: {int(elapsed)}s | "
              f"Remaining: {int(remaining) if remaining >= 0 else '--'}s | "
              f"Processed: {processed[0]}/{total}", end="")
        logger.debug(f"Progress updated: value={value}, processed={processed[0]}, total={total}")

    # Initialize processed as a list to match GUI mode
    processed = [0]

    # Early exit if no files to process
    if total_files == 0:
        print_progress(100, time.time() - start_time, processed, 0, 0)
        print(f"\nCompleted: 0 groups created, 0 images moved, 0 singles left")
        logger.info("CLI processing complete: 0 groups, 0 images moved, 0 singles left")
        profiler.disable()
        profile_file = os.path.join(get_app_dir(), "imgsetsortr.prof")
        profiler.dump_stats(profile_file)
        ps = pstats.Stats(profile_file)
        ps.sort_stats(pstats.SortKey.CUMULATIVE)
        ps.print_stats(10)
        logger.info(f"Profiling data saved to {profile_file}")
        return

    # Sort images by timestamp, then by filename
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
        elapsed = time.time() - start_time
        progress_value = min(100, (i + 1) / len(image_files) * 100)
        processed[0] = i + 1
        print_progress(progress_value, elapsed, processed, i + 1, total_files)

    if len(current_group) >= 5:
        groups.append(current_group)
        logger.debug(f"Formed final group of {len(current_group)} images")

    # Move groups to output folder
    for idx, group in enumerate(groups, 1):
        if not group:
            continue
        move_start = time.time()
        place = get_place_from_exif_or_xmp(group[0])
        first_time = get_image_timestamp(group[0])
        if first_time:
            date_time_str = first_time.strftime("%Y%m%d-%H%M")
            count = len(group)
            folder_name = f"{place}_{date_time_str}_{idx:02d}_{count}"
            group_dir = os.path.join(output, folder_name)
            try:
                os.makedirs(group_dir, exist_ok=True)
                logger.info(f"Created group directory: {group_dir} with {count} images")
            except Exception as e:
                logger.error(f"Failed to create group directory {group_dir}: {str(e)}")
                continue
            for file in group:
                try:
                    dest_path = os.path.join(group_dir, os.path.basename(file))
                    shutil.move(file, dest_path)
                    logger.debug(f"Moved {file} to {dest_path}")
                except Exception as e:
                    logger.error(f"Failed to move {file}: {e}")
        elapsed = time.time() - move_start
        logger.debug(f"Moved group {idx} ({count} images) in {elapsed:.2f}s")

    num_groups = len(groups)
    total_moved = sum(len(g) for g in groups)
    num_singles = total_files - total_moved
    elapsed = time.time() - start_time
    print_progress(100, elapsed, processed, total_files, total_files)
    print(f"\nCompleted: {num_groups} groups created, {total_moved} images moved, {num_singles} singles left")
    logger.info(f"CLI processing complete: {num_groups} groups, {total_moved} images moved, {num_singles} singles left")

    # Save profiling data
    profiler.disable()
    profile_file = os.path.join(get_app_dir(), "imgsetsortr.prof")
    profiler.dump_stats(profile_file)
    ps = pstats.Stats(profile_file)
    ps.sort_stats(pstats.SortKey.CUMULATIVE)
    ps.print_stats(10)
    logger.info(f"Profiling data saved to {profile_file}")

def main():
    """Launch the application in CLI or GUI mode based on command-line arguments."""
    # Define a custom help formatter for better CLI help message
    class CustomHelpFormatter(argparse.RawDescriptionHelpFormatter):
        def add_usage(self, usage, actions, groups, prefix=None):
            if prefix is None:
                prefix = "Usage: "
            super().add_usage(usage, actions, groups, prefix)

    parser = argparse.ArgumentParser(
        description=HELP_CONTENT,
        formatter_class=CustomHelpFormatter,
        add_help=False
    )
    parser.add_argument("-s", "--source", help="Source folder to process")
    parser.add_argument("-r", "--recurse", action="store_true", help="Process subdirectories (default: False)")
    parser.add_argument("-i", "--increment", type=float, default=TIME_DIFF_THRESHOLD,
                        help="Max seconds between images in a group (default: 1.0)")
    parser.add_argument("-o", "--output", help="Output folder for grouped images (default: source/_groups)")
    parser.add_argument("-?", "--help", action="help", help="Show this help message and exit")

    args = parser.parse_args()

    # Check if CLI arguments are provided
    if args.source:
        source = os.path.abspath(args.source)
        output = args.output if args.output else os.path.join(source, "_groups")
        output = os.path.abspath(output)
        process_images_cli(source, args.recurse, args.increment, output)
        return

    # GUI mode
    logger.info("Starting imgsetsortr application in GUI mode")
    create_help_html()  # Create HTML help file at startup
    root = Tk()
    root.resizable(True, True)
    root.title("imgsetsortr - Group Images by Timestamp")
    root.configure(bg="gray90")
    root.tk_setPalette(background="gray90", foreground="black")
    default_font = ("Arial", 12, "bold")
    root.option_add("*Font", default_font)

    # Set window size and position
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width - 800) // 4
    y = (screen_height - 600) // 8
    root.geometry(f"800x950+{x}+{y}")
    logger.debug("Window initialized with geometry 800x950")

    # Set window icon if available
    icon_path = os.path.join(os.path.dirname(__file__), "imgs/imgsetsortr.ico")
    if os.path.exists(icon_path):
        root.iconbitmap(icon_path)
        logger.debug(f"Set window icon: {icon_path}")

    # Create main frame with scrollbar
    canvas = Canvas(root, bg="gray90")
    scrollbar = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)
    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    # Help button (top-left)
    def show_help():
        """Display a popup with help content and a link to open as HTML."""
        help_window = Toplevel(root)
        help_window.title("imgsetsortr Help")
        help_window.geometry("600x400")
        help_window.configure(bg="gray90")
        help_window.resizable(True, True)

        # Create frame for text and scrollbar
        help_frame = ttk.Frame(help_window)
        help_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Scrollbar on the left
        help_scrollbar = ttk.Scrollbar(help_frame, orient="vertical")
        help_scrollbar.pack(side="left", fill="y")

        # Text widget for help content
        help_text = Text(
            help_frame,
            wrap="word",
            height=20,
            bg="gray80",
            fg="black",
            font=("Arial", 10),
            yscrollcommand=help_scrollbar.set
        )
        help_text.pack(side="left", fill="both", expand=True)
        help_scrollbar.config(command=help_text.yview)

        # Insert help content
        help_text.insert(END, HELP_CONTENT)
        help_text.config(state="disabled")  # Make read-only

        # Button to open help as HTML
        def open_html_help():
            try:
                webbrowser.open(f"file://{os.path.abspath(HELP_FILE)}")
                logger.info(f"Opened help HTML in browser: {HELP_FILE}")
            except Exception as e:
                logger.error(f"Failed to open help HTML: {e}")
                messagebox.showerror("Error", f"Failed to open help file: {e}")

        html_button = Button(
            help_window,
            text="Open as HTML",
            command=open_html_help,
            bg="gray70",
            font=("Arial", 10, "bold")
        )
        html_button.pack(pady=5)

        # Center the help window
        help_window.update_idletasks()
        screen_width = help_window.winfo_screenwidth()
        screen_height = help_window.winfo_screenheight()
        x = (screen_width - 600) // 2
        y = (screen_height - 400) // 2
        help_window.geometry(f"600x400+{x}+{y}")
        logger.info("Opened help popup")

    help_button = Button(
        scrollable_frame,
        text="Help",
        command=show_help,
        bg="blue",
        fg="white",
        font=("Arial", 12, "bold")
    )
    help_button.pack(anchor="nw", padx=10, pady=5)

    # Store selected folders
    input_folder, output_folder = load_last_folders()
    selected_folders = {"input": input_folder, "output": output_folder}

    # Input folder prompt
    label_input = Label(
        scrollable_frame,
        text="Select folder[s] containing images to group:",
        bg="gray90",
        fg="black",
        font=("Arial", 14, "bold"),
    )
    label_input.pack(pady=10)

    # Frame for input folder label and browse button
    frame_input_folder = ttk.Frame(scrollable_frame)
    frame_input_folder.pack(fill="x", padx=10)
    label_selected_input = Label(
        frame_input_folder,
        text=selected_folders["input"] if selected_folders["input"] else "No input folder selected",
        fg="black" if selected_folders["input"] else "gray50",
        bg="gray90",
    )
    label_selected_input.pack(side="left", fill="x", expand=True)

    def browse_input_folder():
        """Handle input folder selection and update the UI with folder contents."""
        initialdir = selected_folders["input"] if selected_folders["input"] else None
        folder = filedialog.askdirectory(initialdir=initialdir)
        if folder:
            selected_folders["input"] = folder
            # Default output folder to input_folder/_groups
            selected_folders["output"] = os.path.join(folder, "_groups")
            # Ensure _groups folder exists
            try:
                os.makedirs(selected_folders["output"], exist_ok=True)
                logger.info(f"Created/verified output folder: {selected_folders['output']}")
            except Exception as e:
                logger.error(f"Failed to create output folder {selected_folders['output']}: {str(e)}")
                messagebox.showerror("Error", f"Failed to create output folder: {str(e)}")
                selected_folders["output"] = None
                label_selected_output.config(text="No output folder selected", fg="gray50")
                return
            save_last_folders(selected_folders["input"], selected_folders["output"])
            label_selected_input.config(text=folder, fg="black")
            label_selected_output.config(text=selected_folders["output"], fg="black")
            listbox_results.delete(0, END)
            progress["value"] = 0
            label_elapsed.config(text="Elapsed: 0s")
            label_remaining.config(text="Estimated remaining: --")
            label_processed.config(text="Processed: 0")
            label_total.config(text="Total: --")
            update_folder_contents_listbox()
            logger.info(f"Selected input folder: {folder}, default output: {selected_folders['output']}")

    button_browse_input = Button(
        frame_input_folder, text="Browse Input", command=browse_input_folder, bg="gray70"
    )
    button_browse_input.pack(side="right", padx=5, pady=5)

    # Output folder prompt
    label_output = Label(
        scrollable_frame,
        text="Select output folder for grouped images:",
        bg="gray90",
        fg="black",
        font=("Arial", 14, "bold"),
    )
    label_output.pack(pady=10)

    # Frame for output folder label and browse button
    frame_output_folder = ttk.Frame(scrollable_frame)
    frame_output_folder.pack(fill="x", padx=10)
    label_selected_output = Label(
        frame_output_folder,
        text=selected_folders["output"] if selected_folders["output"] else "No output folder selected",
        fg="black" if selected_folders["output"] else "gray50",
        bg="gray90",
    )
    label_selected_output.pack(side="left", fill="x", expand=True)

    def browse_output_folder():
        """Handle output folder selection and update the UI."""
        initialdir = selected_folders["output"] if selected_folders["output"] else selected_folders["input"]
        folder = filedialog.askdirectory(initialdir=initialdir)
        if folder:
            # Ensure _groups suffix if not present
            if not folder.endswith('_groups'):
                folder = os.path.join(folder, '_groups')
            # Create output folder
            try:
                os.makedirs(folder, exist_ok=True)
                logger.info(f"Created/verified output folder: {folder}")
            except Exception as e:
                logger.error(f"Failed to create output folder {folder}: {str(e)}")
                messagebox.showerror("Error", f"Failed to create output folder: {str(e)}")
                return
            selected_folders["output"] = folder
            save_last_folders(selected_folders["input"], selected_folders["output"])
            label_selected_output.config(text=folder, fg="black")
            logger.info(f"Selected output folder: {folder}")

    button_browse_output = Button(
        frame_output_folder, text="Browse Output", command=browse_output_folder, bg="gray70"
    )
    button_browse_output.pack(side="right", padx=5, pady=5)

    # Checkbox for processing subfolders
    frame_folder_options = ttk.Frame(scrollable_frame)
    frame_folder_options.pack(pady=5, fill="x")
    style = ttk.Style()
    frame_folder_options.configure(style="FolderOptions.TFrame")
    style.configure("TCheckbutton", background="gray90", foreground="black")
    style.configure("FolderOptions.TFrame", background="gray90")

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
    frame_thresholds = ttk.Frame(scrollable_frame)
    frame_thresholds.pack(pady=5, fill="x")
    frame_thresholds.configure(style="Thresholds.TFrame")
    style.configure("Thresholds.TFrame", background="gray90")

    frame_thresholds.columnconfigure(0, weight=1)
    frame_thresholds.columnconfigure(1, weight=0)
    frame_thresholds.columnconfigure(2, weight=0)
    frame_thresholds.columnconfigure(3, weight=1)

    Label(frame_thresholds, text="Time diff (s):", font=("Arial", 12, "bold"), bg="gray90", fg="black").grid(
        row=0, column=1, padx=(0, 2), pady=2, sticky="e"
    )
    time_diff_var = StringVar(value=str(TIME_DIFF_THRESHOLD))
    entry_time_diff = ttk.Entry(frame_thresholds, textvariable=time_diff_var, width=5)
    entry_time_diff.grid(row=0, column=2, padx=(0, 10), pady=2, sticky="w")
    entry_time_diff.configure(background="gray80", foreground="black")

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
    label_image_count = Label(scrollable_frame, text="No folder selected", bg="gray90", fg="black")
    label_image_count.pack()

    # Listbox for folder contents
    frame_listbox = ttk.Frame(scrollable_frame)
    frame_listbox.pack(fill="both", expand=True, padx=10, pady=5)
    listbox_folder_contents = Listbox(
        frame_listbox, width=80, height=18, bg="gray80", fg="black"
    )
    listbox_folder_contents.pack(side="left", fill="both", expand=True)
    scrollbar_folder = ttk.Scrollbar(
        frame_listbox, orient="vertical", command=listbox_folder_contents.yview
    )
    scrollbar_folder.pack(side="right", fill="y")
    listbox_folder_contents.config(yscrollcommand=scrollbar_folder.set)

    # Results listbox
    listbox_results = Listbox(scrollable_frame, width=30, height=3, bg="gray80", fg="black")
    listbox_results.pack(pady=10)

    def update_folder_contents_listbox():
        """Update the listbox with the contents of the selected input folder(s)."""
        listbox_folder_contents.delete(0, END)
        folder = selected_folders["input"]
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
    frame_progress = ttk.Frame(scrollable_frame)
    frame_progress.pack(pady=5, fill="x")
    frame_progress.configure(style="Progress.TFrame")
    style.configure("Progress.TFrame", background="gray90")

    frame_labels = ttk.Frame(frame_progress)
    frame_labels.pack(fill="x")
    frame_labels.configure(style="Labels.TFrame")
    style.configure("Labels.TFrame", background="gray90", foreground="black")

    frame_left = ttk.Frame(frame_labels)
    frame_left.pack(side="left", anchor="w")
    frame_left.configure(style="Labels.TFrame")
    frame_right = ttk.Frame(frame_labels)
    frame_right.pack(side="right", anchor="e")
    frame_right.configure(style="Labels.TFrame")

    label_elapsed = Label(
        frame_left,
        text="Elapsed: 0s",
        bg="gray90",
        fg="black",
        font=("Arial", 12, "bold"),
    )
    label_elapsed.pack(anchor="w")
    label_remaining = Label(
        frame_left,
        text="Estimated remaining: --",
        bg="gray90",
        fg="black",
        font=("Arial", 12, "bold"),
    )
    label_remaining.pack(anchor="w")

    label_processed = Label(
        frame_right,
        text="Processed: 0",
        bg="gray90",
        fg="black",
        font=("Arial", 12, "bold"),
    )
    label_processed.pack(anchor="e")
    label_total = Label(
        frame_right,
        text="Total: --",
        bg="gray90",
        fg="black",
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
        """Perform image grouping based on contiguous timestamps and move to output folder."""
        progress["value"] = 0
        label_elapsed.config(text="Elapsed: 0s")
        label_remaining.config(text="Estimated remaining: --")
        label_processed.config(text="Processed: 0")
        label_total.config(text="Total: --")
        listbox_results.delete(0, END)

        input_folder = selected_folders["input"]
        output_folder = selected_folders["output"]
        if not input_folder:
            messagebox.showerror(
                "No input folder selected", "Please select an input folder before starting."
            )
            logger.error("Start attempted with no input folder selected")
            return
        if not output_folder or not os.path.isdir(output_folder):
            messagebox.showerror(
                "Invalid output folder", "Please select a valid output folder."
            )
            logger.error(f"Invalid output folder: {output_folder}")
            return
        update_thresholds()
        logger.info(f"Starting grouping: input={input_folder}, output={output_folder}, threshold={TIME_DIFF_THRESHOLD}s")

        def task():
            # Initialize profiler
            profiler = cProfile.Profile()
            profiler.enable()

            start_time = time.time()
            folders_dict = get_image_files_by_folder(
                input_folder, recursive=(process_subfolders_var.get() == "1")
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

            # Move groups to output folder
            for idx, group in enumerate(groups, 1):
                if not group:
                    continue
                move_start = time.time()
                place = get_place_from_exif_or_xmp(group[0])
                first_time = get_image_timestamp(group[0])
                if first_time:
                    date_time_str = first_time.strftime("%Y%m%d-%H%M")
                    count = len(group)
                    folder_name = f"{place}_{date_time_str}_{idx:02d}_{count}"
                    group_dir = os.path.join(output_folder, folder_name)
                    try:
                        os.makedirs(group_dir, exist_ok=True)
                        logger.info(f"Created group directory: {group_dir} with {count} images")
                    except Exception as e:
                        logger.error(f"Failed to create group directory {group_dir}: {str(e)}")
                        continue
                    for file in group:
                        try:
                            dest_path = os.path.join(group_dir, os.path.basename(file))
                            shutil.move(file, dest_path)
                            logger.debug(f"Moved {file} to {dest_path}")
                        except Exception as e:
                            logger.error(f"Failed to move {file}: {e}")
                elapsed = time.time() - move_start
                logger.debug(f"Moved group {idx} ({count} images) in {elapsed:.2f}s")

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

            # Save profiling data
            profiler.disable()
            profile_file = os.path.join(get_app_dir(), "imgsetsortr.prof")
            profiler.dump_stats(profile_file)
            ps = pstats.Stats(profile_file)
            ps.sort_stats(pstats.SortKey.CUMULATIVE)
            ps.print_stats(10)
            logger.info(f"Profiling data saved to {profile_file}")

        threading.Thread(target=task, daemon=True).start()

    # Button row: Start | Pause | Close
    frame_buttons = ttk.Frame(scrollable_frame)
    frame_buttons.pack(fill="x", pady=10)
    frame_buttons.configure(style="Buttons.TFrame")
    style.configure("Buttons.TFrame", background="gray90")

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
        bg="green",
        activebackground="aqua",
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
        activebackground="orange",
        font=("Arial", 12, "bold"),
    )
    button_close.grid(row=0, column=5, padx=10)

    root.mainloop()

if __name__ == "__main__":
    main()