from collections import Counter
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import zipfile


def local(tag):
    return tag.rsplit("}", 1)[-1]


for raw in sys.argv[1:]:
    path = Path(raw)
    with zipfile.ZipFile(path) as zf:
        bad = zf.testzip()
        infos = zf.infolist()
        xml_errors = []
        para_ids = []
        for info in infos:
            if not info.filename.lower().endswith((".xml", ".hpf")):
                continue
            try:
                root = ET.fromstring(zf.read(info.filename))
            except Exception as exc:
                xml_errors.append(f"{info.filename}: {exc}")
                continue
            if "/section" in info.filename.lower():
                for elem in root.iter():
                    if local(elem.tag) == "p":
                        for key, value in elem.attrib.items():
                            if local(key).lower() == "id":
                                para_ids.append(value)
        # Hancom uses these sentinel paragraph IDs repeatedly for generated
        # paragraphs; they are not stable document-identity values.
        duplicates = [k for k, v in Counter(para_ids).items() if v > 1 and k not in {"0", "2147483648"}]
        print(
            f"{path}\tzip_ok={bad is None}\t"
            f"mimetype_first={bool(infos) and infos[0].filename == 'mimetype'}\t"
            f"mimetype_stored={bool(infos) and infos[0].compress_type == zipfile.ZIP_STORED}\t"
            f"xml_errors={len(xml_errors)}\tduplicate_para_ids={len(duplicates)}\t"
            f"entries={len(infos)}"
        )
        for err in xml_errors[:5]:
            print(f"  XML_ERROR {err}")
        for dup in duplicates[:5]:
            print(f"  DUPLICATE_PARA_ID {dup}")
