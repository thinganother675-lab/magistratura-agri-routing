from pathlib import Path
import re,sys
root=Path(__file__).parent
for n in sys.argv[1:]:
    text=(root/'extracted'/f'Лекция {n}.pdf.txt').read_text(encoding='utf-8')
    print(f'=== ЛЕКЦИЯ {n} ===')
    for page in re.split(r'--- Страница (\d+) ---',text)[1:][::2]:
        pass
    chunks=re.split(r'--- Страница (\d+) ---',text)
    for i in range(1,len(chunks),2):
        p,body=chunks[i],chunks[i+1]
        lines=[x.strip() for x in body.splitlines() if x.strip()]
        idx=next((j for j,x in enumerate(lines) if re.match(r'Лекция \d+ ·',x)),None)
        if idx is None:
            print(p, ' '.join(lines))
            continue
        title=' '.join(lines[:idx])
        rest=' '.join(lines[idx+1:])
        # A reading index of every slide: heading and opening explanation.
        # Full extracted text remains separately available without shortening.
        intro=re.split(r'(?<=[.!?])\s+(?=[А-ЯA-Z])',rest)
        snippet=' '.join(intro[:2])
        print(f'{p}. {title}: {snippet[:270]}')
