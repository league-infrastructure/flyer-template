# About Flyte: Flyer Template System

## Overview

Flyte is a Python-based system for creating and rendering customizable flyer templates. It enables automated generation of flyers by separating template design from content, using computer vision to detect content regions, and rendering HTML to high-quality PNG or PDF output.

## System Architecture

Flyte uses a three-stage workflow:

1. **Import** - Analyze a template image to identify content regions
2. **Compile** - Merge content with the template to generate HTML
3. **Render** - Convert HTML to PNG or PDF for distribution

## The Import Process

The `flyte import` command analyzes a source template image containing placeholder regions (colored rectangles) and generates a complete template project directory.

### Command Usage

```bash
flyte import source_template.png [-o output_dir]
```

If `-o` is not specified, the template directory is created in the same location as the source file.

### Template Requirements

Template images must contain **placeholder regions** - rectangular areas filled with a specific color (default: `#6fe600`, bright green) that indicate where content should be inserted. The import process detects these regions using computer vision techniques.

## Import Output Structure

The import process creates a directory named after the source file (without extension) containing four files:

```
TemplateName/
├── src.png           # Original source image (converted to PNG)
├── template.png      # Processed template with placeholder regions removed
├── reference.png     # Annotated reference showing region IDs and positions
└── regions.yaml      # Metadata file describing all content regions
```

### File Descriptions

#### `src.png`
The original source template image, converted to PNG format regardless of input format. This preserves the original design including all placeholder regions.

**Purpose**: Archive of the original template design.

#### `template.png`
The processed template with placeholder regions removed (replaced with background). This image serves as the background for the final rendered flyer.

**Purpose**: Background layer for rendering content.

#### `reference.png`
An annotated version of the template showing:
- Region boundaries (outlined)
- Region IDs (large numbers)
- Region positions and dimensions

**Purpose**: Visual guide for template designers to identify which region corresponds to which ID in the regions.yaml file.

#### `regions.yaml`
The metadata file containing structured information about all detected content regions. This is the **most critical file** for the rendering process.

## The regions.yaml File Structure

### Top-Level Fields

```yaml
content_color: '#6fe600'
width: 816
height: 1056
css: []
regions:
  - [region definitions]
```

**`content_color`**: The hex color code used for placeholder detection. Preserved for reference and potential re-import.

**`width`**: The width of the template image in pixels. Used for layout calculations and validation.

**`height`**: The height of the template image in pixels. Used for layout calculations and validation.

**`css`**: Array of CSS file paths to apply during rendering. Can be populated manually or left empty to use inline styles.

**`regions`**: Array of region objects, each defining a content area.

### Region Object Structure

Each region in the `regions` array contains:

```yaml
- id: 1
  name: "Pack Meeting"
  role: "content"
  x: 71
  y: 439
  width: 390
  height: 408
  background_color: '#e8f8f8'
```

#### Field Descriptions

**`id`** (integer, required)
- Unique numeric identifier assigned sequentially during import
- Used to match regions when preserving names during re-import
- Corresponds to the large numbers shown in `reference.png`

**`name`** (string, optional)
- Text extracted from the placeholder region using OCR (Optical Character Recognition)
- Automatically populated during import by reading any text visible in the placeholder area
- Can be manually edited after import for clarity or corrections
- Used to map content in YAML/JSON content files

**`role`** (string, optional)
- Semantic role of the region auto-detected from position, size, and aspect ratio
- Common values: \"content\", \"content2\", \"title\", \"date\", \"time\", \"place\", \"url\", \"qr_code\"
- Helps understand the intended purpose of each region
- **Preserved during re-import** if region positions remain unchanged

**`x`** (integer, required)
- Horizontal position of region's top-left corner in pixels
- Measured from the left edge of the template

**`y`** (integer, required)
- Vertical position of region's top-left corner in pixels
- Measured from the top edge of the template

**`width`** (integer, required)
- Width of the region in pixels

**`height`** (integer, required)
- Height of the region in pixels

**`background_color`** (string, required)
- Hex color code of the background beneath the placeholder
- Sampled from pixels adjacent to the placeholder region
- Used to ensure content backgrounds match the template design

### Region Area Size Classification

During rendering, regions are automatically classified by area for font scaling:

- **xs** (extra small): < 50,000 px² → 32px base font
- **sm** (small): 50,000 - 150,000 px² → 52px base font
- **md** (medium): 150,000 - 300,000 px² → 72px base font
- **lg** (large): > 300,000 px² → 90px base font

## Re-Import and Role Preservation

When running `flyte import` on a source file that already has an existing `regions.yaml`:

**Without `--replace` flag** (default):
1. Loads the existing `regions.yaml`
2. Validates that region count and positions (x, y, width, height) match
3. If positions match exactly, preserves the `role` field from the existing file
4. Re-extracts text using OCR to populate the `name` field (text may change if placeholder text was updated)
5. Outputs: "Preserved region roles from existing regions.yaml"

**With `--replace` flag**:
- Overwrites `regions.yaml` completely
- Extracts new text via OCR for names
- Generates new auto-detected roles
- Ignores any existing region metadata

This allows users to:
- Adjust import parameters (color tolerance, dilation, etc.) without losing custom region roles
- Update placeholder text and have it automatically re-extracted
- Re-generate reference images while preserving metadata
- Safely update templates when only visual elements change

## Content Mapping

Content files (YAML or JSON) map region names or IDs to HTML content:

```yaml
regions: path/to/template/regions.yaml
css: path/to/style.css
content:
  content: "<h2>Main Event</h2><p>Join us for an exciting evening</p>"
  date: "December 13, 2025"
  time: "7:00 PM - 9:00 PM"
  qr_code: "https://example.com/register"
```

### Special Region Names

**`qr_code`**: Automatically generates a QR code image from the content URL.

**`url`**: Can be used as an alternative name for QR code generation.

## Rendering Process

### Compile Stage
```bash
flyte compile content.yaml template_dir/ -o output.html [-s style.css]
```

Creates an HTML file with:
- Template image as background (`background-image`)
- Content regions as absolutely positioned `<div>` elements
- Inline CSS for styling and layout
- Optional custom stylesheet

### Render Stage
```bash
flyte render page.html -o output.png
flyte render page.html -o output.pdf
```

Converts HTML to final output:
- **PNG**: For digital display, social media, email
- **PDF**: For print, preserves active links

Uses WeasyPrint (HTML → PDF) and pypdfium2 (PDF → PNG) for high-quality rendering.

## Best Practices

### Template Design
1. Use consistent placeholder colors
2. Leave adequate spacing around placeholder regions
3. Ensure region backgrounds are solid colors (not gradients)
4. Design regions with expected content size in mind

### Region Naming
1. Include descriptive text in template placeholders for automatic OCR extraction
2. Manually edit `name` field in `regions.yaml` to correct OCR errors or improve clarity
3. Use consistent naming conventions across templates
4. Common names: `title`, `subtitle`, `content`, `date`, `time`, `location`, `url`, `qr_code`
5. The `role` field provides semantic context; `name` should be human-readable text

### Region Management
1. Avoid re-importing with `--replace` unless necessary
2. Re-import without `--replace` when adjusting detection parameters or updating placeholder text
3. Check region positions in `reference.png` to ensure correct detection
4. Validate region count and positions after import
5. Review OCR-extracted names and edit for accuracy if needed

### Content Files
1. Use region names rather than IDs when possible (more maintainable)
2. Include `css` reference for consistent styling across content files
3. Keep HTML content simple (headings, paragraphs, links)
4. Test QR codes after generation to ensure correct encoding

## Technical Details

### Detection Algorithm
1. Color-based masking using HSV color space
2. Contour detection to identify rectangular regions
3. Bounding box calculation for each region
4. Background color sampling from adjacent pixels
5. Region naming using pattern matching heuristics

### Coordinate System
- Origin (0, 0) is the top-left corner of the template
- X increases rightward
- Y increases downward
- All measurements in pixels

### File Formats
- Input: PNG, JPEG, or other common image formats
- Output images: PNG (for import), PNG or PDF (for render)
- Metadata: YAML (human-readable, version-controllable)
- Content: YAML or JSON

## Example Workflow

```bash
# 1. Import a template
flyte import event_poster.png
# Creates: event_poster/src.png, template.png, reference.png, regions.yaml

# 2. Edit regions.yaml to assign meaningful names
# Manually edit: event_poster/regions.yaml

# 3. Create content file
cat > event_content.yaml << EOF
regions: event_poster/regions.yaml
css: style.css
content:
  title: "<h1>Community Event</h1>"
  date: "December 20, 2025"
  time: "6:00 PM"
  location: "Community Center"
EOF

# 4. Compile to HTML
flyte compile event_content.yaml event_poster/ -o event.html

# 5. Render to PNG and PDF
flyte render event.html -o event.png
flyte render event.html -o event.pdf
```

## Advanced Features

### Custom Import Parameters
- `--color`: Change placeholder color (useful for templates with multiple color schemes)
- `--tolerance`: Adjust color matching sensitivity (0-255)
- `--dilate`: Control region edge smoothing
- `--offset`: Adjust background sampling distance
- `--label-font`: Specify font for reference image labels

### Web Service
Remote rendering via HTTP API:
```bash
curl "http://localhost:8088/png?url=https://example.com" > page.png
curl "http://localhost:8088/pdf?url=https://example.com" > page.pdf
```

### Docker Deployment
Containerized service with WeasyPrint and all dependencies pre-installed.

## Troubleshooting

### Regions Not Detected
- Verify placeholder color matches `--color` parameter
- Increase `--tolerance` value
- Ensure placeholders are solid rectangular fills
- Check that placeholders are not transparent or semi-transparent

### Region Names Not Preserved
- Verify region positions haven't changed
- Check that region count matches
- Ensure existing `regions.yaml` is valid YAML
- Use `--replace` flag intentionally when structure changes

### Rendering Issues
- Verify all region names in content file match `regions.yaml`
- Check CSS syntax if using custom stylesheets
- Ensure referenced URLs are accessible for QR code generation
- Validate HTML content is properly escaped/formatted
