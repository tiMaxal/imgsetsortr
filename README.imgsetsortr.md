# imgsetsortr

## Overview
`imgsetsortr` is a Python utility that groups images in a folder based on contiguous timestamps from EXIF `DateTimeOriginal` metadata. Images are grouped if 5 or more have timestamps within a user-specified time threshold (default: 1.0 second). Groups are moved into subfolders named with the format `[place]_[date]_[24hrs]_[group-increment]_[no.-of-imgs]` (e.g., `sydney_20250410_0600hrs_01_20`). The place is derived from EXIF metadata (`XPTitle`, `XPSubject`, etc.), XMP metadata (`<xmp:City>`), or GPS reverse geocoding as a fallback. The application features a Tkinter-based GUI for folder selection, time threshold adjustment, and progress monitoring, with comprehensive logging.

## Features
- **Input Folder Selection**: Choose a folder containing images (.jpg, .jpeg, .png).
- **Output Folder Selection**: Select an output folder (defaults to `input_folder/_groups`).
- **Subfolder Processing**: Option to include subfolders (default: off).
- **Time Threshold**: User-settable time difference (seconds) for grouping images.
- **Geocoding**: Extracts location from EXIF, XMP, or GPS reverse geocoding (requires internet for GPS fallback - UNTESTED).
- **GUI**: Tkinter interface with a scrollable window, folder contents listbox, progress bar, and Start/Pause/Close buttons.
- **Logging**: Detailed logs saved to `imgsetsortr.log` in the application directory.
- **Group Naming**: Subfolders named as `[place]_[YYYYMMDD]_[HH00hrs]_[group-increment]_[no.-of-imgs]`.
- **Minimum Group Size**: Groups require 5 or more images.
- **Progress Tracking**: Displays elapsed time, estimated remaining time, and processed/total image counts.

## Dependencies
- **Python**: Version 3.6 or higher.
- **exifread**: For reading EXIF metadata from images.
  ```bash
  pip install exifread
  ```
- **geopy**: For reverse geocoding GPS coordinates to city names (used as a fallback).
  ```bash
  pip install geopy
  ```
- **pillow**: For potential image processing (required for PIL imports).
  ```bash
  pip install pillow
  ```
- **tkinter**: Included with standard Python installations for the GUI.

## Installation
1. Ensure Python 3.6+ is installed.
2. Install dependencies:
   ```bash
   pip install exifread geopy pillow
   ```
3. Download or clone the `imgsetsortr.py` script to a local directory.
4. Ensure the script has access to a writable directory for logs and settings (`settings.txt`).

## Usage
1. Run the script:
   ```bash
   python imgsetsortr.py
   ```
2. **Select Input Folder**:
   - Click "Browse Input" to choose a folder containing images (e.g., `E:/images/20250410_0600hrs`).
3. **Select Output Folder**:
   - The output folder defaults to `input_folder/_groups`.
   - Click "Browse Output" to select a different folder if desired.
4. **Configure Options**:
   - Check "Process subfolders" to include subdirectories (default: off).
   - Adjust "Time diff (s)" to set the grouping threshold (default: 1.0 seconds).
5. **Start Grouping**:
   - Click "Start" to begin grouping. Images are moved to subfolders in the output folder.
   - Example output: `sydney_20250410_0600hrs_01_20` for a group of 20 images.
6. **Monitor Progress**:
   - View the folder contents in the listbox.
   - Track progress via the progress bar and labels (elapsed time, remaining time, processed images).
7. **Pause/Resume**:
   - Click "Pause" to pause processing; click "Continue" to resume.
8. **Exit**:
   - Click "EXIT" to close. A confirmation prompt appears if processing is ongoing.
9. **Logs**:
   - Check `imgsetsortr.log` in the application directory for detailed processing information.

## Output Format
- Groups are created in the output folder with names like `sydney_20250410_0600hrs_01_20`:
  - `place`: City from EXIF, XMP, or GPS (lowercase, underscores).
  - `YYYYMMDD`: Date from the first image's timestamp.
  - `HH00hrs`: Hour from the first image's timestamp.
  - `group-increment`: Zero-padded group number (e.g., `01`, `02`).
  - `no.-of-imgs`: Number of images in the group (e.g., `20`).

## Notes
- Images without EXIF `DateTimeOriginal` use file modification time as a fallback.
- Geocoding requires an internet connection only for GPS reverse geocoding (if EXIF/XMP metadata is unavailable).
- The minimum group size is 5 images; smaller groups are left ungrouped ("singles").
- The GUI includes a vertical scrollbar to ensure all controls (e.g., buttons) are accessible.
- Settings (last input/output folders) are saved in `settings.txt` in the application directory.

## Example
- Input folder: `E:/images/20250410_0600hrs`
- Images:
  - `image1.jpg`: `2025-04-10 06:25:03`, EXIF `XPTitle: Sydney`
  - `image2.jpg`: `2025-04-10 06:25:03.500`
  - `image3.jpg`: `2025-04-10 06:25:04`
  - `image4.jpg`: `2025-04-10 06:25:04.500`
  - `image5.jpg`: `2025-04-10 06:25:05`
- Output: `E:/images/20250410_0600hrs/_groups/sydney_20250410_0600hrs_01_5`
- Log entry: `Creating group directory: ...sydney_20250410_0600hrs_01_5 with 5 images`

## Troubleshooting
- **No Groups Created**: Ensure images have valid EXIF timestamps and at least 5 images are within the time threshold.
- **Geocoding Fails**: Check internet connectivity or add EXIF/XMP location metadata to images.
- **UI Issues**: Use the scrollbar to access buttons if the window is resized.
- **Logs**: Review `imgsetsortr.log` for errors (e.g., missing timestamps, file move failures).