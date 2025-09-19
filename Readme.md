# Image Metadata Extractor (`sid.py`)

**Version:** 1.0  
**Author:** Sidharth 
**License:** MIT

---

## Overview

`sid.py` is a Python tool to extract **human-friendly metadata highlights** from image files (JPEG, PNG, etc.). It extracts and displays:

- Device/Camera make & model  
- Author/Artist (if available)  
- Software/editor used  
- Original date/time photo was taken  
- GPS coordinates (latitude/longitude in decimal)  
- Image dimensions and file size  

Optionally, it can save **full metadata** to a JSON sidecar file and/or generate a CSV summary of multiple images.

---

## Requirements

Python 3.8+ and the following packages:

```bash
pip install -r requirements.txt
# Basic Extraction (prints highlights)
python sid.py extract IMAGE1.jpg IMAGE2.png

# Extraction with JSON sidecar (full metadata saved)
python sid.py extract --json IMAGE1.jpg IMAGE2.png

# Extraction with CSV summary (batch processing)
python sid.py extract --json --csv summary.csv *.jpg

```

##OUTPUT
```bash
============================================================
File: photo.jpg
Format: JPEG
Dimensions: 4032x3024
Size: 2.3MB
Device: Apple iPhone 13 Pro
Author: John Doe
Software: Adobe Lightroom
Taken: 2023:09:17 15:30:22
GPS (decimal): 51.504200, -0.123100
Notes:
  - No GPS data found (or stripped by app).
============================================================
