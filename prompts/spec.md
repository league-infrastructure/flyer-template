# Template Analyzer Specification

## Overview

This specification describes a process for analyzing image templates that contain colored placeholder regions, extracting their positions and surrounding colors, and generating derivative assets for template-based content generation.

## Purpose

Given an image template with solid-colored placeholder rectangles (default: green `#6fe600`), this process:

1. **Identifies** all placeholder regions by color
2. **Extracts** the bounding box coordinates for each region
3. **Detects** the background/border color surrounding each placeholder
4. **Generates** three output files:
   - A **reference image** with numbered outline boxes (for human review)
   - A **template image** with placeholders replaced by background colors (for content insertion)
   - A **YAML data file** with region coordinates and metadata

---

## Input

### Required
- **Source Image**: PNG or JPEG image containing one or more solid-colored placeholder regions
- **Placeholder Color**: Hex color code of the placeholder regions (default: `#6fe600`)

### Optional
- **Color Tolerance**: How much variation from the exact color to accept (default: `20` on 0-255 scale)
- **Edge Dilation**: Pixels to expand mask to catch anti-aliased edges (default: `5`)
- **Background Sample Offset**: Distance in pixels from placeholder edge to sample background color (default: `5`)

---

## Output

### 1. Reference Image (`{name}_reference.png`)

Visual reference showing detected regions with:
- Placeholder regions replaced with detected background color
- 2px outline in the original placeholder color around each region
- Centered region number (1-indexed) with:
  - Black text
  - White outline/shadow for readability
  - Font size appropriate to region (recommended: 72px for large regions)

### 2. Template Image (`{name}_template.png`)

Working template with:
- All placeholder regions replaced with their detected background colors
- Anti-aliased edges cleaned up (via mask dilation)
- Ready for content overlay/insertion

### 3. Region Data (`{name}_regions.yaml`)

YAML file containing:

```yaml
source: <original_filename>
template: <template_filename>
reference: <reference_filename>
regions:
  - id: <integer>           # 1-indexed region identifier
    x: <integer>            # Left edge x-coordinate (pixels)
    y: <integer>            # Top edge y-coordinate (pixels)
    width: <integer>        # Region width (pixels)
    height: <integer>       # Region height (pixels)
    background_color: <hex> # Detected background color (e.g., '#f89048')
```

---

## Algorithm

### Step 1: Load and Prepare Image

```
1. Load source image in BGR color format (OpenCV convention)
2. Record image dimensions (width, height)
```

### Step 2: Create Color Mask

```
1. Convert placeholder hex color to BGR tuple
2. Calculate lower bound: (B - tolerance, G - tolerance, R - tolerance), clamped to 0
3. Calculate upper bound: (B + tolerance, G + tolerance, R + tolerance), clamped to 255
4. Create binary mask using cv2.inRange(image, lower, upper)
5. Result: 255 where color matches, 0 elsewhere
```

### Step 3: Find Regions

```
1. Find contours in mask using cv2.findContours(mask, RETR_EXTERNAL, CHAIN_APPROX_SIMPLE)
2. For each contour:
   a. Calculate bounding box: cv2.boundingRect(contour)
   b. Store: x, y, width, height, contour points
3. Sort regions by position:
   a. Primary sort: y-coordinate (top to bottom)
   b. Secondary sort: x-coordinate (left to right)
4. Assign 1-indexed IDs based on sorted order
```

### Step 4: Detect Background Colors

For each region, sample the border/background color from pixels just outside the placeholder:

```
1. Define sample offset (default: 5 pixels from edge)
2. Sample from LEFT and RIGHT sides only (avoids adjacent regions):
   a. Sample vertical strip at (x - offset) for left side
   b. Sample vertical strip at (x + width + offset) for right side
   c. Only sample middle 60% of height to avoid corner artifacts
3. Quantize sampled colors:
   a. Round each channel to nearest multiple of 8
   b. This reduces noise from gradients/compression
4. Find mode (most frequent) color among samples
5. Store as background_color for this region
```

**Why sample sides only?**
- Top/bottom edges may hit adjacent placeholder regions
- Side edges typically extend into the consistent border/frame area

### Step 5: Generate Template Image

```
For each region:
1. Create region-specific mask from contour
2. Dilate mask by 5px kernel to catch anti-aliased edges:
   kernel = np.ones((5, 5), np.uint8)
   dilated_mask = cv2.dilate(mask, kernel, iterations=1)
3. Replace all pixels where dilated_mask > 0 with background_color
```

### Step 6: Generate Reference Image

```
For each region:
1. Start with template image (background already filled)
2. Draw 2px rectangle outline in placeholder color:
   cv2.rectangle(img, (x, y), (x+w-1, y+h-1), placeholder_color, 2)
3. Add centered number label:
   a. Calculate text size
   b. Center position: text_x = x + (w - text_w) / 2
   c. Draw white outline (multiple offset positions)
   d. Draw black text on top
```

### Step 7: Generate YAML Data

```
1. Collect metadata:
   - source filename
   - template filename
   - reference filename
2. For each region, record:
   - id (1-indexed)
   - x, y, width, height (integers)
   - background_color (hex string with '#' prefix)
3. Write as YAML with regions in sorted order
```

---

## Implementation Notes

### Color Space
- OpenCV uses BGR order (not RGB)
- When converting hex to BGR: `#RRGGBB` → `(BB, GG, RR)`
- When converting BGR to hex: `(B, G, R)` → `#RRGGBB`

### Anti-Aliasing Handling
- Placeholder edges often have anti-aliased pixels that don't exactly match the target color
- Dilating the mask by 2-5 pixels captures these edge pixels
- This prevents colored "halos" around replaced regions

### Quantization for Mode Calculation
- Raw pixel values vary due to compression artifacts and gradients
- Quantizing to nearest 8 (or 16) groups similar colors together
- Mode of quantized values gives the dominant "true" color

### Text Rendering
- PIL/Pillow provides better text rendering than OpenCV
- Use TrueType fonts when available (e.g., DejaVuSans-Bold)
- White outline created by drawing text at 8 offset positions before black text

---

## Example Usage

### Input
- Image: `Sept_2025_Events.png` (1545×2000 pixels)
- Placeholder color: `#6fe600` (bright green)

### Processing
```
Found 7 green regions:
  Region 1: 361×120 at (980, 279)   → background: #f89048 (orange)
  Region 2: 1114×196 at (226, 659)  → background: #e8e870 (yellow)
  Region 3: 1112×195 at (231, 885)  → background: #60c0c8 (cyan)
  Region 4: 1113×195 at (230, 1112) → background: #f89048 (orange)
  Region 5: 1112×195 at (227, 1356) → background: #60c0c8 (cyan)
  Region 6: 1114×196 at (230, 1591) → background: #e8e870 (yellow)
  Region 7: 352×117 at (205, 1855)  → background: #60c0c8 (cyan)
```

### Output Files
- `events_reference.png` - Numbered outline boxes for review
- `events_template.png` - Ready for content insertion
- `events_regions.yaml` - Machine-readable region data

---

## Dependencies

### Required Libraries
- **OpenCV** (`cv2`): Image loading, color masking, contour detection, drawing
- **NumPy** (`numpy`): Array operations, mask manipulation
- **Pillow** (`PIL`): Text rendering with TrueType fonts
- **PyYAML** (`yaml`): YAML file generation

### Installation
```bash
pip install opencv-python numpy pillow pyyaml
```

---

## Error Handling

### No Regions Found
- If no contours match the placeholder color, warn and exit gracefully
- Check: tolerance may be too low, or color may be incorrect

### Invalid Background Detection
- If background sampling returns unexpected colors, increase sample offset
- If hitting adjacent regions, switch to side-only sampling

### Image Loading Failure
- Verify file exists and is a valid image format
- Check file permissions

---

## Extension Points

### Multiple Placeholder Colors
- Run the detection process for each color independently
- Merge results, ensuring unique region IDs across colors

### Non-Rectangular Regions
- Current algorithm uses bounding boxes
- For complex shapes, store full contour in addition to bbox

### Automatic Color Detection
- Instead of specifying placeholder color, detect dominant solid-colored rectangles
- Use edge detection + color histogram analysis

