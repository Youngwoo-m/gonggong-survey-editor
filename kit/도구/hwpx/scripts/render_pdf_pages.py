from pathlib import Path
import sys

import pypdfium2 as pdfium


def render(pdf_path: Path, out_dir: Path, scale: float = 1.35) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf = pdfium.PdfDocument(str(pdf_path))
    for index in range(len(pdf)):
        bitmap = pdf[index].render(scale=scale)
        bitmap.to_pil().convert("RGB").save(
            out_dir / f"page-{index + 1:03d}.png", optimize=True
        )
    print(f"RENDERED\t{pdf_path}\tpages={len(pdf)}\tout={out_dir}")


if __name__ == "__main__":
    render(Path(sys.argv[1]), Path(sys.argv[2]))
