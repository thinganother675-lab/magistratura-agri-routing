from pathlib import Path
import struct
import zipfile
import xml.etree.ElementTree as ET
import zlib

BASE = Path(r'C:/sarychev/Codex/magistratura/coursework/mmm-ppr/audit-2026-10-07')
TMP = Path(r'C:/sarychev/Codex/magistratura/tmp/pdfs/course-audit')

def legacy_ppt_text(path):
    data = path.read_bytes()
    assert data[:8] == bytes.fromhex('d0cf11e0a1b11ae1')
    size = 1 << struct.unpack_from('<H', data, 30)[0]
    def sector(n):
        return data[(n+1)*size:(n+2)*size]
    difat = list(struct.unpack_from('<109I', data, 76))
    nxt, count = struct.unpack_from('<II', data, 68)
    for _ in range(count):
        nums = struct.unpack('<'+'I'*(size//4), sector(nxt))
        difat.extend(nums[:-1]); nxt = nums[-1]
    fat = []
    for n in difat:
        if n < 0xfffffffa:
            fat.extend(struct.unpack('<'+'I'*(size//4), sector(n)))
    def chain(n):
        result = bytearray(); seen = set()
        while n < 0xfffffffa and n not in seen:
            seen.add(n); result.extend(sector(n)); n = fat[n]
        return bytes(result)
    directory = chain(struct.unpack_from('<I', data, 48)[0])
    streams = {}
    for off in range(0, len(directory), 128):
        entry = directory[off:off+128]
        length = struct.unpack_from('<H', entry, 64)[0]
        name = entry[:max(0,length-2)].decode('utf-16le', errors='replace')
        if name in ('PowerPoint Document','Pictures'):
            streams[name] = chain(struct.unpack_from('<I',entry,116)[0])[:struct.unpack_from('<Q',entry,120)[0]]
    if 'PowerPoint Document' not in streams:
        raise ValueError('PowerPoint Document stream missing')
    texts = []
    def walk(buf):
        off = 0
        while off+8 <= len(buf):
            flags, kind, length = struct.unpack_from('<HHI', buf, off)
            if off+8+length > len(buf):
                break
            body = buf[off+8:off+8+length]
            if flags & 15 == 15:
                walk(body)
            elif kind in (4000,4008):
                value = body.decode('utf-16le' if kind == 4000 else 'cp1251',errors='replace')
                if value.strip(): texts.append(value.replace('\r','\n'))
            elif kind in (0xf01a,0xf01b,0xf01c):
                for start in (50,66):
                    try:
                        raw = zlib.decompress(body[start:])
                        p = TMP/f'dea-image-{len(list(TMP.glob("dea-image-*")))}.wmf'
                        p.write_bytes(raw)
                        from PIL import Image
                        im = Image.open(p); im.load(dpi=160); im.save(p.with_suffix('.png'))
                        break
                    except Exception:
                        pass
            elif kind in (0xf01d,0xf01e,0xf01f):
                for signature, ext in ((b'\x89PNG\r\n\x1a\n','.png'),(b'\xff\xd8\xff','.jpg')):
                    pos=body.find(signature)
                    if pos>=0:
                        (TMP/f'dea-bitmap-{len(list(TMP.glob("dea-bitmap-*")))}{ext}').write_bytes(body[pos:])
                        break
            off += 8+length
    walk(streams['PowerPoint Document'])
    if 'Pictures' in streams: walk(streams['Pictures'])
    return '\n\n'.join(texts)

(BASE/'sources/lecture-dea-extracted.txt').write_text(legacy_ppt_text(BASE/'sources/lecture-dea.ppt'), encoding='utf-8')
z = zipfile.ZipFile(BASE/'sources/lecture-8.pptx')
ns = {'a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
slides = sorted([n for n in z.namelist() if n.startswith('ppt/slides/slide') and n.endswith('.xml')],key=lambda n:int(n.split('slide')[-1].split('.')[0]))
texts = []
for i,n in enumerate(slides):
    texts.append(f'SLIDE {i+1}\n'+'\n'.join(x.text or '' for x in ET.fromstring(z.read(n)).findall('.//a:t',ns)))
(BASE/'sources/lecture-8-extracted.txt').write_text('\n\n'.join(texts),encoding='utf-8')
from PIL import Image
for n in z.namelist():
    if n.startswith('ppt/media/'):
        p = TMP/Path(n).name
        p.write_bytes(z.read(n))
        if p.suffix == '.wmf':
            try:
                im = Image.open(p); im.load(dpi=160); im.save(p.with_suffix('.png'))
            except Exception as e:
                print(p.name, type(e).__name__, str(e))
print((BASE/'sources/lecture-dea-extracted.txt').read_text(encoding='utf-8'))
