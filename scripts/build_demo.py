"""Create a labelled edited walkthrough from genuine browser captures, not simulated UI."""
from pathlib import Path
import subprocess

segments=[('chat-desktop',10,'GeoLens | Edited walkthrough of genuine captured application screens.'),
('chat-followup',14,'Two hours later: typed conversation retains Lonavala and hiking while comparing the new time.'),
('chat-evidence',12,'Inspect sources, restrictions and scoring. Regional modeled AQ is not a park sensor.'),
('chat-satellite',10,'EOX / Copernicus satellite imagery from 2024. Historical geographic context, not live weather.'),
('chat-mobile-map',12,'Mobile separates Chat, Map, Compare and Details while retaining the same analysis.'),
('chat-hindi',14,'Hindi follow-up preserves the location and activity. One Qwen model. Core: geo.setuconsultants.in. Captures are from localhost.')]

root=Path(__file__).resolve().parents[1]
manifest=root/'output/demo.ffconcat';subtitle=root/'submission/demo-captions.srt'
lines=['ffconcat version 1.0'];captions=[];time=0
def stamp(n):return f'{n//3600:02}:{n//60%60:02}:{n%60:02},000'
for i,(name,duration,text) in enumerate(segments,1):
    path=root/f'output/playwright/{name}.png'
    if not path.exists():raise FileNotFoundError(path)
    lines.extend([f"file 'playwright/{name}.png'",f'duration {duration}'])
    captions.append(f'{i}\n{stamp(time)} --> {stamp(time+duration)}\n{text}\n')
    time+=duration
lines.append(f"file 'playwright/{segments[-1][0]}.png'")
manifest.write_text('\n'.join(lines),encoding='utf-8')
subtitle.write_text('\n'.join(captions),encoding='utf-8')
subprocess.run(['ffmpeg','-y','-hide_banner','-loglevel','warning','-f','concat','-safe','0','-i',str(manifest),'-vf',"scale=1440:900,pad=1440:980:0:0:color=0x142d38,subtitles=submission/demo-captions.srt:force_style='FontName=Arial,FontSize=18,PrimaryColour=&H00FFFFFF,MarginV=10,Alignment=2'",'-r','24','-t',str(time),'-c:v','libx264','-preset','veryfast','-threads','2','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(root/'submission/GeoLens-demo.mp4')],cwd=root,check=True)
print(f'Wrote {time}s edited capture walkthrough, no simulated results.')
