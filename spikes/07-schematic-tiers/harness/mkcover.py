import json,sys
from PIL import Image,ImageDraw,ImageFont
rows={r[1]:r for r in json.load(open('final_rows.json'))}
desc={'mx':'Sonnet, max effort, 4-round self-review loop','hi':'Sonnet, high effort, 4-round self-review loop',
'sb':'Sonnet, default effort, self-review loop + brief with corrected facts','ss':'Sonnet, default effort, 4-round self-review loop',
'sp':'Sonnet lead + one Sonnet subagent per page','gm':'Sonnet, medium effort + domain-agnostic guide + self-review loop',
'gh':'Sonnet, high effort + domain-agnostic guide + self-review loop'}
F=lambda s:ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',s)
for run in sys.argv[1:]:
    r=rows[run]; im=Image.new('RGB',(2339,1654),'white'); d=ImageDraw.Draw(im)
    d.text((150,200),run,font=F(120),fill='black'); d.text((150,380),desc[run[:2]],font=F(56),fill='black')
    lines=[f'Blind Opus rubric score: {r[0]:.2f} / 5',f'Cost: ${r[3]:.2f}   Active time: {r[4]:.0f} min']
    if r[5]: lines.append(f'Mean rank among 12 finalists (per sheet): {r[5]}')
    lines.append('Fable runs for reference: 4.16 and 3.66 (about $13-17)')
    for i,l in enumerate(lines): d.text((150,560+i*90),l,font=F(52),fill='black')
    im.save(f'cover/{run}.pdf',resolution=200)
