import zipfile
import xml.etree.ElementTree as ET
import os

docx_path = "docs/correcciones junio/Liquidaciones_Especificacion.docx"

if not os.path.exists(docx_path):
    print(f"Error: file {docx_path} does not exist.")
else:
    try:
        with zipfile.ZipFile(docx_path) as z:
            xml_content = z.read('word/document.xml')
            root = ET.fromstring(xml_content)
            
            # Namespaces
            ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            
            # Extract paragraphs
            text_parts = []
            for p in root.findall('.//w:p', ns):
                p_text = []
                for r in p.findall('.//w:r', ns):
                    t = r.find('.//w:t', ns)
                    if t is not None and t.text:
                        p_text.append(t.text)
                if p_text:
                    text_parts.append("".join(p_text))
            
            print("\n".join(text_parts))
    except Exception as e:
        print(f"Error reading docx: {e}")
