# imgsetsortr Prompt History
## Grok20250902tdwm

1. create a gui app that takes a chosen folder, allows to select sub-dirs as well, and processes for 5 or more images with contiguous timestamps each no more than a second apart [with a user-settable box to change that increment], and separates groups to dirs under a chosen root [default, starting dir of sorting] with a naming protocol of place [if city/locale present in metadata] + date + hour + file-count ie, 'brisbane_20250403_1600hrs_20';

- use the attached app as a format to:
   - supply an elapsed + estimated time, and processed + total file-count, above a progress bar
   - include a set of start, pause and close [with a warning if still active] buttons in a row

1. if location not in exif, use location from xmp metadata

-  first usage shows img not sorted by time; 180 imgs to one dir, when actually several sets, separated by only 2s [in 1 instance] but 3s, 5s or more, up to 30s;
    - datetimeoriginal, may be more accurate;
    - ensure docstrings are adequate and provide comprehensive logging, to file

[some images have the same hhmmss timestamp across up to at least 4 images]

1. add user-designated output folder, using current working dir as default

[
###  Recommendations

#### Fix Output Directory:
Confirm that the _groups folder is always created under the input directory. If not, update the configuration or code to ensure output_dir = input_dir + "/_groups".

#### Debug Grouping Logic:
Check the code for group directory creation and ensure each group gets a unique directory (e.g., incrementing numbers like sydney_20250410_0600hrs_01, sydney_20250410_0600hrs_02, etc.).
Verify that the 1.0-second threshold is applied correctly by logging timestamp differences.

#### Test and Validate:
Test with a small dataset to confirm that multiple group directories are created.
Use the timestamp analysis script to confirm the expected number of groups.

#### GUI Feedback:
Update the GUI to display the actual group directories created (e.g., list sydney_20250410_0600hrs_01, sydney_20250410_0600hrs_02, etc.) to help users verify the output.

#### Log Enhancements:
Add logging for each group creation, including the timestamp range and number of images per group. For example:
INFO - Created group sydney_20250410_0600hrs_01: 2025-04-10 06:25:03 to 2025-04-10 06:25:12 (20 images)
INFO - Created group sydney_20250410_0600hrs_02: 2025-04-10 06:26:04 to 2025-04-10 06:26:11 (15 images)

]

4. manifest complete code with Recommendations;  
   - also, provide a scroll bar at the side of the window for when 'start,pause,exit' buttons are not visible;  
   - sydney_20250410_0600hrs_20, is correct for first group in this batch, but 'group number should increment for each new group' is better, but add number of images in group to the end of that, also ie, [place]_[date]_[24hrs]_[group-increment]_[no.-of-imgs]
  
5. geocoding should read from exif, or xmp-location, and only *then* if required use reverse lookup by internet access  

6. appears functional;  
   provide readme.imgsetsortr.md, including dependencies, and separate file with a summation of the prompts from this chat [without answers] 'ai-hist_imgsetsortr.md'

20250803

7. in naming convention, when location/place is 2 or more words, hyphenate the place-name instead of underscore [to separate from the rest of the new dir-name parts], then join with underscore

8. remove the 'anaglyph' coral+blue theming - just grays with black text

9. implement caching, read performance improvement

10. for naming convention, use hrs+mins, ie '0627' [using time of first img in set], and hyphenate date+time

11. implement cli capability:
- s/source = folder to process
- r/recurse = process sub-dirs [default 'false' if absent]
- i/increment = max number of seconds between imgs [only needed if different from default '1']
- o/output = target folder [only needed if different from default '[source]/_groups']

12. add:
- cli Help Message .. Provide usage instructions via --help or -?
- 'help' button in top left to open popup with 'howto' instructs [and include link to open as local html webpage in default browse]