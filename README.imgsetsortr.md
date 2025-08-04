# imgsetsortr

## Overview
`imgsetsortr` [image-sets-sorter] is a Python utility that groups images in a folder based on contiguous timestamps from EXIF `DateTimeOriginal` metadata. 

Images are grouped if 5 or more have timestamps within a user-specified time threshold (default: 1.0 second). 

Groups are moved into subfolders named with the format `[place]_[YYYYMMDD-HHMM]_[group-increment]_[no.-of-imgs]` (e.g., `sydney_20250410-0600_01_20`). 

The place is derived from XMP metadata (`photoshop:City`, `Iptc4xmpCore:LocationCreated`, etc.), EXIF metadata (`XPTitle`, `XPSubject`, etc.), GPS reverse geocoding, or the parent directory as a fallback. 

The application supports both a Tkinter-based GUI and a command-line interface (CLI) for flexible usage. 

Comprehensive logging and profiling data are saved to the application directory.

## Features
- **Input Folder Selection**: Choose a folder containing images (.jpg, .jpeg, .png) via GUI or CLI.
- **Output Folder Selection**: Select an output folder (defaults to `input_folder/_groups`) via GUI or CLI.
- **Subfolder Processing**: Option to include subfolders (default: off) via GUI checkbox or CLI `-r` flag.
- **Time Threshold**: User-settable time difference (seconds, default: 1.0) for grouping images via GUI entry or CLI `-i` option.
- **Geocoding**: Extracts location from XMP, EXIF, GPS reverse geocoding, or parent directory (requires internet for GPS fallback - UNTESTED).
- **GUI**: Tkinter interface with a scrollable window, folder contents listbox, progress bar, Start/Pause/Close buttons, and a Help button with a popup.
- **CLI**: Command-line interface with options for source folder (`-s`), recursive processing (`-r`), time increment (`-i`), output folder (`-o`), and help (`-?` or `--help`).
- **Logging**: Detailed logs saved to `imgsetsortr.log` in the application directory.
- **Profiling**: Performance profiling data saved to `imgsetsortr.prof`.
- **Group Naming**: Subfolders named as `[place]_[YYYYMMDD-HHMM]_[group-increment]_[no.-of-imgs]`.
- **Minimum Group Size**: Groups require 5 or more images.
- **Progress Tracking**: GUI displays elapsed time, estimated remaining time, and processed/total image counts; CLI prints progress to console.
- **Help System**: CLI supports detailed help via `-?` or `--help`; GUI includes a Help button with a scrollable popup and an option to view instructions as an HTML webpage.

## Dependencies
- **Python**: Version 3.6 or higher.
- **exifread**: For reading EXIF metadata from images.
  ```bash
  pip install exifread
  ```
- **geopy**: For reverse geocoding GPS coordinates to location names (used as a fallback).
  ```bash
  pip install geopy
  ```
- **pillow**: For image processing (required for PIL imports).
  ```bash
  pip install pillow
  ```
- **pyexiv2**: For reading XMP metadata.
  ```bash
  pip install pyexiv2
  ```
- **tkinter**: Included with standard Python installations for the GUI (not required for CLI usage).
- **webbrowser**: Included with standard Python for opening the HTML help file (GUI mode only).

## Installation
1. Ensure Python 3.6+ is installed.
2. Install dependencies:
   ```bash
   pip install exifread geopy pillow pyexiv2
   ```
3. Download or clone the `imgsetsortr.py` script to a local directory.
4. Ensure the script has access to a writable directory for logs (`imgsetsortr.log`), profiling data (`imgsetsortr.prof`), settings (`settings.txt`), and help file (`imgsetsortr_help.html`).

## Usage

### GUI Mode
1. Run the script without arguments to launch the GUI:
   ```bash
   python imgsetsortr.py
   ```
2. **Access Help**:
   - Click the "Help" button (top-left) to open a popup with detailed usage instructions.
   - In the popup, scroll using the left-side scrollbar to view all instructions.
   - Click "Open as HTML" to view the instructions in your default web browser (saved as `imgsetsortr_help.html` in the application directory).
3. **Select Input Folder**:
   - Click "Browse Input" to choose a folder containing images (e.g., `E:/images/20250410-0600`).
4. **Select Output Folder**:
   - The output folder defaults to `input_folder/_groups`.
   - Click "Browse Output" to select a different folder if desired.
5. **Configure Options**:
   - Check "Process subfolders" to include subdirectories (default: off).
   - Adjust "Time diff (s)" to set the grouping threshold (default: 1.0 seconds).
6. **Start Grouping**:
   - Click "Start" to begin grouping. Images are moved to subfolders in the output folder.
   - Example output: `sydney_20250410-0600_01_20` for a group of 20 images.
7. **Monitor Progress**:
   - View the folder contents in the listbox.
   - Track progress via the progress bar and labels (elapsed time, remaining time, processed images).
8. **Pause/Resume**:
   - Click "Pause" to pause processing; click "Continue" to resume.
9. **Exit**:
   - Click "EXIT" to close. A confirmation prompt appears if processing is ongoing.
10. **Logs**:
    - Check `imgsetsortr.log` in the application directory for detailed processing information.

### CLI Mode
Run the script with command-line arguments to process images non-interactively:
```bash
python imgsetsortr.py -s <source_folder> [-r] [-i <increment>] [-o <output_folder>] [-? | --help]
```
- **`-s/--source <source_folder>`**: Specify the folder containing images to process (required).
- **`-r/--recurse`**: Enable recursive processing of subdirectories (default: False).
- **`-i/--increment <seconds>`**: Set the maximum seconds between images in a group (default: 1.0).
- **`-o/--output <output_folder>`**: Specify the output folder (default: `<source_folder>/_groups`).
- **`-?/--help`**: Display detailed usage instructions and exit.

**Example**:
```bash
python imgsetsortr.py -s /path/to/images -r -i 2.0 -o /path/to/output
```
This processes all images in `/path/to/images` and its subdirectories, grouping images within 2.0 seconds of each other, and places groups in `/path/to/output/_groups`.

**Help Command**:
```bash
python imgsetsortr.py --help
```
or
```bash
python imgsetsortr.py -?
```
Displays detailed usage instructions, including CLI and GUI modes, options, and examples.

**Output**:
- Progress updates are printed to the console (e.g., `Progress: 50.0%, Elapsed: 10s, Remaining: 10s, Processed: 100/200`).
- Final results are displayed (e.g., `Completed: 5 groups created, 100 images moved, 50 singles left`).

## Output Format
- Groups are created in the output folder with names like `sydney_20250410-0600_01_20`:
  - `place`: Location from XMP, EXIF, GPS, or parent directory (lowercase, hyphens).
  - `YYYYMMDD-HHMM`: Date and time from the first image's timestamp.
  - `group-increment`: Zero-padded group number (e.g., `01`, `02`).
  - `no.-of-imgs`: Number of images in the group (e.g., `20`).

## Notes
- Images without EXIF `DateTimeOriginal` use file modification time as a fallback.
- Geocoding requires an internet connection only for GPS reverse geocoding (if XMP/EXIF metadata is unavailable).
- The minimum group size is 5 images; smaller groups are left ungrouped ("singles").
- The GUI includes a vertical scrollbar to ensure all controls are accessible.
- Settings (last input/output folders) are saved in `settings.txt` in the application directory for GUI mode.
- CLI mode saves the provided input/output folders to `settings.txt` for consistency with GUI mode.
- Profiling data is saved to `imgsetsortr.prof` for performance analysis.
- A help file (`imgsetsortr_help.html`) is generated in the application directory for GUI mode when the script starts.

## Example
- **Input folder**: `E:/images/20250410-0600`
- **Images**:
  - `image1.jpg`: `2025-04-10 06:00:03`, XMP `photoshop:City: Sydney`
  - `image2.jpg`: `2025-04-10 06:00:03.500`
  - `image3.jpg`: `2025-04-10 06:00:04`
  - `image4.jpg`: `2025-04-10 06:00:04.500`
  - `image5.jpg`: `2025-04-10 06:00:05`
- **Command**: `python imgsetsortr.py -s E:/images/20250410-0600 -i 1.0`
- **Output**: `E:/images/20250410-0600/_groups/sydney_20250410-0600_01_5`
- **Log entry**: `Creating group directory: ...sydney_20250410-0600_01_5 with 5 images`

## Troubleshooting
- **No Groups Created**: Ensure images have valid EXIF timestamps and at least 5 images are within the time threshold.
- **Geocoding Fails**: Check internet connectivity or add XMP/EXIF location metadata to images.
- **CLI Errors**: Verify the source folder exists and the output folder is writable.
- **UI Issues**: Use the scrollbar to access buttons if the window is resized; check the Help popup for guidance.
- **Logs**: Review `imgsetsortr.log` for errors (e.g., missing timestamps, file move failures).
- **Profiling**: Check `imgsetsortr.prof` for performance bottlenecks using a profiler tool (e.g., `snakeviz`).