"""Create test PDF dataset with manifest and readme."""

import shutil
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / "data"
PDF_DIR = DATA_DIR / "PDFs"
SOURCE_PDF = DATA_DIR / "sample.pdf"
DATASET_NAME = "test_pdfs"


def create_pdfs():
    """Copy source PDF to 0000.pdf-0020.pdf (21 files)."""
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    for i in range(21):
        dest = PDF_DIR / f"{i:04d}.pdf"
        if not dest.exists():
            shutil.copy2(SOURCE_PDF, dest)
    return sorted(PDF_DIR.glob("*.pdf"))


def create_manifest(pdf_files: list[Path]):
    """Create manifest.csv with filename, doc_id, and rotating category."""
    categories = ["report", "invoice", "contract", "memo"]
    csv_lines = ["filename,doc_id,category"]
    for i, pdf in enumerate(pdf_files):
        csv_lines.append(f"{pdf.name},DOC{i:05d},{categories[i % 4]}")
    manifest_path = DATA_DIR / "manifest.csv"
    manifest_path.write_text("\n".join(csv_lines))
    print(f"Created {manifest_path}")


def create_readme():
    """Create readme.md with usage instructions."""
    readme_path = DATA_DIR / "readme.md"
    readme_path.write_text(
        f'20 PDFs created for testing. Use the dataset as:\n'
        f'\n'
        f'dataset_path = sc.resolve_path("syft://private/syft_datasets/{DATASET_NAME}")\n'
        f'dataset_dir = Path(dataset_path).parent\n'
        f'\n'
        f'pdf_files = sorted(dataset_dir.glob("*.pdf"))\n'
    )
    print(f"Created {readme_path}")


def main():
    pdf_files = create_pdfs()
    print(f"Created {len(pdf_files)} PDFs in {PDF_DIR}")
    create_manifest(pdf_files)
    create_readme()


if __name__ == "__main__":
    main()
