# GitHub Actions Workflow

This repository uses GitHub Actions to automatically import templates and deploy them to GitHub Pages.

## Workflow: Import Templates and Deploy

**File**: `.github/workflows/import-and-deploy.yml`

**Trigger**: On every push to the `master` branch

### Jobs

#### 1. `import-templates`
- Runs on Ubuntu (latest)
- Installs Python 3.13 and system dependencies (Tesseract OCR, OpenGL, glib)
- Installs uv package manager
- Installs Python dependencies
- Runs `flyte import ./source/ -o ./templates`
- Uploads templates as an artifact

#### 2. `deploy`
- Depends on `import-templates` job
- Downloads the templates artifact
- Creates an `index.html` file for browsing templates
- Deploys to GitHub Pages

### System Dependencies

The workflow installs these system packages for OCR and image processing:
- `tesseract-ocr` - OCR engine for text extraction
- `tesseract-ocr-eng` - English language data for Tesseract
- `libgl1` - OpenGL library (required by OpenCV)
- `libglib2.0-0` - GLib library (required by OpenCV)

### GitHub Pages Setup

To enable GitHub Pages deployment:

1. Go to repository Settings → Pages
2. Under "Source", select "GitHub Actions"
3. The workflow will automatically deploy on the next push to master

### Viewing the Site

After the first successful deployment, the site will be available at:
```
https://league-infrastructure.github.io/flyer-template/
```

### Workflow Status

Check the status of the workflow:
- Go to the "Actions" tab in the repository
- View recent workflow runs
- Click on a run to see detailed logs

### Manual Trigger

To manually trigger the workflow without pushing:
1. Go to Actions tab
2. Select "Import Templates and Deploy" workflow
3. Click "Run workflow"
4. Select the branch and click "Run workflow"

## Updating Templates

To add or update templates:

1. Add/modify PNG files in the `source/` directory
2. Commit and push to master:
   ```bash
   git add source/
   git commit -m "Add new template"
   git push origin master
   ```
3. GitHub Actions will automatically:
   - Run `flyte import` on all source files
   - Generate template directories
   - Create index.json
   - Deploy to GitHub Pages

## Troubleshooting

### Workflow fails on OCR step
- Check that source images contain valid placeholder regions
- Verify the placeholder color matches (default: `#6fe600`)

### Pages deployment fails
- Ensure GitHub Pages is enabled in repository settings
- Check that the repository has Pages write permissions
- Verify the workflow has `id-token: write` and `pages: write` permissions

### Templates not updating
- Check the Actions tab for workflow errors
- Ensure the workflow completed successfully
- GitHub Pages may take a few minutes to update after deployment
